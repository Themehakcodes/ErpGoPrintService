"""
Graphical Setup Wizard for KCSM Print Service.
Installs application files, configures Windows autostart, and creates desktop shortcuts.
"""

import os
import sys
import shutil
import winreg
from PyQt6.QtWidgets import (
    QApplication, QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QProgressBar,
    QFileDialog, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QBrush, QColor

DEFAULT_INSTALL_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Programs\KCSM Print Service")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "KCSMPrintService"

def get_base_dir():
    if getattr(sys, 'frozen', False):
        # PyInstaller --onefile extracts bundled --add-data files into sys._MEIPASS
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass and os.path.exists(meipass):
            return meipass
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to KCSM Print Service Setup")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        banner = QFrame()
        banner.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7a5af8, stop:1 #6366f1); border-radius: 10px; padding: 18px;")
        b_layout = QVBoxLayout(banner)
        t = QLabel("KCSM Print Service — Desktop Agent")
        t.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 800;")
        s = QLabel("Cloud-to-Desktop Thermal Spooler & Retail Barcode Bridge")
        s.setStyleSheet("color: #e0e7ff; font-size: 13px; font-weight: 500;")
        b_layout.addWidget(t)
        b_layout.addWidget(s)
        layout.addWidget(banner)

        desc = QLabel(
            "This setup wizard will install KCSM Print Service on your computer.\n\n"
            "Features configured during installation:\n"
            "• Direct Windows Spooler integration for TVS, TSC, and ESC/POS printers\n"
            "• Windows System Tray background execution\n"
            "• Automatic startup upon Windows boot\n"
            "• Crash and power-cut protection ledger\n\n"
            "Click Next to continue."
        )
        desc.setStyleSheet("font-size: 13px; color: #334155; line-height: 1.5;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addStretch()

class DirectoryPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Select Installation Folder")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl = QLabel("Choose the folder where KCSM Print Service will be installed:")
        lbl.setStyleSheet("font-size: 13px; color: #334155; font-weight: 600;")
        layout.addWidget(lbl)

        h_box = QHBoxLayout()
        self.dir_input = QLineEdit(DEFAULT_INSTALL_DIR)
        self.dir_input.setStyleSheet("padding: 8px 12px; font-size: 13px; border: 1.5px solid #cbd5e1; border-radius: 6px;")
        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet("padding: 8px 16px; font-weight: 600; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")
        browse_btn.clicked.connect(self._browse)
        h_box.addWidget(self.dir_input)
        h_box.addWidget(browse_btn)
        layout.addLayout(h_box)

        layout.addSpacing(10)
        opt_lbl = QLabel("Startup & Shortcut Options:")
        opt_lbl.setStyleSheet("font-size: 13px; color: #334155; font-weight: 700;")
        layout.addWidget(opt_lbl)

        self.autostart_chk = QCheckBox("Automatically start KCSM Print Service when Windows boots")
        self.autostart_chk.setChecked(True)
        self.autostart_chk.setStyleSheet("font-size: 13px; color: #475569; font-weight: 500;")
        layout.addWidget(self.autostart_chk)

        self.desktop_chk = QCheckBox("Create a Desktop shortcut")
        self.desktop_chk.setChecked(True)
        self.desktop_chk.setStyleSheet("font-size: 13px; color: #475569; font-weight: 500;")
        layout.addWidget(self.desktop_chk)

        self.startmenu_chk = QCheckBox("Create a Start Menu shortcut")
        self.startmenu_chk.setChecked(True)
        self.startmenu_chk.setStyleSheet("font-size: 13px; color: #475569; font-weight: 500;")
        layout.addWidget(self.startmenu_chk)

        layout.addStretch()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory", self.dir_input.text())
        if d:
            self.dir_input.setText(os.path.join(d, "KCSM Print Service"))

class InstallProgressPage(QWizardPage):
    def __init__(self, dir_page: DirectoryPage):
        super().__init__()
        self.dir_page = dir_page
        self.setTitle("Installing KCSM Print Service")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.status_lbl = QLabel("Ready to install...")
        self.status_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #334155;")
        layout.addWidget(self.status_lbl)

        self.progress = QProgressBar()
        self.progress.setStyleSheet("height: 18px; border-radius: 9px; text-align: center;")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        layout.addStretch()

    def initializePage(self):
        QTimer.singleShot(200, self._perform_install)

    def _perform_install(self):
        target_dir = self.dir_page.dir_input.text().strip()
        os.makedirs(target_dir, exist_ok=True)
        self.progress.setValue(20)
        self.status_lbl.setText("Copying executable and configuration...")

        base_dir = get_base_dir()
        src_exe = os.path.join(base_dir, "dist", "ErpGoPrintService.exe")
        if not os.path.exists(src_exe):
            src_exe = os.path.join(base_dir, "ErpGoPrintService.exe")

        dest_exe = os.path.join(target_dir, "ErpGoPrintService.exe")

        try:
            # Stop any currently running instance cleanly so upgrades overwrite cleanly
            import subprocess
            import time
            subprocess.run(
                ["taskkill", "/F", "/IM", "ErpGoPrintService.exe"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            time.sleep(0.6)

            if os.path.exists(src_exe):
                shutil.copy2(src_exe, dest_exe)
            else:
                raise FileNotFoundError(f"Bundled executable not found at {src_exe}")
            self.progress.setValue(50)

            src_cfg = os.path.join(base_dir, "config.json")
            if not os.path.exists(src_cfg):
                src_cfg = os.path.join(base_dir, "config.example.json")
            dest_cfg = os.path.join(target_dir, "config.json")
            if os.path.exists(src_cfg) and not os.path.exists(dest_cfg):
                shutil.copy2(src_cfg, dest_cfg)

            self.progress.setValue(70)
            self.status_lbl.setText("Configuring Windows shortcuts & autostart...")

            # Windows Auto-Start Registry
            if self.dir_page.autostart_chk.isChecked():
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{dest_exe}"')
                    winreg.CloseKey(key)
                except Exception as e:
                    print(f"Registry error: {e}")

            # Create Shortcuts via PowerShell COM
            if self.dir_page.desktop_chk.isChecked() or self.dir_page.startmenu_chk.isChecked():
                self._create_shortcuts(dest_exe, target_dir)

            self.progress.setValue(100)
            self.status_lbl.setText("Installation completed successfully!")
            self.wizard().button(QWizard.WizardButton.NextButton).setEnabled(True)
            self.wizard().next()

        except Exception as e:
            self.status_lbl.setText(f"Installation error: {e}")
            QMessageBox.critical(self, "Installation Failed", str(e))

    def _create_shortcuts(self, exe_path: str, work_dir: str):
        try:
            import subprocess
            cmd = f"""
            $WshShell = New-Object -ComObject WScript.Shell
            if ('{self.dir_page.desktop_chk.isChecked()}' -eq 'True') {{
                $d = [System.Environment]::GetFolderPath('Desktop')
                $s = $WshShell.CreateShortcut("$d\\KCSM Print Service.lnk")
                $s.TargetPath = "{exe_path}"
                $s.WorkingDirectory = "{work_dir}"
                $s.IconLocation = "{exe_path},0"
                $s.Save()
            }}
            if ('{self.dir_page.startmenu_chk.isChecked()}' -eq 'True') {{
                $m = [System.Environment]::GetFolderPath('StartMenu') + '\\Programs'
                $s2 = $WshShell.CreateShortcut("$m\\KCSM Print Service.lnk")
                $s2.TargetPath = "{exe_path}"
                $s2.WorkingDirectory = "{work_dir}"
                $s2.IconLocation = "{exe_path},0"
                $s2.Save()
            }}
            """
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], capture_output=True)
        except Exception as e:
            print(f"Shortcut creation error: {e}")

class FinishedPage(QWizardPage):
    def __init__(self, dir_page: DirectoryPage):
        super().__init__()
        self.dir_page = dir_page
        self.setTitle("Completing KCSM Print Service Setup")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        success_lbl = QLabel("🎉 Installation Complete!")
        success_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #059669;")
        layout.addWidget(success_lbl)

        info = QLabel(
            "KCSM Print Service has been successfully installed on your computer.\n\n"
            "The service will automatically launch when Windows boots and sit in the\n"
            "system tray notification area to receive print jobs."
        )
        info.setStyleSheet("font-size: 13px; color: #475569; line-height: 1.5;")
        layout.addWidget(info)

        self.launch_chk = QCheckBox("Launch KCSM Print Service now")
        self.launch_chk.setChecked(True)
        self.launch_chk.setStyleSheet("font-size: 13px; color: #0f172a; font-weight: 700; margin-top: 10px;")
        layout.addWidget(self.launch_chk)
        layout.addStretch()

    def validatePage(self):
        if self.launch_chk.isChecked():
            import subprocess
            target_dir = self.dir_page.dir_input.text().strip()
            exe_path = os.path.join(target_dir, "ErpGoPrintService.exe")
            if os.path.exists(exe_path):
                subprocess.Popen([exe_path], cwd=target_dir)
        return True

def run_silent_install():
    """Headless silent upgrade/install invoked by --silent flag (zero GUI popups)."""
    import subprocess
    import time

    target_dir = DEFAULT_INSTALL_DIR
    os.makedirs(target_dir, exist_ok=True)
    base_dir = get_base_dir()
    src_exe = os.path.join(base_dir, "dist", "ErpGoPrintService.exe")
    if not os.path.exists(src_exe):
        src_exe = os.path.join(base_dir, "ErpGoPrintService.exe")
    dest_exe = os.path.join(target_dir, "ErpGoPrintService.exe")

    subprocess.run(
        ["taskkill", "/F", "/IM", "ErpGoPrintService.exe"],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    time.sleep(0.8)

    if os.path.exists(src_exe):
        for _ in range(15):
            try:
                shutil.copy2(src_exe, dest_exe)
                break
            except Exception:
                time.sleep(0.5)

    src_cfg = os.path.join(base_dir, "config.json")
    if not os.path.exists(src_cfg):
        src_cfg = os.path.join(base_dir, "config.example.json")
    dest_cfg = os.path.join(target_dir, "config.json")
    if os.path.exists(src_cfg) and not os.path.exists(dest_cfg):
        shutil.copy2(src_cfg, dest_cfg)

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{dest_exe}"')
        winreg.CloseKey(key)
    except Exception:
        pass

    if os.path.exists(dest_exe):
        subprocess.Popen([dest_exe], cwd=target_dir, close_fds=True)


def main():
    if "--silent" in sys.argv:
        run_silent_install()
        sys.exit(0)

    app = QApplication(sys.argv)
    wizard = QWizard()
    wizard.setWindowTitle("KCSM Print Service Setup")
    wizard.resize(600, 440)

    welcome = WelcomePage()
    dir_page = DirectoryPage()
    progress_page = InstallProgressPage(dir_page)
    finish_page = FinishedPage(dir_page)

    wizard.addPage(welcome)
    wizard.addPage(dir_page)
    wizard.addPage(progress_page)
    wizard.addPage(finish_page)

    wizard.show()
    sys.exit(wizard.exec())

if __name__ == "__main__":
    main()
