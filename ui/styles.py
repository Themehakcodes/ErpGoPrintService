"""
QSS Stylesheet and Palette for KCSM Print Service.
Matches KCSM ERP web UI aesthetics (#7a5af8 purple gradient theme).
"""

QSS_THEME = """
QMainWindow {
    background-color: #f8fafc;
}

QWidget {
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    color: #0f172a;
    font-size: 13px;
}

/* ── Card Containers ── */
QFrame#CardFrame {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}

QFrame#HeaderCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7a5af8, stop:1 #6366f1);
    border-radius: 12px;
}

/* ── Typography ── */
QLabel#HeaderTitle {
    color: #ffffff;
    font-size: 17px;
    font-weight: 700;
}

QLabel#HeaderSubtitle {
    color: #e0e7ff;
    font-size: 12px;
}

QLabel#CardTitle {
    color: #1e293b;
    font-size: 14px;
    font-weight: 700;
}

QLabel#CardSubtitle {
    color: #64748b;
    font-size: 11px;
}

QLabel#FieldLabel {
    color: #475569;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}

/* ── Metric Cards ── */
QFrame#MetricBox {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}

QLabel#MetricValue {
    font-size: 20px;
    font-weight: 700;
    color: #0f172a;
}

QLabel#MetricLabel {
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
}

/* ── Form Inputs ── */
QLineEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
    color: #0f172a;
}

QLineEdit:focus, QComboBox:focus {
    border: 2px solid #7a5af8;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid #cbd5e1;
}

/* ── Action Buttons ── */
QPushButton#PrimaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7a5af8, stop:1 #6366f1);
    color: #ffffff;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 18px;
    border: none;
}

QPushButton#PrimaryBtn:hover {
    background: #6840c6;
}

QPushButton#PrimaryBtn:pressed {
    background: #53389e;
}

QPushButton#SecondaryBtn {
    background-color: #f1f5f9;
    color: #334155;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 16px;
    border: 1px solid #cbd5e1;
}

QPushButton#SecondaryBtn:hover {
    background-color: #e2e8f0;
}

QPushButton#OutlineBtn {
    background-color: transparent;
    color: #7a5af8;
    font-weight: 600;
    border-radius: 8px;
    padding: 7px 14px;
    border: 1px solid #7a5af8;
}

QPushButton#OutlineBtn:hover {
    background-color: #f4f3ff;
}

/* ── Table Widget ── */
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    gridline-color: #f1f5f9;
    font-size: 12px;
}

QTableWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #f1f5f9;
}

QTableWidget::item:selected {
    background-color: #f4f3ff;
    color: #0f172a;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
}

/* ── Log Text Area ── */
QTextEdit#LogArea {
    background-color: #0f172a;
    color: #94a3b8;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 8px;
}

/* ── Status Pills ── */
QLabel#StatusOnline {
    background-color: #ecfdf5;
    color: #059669;
    font-weight: 700;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 12px;
}

QLabel#StatusOffline {
    background-color: #fee2e2;
    color: #dc2626;
    font-weight: 700;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 12px;
}
"""
