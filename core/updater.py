"""
GitHub Releases Auto-Updater for KCSM Print Service.
Uses Python standard library (urllib) so no extra runtime dependencies are required.
Supports both public GitHub repos and private repos (via optional github_token in config.json).
"""

import json
import os
import re
import tempfile
import urllib.request
import urllib.error
from PyQt6.QtCore import QThread, pyqtSignal

from core.version import APP_VERSION


def _load_embedded_token() -> str:
    try:
        from core._build_secrets import get_embedded_updater_token
        return (get_embedded_updater_token() or "").strip()
    except Exception:
        return ""


def has_embedded_updater_token() -> bool:
    return bool(_load_embedded_token())


def get_effective_github_token(user_token: str = "") -> str:
    """Uses explicit user token if provided, otherwise silently uses the build-embedded release key."""
    explicit = (user_token or "").strip()
    if explicit:
        return explicit
    return _load_embedded_token()


def parse_version(tag: str) -> tuple[int, ...]:
    """Converts tags like 'v1.2.3' or '1.2.0-beta' into comparable integer tuples."""
    cleaned = (tag or "").strip().lstrip("vV")
    nums = re.findall(r"\d+", cleaned)
    if not nums:
        return (0, 0, 0)
    parts = [int(x) for x in nums[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(latest_tag: str, current_ver: str = APP_VERSION) -> bool:
    return parse_version(latest_tag) > parse_version(current_ver)


class UpdateCheckWorker(QThread):
    """Background worker that checks GitHub Releases API for a newer version."""
    update_available = pyqtSignal(dict)   # {"version", "notes", "download_url", "asset_name", "html_url", "is_api_asset"}
    up_to_date = pyqtSignal(str)          # current version
    check_failed = pyqtSignal(str)        # error message

    def __init__(self, repo: str, github_token: str = "", silent: bool = True):
        super().__init__()
        self.repo = (repo or "").strip().strip("/")
        self.github_token = get_effective_github_token(github_token)
        self.silent = silent

    def run(self):
        if not self.repo or "/" not in self.repo:
            self.check_failed.emit("GitHub repository is not configured (expected owner/repo).")
            return

        url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"KCSM-Print-Service/{APP_VERSION}",
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            latest_tag = data.get("tag_name") or data.get("name") or ""
            if not latest_tag:
                self.check_failed.emit("No version tag found in latest GitHub release.")
                return

            if not is_newer_version(latest_tag, APP_VERSION):
                self.up_to_date.emit(APP_VERSION)
                return

            # Prefer Setup wizard .exe, otherwise fallback to any .exe asset
            assets = data.get("assets") or []
            chosen = None
            for asset in assets:
                name = (asset.get("name") or "").lower()
                if "setup" in name and name.endswith(".exe"):
                    chosen = asset
                    break
            if not chosen:
                for asset in assets:
                    name = (asset.get("name") or "").lower()
                    if name.endswith(".exe"):
                        chosen = asset
                        break

            download_url = ""
            asset_name = ""
            is_api_asset = False
            if chosen:
                asset_name = chosen.get("name", "KCSM_PrintService_Setup.exe")
                if self.github_token and chosen.get("url"):
                    # Private repo asset downloads must go through the API asset URL with Accept: octet-stream
                    download_url = chosen["url"]
                    is_api_asset = True
                else:
                    download_url = chosen.get("browser_download_url", "")

            self.update_available.emit({
                "version": latest_tag.lstrip("vV"),
                "tag": latest_tag,
                "notes": (data.get("body") or "").strip(),
                "download_url": download_url,
                "asset_name": asset_name,
                "html_url": data.get("html_url", f"https://github.com/{self.repo}/releases/latest"),
                "is_api_asset": is_api_asset,
            })

        except urllib.error.HTTPError as e:
            if e.code == 404:
                self.check_failed.emit("No published GitHub release found yet (or private repo needs a token).")
            else:
                self.check_failed.emit(f"GitHub API HTTP {e.code}")
        except Exception as e:
            self.check_failed.emit(str(e))


class UpdateDownloadWorker(QThread):
    """Streams the GitHub release installer .exe to %TEMP% with live progress."""
    progress_signal = pyqtSignal(int)      # 0..100
    finished_signal = pyqtSignal(str)      # local file path
    error_signal = pyqtSignal(str)

    def __init__(self, download_url: str, asset_name: str, github_token: str = "", is_api_asset: bool = False):
        super().__init__()
        self.download_url = download_url
        self.asset_name = asset_name or "KCSM_PrintService_Setup.exe"
        self.github_token = get_effective_github_token(github_token)
        self.is_api_asset = is_api_asset

    def run(self):
        try:
            headers = {"User-Agent": f"KCSM-Print-Service/{APP_VERSION}"}
            if self.github_token:
                headers["Authorization"] = f"Bearer {self.github_token}"
            if self.is_api_asset:
                headers["Accept"] = "application/octet-stream"

            req = urllib.request.Request(self.download_url, headers=headers)
            dest_dir = os.path.join(tempfile.gettempdir(), "KCSMPrintServiceUpdates")
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, self.asset_name)

            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                chunk_size = 65536
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = min(100, int((downloaded * 100) / total))
                            self.progress_signal.emit(pct)

            self.progress_signal.emit(100)
            self.finished_signal.emit(dest_path)
        except Exception as e:
            self.error_signal.emit(str(e))
