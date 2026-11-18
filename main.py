"""
KCSM Print Service — Windows Desktop Agent
Entry point with single-instance enforcement, tray-lifecycle handling,
and Windows AppUserModelID registration.
"""

import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QBrush, QColor
from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from ui.main_window import MainWindow
from ui.startup_dialog import StartupPrinterDialog
from core.config import load_config
from core.autostart import set_autostart, is_autostart_enabled

APP_ID = "kcsm.erp.printservice.agent.1.0"
SERVER_NAME = "KCSM_PRINT_SERVICE_IPC_LOCK"

def setup_app_user_model_id():
    """Sets explicit Windows AppUserModelID so taskbar pinning and notifications display cleanly."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass

def generate_app_icon() -> QIcon:
    """Generates an embedded brand icon for KCSM Print Service."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Base rounded card (#7a5af8 - KCSM Brand Purple)
    painter.setBrush(QBrush(QColor("#7a5af8")))
    painter.setPen(QColor("#53389e"))
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)

    # Printer body (white)
    painter.setBrush(QBrush(QColor("#ffffff")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(16, 26, 32, 22, 4, 4)

    # Paper slot on top
    painter.setBrush(QBrush(QColor("#e0e7ff")))
    painter.drawRoundedRect(22, 14, 20, 14, 3, 3)

    # Output paper on bottom
    painter.setBrush(QBrush(QColor("#f4f5f7")))
    painter.drawRoundedRect(20, 36, 24, 12, 2, 2)

    # Status LED dot (green)
    painter.setBrush(QBrush(QColor("#10b981")))
    painter.drawEllipse(40, 30, 4, 4)

    painter.end()
    return QIcon(pixmap)

def main():
    setup_app_user_model_id()

    app = QApplication(sys.argv)
    app.setApplicationName("KCSM Print Service")
    app.setOrganizationName("KCSM")
    app.setApplicationDisplayName("KCSM Print Service — Desktop Agent")
    
    icon = generate_app_icon()
    app.setWindowIcon(icon)

    # Crucial: Prevent app exit when main window is closed/hidden to system tray
    app.setQuitOnLastWindowClosed(False)

    # Single-instance check via QLocalSocket / QLocalServer
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(500):
        # An instance is already running; signal it to open window and exit this duplicate process
        socket.write(b"SHOW")
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        print("[Launcher] Existing KCSM Print Service instance already active. Brought window to front.")
        sys.exit(0)

    # No existing instance found; initialize local server for single-instance control
    local_server = QLocalServer()
    # Remove stale pipe/server socket if uncleanly closed previously
    local_server.removeServer(SERVER_NAME)
    local_server.listen(SERVER_NAME)

    cfg = load_config()

    # Sync Windows startup registry if configured
    if cfg.get("autostart_with_windows", True) and not is_autostart_enabled():
        set_autostart(True)

    # Prompt user on startup to select active printer if enabled or if no printer configured yet
    has_valid_printer = bool(cfg.get("selected_printer"))
    if cfg.get("prompt_printer_on_startup", False) or not has_valid_printer:
        startup_dlg = StartupPrinterDialog(cfg)
        startup_dlg.setWindowIcon(icon)
        startup_dlg.exec()
        # Reload cfg in case user updated selection
        cfg = load_config()

    window = MainWindow()
    window.setWindowIcon(icon)

    def handle_ipc_connection():
        client_sock = local_server.nextPendingConnection()
        if client_sock:
            client_sock.readyRead.connect(lambda: on_ipc_message(client_sock, window))

    def on_ipc_message(sock: QLocalSocket, win: MainWindow):
        msg = bytes(sock.readAll()).decode("utf-8")
        if "SHOW" in msg:
            win.show()
            win.raise_()
            win.activateWindow()

    local_server.newConnection.connect(handle_ipc_connection)

    # Launch GUI
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
