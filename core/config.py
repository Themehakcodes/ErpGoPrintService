"""
Configuration Manager for KCSM Print Service.
Persists settings into local config.json.
"""

import json
import os
import sys

from .version import DEFAULT_GITHUB_REPO

DEFAULT_CONFIG = {
    "server_url": "wss://erp.kcsmtraders.com/ws/print-service",
    "device_code": "DEV-0002",
    "secret_key": "",
    "selected_printer": "SNBC TVSE LP 46 NEO BPLE",
    "printer_mode": "TSPL",  # TSPL, TSPL_BALA, TSPL_1UP, ESCPOS, or RAW
    "auto_connect": True,
    "minimize_to_tray": True,
    "sound_alerts": True,
    "autostart_with_windows": True,
    "prompt_printer_on_startup": False,
    "auto_check_updates": True,
    "github_repo": DEFAULT_GITHUB_REPO,
    "github_token": ""
}

def get_app_dir() -> str:
    """Returns the base directory of the running app (works in script or PyInstaller exe)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_config_path() -> str:
    return os.path.join(get_app_dir(), "config.json")

def load_config() -> dict:
    path = get_config_path()
    if not os.path.exists(path):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            # Fill missing keys with defaults
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception as e:
        print(f"[Config] Error reading config.json: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(cfg: dict) -> bool:
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        return True
    except Exception as e:
        print(f"[Config] Error writing config.json: {e}")
        return False
