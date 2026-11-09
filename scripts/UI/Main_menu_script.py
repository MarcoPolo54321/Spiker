# -*- coding: utf-8 -*-
"""Start screen for Spiker's calm, focused desktop interface."""
from math import cos, sin
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QPixmap, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget, QStatusBar, QMenuBar, QScrollArea,
)
from PySide6.QtSvg import QSvgRenderer

from app_paths import get_app_root

PROJECT_ROOT = get_app_root()
ICON_ROOT = PROJECT_ROOT / "icons"

# Centralized colors for the home-screen surfaces.
MIDNIGHT_NAVY = "#071943"
ROYAL_BLUE = "#0C2D70"
ELECTRIC_BLUE = "#1680F8"
BRIGHT_BLUE = "#36A4FF"
NEON_CYAN = "#66E7FF"
ICE_BLUE = "#A9DCFF"
PERIWINKLE = "#C1CFFF"
WHITE = "#F5FBFF"
CARD_RADIUS = 20
CARD_BORDER_ALPHA = 150
CARD_HOVER_BORDER_ALPHA = 235


class LiquidGlassBackground(QWidget):
    """Paint a vivid blue canvas with slow, low-distraction light movement."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._animation = QTimer(self)
        self._animation.setInterval(70)
        self._animation.timeout.connect(self._advance_animation)

    def _advance_animation(self):
        self._phase = (self._phase + 0.035) % (2 * 3.14159)
        self.update()

    def showEvent(self, event):
        self._animation.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._animation.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        bounds = self.rect()
        w, h = float(bounds.width()), float(bounds.height())

        base = QLinearGradient(QPointF(0, 0), QPointF(w, h))
        base.setColorAt(0.0, QColor("#0B2D75"))
        base.setColorAt(0.48, QColor("#09245F"))
        base.setColorAt(1.0, QColor("#061943"))
        painter.fillRect(bounds, QBrush(base))

        glows = (
            (w * (0.83 + 0.08 * sin(self._phase)), h * 0.12, QColor(25, 149, 255, 78)),
            (w * (0.12 + 0.06 * cos(self._phase * 0.72)), h * 0.91, QColor(44, 98, 255, 62)),
        )
        for x, y, color in glows:
            glow = QRadialGradient(QPointF(x, y), max(w, h) * 0.64)
            glow.setColorAt(0.0, color)
            glow.setColorAt(0.48, QColor(color.red(), color.green(), color.blue(), 20))
            glow.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillRect(bounds, QBrush(glow))

        # Slow flowing contour lines add depth while keeping the copy readable.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for index in range(3):
            offset = self._phase * 18 + index * 24
            path = QPainterPath(QPointF(-w * 0.05, h * (0.20 + index * 0.035)))
            path.cubicTo(
                QPointF(w * 0.28, h * (0.13 + index * 0.035) + sin(self._phase + index) * 18),
                QPointF(w * 0.68, h * (0.23 + index * 0.035) + cos(self._phase + index) * 16),
                QPointF(w * 1.06, h * (0.16 + index * 0.035) + offset % 18),
            )
            painter.setPen(QPen(QColor(74, 188, 255, 18 - index * 3), 1.4))
            painter.drawPath(path)
        painter.end()


class NeonVoiceWaveform(QWidget):
    """A compact animated voice waveform in the app's blue and violet icon palette."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._animation = QTimer(self)
        self._animation.setInterval(65)
        self._animation.timeout.connect(self._advance_animation)
        self.setObjectName("voiceWaveform")
        self.setAccessibleName("Анимированная звуковая волна")
        self.setMinimumSize(174, 50)
        self.setMaximumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _advance_animation(self):
        self._phase = (self._phase + 0.19) % (2 * 3.14159)
        self.update()

    def showEvent(self, event):
        self._animation.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._animation.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bounds = self.rect().adjusted(1, 1, -1, -1)

        panel = QLinearGradient(QPointF(bounds.left(), bounds.top()), QPointF(bounds.right(), bounds.bottom()))
        panel.setColorAt(0.0, QColor(14, 76, 157, 205))
        panel.setColorAt(1.0, QColor(7, 35, 99, 220))
        panel_path = QPainterPath()
        panel_path.addRoundedRect(bounds, 17, 17)
        painter.fillPath(panel_path, QBrush(panel))
        painter.setPen(QPen(QColor(96, 216, 255, 118), 1.0))
        painter.drawPath(panel_path)

        center_y = bounds.center().y()
        inner_left = bounds.left() + 13
        inner_width = max(1.0, bounds.width() - 26)
        count = max(22, min(44, int(inner_width / 5.2)))
        step = inner_width / count
        bar_width = max(2.0, step * 0.48)
        for index in range(count):
            wave_a = abs(sin(index * 0.39 - self._phase))
            wave_b = abs(cos(index * 0.17 + self._phase * 0.76))
            envelope = 0.20 + 0.80 * wave_a * (0.42 + wave_b * 0.58)
            height = 4.0 + (bounds.height() - 16.0) * envelope
            x = inner_left + index * step + (step - bar_width) / 2
            bar = QPainterPath()
            bar.addRoundedRect(x, center_y - height / 2, bar_width, height, bar_width / 2, bar_width / 2)
            hue = index / max(1, count - 1)
            top = QColor.fromRgbF(0.37 - 0.03 * hue, 0.91 - 0.34 * hue, 1.0, 0.98)
            bottom = QColor.fromRgbF(0.25 + 0.30 * hue, 0.63 - 0.19 * hue, 1.0, 0.88)
            gradient = QLinearGradient(QPointF(x, center_y - height / 2), QPointF(x, center_y + height / 2))
            gradient.setColorAt(0.0, top)
            gradient.setColorAt(1.0, bottom)
            painter.fillPath(bar, QBrush(gradient))
        painter.end()


