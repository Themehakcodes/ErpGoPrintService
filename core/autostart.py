"""
Windows Registry Startup Manager for KCSM Print Service.
Configures automatic launch upon Windows boot via HKCU Run registry key.
"""

import os
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_ENTRY_NAME = "KCSMPrintService"

def get_executable_command() -> str:
    """Returns the executable command line to register for startup."""
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
        return f'"{exe_path}"'
    else:
        # Running from Python source
        python_exe = sys.executable
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        return f'"{python_exe}" "{script_path}"'

def is_autostart_enabled() -> bool:
    """Checks whether the application is registered in Windows startup registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, REG_ENTRY_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False

def set_autostart(enable: bool) -> bool:
    """Enables or disables auto-start on Windows startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            cmd = get_executable_command()
            winreg.SetValueEx(key, REG_ENTRY_NAME, 0, winreg.REG_SZ, cmd)
            print(f"[Autostart] Registered Windows startup command: {cmd}")
        else:
            try:
                winreg.DeleteValue(key, REG_ENTRY_NAME)
                print("[Autostart] Removed Windows startup registry key")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"[Autostart] Failed to update startup registry: {e}")
        return False
