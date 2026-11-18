"""
Build-Time Secret Injector for KCSM Print Service.
Reads KCSM_UPDATER_TOKEN from environment (GitHub Actions secret) or local .env.build (gitignored),
obfuscates it with a random per-build XOR mask, and writes core/_build_secrets.py (gitignored)
before PyInstaller packages the executable.

Zero secrets are ever stored in Git source history.
"""

import base64
import os
import secrets

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_BUILD_PATH = os.path.join(ROOT_DIR, ".env.build")
OUT_PATH = os.path.join(ROOT_DIR, "core", "_build_secrets.py")


def read_token() -> str:
    # 1. Prefer CI / shell environment variable
    env_val = os.environ.get("KCSM_UPDATER_TOKEN", "").strip()
    if env_val:
        return env_val

    # 2. Fallback to local gitignored .env.build file
    if os.path.exists(ENV_BUILD_PATH):
        with open(ENV_BUILD_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "KCSM_UPDATER_TOKEN":
                    return v.strip().strip('"').strip("'")
    return ""


def generate():
    token = read_token()
    if token:
        raw = token.encode("utf-8")
        mask = secrets.token_bytes(len(raw))
        xored = bytes(a ^ b for a, b in zip(raw, mask))
        m_b64 = base64.b64encode(mask).decode("ascii")
        x_b64 = base64.b64encode(xored).decode("ascii")
        status = "EMBEDDED"
    else:
        m_b64 = ""
        x_b64 = ""
        status = "EMPTY (no KCSM_UPDATER_TOKEN set)"

    code = f'''"""Auto-generated at build time. Do NOT commit to Git."""
import base64

_M = "{m_b64}"
_X = "{x_b64}"


def get_embedded_updater_token() -> str:
    if not _M or not _X:
        return ""
    try:
        m = base64.b64decode(_M)
        x = base64.b64decode(_X)
        return bytes(a ^ b for a, b in zip(x, m)).decode("utf-8")
    except Exception:
        return ""
'''
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"[BuildSecrets] Generated core/_build_secrets.py -> {status}")


if __name__ == "__main__":
    generate()
