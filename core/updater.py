"""
Silent GitHub Releases Auto-Updater for KCSM Print Service.
Uses Python standard library (urllib) so no extra runtime dependencies are required.
Automatically checks GitHub Releases, downloads the new build in the background,
and replaces the running executable cleanly when the printer is idle.
"""

import json
import os
import re
import subprocess
import sys
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


def _clean_spawn_env() -> dict:
    """
    Returns an environment dict stripped of PyInstaller's dying _MEI* variables
    so the newly launched updated executable initializes cleanly in its own temp dir.
    """
    env = os.environ.copy()
    for key in list(env.keys()):
        upper = key.upper()
        if upper.startswith("_MEI") or upper in ("PYINSTALLER_RESET_ENVIRONMENT", "TCL_LIBRARY", "TK_LIBRARY", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_PLUGIN_PATH"):
            env.pop(key, None)
    # Also remove any _MEI* folder entries from PATH
    if "PATH" in env:
        parts = [p for p in env["PATH"].split(os.pathsep) if "_MEI" not in p]
        env["PATH"] = os.pathsep.join(parts)
    return env


def launch_silent_self_update(downloaded_path: str, asset_type: str = "direct_exe") -> tuple[bool, str]:
    """
    Applies a downloaded update seamlessly without user clicks.
    - Uses a detached PowerShell updater script (never relies on cmd.exe or timeout.exe,
      waits for BOTH PyInstaller child & bootloader parent processes to release the file lock,
      copies + verifies size, strips _MEIPASS env, and launches the updated executable).
    Only executes in-place replacement when running as a frozen PyInstaller .exe.
    """
    if not downloaded_path or not os.path.exists(downloaded_path):
        return False, "Downloaded update file not found."

    # Sanity check: PyInstaller exe must be > 5 MB (guards against HTML error pages)
    if os.path.getsize(downloaded_path) < 5 * 1024 * 1024:
        return False, "Downloaded file appears incomplete or invalid."

    clean_env = _clean_spawn_env()
    create_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    if asset_type == "setup_exe":
        try:
            subprocess.Popen([downloaded_path, "--silent"], creationflags=create_flags, env=clean_env, close_fds=True)
            return True, "Silent installer launched."
        except Exception as e:
            return False, str(e)

    # Direct executable self-replacement (only valid when running as frozen .exe)
    if not getattr(sys, "frozen", False):
        return False, "Running from Python source; skipping binary self-swap."

    current_exe = os.path.abspath(sys.executable)
    exe_proc_name = os.path.splitext(os.path.basename(current_exe))[0]
    work_dir = os.path.dirname(current_exe)
    ps_dir = os.path.dirname(os.path.abspath(downloaded_path))
    ps_path = os.path.join(ps_dir, "kcsm_apply_update.ps1")
    log_path = os.path.join(ps_dir, "updater.log")

    # Escape single quotes for PowerShell string literals
    src_ps = os.path.abspath(downloaded_path).replace("'", "''")
    dst_ps = current_exe.replace("'", "''")
    dir_ps = work_dir.replace("'", "''")
    proc_ps = exe_proc_name.replace("'", "''")
    log_ps = log_path.replace("'", "''")

    ps_script = f"""$ErrorActionPreference = 'SilentlyContinue'
$src = '{src_ps}'
$dst = '{dst_ps}'
$workDir = '{dir_ps}'
$procName = '{proc_ps}'
$logFile = '{log_ps}'

function Write-Log($msg) {{
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $logFile -Value "[$ts] $msg" -Encoding utf8
}}

Write-Log "Updater started. SRC=$src -> DST=$dst"

# 1. Wait for BOTH PyInstaller Python child and bootloader parent processes to exit
$waited = 0
while ($waited -lt 20) {{
    $running = Get-Process -Name $procName -ErrorAction SilentlyContinue
    if (-not $running) {{ break }}
    Start-Sleep -Milliseconds 500
    $waited++
}}

# Force-close any lingering process still locking the exe
$stillRunning = Get-Process -Name $procName -ErrorAction SilentlyContinue
if ($stillRunning) {{
    Write-Log "Force-stopping lingering $procName process(es)..."
    $stillRunning | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800
}}

# 2. Copy new executable with retries and byte-size verification
$expectedSize = (Get-Item -LiteralPath $src).Length
$copied = $false
for ($i = 1; $i -le 30; $i++) {{
    try {{
        Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop
        $actualSize = (Get-Item -LiteralPath $dst).Length
        if ($actualSize -eq $expectedSize) {{
            $copied = $true
            Write-Log "Copied $actualSize bytes cleanly on attempt $i."
            break
        }}
    }} catch {{
        Write-Log "Attempt $i copy retry: $($_.Exception.Message)"
    }}
    Start-Sleep -Milliseconds 500
}}

# 3. Relaunch updated executable cleanly from its install folder
if ($copied) {{
    Start-Sleep -Milliseconds 400
    try {{
        Start-Process -FilePath $dst -WorkingDirectory $workDir
        Write-Log "Relaunched updated $dst successfully."
    }} catch {{
        Write-Log "Relaunch failed: $($_.Exception.Message)"
    }}
    Remove-Item -LiteralPath $src -Force -ErrorAction SilentlyContinue
}} else {{
    Write-Log "ERROR: Could not overwrite $dst after 30 retries. Relaunching existing exe."
    Start-Process -FilePath $dst -WorkingDirectory $workDir
}}

Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
"""
    try:
        with open(ps_path, "w", encoding="utf-8") as f:
            f.write(ps_script)
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", ps_path],
            creationflags=create_flags,
            env=clean_env,
            close_fds=True,
        )
        return True, "Silent PowerShell self-update scheduled."
    except Exception as e:
        return False, str(e)