class LiquidGlassCard(QFrame):
    """Custom-painted translucent glass surface with a restrained highlight."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self.setObjectName("featureCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 7)
        shadow.setColor(QColor(21, 106, 240, 74))
        self.setGraphicsEffect(shadow)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = CARD_RADIUS
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        fill = QLinearGradient(QPointF(rect.left(), rect.top()), QPointF(rect.left(), rect.bottom()))
        fill.setColorAt(0.0, QColor("#1556A5") if not self._hovered else QColor("#1A70CA"))
        fill.setColorAt(1.0, QColor("#0A2A68") if not self._hovered else QColor("#0C3A86"))
        painter.fillPath(path, QBrush(fill))

        border_alpha = CARD_HOVER_BORDER_ALPHA if self._hovered else CARD_BORDER_ALPHA
        border = QColor("#74E9FF") if self._hovered else QColor(75, 180, 255, border_alpha)
        painter.setPen(QPen(border, 1.15))
        painter.drawPath(path)
        painter.end()


class IconGlass(QWidget):
    """Display the supplied high-resolution liquid-glass artwork without adding a competing halo."""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self._target_width = 112
        self.setFixedSize(self._target_width, int(self._target_width * 0.84))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._svg = QSvgRenderer(str(image_path)) if str(image_path).lower().endswith(".svg") else None
        self._pixmap = QPixmap(str(image_path)) if self._svg is None else QPixmap()

    def set_responsive_width(self, width):
        width = max(88, min(160, int(width)))
        if width != self._target_width:
            self._target_width = width
            self.setFixedSize(width, int(width * 0.84))
            self.update()

    def paintEvent(self, event):
        if (self._svg is None or not self._svg.isValid()) and self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._svg is not None and self._svg.isValid():
            self._svg.render(painter, QRectF(self.rect()))
        else:
            pixmap = self._pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - pixmap.width()) // 2
            y = (self.height() - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)
        painter.end()


def _create_feature_card(eyebrow_text, image_path, title_text, description_text,
                         hint_text, button_text, button_name, tooltip=None):
    """Create a compact two-column action card with an obvious primary button."""
    card = LiquidGlassCard()
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    outer = QHBoxLayout(card)
    outer.setContentsMargins(18, 16, 18, 16)
    outer.setSpacing(16)

    media_panel = QWidget(card)
    media_panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    media = QVBoxLayout(media_panel)
    media.setContentsMargins(0, 0, 0, 0)
    media.setSpacing(8)
    eyebrow = QLabel(eyebrow_text)
    eyebrow.setObjectName("cardEyebrow")
    eyebrow.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    icon = IconGlass(image_path, media_panel)
    media.addWidget(eyebrow)
    media.addWidget(icon, 0, Qt.AlignmentFlag.AlignCenter)
    media.addStretch(1)
    outer.addWidget(media_panel, 0)

    content_panel = QWidget(card)
    content_panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    content = QVBoxLayout(content_panel)
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(6)
    title = QLabel(title_text)
    title.setObjectName("compactCardTitle")
    title.setWordWrap(True)
    description = QLabel(description_text)
    description.setObjectName("cardDescription")
    description.setWordWrap(True)
    description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    hint = QLabel(hint_text)
    hint.setObjectName("formatLabel")
    hint.setWordWrap(True)
    button = QPushButton(button_text)
    button.setObjectName(button_name)
    button.setProperty("role", "primary")
    button.setMinimumHeight(38)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if tooltip:
        button.setToolTip(tooltip)
    content.addWidget(title)
    content.addWidget(description)
    content.addWidget(hint)
    content.addStretch(1)
    content.addWidget(button)
    outer.addWidget(content_panel, 1)
    return card, outer, media_panel, icon, title, description, hint, button


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1024, 720)
        MainWindow.setMinimumSize(QSize(720, 540))
        MainWindow.setWindowTitle("СПИКЕР")

        self.centralwidget = LiquidGlassBackground(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        shell = QVBoxLayout(self.centralwidget)
        shell.setContentsMargins(0, 0, 0, 0)
        self.home_scroll = QScrollArea(self.centralwidget)
        self.home_scroll.setObjectName("homeScroll")
        self.home_scroll.setWidgetResizable(True)
        self.home_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.home_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # The start page is a dashboard, not a document: keep it fitted to the
        # main window and let its cards compact when the window is resized.
        self.home_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.home_scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.home_scroll.setAutoFillBackground(False)
        self.home_scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.home_scroll.viewport().setAutoFillBackground(False)
        self.home_scroll.viewport().setStyleSheet("background: transparent; border: none;")
        self.home_content = QWidget()
        self.home_content.setObjectName("homeContent")
        self.home_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.home_content.setAutoFillBackground(False)
        root = QVBoxLayout(self.home_content)
        root.setContentsMargins(30, 24, 30, 22)
        root.setSpacing(0)
        self.root_layout = root
        self.home_scroll.setWidget(self.home_content)
        shell.addWidget(self.home_scroll)

        # Brand header
        header = QHBoxLayout()
        header.setSpacing(10)
        self.brandMark = QLabel()
        self.brandMark.setObjectName("brandMark")
        self.brandMark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brandMark.setFixedSize(62, 62)
        self.brandMark.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        brand_pixmap = QPixmap(str(ICON_ROOT / "spiker_app.png"))
        if not brand_pixmap.isNull():
            self.brandMark.setPixmap(brand_pixmap.scaled(
                QSize(60, 60), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        header.addWidget(self.brandMark)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        self.label_hello_main = QLabel("СПИКЕР")
        self.label_hello_main.setObjectName("brandTitle")
        self.label_hello_main.setFont(QFont("Segoe UI", 17, QFont.Weight.DemiBold))
        self.label_brand_subtitle = QLabel("Голос в текст")
        self.label_brand_subtitle.setObjectName("mutedLabel")
        brand_text.addWidget(self.label_hello_main)
        brand_text.addWidget(self.label_brand_subtitle)
        header.addLayout(brand_text)
        header.addStretch(1)

        # Utility controls stay together; the waveform aligns to the three-icon row.
        utility_column = QVBoxLayout()
        utility_column.setSpacing(7)
        self.label_local_badge = QLabel("ОБРАБОТКА НА УСТРОЙСТВЕ")
        self.label_local_badge.setObjectName("statusBadge")
        self.label_local_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_local_badge.setMinimumHeight(32)
        utility_column.addWidget(self.label_local_badge, 0, Qt.AlignmentFlag.AlignRight)

        utility_buttons = QHBoxLayout()
        utility_buttons.setSpacing(8)
        self.pushButton_settings = QPushButton()
        self.pushButton_settings.setObjectName("pushButton_settings")
        self.pushButton_settings.setToolTip("Настройки СПИКЕР")
        self.pushButton_settings.setAccessibleName("Настройки")
        self.pushButton_settings.setFixedSize(46, 46)
        self.pushButton_settings.setIcon(QIcon(str(ICON_ROOT / "settings_button.png")))
        self.pushButton_settings.setIconSize(QSize(43, 43))
        self.pushButton_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        utility_buttons.addWidget(self.pushButton_settings)

        self.pushButton_about_prog = QPushButton()
        self.pushButton_about_prog.setObjectName("pushButton_about_prog")
        self.pushButton_about_prog.setToolTip("Справка СПИКЕР")
        self.pushButton_about_prog.setAccessibleName("Справка")
        self.pushButton_about_prog.setFixedSize(46, 46)
        self.pushButton_about_prog.setIcon(QIcon(str(ICON_ROOT / "help_button.png")))
        self.pushButton_about_prog.setIconSize(QSize(43, 43))
        self.pushButton_about_prog.setCursor(Qt.CursorShape.PointingHandCursor)
        utility_buttons.addWidget(self.pushButton_about_prog)

        self.pushButton_user_guide = QPushButton()
        self.pushButton_user_guide.setObjectName("pushButton_user_guide")
        self.pushButton_user_guide.setToolTip("Обучение: инструкция по работе с приложением СПИКЕР")
        self.pushButton_user_guide.setAccessibleName("Обучение")
        self.pushButton_user_guide.setFixedSize(46, 46)
        self.pushButton_user_guide.setIcon(QIcon(str(ICON_ROOT / "training_button.png")))
        self.pushButton_user_guide.setIconSize(QSize(43, 43))
        self.pushButton_user_guide.setCursor(Qt.CursorShape.PointingHandCursor)
        utility_buttons.addWidget(self.pushButton_user_guide)
        utility_column.addLayout(utility_buttons)
        self.voice_waveform = NeonVoiceWaveform()
        self.voice_waveform.setFixedWidth(154)
        utility_column.addWidget(self.voice_waveform, 0, Qt.AlignmentFlag.AlignRight)
        header.addLayout(utility_column)
        root.addLayout(header)

        root.addSpacing(8)
        self.label_easy_fast_slogan = QLabel("Голос в текст. Просто.")
        self.label_easy_fast_slogan.setObjectName("pageTitle")
        self.label_easy_fast_slogan.setFont(QFont("Segoe UI", 25, QFont.Weight.DemiBold))
        hero = QHBoxLayout()
        hero.setSpacing(18)
        self.hero_layout = hero
        hero.addWidget(self.label_easy_fast_slogan, 1)
        root.addLayout(hero)
        self.label_every_audio_to_text = QLabel("Диктуйте, расшифровывайте аудио и обрабатывайте результат с помощью ИИ.")
        self.label_every_audio_to_text.setObjectName("pageSubtitle")
        self.label_every_audio_to_text.setWordWrap(True)
        root.addWidget(self.label_every_audio_to_text)

        root.addSpacing(8)
        self.label_what_u_want = QLabel("ВЫБЕРИТЕ ДЕЙСТВИЕ")
        self.label_what_u_want.setObjectName("sectionLabel")
        root.addWidget(self.label_what_u_want)
        root.addSpacing(9)

        cards = QGridLayout()
        self.cards_layout = cards
        cards.setSpacing(16)
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        cards.setRowStretch(0, 1)
        cards.setRowStretch(1, 1)

        self.dictation_card, self.dictation_card_layout, self.dictation_media_panel, \
            self.dictation_icon, self.label_dictation_card_title, self.label_dictation_card_description, \
            self.label_dictation_hint, self.pushButton_record_audio = _create_feature_card(
                "01  /  МИКРОФОН", ICON_ROOT / "dict_text_monitor_round.png", "Диктовать",
                "Говорите в микрофон — текст появляется по мере распознавания. "
                "Подходит для заметок, идей и диктовки.",
                "МИКРОФОН · ТЕКСТ ПО МЕРЕ РЕЧИ", "Диктовать", "pushButton_record_audio",
                "Записать речь с микрофона и преобразовать её в текст",
            )
        cards.addWidget(self.dictation_card, 0, 0)

        self.file_card, self.file_card_layout, self.file_media_panel, self.file_icon, \
            self.label_file_card_title, self.label_file_card_description, self.label_file_formats, \
            self.pushButton_choose_file = _create_feature_card(
                "02  /  ФАЙЛЫ", ICON_ROOT / "transcribation_round.png", "Загрузить файл",
                "Загрузите аудио или видео. Очередь помогает обрабатывать несколько файлов, "
                "приостанавливать работу и продолжать позже.",
                "MP3 · WAV · M4A · MP4 · MOV · MKV", "Загрузить файл", "pushButton_choose_file",
                "Выбрать аудио- или видеофайл для распознавания",
            )
        cards.addWidget(self.file_card, 0, 1)

        self.ai_card, self.ai_card_layout, self.ai_media_panel, self.ai_icon, \
            self.label_ai_card_title, self.label_ai_card_description, self.label_ai_card_hint, \
            self.pushButton_ai_card = _create_feature_card(
                "03  /  ИНТЕЛЛЕКТ", ICON_ROOT / "ai_processing.png", "ИИ-обработка",
                "Создайте краткое содержание, конспект или протокол. "
                "Выбирайте локальную модель либо внешний API.",
                "ОФЛАЙН-РЕЖИМ · API ПО ВЫБОРУ", "Обработать текст", "pushButton_ai_card",
                "Открыть инструменты ИИ-обработки расшифровок",
            )
        cards.addWidget(self.ai_card, 1, 0)

        root.addLayout(cards, 1)
        self.speech_card, self.speech_card_layout, self.speech_media_panel, self.speech_icon, \
            self.label_speech_card_title, self.label_speech_card_description, self.label_speech_hint, \
            self.pushButton_speech = _create_feature_card(
                "04  /  ОЗВУЧКА", ICON_ROOT / "main_text_to_voice.png", "Озвучить текст",
                "Превратите текст в голос, выберите диктора и сохраните готовое аудио. "
                "Русские голоса работают без интернета.",
                "ТЕКСТ → WAV / MP3 · ИРИНА И РУСЛАН", "Озвучить текст", "pushButton_speech",
            )
        cards.addWidget(self.speech_card, 1, 1)

        footer = QHBoxLayout()
        footer.setSpacing(12)
        footer_copy = QVBoxLayout()
        footer_copy.setSpacing(2)
        footer_title = QLabel("Диктовка, транскрибация и интеллектуальная обработка текста.")
        self.footer_title = footer_title
        footer_title.setObjectName("footerTitle")
        footer_copy.addWidget(footer_title)
        footer.addLayout(footer_copy, 1)
        root.addLayout(footer)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.menubar.setVisible(False)  # No menu actions are defined; avoid an empty strip.
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        self.statusbar.showMessage("Готово к работе")
        MainWindow.setStatusBar(self.statusbar)

        self.pushButton_choose_file.setToolTip("Выбрать аудио- или видеофайл для распознавания")
        self.pushButton_record_audio.setToolTip("Записать речь с микрофона и преобразовать её в текст")
        self.pushButton_about_prog.setToolTip("Справка: информация о приложении и моделях распознавания")

    def update_responsive_icons(self, window_width: int, window_height: int = 900):
        # A 900 px high Windows work area is already tight for two card rows;
        # switch to the dense dashboard before Qt's layouts start clipping them.
        compact = window_width < 1000 or window_height < 980
        dense = window_height < 920
        icon_width = max(112, min(146 if compact else 160, int(window_width * 0.095)))
        media_width = max(132, min(176, icon_width + 24))
        horizontal = 14 if compact else 30
        vertical = 8 if dense else (12 if compact else 24)
        self.root_layout.setContentsMargins(horizontal, vertical, horizontal,
                                            8 if dense else (12 if compact else 22))
        self.root_layout.setSpacing(0)
        self.label_easy_fast_slogan.setFont(QFont("Segoe UI", 19 if dense else (22 if compact else 25), QFont.Weight.DemiBold))
        self.label_every_audio_to_text.setMaximumHeight(34 if dense else 44)
        self.label_what_u_want.setMaximumHeight(22)
        self.label_what_u_want.setVisible(not dense)
        self.footer_title.setVisible(not dense)
        self.hero_layout.setDirection(
            QHBoxLayout.Direction.TopToBottom if window_width < 860 else QHBoxLayout.Direction.LeftToRight
        )
        self.hero_layout.setSpacing(4 if compact else 18)
        self.voice_waveform.setFixedWidth(154)
        self.voice_waveform.setMinimumHeight(30 if dense else (42 if compact else 50))
        self.voice_waveform.setMaximumHeight(34 if dense else (48 if compact else 56))
        self.cards_layout.setSpacing(6 if compact else 16)
        for card_layout in (self.dictation_card_layout, self.file_card_layout,
                            self.ai_card_layout, self.speech_card_layout):
            card_layout.setContentsMargins(12 if compact else 18, 10 if dense else 16,
                                           12 if compact else 18, 10 if dense else 16)
            card_layout.setSpacing(10 if compact else 16)
        for media_panel in (self.dictation_media_panel, self.file_media_panel,
                            self.ai_media_panel, self.speech_media_panel):
            media_panel.setFixedWidth(media_width)
        for card in (self.dictation_card, self.file_card, self.ai_card, self.speech_card):
            card.setMinimumHeight(0)
        for button in (self.pushButton_record_audio, self.pushButton_choose_file,
                       self.pushButton_ai_card, self.pushButton_speech):
            button.setMinimumHeight(34 if dense else 40)
        self.dictation_icon.set_responsive_width(icon_width)
        self.file_icon.set_responsive_width(icon_width)
        self.ai_icon.set_responsive_width(icon_width)
        if hasattr(self, "speech_icon"):
            self.speech_icon.set_responsive_width(icon_width)

    def retranslateUi(self, MainWindow):
        pass
