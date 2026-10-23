# -*- coding: utf-8 -*-
"""Compact visual help for Spiker, based on the user's supplied illustrations."""
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QScrollArea, QWidget, QBoxLayout,
)

from app_paths import get_app_root

PROJECT_ROOT = get_app_root()
ICON_ROOT = PROJECT_ROOT / "icons"


class Ui_Dialog_info(object):
    def setupUi(self, Dialog_info):
        Dialog_info.setObjectName("Dialog_info")
        Dialog_info.resize(980, 740)
        Dialog_info.setMinimumSize(QSize(720, 600))
        Dialog_info.setWindowTitle("СПИКЕР — Справка")

        outer = QVBoxLayout(Dialog_info)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("helpScroll")
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("helpContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(2, 2, 8, 8)
        root.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("panel")
        header = QVBoxLayout(header_card)
        header.setContentsMargins(14, 10, 14, 12)
        header.setSpacing(4)
        nav = QHBoxLayout()
        self.pushButton_back_to_main = QPushButton("←  Назад")
        self.pushButton_back_to_main.setObjectName("pushButton_back_to_main")
        self.pushButton_back_to_main.setProperty("role", "back")
        self.pushButton_back_to_main.setMinimumHeight(32)
        nav.addWidget(self.pushButton_back_to_main, 0, Qt.AlignmentFlag.AlignLeft)
        nav.addStretch(1)
        header.addLayout(nav)

        self.label_main_label_info = QLabel("Справка СПИКЕР")
        self.label_main_label_info.setObjectName("helpTitle")
        self.label_main_label_info.setFont(QFont("Segoe UI", 20, QFont.Weight.DemiBold))
        header.addWidget(self.label_main_label_info)
        self.label_info_subtitle = QLabel("Четыре главных раздела — без лишних технических подробностей.")
        self.label_info_subtitle.setObjectName("mutedLabel")
        self.label_info_subtitle.setWordWrap(True)
        header.addWidget(self.label_info_subtitle)
        root.addWidget(header_card)

        self.cards_widget = QWidget()
        self.cards_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)

        cards = [
            (
                "Локальная обработка",
                "ИИ работает через Ollama на этом компьютере. Установите Ollama и скачайте модель заранее; после этого обработка текста доступна без облачного API.",
                ICON_ROOT / "help_local_processing.png",
            ),
            (
                "Диктовка блоками",
                "Речь обрабатывается небольшими фрагментами. Для более быстрой реакции в диктовке выбирайте модель распознавания, которая успевает за темпом речи.",
                ICON_ROOT / "help_dictation_blocks.png",
            ),
            (
                "Совместимость моделей",
                "Whisper распознаёт речь, а языковая модель (например, Qwen в Ollama) анализирует готовый текст. qwen3.8:27b занимает около 18 ГБ на диске и может быть тяжёлой для 16 ГБ RAM и 8–12 ГБ VRAM.",
                ICON_ROOT / "help_model_compatibility.png",
            ),
            (
                "Обработка расшифровок",
                "Откройте TXT или передайте текст из очереди. ИИ может исправить оформление, сделать резюме или конспект, подготовить протокол и извлечь задачи. Оригинал сохраняется отдельно.",
                ICON_ROOT / "help_transcript_processing.png",
            ),
        ]
        self.help_cards = []
        self._image_labels = []
        self._source_pixmaps = []
        for title, description, image_path in cards:
            card, image, pixmap = self._image_card(title, description, image_path)
            self.help_cards.append(card)
            self._image_labels.append(image)
            self._source_pixmaps.append(pixmap)
            self.cards_layout.addWidget(card, 1)
        root.addWidget(self.cards_widget)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.author_label = QLabel("Автор: Ивасик")
        self.author_label.setObjectName("helpAuthor")
        self.author_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(self.author_label)
        root.addLayout(footer)
        scroll.setWidget(content)

    def set_compact(self, compact: bool, viewport_width: int = 900):
        direction = QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        if self.cards_layout.direction() != direction:
            self.cards_layout.setDirection(direction)
        image_max = 132 if compact else min(190, max(145, int(viewport_width * 0.16)))
        image_width = min(420, max(170, int(viewport_width * (0.68 if compact else 0.22))))
        for label, pixmap in zip(self._image_labels, self._source_pixmaps):
            label.setMinimumHeight(112 if compact else 125)
            label.setMaximumHeight(image_max)
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(
                    QSize(image_width, image_max),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))

    def _image_card(self, title: str, description: str, image_path: Path):
        card = QFrame()
        card.setObjectName("helpImageCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 9, 10, 11)
        layout.setSpacing(6)

        image = QLabel()
        image.setObjectName("helpIllustration")
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setMinimumHeight(112)
        image.setMaximumHeight(170)
        image.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pixmap = QPixmap(str(image_path))
        if not pixmap.isNull():
            image.setPixmap(pixmap.scaled(
                QSize(220, 160), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        layout.addWidget(image)

        title_label = QLabel(title)
        title_label.setObjectName("helpCardTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        description_label = QLabel(description)
        description_label.setObjectName("helpCardDescription")
        description_label.setWordWrap(True)
        layout.addWidget(description_label, 1)
        return card, image, pixmap


class InfoMenu(QDialog):
    """Help view embedded in the application's tab stack."""

    def __init__(self, main_window):
        super().__init__()
        self.ui = Ui_Dialog_info()
        self.ui.setupUi(self)
        from UI.theme import apply_window_theme
        apply_window_theme(self)
        self.main_window = main_window
        self.setWindowTitle("СПИКЕР — Справка")
        self.ui.pushButton_back_to_main.clicked.connect(self.back_to_main)
        self.ui.set_compact(self.width() < 1100, self.width())

    def resizeEvent(self, event):
        self.ui.set_compact(self.width() < 1100, self.width())
        super().resizeEvent(event)

    def back_to_main(self):
        self.main_window.show_home_tab()
