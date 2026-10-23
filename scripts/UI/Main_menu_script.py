# -*- coding: utf-8 -*-
"""Deep Blue Liquid Glass start screen for Spiker."""
from pathlib import Path

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QPixmap, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget, QStatusBar, QMenuBar,
)

from app_paths import get_app_root

PROJECT_ROOT = get_app_root()
ICON_ROOT = PROJECT_ROOT / "icons"

# Centralized material settings: tweak these values to tune the glass effects.
MIDNIGHT_NAVY = "#061746"
ROYAL_BLUE = "#0B2F83"
ELECTRIC_BLUE = "#1265E8"
BRIGHT_BLUE = "#087BFF"
NEON_CYAN = "#16BFFF"
ICE_BLUE = "#72E8FF"
PERIWINKLE = "#A7BFFF"
WHITE = "#F5FAFF"
CARD_RADIUS = 30
CARD_BORDER_ALPHA = 82
CARD_HOVER_BORDER_ALPHA = 150


class LiquidGlassBackground(QWidget):
    """Paint an atmospheric, asymmetric navy-blue background with edge ribbons."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        bounds = self.rect()
        w, h = float(bounds.width()), float(bounds.height())

        base = QLinearGradient(QPointF(0, 0), QPointF(w, h))
        base.setColorAt(0.0, QColor(MIDNIGHT_NAVY))
        base.setColorAt(0.48, QColor("#08235F"))
        base.setColorAt(1.0, QColor("#07153D"))
        painter.fillRect(bounds, QBrush(base))

        # Soft, differently sized light fields: bright at upper right, restrained at center.
        lights = [
            (QPointF(w * 0.91, h * 0.09), w * 0.52, [(0.0, QColor(18, 101, 232, 96)), (0.32, QColor(8, 123, 255, 48)), (1.0, QColor(8, 123, 255, 0))]),
            (QPointF(w * 0.49, h * 0.49), w * 0.42, [(0.0, QColor(18, 101, 232, 30)), (0.42, QColor(18, 101, 232, 12)), (1.0, QColor(18, 101, 232, 0))]),
            (QPointF(w * 0.37, h * 1.02), w * 0.49, [(0.0, QColor(22, 191, 255, 28)), (0.35, QColor(18, 101, 232, 18)), (1.0, QColor(18, 101, 232, 0))]),
            (QPointF(w * 0.99, h * 0.71), w * 0.30, [(0.0, QColor(114, 232, 255, 22)), (0.40, QColor(22, 191, 255, 10)), (1.0, QColor(22, 191, 255, 0))]),
        ]
        for center, radius, stops in lights:
            gradient = QRadialGradient(center, radius)
            for stop, color in stops:
                gradient.setColorAt(stop, color)
            painter.fillRect(bounds, QBrush(gradient))

        # Left-edge liquid ribbon. Multiple strokes create distinct shadow, body and rim.
        left = QPainterPath()
        left.moveTo(w * 0.02, -h * 0.08)
        left.cubicTo(-w * 0.035, h * 0.14, w * 0.065, h * 0.25, w * 0.018, h * 0.41)
        left.cubicTo(-w * 0.018, h * 0.56, w * 0.052, h * 0.70, w * 0.012, h * 0.86)
        left.cubicTo(-w * 0.008, h * 0.98, w * 0.10, h * 1.03, w * 0.20, h * 1.08)
        painter.setPen(QPen(QColor(1, 8, 35, 110), max(32, w * 0.055), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(left)
        painter.setPen(QPen(QColor(18, 101, 232, 32), max(22, w * 0.036), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(left)
        painter.setPen(QPen(QColor(22, 191, 255, 24), max(9, w * 0.014), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(left)
        painter.setPen(QPen(QColor(114, 232, 255, 75), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(left)

        # Upper-right ribbon, kept near the edge so it never competes with the title.
        right = QPainterPath()
        right.moveTo(w * 1.08, -h * 0.03)
        right.cubicTo(w * 0.89, h * 0.04, w * 0.88, h * 0.15, w * 0.99, h * 0.24)
        right.cubicTo(w * 1.065, h * 0.31, w * 1.035, h * 0.42, w * 0.94, h * 0.49)
        painter.setPen(QPen(QColor(1, 7, 31, 95), max(28, w * 0.043), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(right)
        painter.setPen(QPen(QColor(18, 101, 232, 38), max(17, w * 0.026), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(right)
        painter.setPen(QPen(QColor(22, 191, 255, 35), max(5, w * 0.008), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(right)
        painter.setPen(QPen(QColor(167, 191, 255, 70), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(right)

        # A quiet lower-edge reflection adds depth without crossing the main cards' labels.
        lower = QPainterPath()
        lower.moveTo(w * 0.61, h * 1.05)
        lower.cubicTo(w * 0.75, h * 0.95, w * 0.88, h * 0.98, w * 1.05, h * 0.89)
        painter.setPen(QPen(QColor(0, 10, 44, 70), max(24, w * 0.03), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(lower)
        painter.setPen(QPen(QColor(22, 191, 255, 25), max(8, w * 0.010), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(lower)
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
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 13)
        shadow.setColor(QColor(0, 5, 25, 115))
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

        fill = QLinearGradient(QPointF(rect.left(), rect.top()), QPointF(rect.right(), rect.bottom()))
        fill.setColorAt(0.0, QColor(104, 169, 255, 43 if not self._hovered else 55))
        fill.setColorAt(0.35, QColor(31, 82, 175, 34 if not self._hovered else 44))
        fill.setColorAt(1.0, QColor(3, 19, 58, 93 if not self._hovered else 80))
        painter.fillPath(path, QBrush(fill))

        # Internal side reflection, masked to the glass contour.
        painter.save()
        painter.setClipPath(path)
        side = QLinearGradient(rect.left(), 0, rect.left() + rect.width() * 0.34, 0)
        side.setColorAt(0.0, QColor(114, 232, 255, 17 if not self._hovered else 27))
        side.setColorAt(1.0, QColor(114, 232, 255, 0))
        painter.fillRect(rect, QBrush(side))
        sheen = QLinearGradient(0, rect.top(), 0, rect.top() + rect.height() * 0.30)
        sheen.setColorAt(0.0, QColor(245, 250, 255, 25))
        sheen.setColorAt(0.26, QColor(167, 191, 255, 9))
        sheen.setColorAt(1.0, QColor(167, 191, 255, 0))
        painter.fillRect(rect, QBrush(sheen))
        painter.restore()

        border_alpha = CARD_HOVER_BORDER_ALPHA if self._hovered else CARD_BORDER_ALPHA
        painter.setPen(QPen(QColor(167, 191, 255, border_alpha), 1.1))
        painter.drawPath(path)

        # Bright upper-left rim with a calm fade toward the lower-right edge.
        rim = QPainterPath()
        rim.moveTo(rect.left() + radius, rect.top() + 1)
        rim.cubicTo(rect.left() + radius * 0.25, rect.top() + 1, rect.left() + 1, rect.top() + radius * 0.25, rect.left() + 1, rect.top() + radius)
        rim.lineTo(rect.left() + 1, rect.top() + rect.height() * 0.27)
        rim.moveTo(rect.left() + radius, rect.top() + 1)
        rim.lineTo(rect.right() - radius, rect.top() + 1)
        rim.cubicTo(rect.right() - radius * 0.30, rect.top() + 1, rect.right() - 1, rect.top() + radius * 0.30, rect.right() - 1, rect.top() + radius)
        rim_pen = QPen(QColor(114, 232, 255, 100 if self._hovered else 62), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(rim_pen)
        painter.drawPath(rim)
        painter.end()


class IconGlass(QWidget):
    """Display the supplied high-resolution liquid-glass artwork without adding a competing halo."""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self._target_width = 132
        self.setFixedSize(self._target_width, int(self._target_width * 0.84))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._pixmap = QPixmap(str(image_path))

    def set_responsive_width(self, width):
        width = max(112, min(176, int(width)))
        if width != self._target_width:
            self._target_width = width
            self.setFixedSize(width, int(width * 0.84))
            self.update()

    def paintEvent(self, event):
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        pixmap = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
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
        MainWindow.setMinimumSize(QSize(840, 620))
        MainWindow.setWindowTitle("СПИКЕР")

        self.centralwidget = LiquidGlassBackground(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        root = QVBoxLayout(self.centralwidget)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(0)

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
        self.label_local_badge = QLabel("ОБРАБОТКА НА УСТРОЙСТВЕ")
        self.label_local_badge.setObjectName("statusBadge")
        self.label_local_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.label_local_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.pushButton_settings = QPushButton()
        self.pushButton_settings.setObjectName("pushButton_settings")
        self.pushButton_settings.setToolTip("Настройки СПИКЕР")
        self.pushButton_settings.setAccessibleName("Настройки")
        self.pushButton_settings.setFixedSize(46, 46)
        self.pushButton_settings.setIcon(QIcon(str(ICON_ROOT / "settings_button.png")))
        self.pushButton_settings.setIconSize(QSize(43, 43))
        self.pushButton_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.pushButton_settings)

        self.pushButton_about_prog = QPushButton()
        self.pushButton_about_prog.setObjectName("pushButton_about_prog")
        self.pushButton_about_prog.setToolTip("Справка СПИКЕР")
        self.pushButton_about_prog.setAccessibleName("Справка")
        self.pushButton_about_prog.setFixedSize(46, 46)
        self.pushButton_about_prog.setIcon(QIcon(str(ICON_ROOT / "help_button.png")))
        self.pushButton_about_prog.setIconSize(QSize(43, 43))
        self.pushButton_about_prog.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.pushButton_about_prog)
        root.addLayout(header)

        root.addSpacing(24)
        self.label_easy_fast_slogan = QLabel("Голос в текст. Просто.")
        self.label_easy_fast_slogan.setObjectName("pageTitle")
        self.label_easy_fast_slogan.setFont(QFont("Segoe UI", 25, QFont.Weight.DemiBold))
        root.addWidget(self.label_easy_fast_slogan)
        self.label_every_audio_to_text = QLabel("Диктуйте, расшифровывайте аудио и обрабатывайте результат с помощью ИИ.")
        self.label_every_audio_to_text.setObjectName("pageSubtitle")
        self.label_every_audio_to_text.setWordWrap(True)
        root.addWidget(self.label_every_audio_to_text)

        root.addSpacing(20)
        self.label_what_u_want = QLabel("ВЫБЕРИТЕ ДЕЙСТВИЕ")
        self.label_what_u_want.setObjectName("sectionLabel")
        root.addWidget(self.label_what_u_want)
        root.addSpacing(9)

        cards = QHBoxLayout()
        cards.setSpacing(12)

        # Card 1: Dictation, preserved functional objectName for existing signal connection.
        self.dictation_card = LiquidGlassCard()
        self.dictation_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        dict_layout = QVBoxLayout(self.dictation_card)
        dict_layout.setContentsMargins(16, 16, 16, 16)
        dict_layout.setSpacing(8)
        dict_head = QHBoxLayout()
        dict_head.setSpacing(8)
        dict_icon = IconGlass(ICON_ROOT / "dict_text_monitor_round.png")
        self.dictation_icon = dict_icon
        dict_head.addWidget(dict_icon, 0, Qt.AlignmentFlag.AlignTop)
        dict_label_stack = QVBoxLayout()
        dict_label_stack.setSpacing(6)
        dict_eyebrow = QLabel("01  /  МИКРОФОН")
        dict_eyebrow.setObjectName("cardEyebrow")
        dict_label_stack.addWidget(dict_eyebrow)
        self.label_dictation_card_title = QLabel("Диктовать")
        self.label_dictation_card_title.setObjectName("compactCardTitle")
        dict_label_stack.addWidget(self.label_dictation_card_title)
        dict_head.addLayout(dict_label_stack, 1)
        dict_layout.addLayout(dict_head)
        self.label_dictation_card_description = QLabel(
            "Говорите в микрофон — текст появляется по мере распознавания. "
            "Подходит для заметок, идей и диктовки."
        )
        self.label_dictation_card_description.setObjectName("cardDescription")
        self.label_dictation_card_description.setWordWrap(True)
        dict_layout.addWidget(self.label_dictation_card_description)
        dict_layout.addStretch(1)
        self.label_dictation_hint = QLabel("МИКРОФОН · ТЕКСТ ПО МЕРЕ РЕЧИ")
        self.label_dictation_hint.setObjectName("formatLabel")
        dict_layout.addWidget(self.label_dictation_hint)
        self.pushButton_record_audio = QPushButton("Диктовать")
        self.pushButton_record_audio.setObjectName("pushButton_record_audio")
        self.pushButton_record_audio.setProperty("role", "primary")
        self.pushButton_record_audio.setMinimumHeight(42)
        self.pushButton_record_audio.setCursor(Qt.CursorShape.PointingHandCursor)
        dict_layout.addWidget(self.pushButton_record_audio)
        cards.addWidget(self.dictation_card, 1)

        # Card 2: File transcription, preserving its existing functional objectName.
        self.file_card = LiquidGlassCard()
        self.file_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        file_layout = QVBoxLayout(self.file_card)
        file_layout.setContentsMargins(16, 16, 16, 16)
        file_layout.setSpacing(8)
        file_head = QHBoxLayout()
        file_head.setSpacing(8)
        file_icon = IconGlass(ICON_ROOT / "transcribation_round.png")
        self.file_icon = file_icon
        file_head.addWidget(file_icon, 0, Qt.AlignmentFlag.AlignTop)
        file_label_stack = QVBoxLayout()
        file_label_stack.setSpacing(6)
        file_eyebrow = QLabel("02  /  ФАЙЛЫ")
        file_eyebrow.setObjectName("cardEyebrow")
        file_label_stack.addWidget(file_eyebrow)
        self.label_file_card_title = QLabel("Загрузить файл")
        self.label_file_card_title.setObjectName("compactCardTitle")
        file_label_stack.addWidget(self.label_file_card_title)
        file_head.addLayout(file_label_stack, 1)
        file_layout.addLayout(file_head)
        self.label_file_card_description = QLabel(
            "Загрузите аудио или видео. Очередь помогает обрабатывать несколько файлов, "
            "приостанавливать работу и продолжать позже."
        )
        self.label_file_card_description.setObjectName("cardDescription")
        self.label_file_card_description.setWordWrap(True)
        file_layout.addWidget(self.label_file_card_description)
        file_layout.addStretch(1)
        self.label_file_formats = QLabel("MP3  ·  WAV  ·  M4A  ·  MP4  ·  MOV  ·  MKV")
        self.label_file_formats.setObjectName("formatLabel")
        self.label_file_formats.setWordWrap(True)
        file_layout.addWidget(self.label_file_formats)
        self.pushButton_choose_file = QPushButton("Загрузить файл")
        self.pushButton_choose_file.setObjectName("pushButton_choose_file")
        self.pushButton_choose_file.setProperty("role", "secondary")
        self.pushButton_choose_file.setMinimumHeight(42)
        self.pushButton_choose_file.setCursor(Qt.CursorShape.PointingHandCursor)
        file_layout.addWidget(self.pushButton_choose_file)
        cards.addWidget(self.file_card, 1)

        # Card 3: AI post-processing is a first-class workflow, not a hidden shortcut.
        self.ai_card = LiquidGlassCard()
        self.ai_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        ai_layout = QVBoxLayout(self.ai_card)
        ai_layout.setContentsMargins(16, 16, 16, 16)
        ai_layout.setSpacing(8)
        ai_head = QHBoxLayout()
        ai_head.setSpacing(8)
        self.ai_icon = IconGlass(ICON_ROOT / "ai_processing.png")
        ai_head.addWidget(self.ai_icon, 0, Qt.AlignmentFlag.AlignTop)
        ai_label_stack = QVBoxLayout()
        ai_label_stack.setSpacing(5)
        ai_eyebrow = QLabel("03  /  ИНТЕЛЛЕКТ")
        ai_eyebrow.setObjectName("cardEyebrow")
        ai_label_stack.addWidget(ai_eyebrow)
        self.label_ai_card_title = QLabel("ИИ-обработка")
        self.label_ai_card_title.setObjectName("compactCardTitle")
        ai_label_stack.addWidget(self.label_ai_card_title)
        ai_head.addLayout(ai_label_stack, 1)
        ai_layout.addLayout(ai_head)
        self.label_ai_card_description = QLabel(
            "Создайте краткое содержание, конспект или протокол. "
            "Выбирайте локальную модель либо внешний API."
        )
        self.label_ai_card_description.setObjectName("cardDescription")
        self.label_ai_card_description.setWordWrap(True)
        ai_layout.addWidget(self.label_ai_card_description)
        ai_layout.addStretch(1)
        self.label_ai_card_hint = QLabel("ОФЛАЙН-РЕЖИМ · API ПО ВЫБОРУ")
        self.label_ai_card_hint.setObjectName("formatLabel")
        self.label_ai_card_hint.setWordWrap(True)
        ai_layout.addWidget(self.label_ai_card_hint)
        self.pushButton_ai_card = QPushButton("Обработать текст")
        self.pushButton_ai_card.setObjectName("pushButton_ai_card")
        self.pushButton_ai_card.setProperty("role", "primary")
        self.pushButton_ai_card.setMinimumHeight(42)
        self.pushButton_ai_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pushButton_ai_card.setToolTip("Открыть инструменты ИИ-обработки расшифровок")
        ai_layout.addWidget(self.pushButton_ai_card)
        cards.addWidget(self.ai_card, 1)

        root.addLayout(cards, 1)
        root.addSpacing(14)

        footer = QHBoxLayout()
        footer.setSpacing(12)
        footer_copy = QVBoxLayout()
        footer_copy.setSpacing(2)
        footer_title = QLabel("Диктовка, транскрибация и интеллектуальная обработка текста.")
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
        self.pushButton_about_prog.setToolTip("Информация о приложении и моделях распознавания")

    def update_responsive_icons(self, window_width: int):
        # Scale with the window, but keep enough horizontal room for card titles.
        # Three compact cards need smaller, equally weighted artwork to keep text readable.
        icon_width = max(72, min(106, int(window_width * 0.095)))
        self.dictation_icon.set_responsive_width(icon_width)
        self.file_icon.set_responsive_width(icon_width)
        self.ai_icon.set_responsive_width(icon_width)

    def retranslateUi(self, MainWindow):
        pass
