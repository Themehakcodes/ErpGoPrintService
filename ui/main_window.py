"""
Main Window for KCSM Print Service Desktop Application.
Modern PyQt6 interface styled with KCSM ERP theme (#7a5af8).
Includes:
- Live Print Jobs Queue with Printed By (requester) tracking
- Animated Printer Busy / Windows Spooler Processing Bar
- Asynchronous FIFO print dispatch so UI never freezes
- GitHub Releases Auto-Update checker & 1-click installer
"""

import sys
import time
from collections import deque
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QFrame, QMessageBox, QTabWidget,
    QAbstractItemView, QCheckBox, QProgressBar, QScrollArea
)
from PyQt6.QtGui import QColor, QCloseEvent
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot

from core.config import load_config, save_config
from core.printer import WindowsPrinter
from core.ledger import JobLedger
from core.ws_client import WebSocketWorker
from core.autostart import is_autostart_enabled, set_autostart
from core.version import APP_VERSION, DEFAULT_GITHUB_REPO
from core.updater import UpdateCheckWorker, UpdateDownloadWorker, launch_silent_self_update
from .styles import QSS_THEME
from .tray_icon import SystemTrayManager


class PrintSpoolerThread(QThread):
    """Dispatches raw bytes to win32print off the GUI thread so progress bars animate smoothly."""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, printer_name: str, data_bytes: bytes, doc_name: str):
        super().__init__()
        self.printer_name = printer_name
        self.data_bytes = data_bytes
        self.doc_name = doc_name

    def run(self):
        ok, msg = WindowsPrinter.send_raw_bytes(self.printer_name, self.data_bytes, self.doc_name)
        self.finished_signal.emit(ok, msg)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"KCSM Print Service — Desktop Agent (v{APP_VERSION})")
        self.resize(1040, 740)
        self.setMinimumSize(880, 620)
        self.setStyleSheet(QSS_THEME)

        # Core subsystems
        self.cfg = load_config()
        self.ledger = JobLedger()
        self.ws_worker = None
        self.is_connected = False
        self.queue_paused = False

        # Sequential print dispatch & live spooler busy state
        self._dispatch_queue = deque()
        self._active_print_ctx = None
        self._spooler_thread = None
        self._busy_min_until = 0.0
        self._last_printed_summary = ""

        # GitHub silent auto-updater state
        self._update_check_worker = None
        self._update_download_worker = None
        self._latest_release_info = None
        self._pending_update_apply = None  # (downloaded_path, asset_type, version)
        self._update_in_progress = False

        # Spooler activity monitor timer (runs only while busy)
        self.spooler_timer = QTimer(self)
        self.spooler_timer.setInterval(650)
        self.spooler_timer.timeout.connect(self._poll_spooler_activity)

        # Periodic silent GitHub release check (every 30 minutes)
        self.auto_update_timer = QTimer(self)
        self.auto_update_timer.setInterval(30 * 60 * 1000)
        self.auto_update_timer.timeout.connect(self._check_for_updates_silent)

        # Initialize UI & Tray
        self._init_ui()
        self.tray_manager = SystemTrayManager(self.window(), self)
        self._wire_tray_signals()

        # Populate printers and metrics
        self._refresh_printers()
        self._update_metrics_ui()
        self._load_recent_jobs_to_table()

        # Auto-connect if enabled
        if self.cfg.get("auto_connect", True):
            QTimer.singleShot(600, self._handle_connect_toggle)

        # Silent GitHub auto-update check 5 seconds after boot + every 30 minutes
        QTimer.singleShot(5000, self._check_for_updates_silent)
        self.auto_update_timer.start()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # ── 1. Top Header Banner ──
        main_layout.addWidget(self._build_header_card())

        # ── 1b. Non-blocking GitHub Update Banner (hidden until an update is found) ──
        self.update_banner = self._build_update_banner()
        self.update_banner.setVisible(False)
        main_layout.addWidget(self.update_banner)

        # ── 2. KPI Metrics Strip ──
        main_layout.addWidget(self._build_kpi_strip())

        # ── 3. Main Tab Widget (Front: Jobs Queue | The Other Side: Settings & Telemetry) ──
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_jobs_tab(), "📋 Live Print Jobs Queue")
        self.tabs.addTab(self._build_settings_tab(), "⚙️ Settings && Hardware Configuration")
        self.tabs.addTab(self._build_logs_tab(), "🖥️ Terminal Logs && Telemetry")
        main_layout.addWidget(self.tabs, 1)

    def _build_header_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("HeaderCard")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        info_box = QVBoxLayout()
        title = QLabel(f"KCSM Print Service — Desktop Agent  v{APP_VERSION}")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("Hardware-Agnostic Cloud-to-Desktop Thermal & Barcode Spooler Bridge")
        subtitle.setObjectName("HeaderSubtitle")
        info_box.addWidget(title)
        info_box.addWidget(subtitle)
        layout.addLayout(info_box)

        layout.addStretch()

        sel_p = self.cfg.get('selected_printer', 'No Printer Selected')
        self.active_printer_pill = QLabel(f"🖨️ {sel_p[:26]}")
        self.active_printer_pill.setToolTip(f"Selected Printer: {sel_p}")
        self.active_printer_pill.setStyleSheet(
            "background-color: #f1f5f9; color: #334155; font-weight: 600; "
            "padding: 7px 14px; border-radius: 12px; font-size: 12px; border: 1px solid #e2e8f0;"
        )
        layout.addWidget(self.active_printer_pill)

        self.status_pill = QLabel("● OFFLINE")
        self.status_pill.setObjectName("StatusOffline")
        layout.addWidget(self.status_pill)

        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setStyleSheet(
            "QPushButton { background-color: #ffffff; color: #334155; font-size: 12px; font-weight: 700; "
            "padding: 7px 14px; border-radius: 10px; border: 1px solid #e2e8f0; min-height: 20px; }"
            "QPushButton:hover { background-color: #f8fafc; }"
        )
        settings_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        layout.addWidget(settings_btn)

        return frame

    def _build_update_banner(self) -> QFrame:
        """Minimal unobtrusive banner shown ONLY while an automatic update is actively downloading/installing."""
        banner = QFrame()
        banner.setStyleSheet(
            "QFrame { background-color: #eef2ff; border: 1px solid #c7d2fe; border-radius: 10px; }"
        )
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(10)

        self.update_banner_lbl = QLabel("🔄 Updating KCSM Print Service in background...")
        self.update_banner_lbl.setStyleSheet("color: #3730a3; font-weight: 700; font-size: 12px; border: none; background: transparent;")
        layout.addWidget(self.update_banner_lbl, 1)

        self.update_dl_progress = QProgressBar()
        self.update_dl_progress.setRange(0, 100)
        self.update_dl_progress.setFixedWidth(180)
        self.update_dl_progress.setFixedHeight(14)
        self.update_dl_progress.setStyleSheet(
            "QProgressBar { border: 1px solid #c7d2fe; border-radius: 7px; background: #ffffff; text-align: center; font-size: 10px; font-weight: 700; color: #3730a3; }"
            "QProgressBar::chunk { background-color: #6366f1; border-radius: 6px; }"
        )
        layout.addWidget(self.update_dl_progress)

        return banner

    def _build_kpi_strip(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        def make_kpi(title, default_val, text_color="#0f172a"):
            box = QFrame()
            box.setObjectName("MetricBox")
            b_layout = QVBoxLayout(box)
            b_layout.setContentsMargins(14, 10, 14, 10)
            b_layout.setSpacing(2)
            val = QLabel(default_val)
            val.setObjectName("MetricValue")
            val.setStyleSheet(f"color: {text_color};")
            lbl = QLabel(title)
            lbl.setObjectName("MetricLabel")
            b_layout.addWidget(val)
            b_layout.addWidget(lbl)
            return box, val

        self.kpi_total_box, self.kpi_total_val = make_kpi("Total Processed", "0")
        self.kpi_comp_box, self.kpi_comp_val = make_kpi("Completed Jobs", "0", "#059669")
        self.kpi_labels_box, self.kpi_labels_val = make_kpi("Labels Printed", "0", "#7a5af8")
        self.kpi_recov_box, self.kpi_recov_val = make_kpi("Power-Cut Guarded", "0", "#d97706")

        layout.addWidget(self.kpi_total_box)
        layout.addWidget(self.kpi_comp_box)
        layout.addWidget(self.kpi_labels_box)
        layout.addWidget(self.kpi_recov_box)

        return widget

    def _build_connection_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Cloud Server & Device Identity")
        title.setObjectName("CardTitle")
        sub = QLabel("Pairing parameters for KCSM ERP WebSocket Hub")
        sub.setObjectName("CardSubtitle")
        layout.addWidget(title)
        layout.addWidget(sub)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Server URL:"), 0, 0)
        self.server_url_input = QLineEdit(self.cfg.get("server_url", "wss://erp.kcsmtraders.com/ws/print-service"))
        grid.addWidget(self.server_url_input, 0, 1)

        grid.addWidget(QLabel("Device Code:"), 1, 0)
        self.device_code_input = QLineEdit(self.cfg.get("device_code", "DEV-0002"))
        grid.addWidget(self.device_code_input, 1, 1)

        grid.addWidget(QLabel("Secret Key:"), 2, 0)
        self.secret_key_input = QLineEdit(self.cfg.get("secret_key", ""))
        self.secret_key_input.setPlaceholderText("(Optional)")
        grid.addWidget(self.secret_key_input, 2, 1)

        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Connect Agent")
        self.connect_btn.setObjectName("PrimaryBtn")
        self.connect_btn.clicked.connect(self._handle_connect_toggle)
        btn_row.addWidget(self.connect_btn)

        self.save_btn = QPushButton("Save Config")
        self.save_btn.setObjectName("SecondaryBtn")
        self.save_btn.clicked.connect(self._handle_save_config)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)
        return card

    def _build_printer_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Local Hardware Printer")
        title.setObjectName("CardTitle")
        sub = QLabel("Windows Spooler routing destination for this Device Code")
        sub.setObjectName("CardSubtitle")
        layout.addWidget(title)
        layout.addWidget(sub)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Target Printer:"), 0, 0)
        self.printer_combo = QComboBox()
        grid.addWidget(self.printer_combo, 0, 1)

        grid.addWidget(QLabel("Protocol / Mode:"), 1, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "TSPL (4-Up Sticker Roll 101.6x25mm)",
            "TSPL_BALA (Bala Single Tag 74.1x25mm)",
            "TSPL_1UP (Single Label 50x25mm)",
            "ESCPOS (Thermal Receipt 58/80mm)",
            "RAW (Direct Pass-Through)"
        ])
        saved_mode = self.cfg.get("printer_mode", "TSPL")
        idx = self.mode_combo.findText(saved_mode, Qt.MatchFlag.MatchStartsWith)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        grid.addWidget(self.mode_combo, 1, 1)

        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        self.refresh_printers_btn = QPushButton("Refresh Printers")
        self.refresh_printers_btn.setObjectName("SecondaryBtn")
        self.refresh_printers_btn.clicked.connect(self._refresh_printers)
        btn_row.addWidget(self.refresh_printers_btn)

        self.test_print_btn = QPushButton("Test Print Alignment")
        self.test_print_btn.setObjectName("OutlineBtn")
        self.test_print_btn.clicked.connect(self._handle_test_print)
        btn_row.addWidget(self.test_print_btn)

        layout.addLayout(btn_row)
        return card

    def _build_settings_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 12, 6, 12)
        layout.setSpacing(14)

        # ── Row 1: Connection & Printer Cards ──
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)
        cards_layout.addWidget(self._build_connection_card(), 1)
        cards_layout.addWidget(self._build_printer_card(), 1)
        layout.addLayout(cards_layout)

        # ── Row 2: Windows System & Startup Preferences (Clean, Software Updates Hidden) ──
        sys_card = QFrame()
        sys_card.setObjectName("CardFrame")
        s_layout = QVBoxLayout(sys_card)
        s_layout.setContentsMargins(18, 14, 18, 14)
        s_layout.setSpacing(10)

        s_title = QLabel("Windows System & Startup Preferences")
        s_title.setObjectName("CardTitle")
        s_sub = QLabel("Configure automatic boot launch, printer prompts, and notification area behavior")
        s_sub.setObjectName("CardSubtitle")
        s_layout.addWidget(s_title)
        s_layout.addWidget(s_sub)

        self.autostart_chk = QCheckBox("Automatically start KCSM Print Service when Windows boots")
        self.autostart_chk.setChecked(self.cfg.get("autostart_with_windows", True) or is_autostart_enabled())
        self.autostart_chk.setStyleSheet("font-size: 13px; color: #334155; font-weight: 600;")
        s_layout.addWidget(self.autostart_chk)

        self.prompt_chk = QCheckBox("Prompt for printer selection on every startup")
        self.prompt_chk.setChecked(self.cfg.get("prompt_printer_on_startup", False))
        self.prompt_chk.setStyleSheet("font-size: 13px; color: #334155; font-weight: 600;")
        s_layout.addWidget(self.prompt_chk)

        self.tray_chk = QCheckBox("Minimize to Windows System Tray on close (keeps agent listening in background)")
        self.tray_chk.setChecked(self.cfg.get("minimize_to_tray", True))
        self.tray_chk.setStyleSheet("font-size: 13px; color: #334155; font-weight: 600;")
        s_layout.addWidget(self.tray_chk)

        save_sys_btn = QPushButton("Save All Settings && Apply")
        save_sys_btn.setObjectName("PrimaryBtn")
        save_sys_btn.setStyleSheet("min-width: 220px; padding: 10px 22px; font-weight: 700;")
        save_sys_btn.clicked.connect(self._handle_save_config)
        s_layout.addWidget(save_sys_btn, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(sys_card)
        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

    def _build_jobs_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        # ── Live Printer Processing / Busy Progress Bar Card ──
        self.printer_activity_frame = QFrame()
        self.printer_activity_frame.setStyleSheet(
            "QFrame { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; }"
        )
        act_layout = QVBoxLayout(self.printer_activity_frame)
        act_layout.setContentsMargins(14, 10, 14, 10)
        act_layout.setSpacing(6)

        act_top = QHBoxLayout()
        self.activity_status_lbl = QLabel("● Printer Ready — Idle")
        self.activity_status_lbl.setStyleSheet(
            "color: #059669; font-size: 13px; font-weight: 700; border: none; background: transparent;"
        )
        act_top.addWidget(self.activity_status_lbl, 1)

        self.activity_queue_lbl = QLabel("Spooler Queue: 0 active")
        self.activity_queue_lbl.setStyleSheet(
            "color: #64748b; font-size: 12px; font-weight: 600; border: none; background: transparent;"
        )
        act_top.addWidget(self.activity_queue_lbl)
        act_layout.addLayout(act_top)

        self.printer_progress_bar = QProgressBar()
        self.printer_progress_bar.setFixedHeight(10)
        self.printer_progress_bar.setTextVisible(False)
        self.printer_progress_bar.setRange(0, 100)
        self.printer_progress_bar.setValue(0)
        self.printer_progress_bar.setVisible(False)
        self.printer_progress_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 5px; background-color: #e2e8f0; }"
            "QProgressBar::chunk { border-radius: 5px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7a5af8, stop:1 #4f46e5); }"
        )
        act_layout.addWidget(self.printer_progress_bar)
        layout.addWidget(self.printer_activity_frame)

        # ── Print Jobs Table (9 Columns including Printed By) ──
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Time", "Job ID", "Product Name", "Barcode", "MRP", "Rate", "Qty", "Printed By", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 76)
        self.table.setColumnWidth(1, 78)
        self.table.setColumnWidth(3, 128)
        self.table.setColumnWidth(4, 72)
        self.table.setColumnWidth(5, 72)
        self.table.setColumnWidth(6, 52)
        self.table.setColumnWidth(7, 130)
        self.table.setColumnWidth(8, 105)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        btn_bar = QHBoxLayout()
        self.pause_queue_btn = QPushButton("Pause Queue")
        self.pause_queue_btn.setObjectName("SecondaryBtn")
        self.pause_queue_btn.clicked.connect(self._handle_pause_toggle)
        btn_bar.addWidget(self.pause_queue_btn)

        btn_bar.addStretch()

        self.sync_pending_btn = QPushButton("Request Pending Jobs from ERP")
        self.sync_pending_btn.setObjectName("OutlineBtn")
        self.sync_pending_btn.clicked.connect(self._handle_request_pending)
        btn_bar.addWidget(self.sync_pending_btn)

        layout.addLayout(btn_bar)
        return widget

    def _build_logs_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("LogArea")
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        clear_btn = QPushButton("Clear Console")
        clear_btn.setObjectName("SecondaryBtn")
        clear_btn.clicked.connect(self.log_area.clear)
        layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

        return widget

    # ─── System Tray Connections ───

    def _wire_tray_signals(self):
        self.tray_manager.show_window_signal.connect(self._restore_from_tray)
        self.tray_manager.toggle_pause_signal.connect(self._handle_pause_toggle)
        self.tray_manager.test_print_signal.connect(self._handle_test_print)
        self.tray_manager.quit_signal.connect(self._handle_force_quit)

    def closeEvent(self, event: QCloseEvent):
        """Hides to tray when user closes the window instead of killing the service."""
        if self.cfg.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray_manager.notify(
                "KCSM Print Service",
                "Service is still active in the Windows background tray to receive print jobs."
            )
        else:
            event.accept()

    def _restore_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _handle_force_quit(self):
        self.spooler_timer.stop()
        self.auto_update_timer.stop()
        if self.ws_worker:
            self.ws_worker.stop()
        if hasattr(self, "tray_manager") and getattr(self.tray_manager, "tray_icon", None):
            self.tray_manager.tray_icon.hide()
        app = QApplication.instance()
        if app:
            app.quit()
        sys.exit(0)

    # ─── Live Printer Busy / Spooler Progress Bar ───

    def _set_printer_busy_ui(self, busy: bool, message: str = "", queue_count: int = 0, warning: bool = False):
        if busy:
            self.printer_activity_frame.setStyleSheet(
                "QFrame { background-color: #f5f3ff; border: 1.5px solid #c4b5fd; border-radius: 10px; }"
            )
            self.activity_status_lbl.setText(f"🖨️ {message or 'Printer Busy — Spooling Labels...'}")
            self.activity_status_lbl.setStyleSheet(
                "color: #5b21b6; font-size: 13px; font-weight: 700; border: none; background: transparent;"
            )
            pending_local = len(self._dispatch_queue)
            q_parts = []
            if queue_count > 0:
                q_parts.append(f"Spooler: {queue_count}")
            if pending_local > 0:
                q_parts.append(f"Waiting: {pending_local}")
            self.activity_queue_lbl.setText(" · ".join(q_parts) if q_parts else "Printing active...")
            self.activity_queue_lbl.setStyleSheet(
                "color: #6d28d9; font-size: 12px; font-weight: 700; border: none; background: transparent;"
            )
            # Indeterminate smooth animated bar while printer is busy
            self.printer_progress_bar.setRange(0, 0)
            self.printer_progress_bar.setVisible(True)
            self.tray_manager.set_busy(True)
        elif warning:
            self.printer_activity_frame.setStyleSheet(
                "QFrame { background-color: #fffbeb; border: 1.5px solid #fcd34d; border-radius: 10px; }"
            )
            self.activity_status_lbl.setText(f"⚠️ {message}")
            self.activity_status_lbl.setStyleSheet(
                "color: #b45309; font-size: 13px; font-weight: 700; border: none; background: transparent;"
            )
            self.activity_queue_lbl.setText(f"Spooler Queue: {queue_count} active")
            self.printer_progress_bar.setRange(0, 100)
            self.printer_progress_bar.setVisible(False)
            self.tray_manager.set_busy(False)
        else:
            self.printer_activity_frame.setStyleSheet(
                "QFrame { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; }"
            )
            self.activity_status_lbl.setText("● Printer Ready — Idle")
            self.activity_status_lbl.setStyleSheet(
                "color: #059669; font-size: 13px; font-weight: 700; border: none; background: transparent;"
            )
            self.activity_queue_lbl.setText("Spooler Queue: 0 active")
            self.activity_queue_lbl.setStyleSheet(
                "color: #64748b; font-size: 12px; font-weight: 600; border: none; background: transparent;"
            )
            self.printer_progress_bar.setRange(0, 100)
            self.printer_progress_bar.setValue(0)
            self.printer_progress_bar.setVisible(False)
            self.tray_manager.set_busy(False)

    def _poll_spooler_activity(self):
        # If we are actively writing a job or have more jobs waiting in local FIFO queue, keep busy bar active
        if self._active_print_ctx is not None or len(self._dispatch_queue) > 0:
            return

        printer_name = self.printer_combo.currentText()
        st = WindowsPrinter.get_spooler_status(printer_name)
        still_pulsing = time.monotonic() < self._busy_min_until

        if st["busy"] or still_pulsing:
            msg = self._last_printed_summary or st["status_text"]
            if st["active_jobs"] > 0:
                msg = f"Printer Busy — {self._last_printed_summary or 'Feeding labels'}"
            self._set_printer_busy_ui(True, msg, queue_count=st["active_jobs"])
        elif st["status_text"] not in ("Printer Ready — Idle", "No printer selected"):
            self._set_printer_busy_ui(False, st["status_text"], queue_count=st["active_jobs"], warning=True)
            self.spooler_timer.stop()
        else:
            self._set_printer_busy_ui(False)
            self.spooler_timer.stop()
            self._apply_pending_update_if_idle()

    # ─── Silent Background GitHub Auto-Updater ───

    def _check_for_updates_silent(self):
        """Silently checks GitHub Releases and auto-downloads/installs newer builds when idle."""
        if self._update_in_progress:
            return
        repo = self.cfg.get("github_repo", DEFAULT_GITHUB_REPO) or DEFAULT_GITHUB_REPO
        token = self.cfg.get("github_token", "")

        self._update_check_worker = UpdateCheckWorker(repo, token, silent=True, prefer_direct_exe=True)
        self._update_check_worker.update_available.connect(self._on_update_available_auto)
        self._update_check_worker.up_to_date.connect(lambda v: self._log("INFO", f"Agent is up to date (v{v})."))
        self._update_check_worker.check_failed.connect(lambda err: self._log("INFO", f"Auto-update check skipped: {err}"))
        self._update_check_worker.start()

    @pyqtSlot(dict)
    def _on_update_available_auto(self, info: dict):
        if self._update_in_progress:
            return
        dl_url = info.get("download_url")
        if not dl_url:
            return

        self._update_in_progress = True
        self._latest_release_info = info
        ver = info.get("version", "")
        self._log("INFO", f"New release v{ver} detected on GitHub. Downloading automatically in background...")

        self.update_banner_lbl.setText(f"🔄 Auto-updating KCSM Print Service to v{ver}...")
        self.update_dl_progress.setValue(0)
        self.update_banner.setVisible(True)

        token = self.cfg.get("github_token", "")
        self._update_download_worker = UpdateDownloadWorker(
            dl_url,
            info.get("asset_name", "ErpGoPrintService.exe"),
            github_token=token,
            is_api_asset=bool(info.get("is_api_asset")),
        )
        self._update_download_worker.progress_signal.connect(self.update_dl_progress.setValue)
        self._update_download_worker.finished_signal.connect(self._on_update_downloaded_auto)
        self._update_download_worker.error_signal.connect(self._on_update_download_error_auto)
        self._update_download_worker.start()

    @pyqtSlot(str)
    def _on_update_downloaded_auto(self, downloaded_path: str):
        info = self._latest_release_info or {}
        ver = info.get("version", "")
        asset_type = info.get("asset_type", "direct_exe")
        self._pending_update_apply = (downloaded_path, asset_type, ver)
        self._log("SUCCESS", f"Downloaded v{ver} update. Waiting for printer idle to install...")
        self.update_banner_lbl.setText(f"⚡ Update v{ver} ready — installing automatically once printer is idle...")
        self._apply_pending_update_if_idle()

    def _apply_pending_update_if_idle(self):
        if not self._pending_update_apply:
            return
        # Never interrupt an active print job or queued batch
        if self._active_print_ctx is not None or len(self._dispatch_queue) > 0:
            return

        downloaded_path, asset_type, ver = self._pending_update_apply
        self._pending_update_apply = None

        ok, msg = launch_silent_self_update(downloaded_path, asset_type=asset_type)
        if ok:
            self._log("SUCCESS", f"Applying v{ver} silently and restarting agent...")
            self.tray_manager.notify("KCSM Print Service", f"Updating automatically to v{ver}...")
            QTimer.singleShot(400, self._handle_force_quit)
        else:
            self._update_in_progress = False
            self.update_banner.setVisible(False)
            self._log("INFO", f"Deferred binary self-update: {msg}")

    @pyqtSlot(str)
    def _on_update_download_error_auto(self, err: str):
        self._update_in_progress = False
        self.update_banner.setVisible(False)
        self._log("WARN", f"Background update download failed (will retry later): {err}")

    # ─── Configuration & Printers ───

    def _refresh_printers(self):
        printers = WindowsPrinter.get_installed_printers()
        self.printer_combo.clear()
        if not printers:
            self.printer_combo.addItem("No Windows Printers Found")
            self._log("WARN", "No Windows printers detected via win32print.")
            return

        self.printer_combo.addItems(printers)
        saved = self.cfg.get("selected_printer")
        default = WindowsPrinter.get_default_printer()

        idx = self.printer_combo.findText(saved) if saved else -1
        if idx >= 0:
            self.printer_combo.setCurrentIndex(idx)
        elif default:
            idx = self.printer_combo.findText(default)
            if idx >= 0:
                self.printer_combo.setCurrentIndex(idx)

        self._log("INFO", f"Detected {len(printers)} installed printers on this PC.")

    def _handle_save_config(self):
        self.cfg["server_url"] = self.server_url_input.text().strip()
        self.cfg["device_code"] = self.device_code_input.text().strip()
        self.cfg["secret_key"] = self.secret_key_input.text().strip()
        self.cfg["selected_printer"] = self.printer_combo.currentText()
        self.cfg["printer_mode"] = self.mode_combo.currentText().split()[0]
        if hasattr(self, 'autostart_chk'):
            self.cfg["autostart_with_windows"] = self.autostart_chk.isChecked()
            set_autostart(self.autostart_chk.isChecked())
        if hasattr(self, 'prompt_chk'):
            self.cfg["prompt_printer_on_startup"] = self.prompt_chk.isChecked()
        if hasattr(self, 'tray_chk'):
            self.cfg["minimize_to_tray"] = self.tray_chk.isChecked()

        if hasattr(self, 'active_printer_pill'):
            p_name = self.cfg.get('selected_printer', 'No Printer')
            self.active_printer_pill.setText(f"🖨️ {p_name[:26]}")
            self.active_printer_pill.setToolTip(f"Selected Printer: {p_name}")

        if save_config(self.cfg):
            self._log("SUCCESS", f"Configuration saved for device {self.cfg['device_code']}.")
            if self.is_connected or (self.ws_worker and self.ws_worker.isRunning()):
                self._log("INFO", "Reconnecting agent with updated configuration...")
                self._disconnect_ws()
                QTimer.singleShot(400, self._connect_ws)
            else:
                QMessageBox.information(self, "Settings Saved", "Configuration saved successfully!")

    def _update_metrics_ui(self):
        m = self.ledger.get_metrics()
        self.kpi_total_val.setText(str(m.get("total_processed", 0)))
        self.kpi_comp_val.setText(str(m.get("completed", 0)))
        self.kpi_labels_val.setText(str(m.get("total_labels_printed", 0)))
        self.kpi_recov_val.setText(str(m.get("interrupted", 0)))

    # ─── WebSocket Connection Control ───

    def _handle_connect_toggle(self):
        if self.is_connected or (self.ws_worker and self.ws_worker.isRunning()):
            self._disconnect_ws()
        else:
            self._connect_ws()

    def _connect_ws(self):
        url = self.server_url_input.text().strip()
        code = self.device_code_input.text().strip()
        secret = self.secret_key_input.text().strip()

        if not url or not code:
            QMessageBox.warning(self, "Input Error", "Server URL and Device Code are required.")
            return

        self.connect_btn.setText("Connecting...")
        self.connect_btn.setEnabled(False)

        self.ws_worker = WebSocketWorker(url, code, secret)
        self.ws_worker.connected_signal.connect(self._on_ws_connected)
        self.ws_worker.disconnected_signal.connect(self._on_ws_disconnected)
        self.ws_worker.job_received_signal.connect(self._on_job_received)
        self.ws_worker.log_signal.connect(self._log)
        self.ws_worker.start()

    def _disconnect_ws(self):
        if self.ws_worker:
            self.ws_worker.stop()
            self.ws_worker = None
        self._on_ws_disconnected("Disconnected by user")

    @pyqtSlot(dict)
    def _on_ws_connected(self, dev_info: dict):
        self.is_connected = True
        code = dev_info.get("device_code", "")
        name = dev_info.get("device_name", "").strip()
        disp_name = f" ({code} — {name[:14]})" if code else ""
        self.status_pill.setText(f"● ONLINE{disp_name}")
        self.status_pill.setObjectName("StatusOnline")
        self.status_pill.setToolTip(f"Connected to {code} — {name}")
        self.status_pill.setStyleSheet("background-color: #ecfdf5; color: #059669; font-weight: 700; padding: 6px 12px; border-radius: 12px;")
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setEnabled(True)
        self.tray_manager.update_status(True, code)
        self.tray_manager.notify("KCSM Print Service", f"Connected as {code} ({name})")

    @pyqtSlot(str)
    def _on_ws_disconnected(self, reason: str):
        self.is_connected = False
        self.status_pill.setText("○ OFFLINE")
        self.status_pill.setObjectName("StatusOffline")
        self.status_pill.setStyleSheet("background-color: #fee2e2; color: #dc2626; font-weight: 700; padding: 6px 12px; border-radius: 12px;")
        self.connect_btn.setText("Connect Agent")
        self.connect_btn.setEnabled(True)
        self.tray_manager.update_status(False)

    def _handle_request_pending(self):
        if self.ws_worker and self.is_connected:
            self.ws_worker.request_pending_jobs()
            self._log("INFO", "Requested pending jobs backlog from server.")
        else:
            QMessageBox.information(self, "Offline", "Agent must be connected to request pending jobs.")

    def _handle_pause_toggle(self):
        self.queue_paused = not self.queue_paused
        self.pause_queue_btn.setText("Resume Queue" if self.queue_paused else "Pause Queue")
        status_txt = "PAUSED" if self.queue_paused else "ACTIVE"
        self._log("WARN" if self.queue_paused else "INFO", f"Print Queue is now {status_txt}.")
        if not self.queue_paused:
            self._process_next_in_queue()

    # ─── Job Execution & Power-Cut Recovery (Non-Blocking FIFO Queue) ───

    @pyqtSlot(dict)
    def _on_job_received(self, job: dict):
        job_id = job.get("id") or job.get("job_id") or ""
        product_name = job.get("print_name") or job.get("product_name") or "Item"
        requested_by = (job.get("created_by_name") or job.get("printed_by_name") or "ERP User").strip()

        # ── 1. Power-Cut & Deduplication Guard ──
        if self.ledger.is_processed(job_id):
            status = self.ledger.get_job_status(job_id)
            self._log("WARN", f"⚠️ Skipping Job #{job_id[:8]} ({product_name}) — Already recorded as {status}. Preventing duplicate reprint.")
            if self.ws_worker:
                self.ws_worker.send_status_update(job_id, status)
            return

        # Prevent duplicate queuing if already sitting in local dispatch queue
        if self._active_print_ctx and self._active_print_ctx["job_id"] == job_id:
            return
        if any(item["job_id"] == job_id for item in self._dispatch_queue):
            return

        # ── 2. Add to UI table ──
        self._add_job_row(job)
        self._dispatch_queue.append({
            "job": job,
            "job_id": job_id,
            "requested_by": requested_by,
        })

        if self.queue_paused:
            self._log("WARN", f"Queue is paused. Job #{job_id[:8]} ({product_name} by {requested_by}) held in local queue.")
            return

        self._process_next_in_queue()

    def _process_next_in_queue(self):
        if self.queue_paused or self._active_print_ctx is not None or not self._dispatch_queue:
            return

        entry = self._dispatch_queue.popleft()
        job = entry["job"]
        job_id = entry["job_id"]
        requested_by = entry["requested_by"]
        product_name = job.get("print_name") or job.get("product_name") or "Item"
        barcode = job.get("barcode", "")
        qty = int(job.get("quantity", 1))
        mrp = float(job.get("print_mrp") or job.get("product_mrp") or 0.0)
        rate = float(job.get("print_sale_rate") or job.get("sale_rate") or 0.0)

        printer_name = self.printer_combo.currentText()
        if not printer_name or "No Windows Printers" in printer_name:
            err_msg = "No valid Windows printer selected."
            self._log("ERROR", f"Job #{job_id[:8]} FAILED: {err_msg}")
            self.ledger.fail_job(job_id, err_msg)
            self._update_job_row_status(job_id, "FAILED", "#dc2626")
            if self.ws_worker:
                self.ws_worker.send_status_update(job_id, "FAILED", error_message=err_msg)
            self._update_metrics_ui()
            QTimer.singleShot(50, self._process_next_in_queue)
            return

        # Mark in progress (power-cut safe ledger write BEFORE spooling)
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.ledger.start_job(
            job_id, product_name, barcode, qty,
            created_by_name=requested_by,
            print_mrp=mrp,
            print_sale_rate=rate,
        )
        self._update_job_row_status(job_id, "PRINTING", "#d97706")

        summary = f"Printing: {product_name} (Qty: {qty}) — by {requested_by}"
        self._last_printed_summary = f"{product_name} (Qty: {qty}) — by {requested_by}"
        self._busy_min_until = time.monotonic() + max(1.2, min(4.0, qty * 0.15))
        self._set_printer_busy_ui(True, summary, queue_count=1)
        if not self.spooler_timer.isActive():
            self.spooler_timer.start()

        if self.ws_worker:
            self.ws_worker.send_status_update(job_id, "PRINTING", start_time=now_str)

        # Generate payload according to selected protocol
        mode = self.mode_combo.currentText()
        if "TSPL_BALA" in mode:
            data_bytes = WindowsPrinter.generate_tspl_bala(product_name, mrp, rate, barcode, qty)
        elif "TSPL_1UP" in mode:
            data_bytes = WindowsPrinter.generate_tspl_1up(product_name, mrp, rate, barcode, qty)
        elif "ESCPOS" in mode:
            data_bytes = WindowsPrinter.generate_escpos_tag(product_name, mrp, rate, barcode, qty, job.get("store_name", "KCSM"))
        elif "RAW" in mode:
            data_bytes = (job.get("raw_payload") or "").encode("utf-8")
        else:
            data_bytes = WindowsPrinter.generate_tspl_4up(product_name, mrp, rate, barcode, qty)

        self._active_print_ctx = {
            "job_id": job_id,
            "product_name": product_name,
            "requested_by": requested_by,
            "qty": qty,
            "printer_name": printer_name,
            "start_time": now_str,
        }

        # Dispatch off the GUI thread so progress bar animates smoothly
        self._spooler_thread = PrintSpoolerThread(printer_name, data_bytes, doc_name=f"KCSM_{barcode}")
        self._spooler_thread.finished_signal.connect(self._on_spooler_finished)
        self._spooler_thread.start()

    @pyqtSlot(bool, str)
    def _on_spooler_finished(self, success: bool, message: str):
        ctx = self._active_print_ctx
        self._active_print_ctx = None
        if not ctx:
            return

        job_id = ctx["job_id"]
        product_name = ctx["product_name"]
        requested_by = ctx["requested_by"]
        qty = ctx["qty"]
        printer_name = ctx["printer_name"]
        start_time = ctx["start_time"]
        end_time_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if success:
            self.ledger.complete_job(job_id, qty)
            self._update_job_row_status(job_id, "COMPLETED", "#059669")
            self._log("SUCCESS", f"Printed {qty} copies for Job #{job_id[:8]} ({product_name}) requested by {requested_by} on '{printer_name}'")
            if self.ws_worker:
                self.ws_worker.send_status_update(job_id, "COMPLETED", start_time=start_time, end_time=end_time_str, printed_copies=qty)
            self.tray_manager.notify("Label Printed", f"Printed {qty} labels for {product_name} (by {requested_by})")
        else:
            self.ledger.fail_job(job_id, message)
            self._update_job_row_status(job_id, "FAILED", "#dc2626")
            self._log("ERROR", f"Job #{job_id[:8]} Spooler Error: {message}")
            if self.ws_worker:
                self.ws_worker.send_status_update(job_id, "FAILED", start_time=start_time, end_time=end_time_str, error_message=message)

        self._update_metrics_ui()

        # Continue next queued job immediately, or let spooler_timer monitor hardware completion
        if self._dispatch_queue and not self.queue_paused:
            QTimer.singleShot(80, self._process_next_in_queue)
        elif not self.spooler_timer.isActive():
            self.spooler_timer.start()

    def _handle_test_print(self):
        printer_name = self.printer_combo.currentText()
        if not printer_name or "No Windows Printers" in printer_name:
            QMessageBox.warning(self, "No Printer", "Please select a valid installed Windows printer first.")
            return

        mode_txt = self.mode_combo.currentText()
        if "ESCPOS" in mode_txt:
            mode = "ESCPOS"
        elif "TSPL_BALA" in mode_txt:
            mode = "TSPL_BALA"
        elif "TSPL_1UP" in mode_txt:
            mode = "TSPL_1UP"
        else:
            mode = "TSPL"
        test_bytes = WindowsPrinter.generate_test_print(mode, printer_name)
        self._last_printed_summary = "Test Alignment Label"
        self._busy_min_until = time.monotonic() + 1.5
        self._set_printer_busy_ui(True, f"Sending Test Alignment Label to {printer_name}...", queue_count=1)
        if not self.spooler_timer.isActive():
            self.spooler_timer.start()

        success, msg = WindowsPrinter.send_raw_bytes(printer_name, test_bytes, "KCSM_Test_Print")

        if success:
            QMessageBox.information(self, "Test Print Sent", f"Test print job sent successfully to '{printer_name}'!")
            self._log("SUCCESS", f"Test print job sent to '{printer_name}'.")
        else:
            QMessageBox.critical(self, "Test Print Failed", f"Could not print to '{printer_name}':\n{msg}")
            self._log("ERROR", f"Test print failed: {msg}")

    # ─── Table & Log Helpers ───

    def _add_job_row(self, job: dict) -> int:
        row = 0
        self.table.insertRow(row)

        job_id = job.get("id") or job.get("job_id") or ""
        time_str = time.strftime("%H:%M:%S")
        start_iso = job.get("start_time") or job.get("created_at") or ""
        if "T" in start_iso and len(start_iso) >= 19:
            time_str = start_iso[11:19]

        self.table.setItem(row, 0, QTableWidgetItem(time_str))

        id_item = QTableWidgetItem(job_id[:8])
        id_item.setData(Qt.ItemDataRole.UserRole, job_id)
        self.table.setItem(row, 1, id_item)

        self.table.setItem(row, 2, QTableWidgetItem(job.get("print_name") or job.get("product_name") or "—"))
        self.table.setItem(row, 3, QTableWidgetItem(job.get("barcode", "—")))
        self.table.setItem(row, 4, QTableWidgetItem(f"{float(job.get('print_mrp') or job.get('product_mrp') or 0):.2f}"))
        self.table.setItem(row, 5, QTableWidgetItem(f"{float(job.get('print_sale_rate') or job.get('sale_rate') or 0):.2f}"))
        self.table.setItem(row, 6, QTableWidgetItem(str(job.get("quantity", 1))))

        by_name = (job.get("created_by_name") or job.get("printed_by_name") or "—").strip()
        by_item = QTableWidgetItem(by_name)
        by_item.setForeground(QColor("#4f46e5"))
        self.table.setItem(row, 7, by_item)

        status_str = job.get("status", "QUEUED")
        status_item = QTableWidgetItem(status_str)
        status_color = {
            "COMPLETED": "#059669",
            "FAILED": "#dc2626",
            "INTERRUPTED": "#d97706",
            "PRINTING": "#d97706",
        }.get(status_str, "#7a5af8")
        status_item.setForeground(QColor(status_color))
        self.table.setItem(row, 8, status_item)

        # Cap visible rows to 200 to prevent unbounded memory growth on long-running POS machines
        if self.table.rowCount() > 200:
            self.table.removeRow(self.table.rowCount() - 1)

        return row

    def _update_job_row_status(self, job_id: str, status: str, color_hex: str):
        for r in range(self.table.rowCount()):
            id_item = self.table.item(r, 1)
            if id_item and id_item.data(Qt.ItemDataRole.UserRole) == job_id:
                st_item = self.table.item(r, 8)
                if st_item:
                    st_item.setText(status)
                    st_item.setForeground(QColor(color_hex))
                return

    def _load_recent_jobs_to_table(self):
        recent = self.ledger.get_recent_jobs(30)
        for job in reversed(recent):
            self._add_job_row(job)

    def _log(self, level: str, msg: str):
        t = time.strftime("%H:%M:%S")
        color = "#94a3b8"
        if level == "SUCCESS":
            color = "#4ade80"
        elif level == "ERROR":
            color = "#f87171"
        elif level == "WARN":
            color = "#fbbf24"
        elif level == "JOB":
            color = "#a78bfa"

        html = f"<span style='color: #64748b;'>[{t}]</span> <span style='color: {color}; font-weight: 600;'>[{level}]</span> {msg}"
        self.log_area.append(html)

        # Cap log lines to 400 lines
        if self.log_area.document().blockCount() > 450:
            cursor = self.log_area.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            for _ in range(100):
                cursor.select(cursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()
