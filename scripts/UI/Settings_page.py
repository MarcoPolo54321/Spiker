# -*- coding: utf-8 -*-
"""Settings page for Spiker. Scans real model files; never downloads models silently."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QFrame, QScrollArea, QSizePolicy, QSpacerItem,
)
from PySide6.QtGui import QDesktopServices

from app_config import load_settings, save_settings


class SettingsPage(QWidget):
    def __init__(self, project_root: Path, on_back, model_path_getter, model_path_setter, parent=None):
        super().__init__(parent)
        self.project_root = Path(project_root)
        self.models_root = self.project_root / "models"
        self.on_back = on_back
        self.model_path_getter = model_path_getter
        self.model_path_setter = model_path_setter
        self.models_root.mkdir(parents=True, exist_ok=True)
        (self.models_root / "whisper").mkdir(parents=True, exist_ok=True)
        self.setObjectName("settingsPage")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 24)
        outer.setSpacing(16)

        header = QHBoxLayout()
        self.back_button = QPushButton("←  Назад")
        self.back_button.setObjectName("pushButton_back_to_main")
        self.back_button.setProperty("role", "back")
        self.back_button.setMinimumHeight(40)
        self.back_button.clicked.connect(self.on_back)
        header.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignTop)

        header_copy = QVBoxLayout()
        header_copy.setSpacing(3)
        title = QLabel("Настройки")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("Модели, скорость распознавания и рабочие параметры.")
        subtitle.setObjectName("mutedLabel")
        header_copy.addWidget(title)
        header_copy.addWidget(subtitle)
        header.addLayout(header_copy, 1)
        outer.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 6, 0)
        content_layout.setSpacing(14)

        model_card = QFrame()
        model_card.setObjectName("panel")
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(20, 18, 20, 18)
        model_layout.setSpacing(12)

        model_title = QLabel("МОДЕЛЬ РАСПОЗНАВАНИЯ")
        model_title.setObjectName("sectionLabel")
        model_layout.addWidget(model_title)
        model_description = QLabel(
            "СПИКЕР не скачивает модели автоматически. Поместите файлы Whisper .bin в папку models "
            "или в её подпапку — список ниже обновляется по реальным файлам."
        )
        model_description.setObjectName("cardDescription")
        model_description.setWordWrap(True)
        model_layout.addWidget(model_description)

        model_row = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("modelCombo")
        self.model_combo.setMinimumHeight(42)
        model_row.addWidget(self.model_combo, 1)
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setProperty("role", "secondary")
        self.refresh_button.setMinimumHeight(42)
        self.refresh_button.clicked.connect(self.refresh_models)
        model_row.addWidget(self.refresh_button)
        model_layout.addLayout(model_row)

        dictation_title = QLabel("МОДЕЛЬ ДЛЯ ДИКТОВКИ В РЕАЛЬНОМ ВРЕМЕНИ")
        dictation_title.setObjectName("sectionLabel")
        model_layout.addWidget(dictation_title)
        dictation_description = QLabel(
            "Для быстрых пятисекундных фрагментов можно выбрать Small/Base/Tiny. "
            "Пустой выбор означает авто-подбор: сначала Small/Base/Tiny, иначе активная модель файлов."
        )
        dictation_description.setObjectName("mutedLabel")
        dictation_description.setWordWrap(True)
        model_layout.addWidget(dictation_description)
        self.dictation_model_combo = QComboBox()
        self.dictation_model_combo.setObjectName("modelCombo")
        self.dictation_model_combo.setMinimumHeight(42)
        model_layout.addWidget(self.dictation_model_combo)

        self.model_details = QLabel("Проверяем папку models…")
        self.model_details.setObjectName("mutedLabel")
        self.model_details.setWordWrap(True)
        model_layout.addWidget(self.model_details)

        folder_row = QHBoxLayout()
        self.open_models_button = QPushButton("Открыть папку models")
        self.open_models_button.setProperty("role", "tertiary")
        self.open_models_button.clicked.connect(self.open_models_folder)
        folder_row.addWidget(self.open_models_button)
        folder_row.addStretch(1)
        model_layout.addLayout(folder_row)
        content_layout.addWidget(model_card)

        performance_card = QFrame()
        performance_card.setObjectName("panel")
        performance_layout = QVBoxLayout(performance_card)
        performance_layout.setContentsMargins(20, 18, 20, 18)
        performance_layout.setSpacing(12)
        performance_title = QLabel("ПРОИЗВОДИТЕЛЬНОСТЬ")
        performance_title.setObjectName("sectionLabel")
        performance_layout.addWidget(performance_title)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, max(1, os.cpu_count() or 4))
        self.threads_spin.setSuffix(" потоков CPU")
        self.threads_spin.setToolTip("Больше потоков не всегда означает более высокую скорость.")
        self.language_combo = QComboBox()
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.addItem("Английский", "en")
        self.language_combo.addItem("Автоопределение", "auto")
        form.addRow("Потоки процессора", self.threads_spin)
        form.addRow("Язык речи", self.language_combo)
        performance_layout.addLayout(form)

        note = QLabel(
            "Количество CPU-потоков — число потоков вычислений внутри Whisper, а не количество файлов. "
            "Начните с 3–4 потоков; на слабом компьютере попробуйте 2. Слишком много потоков может замедлить "
            "систему из-за конкуренции за CPU и память. Скорость также зависит от длительности файла, кодека, "
            "модели и доступности GPU (эта сборка использует CPU)."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        performance_layout.addWidget(note)

        model_compatibility = QLabel(
            "Форматы моделей: сейчас поддерживаются локальные модели Whisper.cpp в GGML/GGUF-совместимом "
            "формате, который понимает установленный pywhispercpp. Просто положить сюда модель другой системы "
            "(например CTranslate2/faster-whisper, ONNX или произвольный .bin) недостаточно — для неё нужен "
            "отдельный backend/адаптер. Список .bin показывает кандидатов по расширению и размеру, но не гарантирует совместимость."
        )
        model_compatibility.setObjectName("mutedLabel")
        model_compatibility.setWordWrap(True)
        performance_layout.addWidget(model_compatibility)
        parallel_note = QLabel(
            "Параллельная работа файлов и диктовки использует отдельные контексты модели. Это повышает отзывчивость, "
            "но может почти удвоить потребление памяти при выборе Medium для обоих процессов. Для диктовки лучше Small, "
            "если он установлен."
        )
        parallel_note.setObjectName("mutedLabel")
        parallel_note.setWordWrap(True)
        performance_layout.addWidget(parallel_note)
        content_layout.addWidget(performance_card)

        footer = QHBoxLayout()
        self.status_label = QLabel("Изменения ещё не сохранены.")
        self.status_label.setObjectName("mutedLabel")
        footer.addWidget(self.status_label, 1)
        self.save_button = QPushButton("Сохранить настройки")
        self.save_button.setProperty("role", "primary")
        self.save_button.setMinimumHeight(44)
        self.save_button.clicked.connect(self.save_preferences)
        footer.addWidget(self.save_button)
        content_layout.addLayout(footer)
        content_layout.addItem(QSpacerItem(1, 4, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._populate_preferences()
        self.refresh_models()

    def _populate_preferences(self):
        settings = load_settings(self.project_root)
        self.threads_spin.setValue(int(settings.get("threads", min(4, max(1, (os.cpu_count() or 4) - 1)))))
        language = settings.get("language", "ru")
        index = self.language_combo.findData(language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)

    def refresh_models(self):
        current_path = None
        try:
            current_path = self.model_path_getter()
        except Exception:
            current_path = None
        current_resolved = str(Path(current_path).resolve()) if current_path else None

        self.model_combo.clear()
        self.dictation_model_combo.clear()
        self.dictation_model_combo.addItem("Автовыбор быстрой модели (Small/Base/Tiny)", "")
        settings = load_settings(self.project_root)
        preferred_dictation = str(settings.get("dictation_model_path", "") or "")
        models = []
        if self.models_root.exists():
            for path in self.models_root.rglob("*.bin"):
                try:
                    if path.is_file() and path.stat().st_size >= 10 * 1024 * 1024:
                        models.append(path.resolve())
                except OSError:
                    continue
        models.sort(key=lambda p: (p.name.lower(), str(p).lower()))
        for model_path in models:
            size_gb = model_path.stat().st_size / (1024 ** 3)
            relative = model_path.relative_to(self.models_root.resolve())
            label = f"{model_path.name}  ·  {size_gb:.2f} ГБ  ·  {relative.parent.as_posix()}"
            self.model_combo.addItem(label, str(model_path))
            if current_resolved == str(model_path):
                self.model_combo.setCurrentIndex(self.model_combo.count() - 1)
            self.dictation_model_combo.addItem(label, str(model_path))
            if preferred_dictation and str(model_path) == str(Path(preferred_dictation).expanduser().resolve()):
                self.dictation_model_combo.setCurrentIndex(self.dictation_model_combo.count() - 1)

        if current_resolved and Path(current_resolved).is_file() and current_resolved not in [
            self.model_combo.itemData(i) for i in range(self.model_combo.count())
        ]:
            p = Path(current_resolved)
            size_gb = p.stat().st_size / (1024 ** 3)
            self.model_combo.addItem(f"{p.name}  ·  {size_gb:.2f} ГБ  ·  вне папки models", str(p))
            self.model_combo.setCurrentIndex(self.model_combo.count() - 1)

        if models:
            self.model_details.setText(
                f"Найдено моделей: {len(models)}. Активная модель отмечена в списке. "
                "Файлы меньше 10 МБ не показываются как полноценные модели Whisper."
            )
        else:
            self.model_details.setText(
                "В папке models пока не найдено файлов .bin размером от 10 МБ. "
                "Скопируйте ggml-small.bin или ggml-medium.bin в models/whisper и нажмите «Обновить»."
            )
        self.status_label.setText(f"Папка моделей: {self.models_root}")

    def open_models_folder(self):
        self.models_root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.models_root.resolve())))

    def save_preferences(self):
        selected_model = self.model_combo.currentData()
        try:
            if selected_model:
                self.model_path_setter(selected_model)
            settings = load_settings(self.project_root)
            settings["threads"] = int(self.threads_spin.value())
            settings["language"] = str(self.language_combo.currentData() or "ru")
            settings["dictation_model_path"] = str(self.dictation_model_combo.currentData() or "")
            save_settings(self.project_root, settings)
            model_name = Path(selected_model).name if selected_model else "не выбрана"
            dictation_name = Path(settings["dictation_model_path"]).name if settings["dictation_model_path"] else "автовыбор"
            self.status_label.setText(
                f"Настройки сохранены. Файлы: {model_name}; диктовка: {dictation_name}; "
                f"CPU-потоки: {settings['threads']}."
            )
        except Exception as exc:
            self.status_label.setText(f"Не удалось сохранить настройки: {exc}")

    def set_busy(self, busy: bool):
        """Prevent switching the model during active native inference."""
        self.model_combo.setEnabled(not busy)
        self.dictation_model_combo.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.open_models_button.setEnabled(not busy)
        self.threads_spin.setEnabled(not busy)
        self.language_combo.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        if busy:
            self.status_label.setText("Параметры нельзя применять во время активной обработки.")
        else:
            self.status_label.setText(f"Папка моделей: {self.models_root}")