class UpdateCheckWorker(QThread):
    """Background worker that checks GitHub Releases API for a newer version."""
    update_available = pyqtSignal(dict)
    up_to_date = pyqtSignal(str)
    check_failed = pyqtSignal(str)

    def __init__(self, repo: str, github_token: str = "", silent: bool = True, prefer_direct_exe: bool = True):
        super().__init__()
        self.repo = (repo or "").strip().strip("/")
        self.github_token = get_effective_github_token(github_token)
        self.silent = silent
        self.prefer_direct_exe = prefer_direct_exe

    def run(self):
        if not self.repo or "/" not in self.repo:
            self.check_failed.emit("GitHub repository is not configured.")
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

            assets = data.get("assets") or []
            chosen = None
            asset_type = "direct_exe"

            if self.prefer_direct_exe:
                # Prefer standalone ErpGoPrintService.exe for zero-click silent swap
                for asset in assets:
                    name = (asset.get("name") or "").lower()
                    if name == "erpgoprintservice.exe" or ("erpgoprintservice" in name and "setup" not in name and name.endswith(".exe")):
                        chosen = asset
                        asset_type = "direct_exe"
                        break

            if not chosen:
                for asset in assets:
                    name = (asset.get("name") or "").lower()
                    if "setup" in name and name.endswith(".exe"):
                        chosen = asset
                        asset_type = "setup_exe"
                        break

            if not chosen:
                for asset in assets:
                    name = (asset.get("name") or "").lower()
                    if name.endswith(".exe"):
                        chosen = asset
                        asset_type = "direct_exe"
                        break

            download_url = ""
            asset_name = ""
            is_api_asset = False
            if chosen:
                asset_name = chosen.get("name", "ErpGoPrintService.exe")
                if self.github_token and chosen.get("url"):
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
                "asset_type": asset_type,
                "html_url": data.get("html_url", f"https://github.com/{self.repo}/releases/latest"),
                "is_api_asset": is_api_asset,
            })

        except urllib.error.HTTPError as e:
            self.check_failed.emit(f"GitHub API HTTP {e.code}")
        except Exception as e:
            self.check_failed.emit(str(e))


class UpdateDownloadWorker(QThread):
    """Streams the GitHub release binary to %TEMP% with live progress."""
    progress_signal = pyqtSignal(int)      # 0..100
    finished_signal = pyqtSignal(str)      # local file path
    error_signal = pyqtSignal(str)

    def __init__(self, download_url: str, asset_name: str, github_token: str = "", is_api_asset: bool = False):
        super().__init__()
        self.download_url = download_url
        self.asset_name = asset_name or "ErpGoPrintService.exe"
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
            dest_path = os.path.join(dest_dir, f"update_{self.asset_name}")

            with urllib.request.urlopen(req, timeout=120) as resp:
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
