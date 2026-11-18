"""
System Tray Manager for KCSM Print Service.
Allows minimizing the app to Windows taskbar notification area.
"""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QBrush, QAction
from PyQt6.QtCore import QObject, pyqtSignal

class SystemTrayManager(QObject):
    show_window_signal = pyqtSignal()
    toggle_pause_signal = pyqtSignal()
    test_print_signal = pyqtSignal()
    quit_signal = pyqtSignal()

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.tray = QSystemTrayIcon(parent)
        self.is_paused = False
        self.is_connected = False
        self._init_icon()
        self._init_menu()
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    def _create_colored_pixmap(self, color_hex: str) -> QPixmap:
        """Generates a dynamic 32x32 round icon with status dot."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outer purple ring (KCSM brand)
        painter.setBrush(QBrush(QColor("#7a5af8")))
        painter.setPen(QColor("#53389e"))
        painter.drawRoundedRect(2, 2, 28, 28, 8, 8)

        # Inner status circle
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.setPen(QColor("#ffffff"))
        painter.drawEllipse(18, 18, 12, 12)

        painter.end()
        return pixmap

    def _init_icon(self):
        self.icon_offline = QIcon(self._create_colored_pixmap("#ef4444"))
        self.icon_online = QIcon(self._create_colored_pixmap("#10b981"))
        self.icon_busy = QIcon(self._create_colored_pixmap("#f59e0b"))
        self.tray.setIcon(self.icon_offline)
        self.tray.setToolTip("KCSM Print Service (Disconnected)")

    def _init_menu(self):
        self.menu = QMenu()

        self.action_show = QAction("Open Dashboard", self.menu)
        self.action_show.triggered.connect(self.show_window_signal.emit)
        self.menu.addAction(self.action_show)

        self.menu.addSeparator()

        self.action_pause = QAction("Pause Queue", self.menu)
        self.action_pause.triggered.connect(self._handle_toggle_pause)
        self.menu.addAction(self.action_pause)

        self.action_test = QAction("Test Print", self.menu)
        self.action_test.triggered.connect(self.test_print_signal.emit)
        self.menu.addAction(self.action_test)

        self.menu.addSeparator()

        self.action_quit = QAction("Exit", self.menu)
        self.action_quit.triggered.connect(self.quit_signal.emit)
        self.menu.addAction(self.action_quit)

        self.tray.setContextMenu(self.menu)

    def _handle_toggle_pause(self):
        self.is_paused = not self.is_paused
        self.action_pause.setText("Resume Queue" if self.is_paused else "Pause Queue")
        self.toggle_pause_signal.emit()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick or reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window_signal.emit()

    def update_status(self, is_connected: bool, device_code: str = ""):
        self.is_connected = is_connected
        if is_connected:
            self.tray.setIcon(self.icon_online)
            self.tray.setToolTip(f"KCSM Print Service - {device_code} (Online)")
        else:
            self.tray.setIcon(self.icon_offline)
            self.tray.setToolTip("KCSM Print Service (Offline - Reconnecting)")

    def set_busy(self, is_busy: bool):
        if is_busy:
            self.tray.setIcon(self.icon_busy)
        else:
            self.tray.setIcon(self.icon_online if self.is_connected else self.icon_offline)

    def notify(self, title: str, message: str):
        """Displays native Windows balloon notification."""
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
