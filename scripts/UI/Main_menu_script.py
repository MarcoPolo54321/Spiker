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
        self._target_width = 96
        self.setFixedSize(self._target_width, int(self._target_width * 0.84))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._svg = QSvgRenderer(str(image_path)) if str(image_path).lower().endswith(".svg") else None
        self._pixmap = QPixmap(str(image_path)) if self._svg is None else QPixmap()

    def set_responsive_width(self, width):
        width = max(78, min(128, int(width)))
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

        # Utility controls are stacked at the upper-right: local processing badge first,
        # then a compact row of settings/help/training shortcuts immediately below.
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
        self.voice_waveform = NeonVoiceWaveform()
        hero.addWidget(self.voice_waveform, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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

        # Card 1: Dictation, preserved functional objectName for existing signal connection.
        self.dictation_card = LiquidGlassCard()
        self.dictation_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        dict_layout = QVBoxLayout(self.dictation_card)
        self.dictation_card_layout = dict_layout
        dict_layout.setContentsMargins(20, 18, 20, 18)
        dict_layout.setSpacing(10)
        dict_eyebrow = QLabel("01  /  МИКРОФОН")
        dict_eyebrow.setObjectName("cardEyebrow")
        dict_eyebrow.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        dict_layout.addWidget(dict_eyebrow)
        dict_icon = IconGlass(ICON_ROOT / "dict_text_monitor_round.png")
        self.dictation_icon = dict_icon
        dict_layout.addWidget(dict_icon, 0, Qt.AlignmentFlag.AlignLeft)
        self.label_dictation_card_title = QLabel("Диктовать")
        self.label_dictation_card_title.setObjectName("compactCardTitle")
        self.label_dictation_card_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        dict_layout.addWidget(self.label_dictation_card_title)
        self.label_dictation_card_description = QLabel(
            "Говорите в микрофон — текст появляется по мере распознавания. "
            "Подходит для заметок, идей и диктовки."
        )
        self.label_dictation_card_description.setObjectName("cardDescription")
        self.label_dictation_card_description.setWordWrap(True)
        self.label_dictation_card_description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        dict_layout.addWidget(self.label_dictation_card_description)
        dict_layout.addStretch(1)
        self.label_dictation_hint = QLabel("МИКРОФОН · ТЕКСТ ПО МЕРЕ РЕЧИ")
        self.label_dictation_hint.setObjectName("formatLabel")
        self.label_dictation_hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        dict_layout.addWidget(self.label_dictation_hint)
        self.pushButton_record_audio = QPushButton("Диктовать")
        self.pushButton_record_audio.setObjectName("pushButton_record_audio")
        self.pushButton_record_audio.setProperty("role", "primary")
        self.pushButton_record_audio.setProperty("role", "navigation")
        self.pushButton_record_audio.setMinimumHeight(36)
        self.pushButton_record_audio.setCursor(Qt.CursorShape.PointingHandCursor)
        dict_layout.addWidget(self.pushButton_record_audio)
        cards.addWidget(self.dictation_card, 0, 0)

        # Card 2: File transcription, preserving its existing functional objectName.
        self.file_card = LiquidGlassCard()
        self.file_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        file_layout = QVBoxLayout(self.file_card)
        self.file_card_layout = file_layout
        file_layout.setContentsMargins(20, 18, 20, 18)
        file_layout.setSpacing(10)
        file_eyebrow = QLabel("02  /  ФАЙЛЫ")
        file_eyebrow.setObjectName("cardEyebrow")
        file_eyebrow.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        file_layout.addWidget(file_eyebrow)
        file_icon = IconGlass(ICON_ROOT / "transcribation_round.png")
        self.file_icon = file_icon
        file_layout.addWidget(file_icon, 0, Qt.AlignmentFlag.AlignLeft)
        self.label_file_card_title = QLabel("Загрузить файл")
        self.label_file_card_title.setObjectName("compactCardTitle")
        self.label_file_card_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        file_layout.addWidget(self.label_file_card_title)
        self.label_file_card_description = QLabel(
            "Загрузите аудио или видео. Очередь помогает обрабатывать несколько файлов, "
            "приостанавливать работу и продолжать позже."
        )
        self.label_file_card_description.setObjectName("cardDescription")
        self.label_file_card_description.setWordWrap(True)
        self.label_file_card_description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        file_layout.addWidget(self.label_file_card_description)
        file_layout.addStretch(1)
        self.label_file_formats = QLabel("MP3  ·  WAV  ·  M4A  ·  MP4  ·  MOV  ·  MKV")
        self.label_file_formats.setObjectName("formatLabel")
        self.label_file_formats.setWordWrap(True)
        self.label_file_formats.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        file_layout.addWidget(self.label_file_formats)
        self.pushButton_choose_file = QPushButton("Загрузить файл")
        self.pushButton_choose_file.setObjectName("pushButton_choose_file")
        self.pushButton_choose_file.setProperty("role", "navigation")
        self.pushButton_choose_file.setMinimumHeight(36)
        self.pushButton_choose_file.setCursor(Qt.CursorShape.PointingHandCursor)
        file_layout.addWidget(self.pushButton_choose_file)
        cards.addWidget(self.file_card, 0, 1)

        # Card 3: AI post-processing is a first-class workflow, not a hidden shortcut.
        self.ai_card = LiquidGlassCard()
        self.ai_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        ai_layout = QVBoxLayout(self.ai_card)
        self.ai_card_layout = ai_layout
        ai_layout.setContentsMargins(20, 18, 20, 18)
        ai_layout.setSpacing(10)
        ai_eyebrow = QLabel("03  /  ИНТЕЛЛЕКТ")
        ai_eyebrow.setObjectName("cardEyebrow")
        ai_eyebrow.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        ai_layout.addWidget(ai_eyebrow)
        self.ai_icon = IconGlass(ICON_ROOT / "ai_processing.png")
        ai_layout.addWidget(self.ai_icon, 0, Qt.AlignmentFlag.AlignLeft)
        self.label_ai_card_title = QLabel("ИИ-обработка")
        self.label_ai_card_title.setObjectName("compactCardTitle")
        self.label_ai_card_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        ai_layout.addWidget(self.label_ai_card_title)
        self.label_ai_card_description = QLabel(
            "Создайте краткое содержание, конспект или протокол. "
            "Выбирайте локальную модель либо внешний API."
        )
        self.label_ai_card_description.setObjectName("cardDescription")
        self.label_ai_card_description.setWordWrap(True)
        self.label_ai_card_description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        ai_layout.addWidget(self.label_ai_card_description)
        ai_layout.addStretch(1)
        self.label_ai_card_hint = QLabel("ОФЛАЙН-РЕЖИМ · API ПО ВЫБОРУ")
        self.label_ai_card_hint.setObjectName("formatLabel")
        self.label_ai_card_hint.setWordWrap(True)
        self.label_ai_card_hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        ai_layout.addWidget(self.label_ai_card_hint)
        self.pushButton_ai_card = QPushButton("Обработать текст")
        self.pushButton_ai_card.setObjectName("pushButton_ai_card")
        self.pushButton_ai_card.setProperty("role", "primary")
        self.pushButton_ai_card.setProperty("role", "navigation")
        self.pushButton_ai_card.setMinimumHeight(36)
        self.pushButton_ai_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pushButton_ai_card.setToolTip("Открыть инструменты ИИ-обработки расшифровок")
        ai_layout.addWidget(self.pushButton_ai_card)
        cards.addWidget(self.ai_card, 1, 0)

        root.addLayout(cards, 1)
        self.speech_card = LiquidGlassCard()
        self.speech_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        speech_layout = QVBoxLayout(self.speech_card)
        self.speech_card_layout = speech_layout
        speech_layout.setContentsMargins(20, 18, 20, 18)
        speech_layout.setSpacing(10)
        speech_eyebrow = QLabel("04  /  ОЗВУЧКА")
        speech_eyebrow.setObjectName("cardEyebrow")
        speech_eyebrow.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        speech_layout.addWidget(speech_eyebrow)
        self.speech_icon = IconGlass(ICON_ROOT / "main_text_to_voice.png")
        speech_layout.addWidget(self.speech_icon, 0, Qt.AlignmentFlag.AlignLeft)
        speech_heading = QLabel("Озвучить текст")
        speech_heading.setObjectName("compactCardTitle")
        speech_layout.addWidget(speech_heading)
        speech_description = QLabel(
            "Превратите текст в голос, выберите диктора и сохраните готовое аудио. "
            "Русские голоса работают без интернета."
        )
        speech_description.setObjectName("cardDescription")
        speech_description.setWordWrap(True)
        speech_layout.addWidget(speech_description)
        speech_layout.addStretch(1)
        self.label_speech_hint = QLabel("ТЕКСТ → WAV / MP3 · ИРИНА И РУСЛАН")
        self.label_speech_hint.setObjectName("formatLabel")
        self.label_speech_hint.setWordWrap(True)
        speech_layout.addWidget(self.label_speech_hint)
        self.pushButton_speech = QPushButton('Озвучить текст')
        self.pushButton_speech.setProperty('role', 'navigation')
        self.pushButton_speech.setMinimumHeight(36)
        speech_layout.addWidget(self.pushButton_speech)
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
        compact = window_width < 1000 or window_height < 820
        dense = window_height < 800
        icon_width = max(48, min(92 if compact else 106, int(window_width * (0.07 if compact else 0.085))))
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
        self.voice_waveform.setMinimumSize(88 if dense else (118 if compact else 174), 30 if dense else (42 if compact else 50))
        self.voice_waveform.setMinimumWidth(88 if dense else (118 if compact else 174))
        self.voice_waveform.setMaximumHeight(34 if dense else (48 if compact else 56))
        self.cards_layout.setSpacing(6 if compact else 16)
        for card_layout in (self.dictation_card_layout, self.file_card_layout,
                            self.ai_card_layout, self.speech_card_layout):
            card_layout.setContentsMargins(10 if compact else 20, 7 if dense else (10 if compact else 18),
                                           10 if compact else 20, 7 if dense else (10 if compact else 18))
            card_layout.setSpacing(3 if dense else (5 if compact else 10))
        for card in (self.dictation_card, self.file_card, self.ai_card, self.speech_card):
            card.setMinimumHeight(0)
        for button in (self.pushButton_record_audio, self.pushButton_choose_file,
                       self.pushButton_ai_card, self.pushButton_speech):
            button.setMinimumHeight(30 if dense else 36)
        self.dictation_icon.set_responsive_width(icon_width)
        self.file_icon.set_responsive_width(icon_width)
        self.ai_icon.set_responsive_width(icon_width)
        if hasattr(self, "speech_icon"):
            self.speech_icon.set_responsive_width(icon_width)

    def retranslateUi(self, MainWindow):
        pass
