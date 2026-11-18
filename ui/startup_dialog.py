"""
Startup Printer Selection Dialog for KCSM Print Service.
Prompts the user on application launch to select their active printer and template.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QPushButton, QCheckBox, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QCloseEvent

from core.printer import WindowsPrinter
from core.config import save_config
from core.autostart import set_autostart, is_autostart_enabled

class StartupPrinterDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Select Active Printer")
        self.setFixedSize(540, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            QLabel {
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QFrame#HeaderCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7a5af8, stop:1 #6366f1);
                border-radius: 10px;
            }
            QFrame#SelectionCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: 600;
            }
            QComboBox:hover {
                border-color: #94a3b8;
            }
            QComboBox:focus {
                border: 2px solid #7a5af8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #e2e8f0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: #f8fafc;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #475569;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: #f4f3ff;
                selection-color: #6941c6;
                border: 1px solid #cbd5e1;
            }
            QPushButton#PrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7a5af8, stop:1 #6366f1);
                color: #ffffff;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#PrimaryBtn:hover {
                background: #6941c6;
            }
            QPushButton#SecondaryBtn {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton#SecondaryBtn:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            QPushButton#OutlineBtn {
                background-color: #f8fafc;
                color: #475569;
                border: 1px solid #cbd5e1;
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton#OutlineBtn:hover {
                background-color: #f1f5f9;
                color: #0f172a;
            }
            QCheckBox {
                font-size: 12px;
                color: #334155;
                font-weight: 500;
                spacing: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # ── Header Banner ──
        banner = QFrame()
        banner.setObjectName("HeaderCard")
        b_layout = QVBoxLayout(banner)
        b_layout.setContentsMargins(16, 12, 16, 12)
        b_layout.setSpacing(4)

        title = QLabel("Select Active Thermal / Label Printer")
        title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: 800; background: transparent; border: none;")
        dev_code = self.cfg.get('device_code', 'DEV-0002')
        sub = QLabel(f"Device Code: {dev_code} — Cloud Print Bridge Ready")
        sub.setStyleSheet("color: #e0e7ff; font-size: 12px; font-weight: 500; background: transparent; border: none;")
        b_layout.addWidget(title)
        b_layout.addWidget(sub)
        layout.addWidget(banner)

        # ── Selection Card ──
        card = QFrame()
        card.setObjectName("SelectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(12)

        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(12)

        # Printer selector
        lbl_p = QLabel("Target Printer:")
        lbl_p.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px; background: transparent; border: none;")
        self.printer_combo = QComboBox()
        printers = WindowsPrinter.get_installed_printers()
        if printers:
            self.printer_combo.addItems(printers)
            saved_p = self.cfg.get("selected_printer", "")
            idx = self.printer_combo.findText(saved_p)
            if idx >= 0:
                self.printer_combo.setCurrentIndex(idx)
            else:
                default_p = WindowsPrinter.get_default_printer()
                def_idx = self.printer_combo.findText(default_p)
                if def_idx >= 0:
                    self.printer_combo.setCurrentIndex(def_idx)
        else:
            self.printer_combo.addItem("No Windows Printers Found")

        grid.addWidget(lbl_p, 0, 0)
        grid.addWidget(self.printer_combo, 0, 1)

        # Protocol / Template selector
        lbl_m = QLabel("Label Template:")
        lbl_m.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px; background: transparent; border: none;")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "TSPL (4-Up Sticker Roll 101.6x25mm)",
            "TSPL_BALA (Bala Single Tag 74.1x25mm)",
            "TSPL_1UP (Single Label 50x25mm)",
            "ESCPOS (Thermal Receipt 58/80mm)",
            "RAW (Direct Pass-Through)"
        ])
        saved_mode = self.cfg.get("printer_mode", "TSPL")
        idx_m = self.mode_combo.findText(saved_mode, Qt.MatchFlag.MatchStartsWith)
        if idx_m >= 0:
            self.mode_combo.setCurrentIndex(idx_m)

        grid.addWidget(lbl_m, 1, 0)
        grid.addWidget(self.mode_combo, 1, 1)

        card_layout.addLayout(grid)

        # Test Print button row
        test_row = QHBoxLayout()
        test_row.addStretch()
        test_btn = QPushButton("Test Print Alignment")
        test_btn.setObjectName("OutlineBtn")
        test_btn.clicked.connect(self._handle_test_print)
        test_row.addWidget(test_btn)
        card_layout.addLayout(test_row)

        layout.addWidget(card)

        # ── Checkboxes ──
        opt_box = QVBoxLayout()
        opt_box.setSpacing(8)

        self.prompt_chk = QCheckBox("Show this printer selection prompt on every startup")
        self.prompt_chk.setChecked(self.cfg.get("prompt_printer_on_startup", False))
        opt_box.addWidget(self.prompt_chk)

        self.autostart_chk = QCheckBox("Automatically start KCSM Print Service when Windows boots")
        self.autostart_chk.setChecked(self.cfg.get("autostart_with_windows", True) or is_autostart_enabled())
        opt_box.addWidget(self.autostart_chk)

        layout.addLayout(opt_box)

        # ── Action Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        cancel_btn = QPushButton("Use Current Settings")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self._handle_dismiss)

        start_btn = QPushButton("Save && Start Agent")
        start_btn.setObjectName("PrimaryBtn")
        start_btn.clicked.connect(self._handle_confirm)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(start_btn)
        layout.addLayout(btn_layout)

    def _handle_test_print(self):
        p_name = self.printer_combo.currentText()
        if not p_name or "No Windows Printers" in p_name:
            QMessageBox.warning(self, "No Printer", "Please select a valid installed printer.")
            return

        mode_text = self.mode_combo.currentText()
        if "ESCPOS" in mode_text:
            mode = "ESCPOS"
        elif "TSPL_BALA" in mode_text:
            mode = "TSPL_BALA"
        elif "TSPL_1UP" in mode_text:
            mode = "TSPL_1UP"
        else:
            mode = "TSPL"

        test_data = WindowsPrinter.generate_test_print(mode, p_name)
        ok, msg = WindowsPrinter.send_raw_bytes(p_name, test_data, "KCSM_Startup_Test")
        if ok:
            QMessageBox.information(self, "Test Sent", f"Test print sent to '{p_name}' successfully!")
        else:
            QMessageBox.critical(self, "Print Error", f"Spooler error: {msg}")

    def _handle_dismiss(self):
        self.cfg["prompt_printer_on_startup"] = self.prompt_chk.isChecked()
        self.cfg["autostart_with_windows"] = self.autostart_chk.isChecked()
        set_autostart(self.autostart_chk.isChecked())
        save_config(self.cfg)
        self.reject()

    def closeEvent(self, event: QCloseEvent):
        self.cfg["prompt_printer_on_startup"] = self.prompt_chk.isChecked()
        self.cfg["autostart_with_windows"] = self.autostart_chk.isChecked()
        set_autostart(self.autostart_chk.isChecked())
        save_config(self.cfg)
        super().closeEvent(event)

    def _handle_confirm(self):
        p_name = self.printer_combo.currentText()
        if p_name and "No Windows Printers" not in p_name:
            self.cfg["selected_printer"] = p_name
        self.cfg["printer_mode"] = self.mode_combo.currentText().split()[0]
        self.cfg["prompt_printer_on_startup"] = self.prompt_chk.isChecked()
        self.cfg["autostart_with_windows"] = self.autostart_chk.isChecked()

        set_autostart(self.autostart_chk.isChecked())
        save_config(self.cfg)
        self.accept()
