from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


def apply_application_font(app: QApplication) -> None:
    families = set(QFontDatabase.families())
    if "Pretendard" in families:
        family = "Pretendard"
    elif "맑은 고딕" in families:
        family = "맑은 고딕"
    else:
        family = app.font().family()
    app.setFont(QFont(family, 10))


APP_STYLESHEET = """
QMainWindow {
    background: #f4f6f9;
}
QWidget {
    color: #20242c;
    font-size: 13px;
}
QLabel {
    background: transparent;
}
QToolTip {
    background: #20242c;
    color: #ffffff;
    border: 1px solid #20242c;
    padding: 6px 8px;
}
QTabWidget::pane {
    border: 1px solid #d9dee7;
    border-radius: 8px;
    background: #ffffff;
    top: -1px;
}
QTabBar::tab {
    min-height: 24px;
    background: #e9edf3;
    color: #4b5565;
    padding: 10px 17px;
    margin-right: 2px;
    border: 1px solid #d9dee7;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:hover {
    background: #f6f8fb;
    color: #1f4f99;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #1f5fbf;
    font-weight: 700;
    border-top: 3px solid #2f6fce;
    padding-top: 8px;
}
QPushButton {
    min-height: 38px;
    background: #ffffff;
    color: #273142;
    border: 1px solid #c9d0dc;
    border-radius: 6px;
    padding: 0 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #f4f7fb;
    border-color: #8da5c7;
}
QPushButton:pressed {
    background: #e8eef7;
}
QPushButton:focus {
    border: 2px solid #4a82d5;
}
QPushButton:disabled {
    background: #edf0f4;
    color: #8a93a2;
    border-color: #d8dde5;
}
QPushButton[primary="true"] {
    background: #2f6fce;
    color: #ffffff;
    border-color: #2f6fce;
}
QPushButton[primary="true"]:hover {
    background: #255fb5;
    border-color: #255fb5;
}
QPushButton[danger="true"] {
    background: #ffffff;
    color: #b4232f;
    border-color: #e2aab0;
}
QPushButton[danger="true"]:hover {
    background: #fff3f4;
    border-color: #cc6f78;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 36px;
    background: #ffffff;
    border: 1px solid #c9d0dc;
    border-radius: 6px;
    padding: 0 9px;
    selection-background-color: #2f6fce;
}
QTextEdit, QPlainTextEdit {
    padding: 8px 9px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #4a82d5;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: #edf0f4;
    color: #7d8796;
}
QComboBox::drop-down {
    width: 28px;
    border: none;
}
QCheckBox {
    spacing: 8px;
    min-height: 28px;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #d8dee8;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 18px;
    margin: -6px 0;
    background: #2f6fce;
    border-radius: 9px;
}
QTableWidget, QListWidget {
    background: #ffffff;
    alternate-background-color: #f7f9fc;
    border: 1px solid #d9dee7;
    border-radius: 6px;
    selection-background-color: #dce9fb;
    selection-color: #172033;
}
QHeaderView::section {
    min-height: 36px;
    background: #edf1f6;
    color: #354052;
    padding: 0 10px;
    border: none;
    border-right: 1px solid #d9dee7;
    border-bottom: 1px solid #d9dee7;
    font-weight: 700;
}
QGroupBox {
    background: #ffffff;
    border: 1px solid #d9dee7;
    border-radius: 8px;
    margin-top: 15px;
    padding-top: 12px;
    font-weight: 700;
    font-size: 15px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #273142;
}
QSplitter::handle {
    background: #eef1f5;
}
QSplitter::handle:horizontal {
    width: 8px;
}
QSplitter::handle:vertical {
    height: 8px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QStatusBar {
    background: #ffffff;
    border-top: 1px solid #d9dee7;
    color: #596273;
}
#PageHeader {
    background: transparent;
}
#PageTitle {
    font-size: 21px;
    font-weight: 800;
    color: #172033;
}
#PageDescription {
    font-size: 12px;
    color: #5d6675;
}
#SectionTitle {
    font-size: 16px;
    font-weight: 700;
    color: #273142;
}
#Card {
    background: #ffffff;
    border: 1px solid #d9dee7;
    border-radius: 9px;
}
#CardValue {
    font-size: 27px;
    font-weight: 800;
    color: #172033;
}
#CardCaption {
    color: #596273;
    font-weight: 700;
}
#CardDescription, #Muted {
    color: #667080;
    font-size: 12px;
}
#ModeBadge, #StatusInfo {
    color: #1f5fbf;
    background: #e8f1ff;
    border: 1px solid #b9d2f5;
    border-radius: 5px;
    padding: 6px 9px;
    font-weight: 700;
}
#StatusSuccess {
    color: #157347;
    background: #e7f6ee;
    border: 1px solid #b9dfca;
    border-radius: 5px;
    padding: 6px 9px;
    font-weight: 700;
}
#StatusWarning {
    color: #9a5b00;
    background: #fff4db;
    border: 1px solid #efd39b;
    border-radius: 5px;
    padding: 6px 9px;
    font-weight: 700;
}
#StatusError {
    color: #b4232f;
    background: #fff0f1;
    border: 1px solid #e7bcc0;
    border-radius: 5px;
    padding: 6px 9px;
    font-weight: 700;
}
#CanvasFrame {
    background: #1d222b;
    border: 1px solid #c9d0dc;
    border-radius: 7px;
}
"""
