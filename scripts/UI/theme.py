# -*- coding: utf-8 -*-
"""Shared visual theme for Spiker Qt pages."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QPushButton, QWidget

APP_STYLESHEET = r"""
QWidget { font-family: "Segoe UI", "Arial"; color: #F5FAFF; font-size: 10pt; }
QMainWindow, QDialog { background: #061746; }
QMenuBar { background: rgba(6, 23, 70, 238); color: #DDEEFF; border-bottom: 1px solid rgba(114, 232, 255, 45); padding: 4px 8px; }
QMenuBar::item { padding: 7px 11px; background: transparent; border-radius: 7px; }
QMenuBar::item:selected, QMenu::item:selected { background: rgba(18, 101, 232, 90); color: #FFFFFF; }
QMenu { background: #0B235B; color: #F5FAFF; border: 1px solid #2355A4; padding: 5px; }
QMenu::item { padding: 8px 24px; border-radius: 5px; }
QLabel { background: transparent; color: #EAF5FF; }
QLabel#brandMark { background: transparent; border: none; border-radius: 0px; padding: 0px; }
QLabel#brandTitle { color: #F5FAFF; font-size: 17pt; font-weight: 650; }
QLabel#mutedLabel { color: #A7BFFF; font-size: 9pt; }
QLabel#statusBadge { color: #BFEFFF; background: rgba(8, 51, 120, 100); border: 1px solid rgba(114, 232, 255, 68); border-radius: 11px; padding: 8px 12px; font-size: 8pt; font-weight: 650; letter-spacing: 0.8px; }
QLabel#pageTitle { color: #F5FAFF; font-size: 28pt; font-weight: 650; }
QLabel#pageSubtitle { color: #C4D9FA; font-size: 11pt; }
QLabel#sectionLabel, QLabel#cardEyebrow { color: #A7BFFF; font-size: 8pt; font-weight: 700; letter-spacing: 1.05px; }
QLabel#cardTitle { color: #F5FAFF; font-size: 19pt; font-weight: 650; }
QLabel#compactCardTitle { color: #F5FAFF; font-size: 15pt; font-weight: 650; }
QLabel#cardDescription { color: #D3E7FF; font-size: 10.5pt; }
QLabel#formatLabel { color: #B5D8F8; background: rgba(5, 27, 74, 100); border: 1px solid rgba(114, 232, 255, 42); border-radius: 11px; padding: 10px 12px; font-size: 8pt; }
QLabel#footerTitle { color: #BCD5F7; font-size: 9pt; font-weight: 600; }
QFrame#featureCard { background: transparent; border: none; border-radius: 30px; }
QFrame#panel, QFrame#infoCard { background: rgba(8, 38, 97, 180); border: 1px solid rgba(114, 232, 255, 70); border-radius: 18px; }
QLabel#dialogTitle { color: #F5FAFF; font-size: 20pt; font-weight: 650; }
QLabel#infoIntro { color: #C4D9FA; font-size: 11pt; padding: 4px 0; }
QLabel#infoIndex { color: #C8F7FF; background: rgba(18, 101, 232, 115); border: 1px solid rgba(114, 232, 255, 100); border-radius: 10px; font-size: 13pt; font-weight: 700; }
QLabel#infoCardTitle { color: #F5FAFF; font-size: 12pt; font-weight: 650; }
QLabel#infoCardDescription { color: #C4D9FA; font-size: 10pt; }
QLabel#timerLabel { color: #D8F8FF; font-size: 20pt; font-weight: 650; font-family: "Segoe UI", "Consolas"; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #1265E8, stop:0.60 #087BFF, stop:1 #16BFFF); color: #FFFFFF; border: 1px solid rgba(206,246,255,160); border-top-color: rgba(245,250,255,210); border-radius: 15px; padding: 9px 17px; font-size: 10pt; font-weight: 650; }
QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #2479F3, stop:0.60 #138BFF, stop:1 #4BD7FF); border-color: rgba(222,250,255,220); }
QPushButton:pressed { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0849B8, stop:0.60 #075ACB, stop:1 #098EC3); padding-top: 11px; padding-bottom: 7px; }
QPushButton:disabled { color: #839CBD; background: rgba(22, 50, 98, 150); border-color: rgba(116, 150, 192, 50); }
QPushButton[role="primary"] { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #1265E8, stop:0.42 #087BFF, stop:1 #16BFFF); color: #FFFFFF; border: 1px solid rgba(216,249,255,205); }
QPushButton[role="primary"]:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #297BF1, stop:0.42 #1592FF, stop:1 #72E8FF); }
QPushButton[role="secondary"] { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(18,101,232,210), stop:0.55 rgba(8,91,211,230), stop:1 rgba(11,47,131,235)); border: 1px solid rgba(114,232,255,155); }
QPushButton[role="secondary"]:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(35,119,242,225), stop:0.55 rgba(13,115,236,240), stop:1 rgba(22,98,188,245)); }
QPushButton[role="tertiary"] { color: #D5E9FF; background: rgba(8, 38, 97, 116); border: 1px solid rgba(114,232,255,70); border-radius: 12px; }
QPushButton[role="tertiary"]:hover { background: rgba(18, 101, 232, 100); border-color: rgba(114,232,255,145); }
QPushButton[role="back"] { background: rgba(7, 34, 86, 195); color: #D5E9FF; border: 1px solid rgba(114,232,255,75); }

QComboBox {
    color: #F5FAFF;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(13, 47, 108, 245), stop:1 rgba(5, 25, 70, 245));
    border: 1px solid rgba(114, 173, 243, 115);
    border-radius: 10px;
    padding: 6px 30px 6px 10px;
    min-height: 28px;
    selection-background-color: #1265E8;
}
QComboBox:hover { border-color: rgba(114, 232, 255, 190); background: rgba(11, 47, 105, 250); }
QComboBox:focus, QComboBox:on { border-color: #16BFFF; }
QComboBox:disabled { color: #839CBD; background: rgba(16, 37, 83, 180); border-color: rgba(116, 150, 192, 50); }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 27px;
    border-left: 1px solid rgba(114, 232, 255, 55);
    border-top-right-radius: 9px;
    border-bottom-right-radius: 9px;
    background: rgba(22, 101, 198, 45);
}
QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #72E8FF;
    margin-right: 8px;
}
QComboBox QLineEdit {
    color: #F5FAFF;
    background: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px 2px;
    selection-background-color: #1265E8;
}
QAbstractItemView {
    color: #F5FAFF;
    background: #0B235B;
    border: 1px solid #4389C7;
    border-radius: 8px;
    outline: 0;
    selection-background-color: #1265E8;
    selection-color: #FFFFFF;
}
QAbstractItemView::item { min-height: 28px; padding: 6px 9px; border-bottom: 1px solid rgba(114, 173, 243, 25); }
QAbstractItemView::item:hover { background: rgba(22, 101, 232, 110); }
QLabel#aiFieldLabel { color: #BFE8FF; font-size: 8.5pt; font-weight: 650; }
QLabel#helpAuthor { color: #90BAE9; font-size: 9pt; font-weight: 600; padding: 4px 3px; }

QLineEdit, QTextEdit, QPlainTextEdit { background: rgba(4, 19, 58, 225); color: #F5FAFF; border: 1px solid rgba(114, 173, 243, 90); border-radius: 11px; padding: 9px; selection-background-color: #1265E8; selection-color: #FFFFFF; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #16BFFF; }
QLineEdit:disabled { background: rgba(16, 37, 83, 180); color: #91A9CE; }
QTextEdit, QPlainTextEdit { padding: 12px; }
QProgressBar { background: rgba(3, 15, 48, 220); border: 1px solid rgba(114, 173, 243, 75); border-radius: 6px; height: 10px; text-align: center; color: #EAF5FF; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #087BFF, stop:1 #16BFFF); border-radius: 5px; }
QProgressDialog, QMessageBox { background: #081E53; color: #F5FAFF; }
QStatusBar { background: rgba(4, 18, 54, 220); color: #A7BFFF; border-top: 1px solid rgba(114, 232, 255, 38); }
QScrollBar:vertical { background: rgba(6, 23, 70, 220); width: 11px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(114, 171, 235, 135); min-height: 28px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: rgba(114, 232, 255, 175); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QToolTip { background: #0B2F83; color: #F5FAFF; border: 1px solid #16BFFF; padding: 6px 8px; border-radius: 6px; }
"""


def apply_window_theme(window):
    """Remove legacy per-widget gradients/styles so the shared theme can apply consistently."""
    for widget in [window, *window.findChildren(QWidget)]:
        widget.setStyleSheet("")
        if isinstance(widget, QPushButton):
            if "back_to_main" in widget.objectName():
                widget.setProperty("role", "back")
            widget.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
            widget.setMinimumHeight(max(widget.minimumHeight(), 36))
        elif isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            widget.setFont(QFont("Segoe UI", 10))
        elif isinstance(widget, QLabel):
            name = widget.objectName().lower()
            size = 10
            weight = QFont.Normal
            if "main_label" in name or "title" in name or "label_hello" in name:
                size, weight = 17, QFont.DemiBold
            elif "info" in name and ("main" in name or "title" in name):
                size, weight = 16, QFont.DemiBold
            widget.setFont(QFont("Segoe UI", size, weight))
    window.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

APP_STYLESHEET += """
QTabWidget#appTabs::pane { border: 1px solid rgba(157,190,222,95); background: #08245A; top: -1px; }
QTabWidget#appTabs QTabBar::tab { background: #0B285E; color: #C7D9F2; border: 1px solid rgba(125,169,220,80); border-bottom: none; padding: 9px 18px; margin-right: 3px; min-width: 86px; }
QTabWidget#appTabs QTabBar::tab:selected { background: #123C7B; color: #FFFFFF; border-top: 2px solid #BDD6E2; }
QTabWidget#appTabs QTabBar::tab:hover:!selected { background: #10336C; }
"""

APP_STYLESHEET += r'''

QPushButton#pushButton_settings, QPushButton#pushButton_about_prog {
    background: rgba(5, 22, 66, 75);
    border: 1px solid rgba(114, 232, 255, 45);
    border-radius: 14px;
    padding: 1px;
}
QPushButton#pushButton_settings:hover, QPushButton#pushButton_about_prog:hover {
    background: rgba(22, 74, 145, 88);
    border: 1px solid rgba(185, 233, 255, 145);
}
QPushButton#pushButton_settings:pressed, QPushButton#pushButton_about_prog:pressed {
    background: rgba(5, 18, 47, 200);
    padding-top: 2px;
}
QLabel#helpTitle { color: #F4F8FF; font-size: 21pt; font-weight: 700; }
QFrame#helpImageCard {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(22, 65, 126, 190), stop:1 rgba(8, 35, 83, 215));
    border: 1px solid rgba(75, 145, 203, 150);
    border-radius: 17px;
}
QLabel#helpIllustration { background: transparent; }
QLabel#helpCardTitle { color: #F4F8FF; font-size: 13pt; font-weight: 650; }
QLabel#helpCardDescription { color: #C1D5F2; font-size: 9.5pt; }
QFrame#helpImageCard { min-width: 150px; }
QFrame#helpInfoPanel {
    background: rgba(16, 41, 87, 206);
    border: 1px solid rgba(49, 95, 147, 175);
    border-radius: 13px;
}
QLabel#helpInfoSymbol {
    color: #72E8FF; font-size: 17pt; font-weight: 700;
    background: rgba(18, 101, 232, 35); border-radius: 7px;
}
QLabel#helpInfoTitle { color: #F4F8FF; font-size: 11pt; font-weight: 650; }
QLabel#helpInfoDescription { color: #C1D5F2; font-size: 9.5pt; }
QTableWidget#queueTable {
    background: rgba(4, 19, 58, 222);
    alternate-background-color: rgba(12, 39, 91, 205);
    color: #F5FAFF;
    gridline-color: rgba(75, 137, 199, 55);
    border: 1px solid rgba(75, 145, 203, 110);
    border-radius: 12px;
    selection-background-color: rgba(22, 101, 198, 190);
    selection-color: #FFFFFF;
}
QTableWidget#queueTable QHeaderView::section {
    background: rgba(12, 42, 94, 240);
    color: #B9E9FF;
    border: none;
    border-bottom: 1px solid rgba(75, 145, 203, 100);
    padding: 8px 10px;
    font-weight: 650;
}
QTableWidget#queueTable::item { padding: 6px; border: none; }
QComboBox#modelCombo, QSpinBox {
    min-height: 28px;
    padding: 7px 10px;
    background: rgba(4, 19, 58, 230);
    border: 1px solid rgba(114, 173, 243, 100);
    border-radius: 10px;
    color: #F5FAFF;
}
QComboBox#modelCombo QAbstractItemView {
    background: #0B235B; color: #F5FAFF;
    selection-background-color: #1265E8;
    border: 1px solid #4389C7;
}
QPushButton#pushButton_reset_recording {
    background: rgba(8, 38, 97, 120);
    color: #D5E9FF;
    border: 1px solid rgba(114, 232, 255, 70);
    border-radius: 12px;
}
QPushButton#pushButton_reset_recording:hover {
    background: rgba(18, 101, 232, 90);
    border-color: rgba(114, 232, 255, 145);
}

'''

APP_STYLESHEET += r'''
/* Integrated audio player */
QSplitter#mediaWorkspaceSplitter::handle {
    background: rgba(99, 154, 214, 55);
    width: 5px;
    margin: 5px 1px;
    border-radius: 2px;
}
QLabel#playerTime {
    color: #DDEEFF;
    font-size: 9.5pt;
    font-weight: 600;
    background: rgba(4, 18, 52, 140);
    border: 1px solid rgba(102, 165, 225, 75);
    border-radius: 8px;
    padding: 6px 8px;
}
QSlider#playerSeekSlider, QSlider#playerVolumeSlider {
    min-height: 18px;
    background: transparent;
}
QSlider#playerSeekSlider::groove:horizontal, QSlider#playerVolumeSlider::groove:horizontal {
    height: 5px;
    background: rgba(104, 145, 196, 95);
    border-radius: 2px;
}
QSlider#playerSeekSlider::sub-page:horizontal, QSlider#playerVolumeSlider::sub-page:horizontal {
    background: #28A9F5;
    border-radius: 2px;
}
QSlider#playerSeekSlider::handle:horizontal, QSlider#playerVolumeSlider::handle:horizontal {
    width: 12px;
    margin: -5px 0;
    border-radius: 6px;
    background: #E9F8FF;
    border: 1px solid #72CFFF;
}
QComboBox#playerSpeedCombo {
    min-height: 24px;
    padding: 4px 8px;
    background: rgba(4, 19, 58, 230);
    border: 1px solid rgba(114, 173, 243, 100);
    border-radius: 8px;
    color: #F5FAFF;
}
QLabel#audioWaveform { background: transparent; }
'''
