# -*- coding: utf-8 -*-
"""Settings page for Spiker. Scans real model files; never downloads models silently."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QFrame, QScrollArea, QSizePolicy, QSpacerItem,
    QCheckBox, QLineEdit, QFileDialog, QMessageBox,
)
from PySide6.QtGui import QDesktopServices

from app_config import load_settings, save_settings
from app_paths import get_user_data_root
from model_paths import local_models_dir, model_roots
from dictation_models import available_whisper_models, is_multilingual, is_whisper_model, pick_dictation_model
from UI.theme import apply_window_theme


class SettingsPage(QWidget):
    def __init__(self, project_root: Path, on_back, model_path_getter, model_path_setter, parent=None):
        super().__init__(parent)
        self.project_root = Path(project_root)
        self.models_root = local_models_dir(self.project_root)
        self.on_back = on_back
        self.model_path_getter = model_path_getter
        self.model_path_setter = model_path_setter
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
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent; border: none;")
        content = QWidget()
        content.setObjectName("settingsContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content.setAutoFillBackground(False)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 6, 0)
        content_layout.setSpacing(14)

        model_card = QFrame()
        model_card.setObjectName("panel")
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(20, 18, 20, 18)
        model_layout.setSpacing(12)

        model_title = QLabel("ДИКТОВКА")
        model_title.setObjectName("sectionLabel")
        model_layout.addWidget(model_title)
        model_description = QLabel(
            "В режиме «Авто» СПИКЕР использует потоковую модель T-one. Микрофон выбирается на странице диктовки."
        )
        model_description.setObjectName("cardDescription")
        model_description.setWordWrap(True)
        model_layout.addWidget(model_description)

        model_row = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("modelCombo")
        self.model_combo.setMinimumHeight(42)
        self.model_combo.setToolTip("Файл Whisper.cpp .bin для файловой транскрибации. Это не модель faster-whisper и не модель потоковой диктовки.")
        model_row.addWidget(self.model_combo, 1)
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setProperty("role", "secondary")
        self.refresh_button.setMinimumHeight(42)
        self.refresh_button.clicked.connect(self.refresh_models)
        model_row.addWidget(self.refresh_button)
        model_row_widget = QWidget()
        model_row_widget.setLayout(model_row)

        dictation_title = QLabel("Режим диктовки")
        dictation_title.setObjectName("sectionLabel")
        model_layout.addWidget(dictation_title)
        dictation_description = QLabel(
            "Авто сначала пробует T-one (потоковая диктовка на русском), затем Vosk (лёгкая потоковая модель), "
            "затем Whisper.cpp (распознаёт короткими фрагментами, с большей задержкой)."
        )
        dictation_description.setObjectName("mutedLabel")
        dictation_description.setWordWrap(True)
        model_layout.addWidget(dictation_description)
        self.dictation_engine_combo = QComboBox()
        self.dictation_engine_combo.setObjectName("modelCombo")
        self.dictation_engine_combo.setMinimumHeight(40)
        self.dictation_engine_combo.addItem("Авто (T-one → Vosk → Whisper)", "auto")
        self.dictation_engine_combo.addItem("Потоковый Sherpa-ONNX / T-one", "sherpa")
        self.dictation_engine_combo.addItem("Потоковый Vosk", "vosk")
        self.dictation_engine_combo.addItem("Whisper по коротким окнам", "whisper")
        model_layout.addWidget(self.dictation_engine_combo)
        self.dictation_model_combo = QComboBox()
        self.dictation_model_combo.setObjectName("modelCombo")
        self.dictation_model_combo.setMinimumHeight(42)
        self.dictation_model_combo.setToolTip("Резервный GGML/Whisper.cpp .bin. Для Sherpa/T-one или Vosk эта модель не используется.")
        model_layout.addWidget(self.dictation_model_combo)
        dictation_fallback_label = QLabel(
            "Эта модель нужна только для Whisper. Small — баланс точности и скорости, Base — легче и быстрее, "
            "Tiny — самый лёгкий вариант для слабых ПК. Base и Tiny чаще ошибаются в именах и на шумной записи."
        )
        dictation_fallback_label.setObjectName("mutedLabel")
        dictation_fallback_label.setWordWrap(True)

        self.model_details = QLabel("Проверяем папку models…")
        self.model_details.setObjectName("mutedLabel")
        self.model_details.setWordWrap(True)

        self.model_help = QLabel(
            "Как не перепутать модели:\n"
            "• Файл Whisper.cpp (.bin, например ggml-small.bin) — модель для обычной транскрибации файлов и резервной диктовки Whisper.\n"
            "• faster-whisper использует отдельную папку CTranslate2 с config.json. Обычный .bin сюда не подходит.\n"
            "• Потоковая диктовка Sherpa/T-one использует отдельную папку с model.onnx и tokens.txt.\n"
            "• Vosk также использует отдельную папку модели. ИИ-модель (Ollama/API) не распознаёт звук и не заменяет ни одну из этих моделей."
        )
        self.model_help.setObjectName("cardDescription")
        self.model_help.setWordWrap(True)
        model_advanced = QWidget()
        model_advanced_layout = QVBoxLayout(model_advanced)
        model_advanced_layout.setContentsMargins(0, 0, 0, 0)
        model_advanced_layout.addWidget(QLabel("Whisper.cpp для файлов (резервный движок)"))
        model_advanced_layout.addWidget(model_row_widget)
        model_advanced_layout.addWidget(self.model_details)
        model_advanced_layout.addWidget(self.model_help)
        model_advanced.hide()
        model_details_button = QPushButton("Резервные модели для файлов")
        model_details_button.setCheckable(True)
        model_details_button.toggled.connect(model_advanced.setVisible)
        model_layout.addWidget(model_details_button)
        model_layout.addWidget(model_advanced)
        self.dictation_engine_combo.currentIndexChanged.connect(
            lambda: self.dictation_model_combo.setVisible(self.dictation_engine_combo.currentData() == "whisper")
        )
        self.dictation_model_combo.hide()

        folder_row = QHBoxLayout()
        self.install_models_button = QPushButton("Установить / восстановить модели")
        self.install_models_button.setProperty("role", "primary")
        self.install_models_button.setToolTip(
            "Запускает мастер установки Whisper.cpp, faster-whisper, Sherpa/T-one и Vosk. "
            "Модель pyannote для участников устанавливается отдельным защищённым шагом."
        )
        self.install_models_button.clicked.connect(self.install_models)
        folder_row.addWidget(self.install_models_button)
        self.open_models_button = QPushButton("Открыть папку models")
        self.open_models_button.setProperty("role", "tertiary")
        self.open_models_button.clicked.connect(self.open_models_folder)
        folder_row.addWidget(self.open_models_button)
        folder_row.addStretch(1)
        model_layout.addLayout(folder_row)

        download_toggle = QPushButton("Где скачать модели")
        download_toggle.setProperty("role", "secondary")
        download_toggle.setCheckable(True)
        download_help = QLabel(
            '<b>Распознавание файлов.</b> Откройте '
            '<a style="color:#85dbff" href="https://huggingface.co/Systran/faster-whisper-medium">модели faster-whisper</a>. '
            'Скачайте всю папку модели CTranslate2. Поместите папку в <code>models/faster-whisper</code> '
            'и укажите её в «Дополнительных настройках» распознавания (модель: «Авто» в очереди).'
            '<br><br><b>Резервный Whisper.cpp.</b> Скачайте файл <code>ggml-*.bin</code> из '
            '<a style="color:#85dbff" href="https://huggingface.co/ggerganov/whisper.cpp">репозитория Whisper.cpp</a>, '
            'положите его в <code>models/whisper</code> и нажмите «Обновить» в списке резервных моделей.'
            '<br><br><b>ИИ и подготовка дикции.</b> Выберите совместимую с llama.cpp текстовую модель '
            '<a style="color:#85dbff" href="https://huggingface.co/models?library=gguf">в каталоге GGUF</a> '
            '(например, <a style="color:#85dbff" href="https://huggingface.co/Qwen/Qwen3-4B-GGUF">Qwen3‑4B</a>). '
            'Положите один файл <code>.gguf</code> в <code>models/llm</code> и снова откройте «ИИ» или «Озвучку». '
            'Выберите его в списке. Совместимость зависит от архитектуры модели и версии движка.'
        )
        download_help.setOpenExternalLinks(True)
        download_help.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        download_help.setWordWrap(True)
        download_help.hide()
        download_toggle.toggled.connect(download_help.setVisible)
        model_layout.addWidget(download_toggle)
        model_layout.addWidget(download_help)

        performance_card = QFrame()
        performance_card.setObjectName("panel")
        performance_layout = QVBoxLayout(performance_card)
        performance_layout.setContentsMargins(20, 18, 20, 18)
        performance_layout.setSpacing(12)
        performance_title = QLabel("РАСПОЗНАВАНИЕ ФАЙЛОВ")
        performance_title.setObjectName("sectionLabel")
        performance_layout.addWidget(performance_title)

        self.diagnostics_button = QPushButton("Проверить компьютер и подобрать режим")
        self.diagnostics_button.setProperty("role", "secondary")
        self.diagnostics_button.clicked.connect(self.run_diagnostics)
        performance_layout.addWidget(self.diagnostics_button)
        self.diagnostics_label = QLabel("Диагностика ещё не запускалась. Рекомендация не является гарантией скорости.")
        self.diagnostics_label.setObjectName("mutedLabel")
        self.diagnostics_label.setWordWrap(True)
        performance_layout.addWidget(self.diagnostics_label)
        self.effective_backend_label = QLabel("Фактический движок будет определён по установленным библиотекам и моделям.")
        self.effective_backend_label.setObjectName("cardDescription")
        self.effective_backend_label.setWordWrap(True)
        advanced = QWidget()
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(self.effective_backend_label)

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
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Авто: faster-whisper, иначе Whisper.cpp", "auto")
        self.engine_combo.addItem("faster-whisper (принудительно)", "faster-whisper")
        self.engine_combo.addItem("Whisper.cpp (резервный)", "whispercpp")
        self.performance_combo = QComboBox()
        self.performance_combo.addItem("Авто / рекомендации диагностики", "auto")
        self.performance_combo.addItem("Скорость", "speed")
        self.performance_combo.addItem("Сбалансировано", "balanced")
        self.performance_combo.addItem("Высокая точность", "quality")
        self.performance_combo.addItem("Ручная настройка", "manual")
        self.device_combo = QComboBox()
        self.device_combo.addItem("Автовыбор CPU / NVIDIA GPU", "auto")
        self.device_combo.addItem("Принудительно CPU", "cpu")
        self.device_combo.addItem("Принудительно NVIDIA GPU (CUDA)", "cuda")
        self.compute_combo = QComboBox()
        for label, value in (("Авто", "auto"), ("INT8", "int8"), ("FP16", "float16"),
                             ("INT8 + FP16", "int8_float16"), ("FP32", "float32")):
            self.compute_combo.addItem(label, value)
        self.faster_model_combo = QComboBox()
        self.faster_model_combo.setToolTip(
            "faster-whisper использует формат CTranslate2. Small быстрее и легче; Medium обычно точнее, но требует больше памяти."
        )
        for label, value in (("Быстро · Small", "small"), ("Баланс · Medium", "medium"),
                             ("Максимальная точность · Large-v3", "large-v3")):
            self.faster_model_combo.addItem(label, value)
        performance_layout.insertWidget(1, QLabel("Точность по умолчанию"))
        performance_layout.insertWidget(2, self.faster_model_combo)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 32)
        self.batch_spin.setSuffix(" аудиофрагм")
        self.batch_spin.setToolTip("Большой batch может ускорить GPU, но увеличивает потребление видеопамяти.")
        self.context_terms_edit = QLineEdit()
        self.context_terms_edit.setPlaceholderText("Имена, организации, термины через запятую")
        self.context_terms_edit.setToolTip("Контекстная подсказка для faster-whisper; не гарантирует точное написание.")
        self.faster_model_path_edit = QLineEdit()
        self.faster_model_path_edit.setPlaceholderText("models/faster-whisper/<имя> — локальная папка модели")
        self.browse_faster_model_button = QPushButton("Выбрать…")
        self.browse_faster_model_button.setProperty("role", "tertiary")
        self.browse_faster_model_button.clicked.connect(self.browse_faster_model)
        model_path_row = QHBoxLayout()
        model_path_row.addWidget(self.faster_model_path_edit, 1)
        model_path_row.addWidget(self.browse_faster_model_button)
        self.audio_profile_combo = QComboBox()
        self.audio_profile_combo.addItem("Речь — обычные записи", "speech")
        self.audio_profile_combo.addItem("Совещание — длинные разговоры", "meeting")
        self.audio_profile_combo.addItem("Музыка и пение — не отбрасывать вокал", "music")
        self.audio_profile_combo.addItem("Сохранить звук — без VAD и нормализации", "preserve")
        self.audio_profile_combo.setToolTip(
            "Для музыки VAD отключается автоматически, чтобы не удалять тихие вокальные фрагменты. "
            "Профиль «Сохранить звук» также отключает нормализацию."
        )
        self.audio_stream_spin = QSpinBox()
        self.audio_stream_spin.setRange(0, 31)
        self.audio_stream_spin.setToolTip("Номер аудиодорожки в видеофайле. 0 — первая дорожка.")
        self.vad_check = QCheckBox("Пропускать тишину (VAD)")
        self.word_timestamps_check = QCheckBox("Словесные временные метки")
        self.normalize_check = QCheckBox("Мягкая нормализация громкости")
        self.diarization_check = QCheckBox("Автоматически определять спикеров")
        self.show_speakers_check = QCheckBox("Показывать подписи спикеров в результате")
        self.speaker_min_spin = QSpinBox()
        self.speaker_min_spin.setRange(0, 20)
        self.speaker_min_spin.setSpecialValueText("Авто")
        self.speaker_max_spin = QSpinBox()
        self.speaker_max_spin.setRange(0, 20)
        self.speaker_max_spin.setSpecialValueText("Без ограничения")
        speaker_range = QHBoxLayout()
        speaker_range.addWidget(QLabel("Мин."))
        speaker_range.addWidget(self.speaker_min_spin)
        speaker_range.addWidget(QLabel("Макс."))
        speaker_range.addWidget(self.speaker_max_spin)
        speaker_range.addStretch(1)
        speaker_range_label = QLabel("По умолчанию ищем до двух участников, но оставляем запись с одним голосом одним спикером. Равные значения задают точное число; если голосов больше, увеличьте максимум здесь или укажите точное число в очереди.")
        speaker_range_label.setWordWrap(True)
        form.addRow("Движок распознавания", self.engine_combo)
        form.addRow("Профиль скорости / точности", self.performance_combo)
        form.addRow("Устройство", self.device_combo)
        form.addRow("Тип вычислений", self.compute_combo)
        form.addRow("Папка модели faster-whisper", model_path_row)
        form.addRow("Размер пакета", self.batch_spin)
        form.addRow("Потоки процессора", self.threads_spin)
        form.addRow("Язык речи", self.language_combo)
        form.addRow("Профиль аудио", self.audio_profile_combo)
        form.addRow("Аудиодорожка видео", self.audio_stream_spin)
        form.addRow("Контекстный словарь", self.context_terms_edit)
        advanced_layout.addLayout(form)
        options = QVBoxLayout()
        options.addWidget(self.vad_check)
        options.addWidget(self.word_timestamps_check)
        options.addWidget(self.normalize_check)
        options.addWidget(self.show_speakers_check)
        advanced_layout.addLayout(options)
        performance_layout.addWidget(self.diarization_check)

        note = QLabel(
            "Важно: профиль, модель faster-whisper, устройство CUDA/CPU, тип вычислений и batch влияют на "
            "файловую транскрибацию только тогда, когда реально запущен faster-whisper с локальной моделью CTranslate2. "
            "Если активен Whisper.cpp, он использует выбранный выше файл .bin и число потоков CPU; CUDA, FP16 и batch "
            "на него не действуют. Авто выбирает faster-whisper только при наличии библиотеки И папки модели, "
            "иначе использует Whisper.cpp. После ручных изменений нажмите «Сохранить настройки». "
            "Кнопка диагностики применяет и сохраняет рекомендации автоматически."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        advanced_layout.addWidget(note)

        model_compatibility = QLabel(
            "Модели faster-whisper должны быть заранее загружены и находиться в models/faster-whisper/<имя> "
            "либо быть выбраны через поле выше. Диаризация использует отдельную локальную модель "
            "pyannote/speaker-diarization-community-1 в models/pyannote/speaker-diarization-community-1. "
            "Условия доступа к модели pyannote нужно принять на Hugging Face заранее. Токен передаётся через "
            "переменную окружения HF_TOKEN и не сохраняется в настройках СПИКЕР. Смотрите docs/ADVANCED_TRANSCRIPTION.md."
        )
        model_compatibility.setObjectName("mutedLabel")
        model_compatibility.setWordWrap(True)
        advanced_layout.addWidget(model_compatibility)
        parallel_note = QLabel(
            "Параллельная работа файлов и диктовки использует отдельные контексты модели. Это повышает отзывчивость, "
            "но может почти удвоить потребление памяти при выборе Medium для обоих процессов. Для диктовки лучше Small, "
            "если он установлен."
        )
        parallel_note.setObjectName("mutedLabel")
        parallel_note.setWordWrap(True)
        advanced_layout.addWidget(parallel_note)
        advanced.hide()
        details = QPushButton("Дополнительные настройки")
        details.setCheckable(True)
        details.toggled.connect(advanced.setVisible)
        performance_layout.addWidget(details)
        performance_layout.addWidget(advanced)
        self._primary_cards = (performance_card, model_card)
        self._cards_grid = QGridLayout()
        self._cards_columns = 0
        content_layout.addLayout(self._cards_grid)
        self._layout_cards()

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
        author_label = QLabel("Автор: Ивасик")
        author_label.setObjectName("mutedLabel")
        author_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(author_label)
        content_layout.addItem(QSpacerItem(1, 4, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._populate_preferences()
        self.performance_combo.currentIndexChanged.connect(self._performance_preset_changed)
        self.model_combo.currentIndexChanged.connect(self._refresh_backend_status)
        self.engine_combo.currentIndexChanged.connect(self._refresh_backend_status)
        self.dictation_engine_combo.currentIndexChanged.connect(self._refresh_backend_status)
        self.faster_model_combo.currentIndexChanged.connect(self._refresh_backend_status)
        self.faster_model_path_edit.textChanged.connect(self._refresh_backend_status)
        self.refresh_models()
        # This page is created lazily after the main window theme is applied.
        # Apply the shared widget setup here too, especially for styled combo popups.
        apply_window_theme(self)

    def _layout_cards(self):
        width = self.width()
        columns = 2 if width >= 1040 else 1
        if columns == self._cards_columns:
            return
        self._cards_columns = columns
        for column in range(2):
            self._cards_grid.setColumnStretch(column, int(column < columns))
        for index, card in enumerate(self._primary_cards):
            self._cards_grid.addWidget(card, index // columns, index % columns, Qt.AlignmentFlag.AlignTop)

    def resizeEvent(self, event):
        if hasattr(self, "_cards_grid"):
            self._layout_cards()
        super().resizeEvent(event)

    def _populate_preferences(self):
        settings = load_settings(self.project_root)
        self.threads_spin.setValue(int(settings.get("threads", min(4, max(1, (os.cpu_count() or 4) - 1)))))
        for widget, key in (
            (self.engine_combo, "transcription_engine"), (self.performance_combo, "performance_mode"),
            (self.device_combo, "compute_device"), (self.compute_combo, "compute_type"),
            (self.faster_model_combo, "faster_whisper_model"),
        ):
            value = settings.get(key, "auto")
            if key == "faster_whisper_model" and value == "large-v3-turbo":
                value = "large-v3"
            idx = widget.findData(value)
            widget.setCurrentIndex(idx if idx >= 0 else 0)
        self.batch_spin.setValue(int(settings.get("batch_size", 1)))
        self.faster_model_path_edit.setText(settings.get("faster_whisper_model_path", ""))
        self.context_terms_edit.setText(settings.get("context_terms", ""))
        self.vad_check.setChecked(bool(settings.get("vad_filter", True)))
        profile_index = self.audio_profile_combo.findData(settings.get("audio_profile", "speech"))
        self.audio_profile_combo.setCurrentIndex(profile_index if profile_index >= 0 else 0)
        self.audio_stream_spin.setValue(int(settings.get("audio_stream_index", 0)))
        self.word_timestamps_check.setChecked(bool(settings.get("word_timestamps", True)))
        self.normalize_check.setChecked(bool(settings.get("audio_normalize", False)))
        self.diarization_check.setChecked(bool(settings.get("diarization_enabled", True)))
        self.show_speakers_check.setChecked(bool(settings.get("show_speakers", True)))
        self.speaker_min_spin.setValue(int(settings.get("speaker_min", 0)))
        self.speaker_max_spin.setValue(int(settings.get("speaker_max", 0)))
        language = settings.get("language", "ru")
        index = self.language_combo.findData(language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)

    def run_diagnostics(self):
        try:
            from transcription.hardware_diagnostics import diagnose_hardware
            report = diagnose_hardware()
            from transcription.faster_whisper_backend import is_faster_whisper_available, resolve_faster_model
            recommendation = str(report.recommended_model)
            if recommendation == "large-v3-turbo":
                recommendation = "large-v3"
            tiers = ("small", "medium", "large-v3")
            end = tiers.index(recommendation) if recommendation in tiers else 0
            model_override = self.faster_model_path_edit.text().strip()
            available = next(
                (tier for tier in reversed(tiers[:end + 1]) if resolve_faster_model(self.project_root, tier, model_override)),
                None,
            )
            for widget, value in (
                (self.device_combo, report.recommended_device),
                (self.compute_combo, report.recommended_compute_type),
                (self.faster_model_combo, available or recommendation),
            ):
                index = widget.findData(value)
                if index >= 0:
                    widget.setCurrentIndex(index)
            self.batch_spin.setValue(report.recommended_batch_size)
            self.threads_spin.setValue(max(1, min(report.cpu_threads, 8)))
            self.performance_combo.setCurrentIndex(max(0, self.performance_combo.findData("auto")))

            # The recommendation must affect an engine that is actually installed.
            # If the automatic CTranslate2 path is not ready, select the closest
            # available Whisper.cpp .bin model instead of changing only dormant controls.
            faster_ready = bool(available and is_faster_whisper_available())
            engine_choice = str(self.engine_combo.currentData() or "auto")
            if not faster_ready and engine_choice in {"auto", "whispercpp"}:
                self._select_whispercpp_model_for_recommendation(recommendation)

            ram = f"{report.ram_gb:.1f} ГБ всего" if report.ram_gb is not None else "не определена"
            if report.available_ram_gb is not None:
                ram += f" / свободно {report.available_ram_gb:.1f} ГБ"
            gpu = f"{report.gpu} · {report.gpu_vram_gb or '?'} ГБ VRAM"
            if report.gpu and report.gpu_vram_free_gb is not None:
                gpu += f" / свободно {report.gpu_vram_free_gb:.1f} ГБ"
            if report.gpu and report.gpu_utilization_percent is not None:
                gpu += f" / загрузка {report.gpu_utilization_percent:.0f}%"
            if not report.gpu:
                gpu = "не обнаружена"
            cuda = "CUDA доступна для CTranslate2" if report.cuda_runtime_ready else "CUDA для CTranslate2 недоступна"
            details = [
                f"CPU: {report.cpu} ({report.cpu_threads} потоков); ОЗУ: {ram}; GPU: {gpu}; {cuda}.",
                f"Рекомендация применена: {report.recommendation}; модель {model_override or available or 'резервная Whisper.cpp'}; "
                f"устройство {report.recommended_device.upper()} / {report.recommended_compute_type}; "
                f"batch {report.recommended_batch_size}; CPU-потоки {max(1, min(report.cpu_threads, 8))}.",
                *report.notes,
            ]
            self.diagnostics_label.setText("\n".join(details))
            self.save_preferences()
            if self.status_label.text().startswith("Не удалось сохранить"):
                self.diagnostics_label.setText(self.diagnostics_label.text() + "\nНе удалось сохранить рекомендации; проверьте права на папку data.")
            else:
                self.status_label.setText("Диагностика выполнена: параметры применены и сохранены для следующих задач.")
            self._refresh_backend_status()
        except Exception as exc:
            self.diagnostics_label.setText(f"Не удалось выполнить диагностику: {exc}")

    def _select_whispercpp_model_for_recommendation(self, recommended_model: str) -> bool:
        """Choose the closest installed .bin Whisper model for the active fallback backend."""
        if self.model_combo.count() == 0:
            return False
        target = str(recommended_model or "small").lower()
        preferred_tokens = {
            "small": ("small", "base", "tiny"),
            "medium": ("medium", "small", "base"),
            "large-v3-turbo": ("large-v3-turbo", "large", "medium", "small"),
            "large-v3": ("large-v3", "large", "medium", "small"),
        }.get(target, ("small", "medium", "base", "tiny"))
        available = [(index, str(self.model_combo.itemData(index) or "")) for index in range(self.model_combo.count())]
        for token in preferred_tokens:
            for index, path in available:
                if token in Path(path).name.lower():
                    self.model_combo.setCurrentIndex(index)
                    return True
        # Leave the current model untouched when filenames do not reveal their size.
        return bool(self.model_combo.currentData())

    def _refresh_backend_status(self, *_):
        """Show which concrete engines are available; avoid implying dormant settings are active."""
        try:
            from transcription.faster_whisper_backend import is_faster_whisper_available, resolve_faster_model
            faster_installed = is_faster_whisper_available()
            faster_path = resolve_faster_model(
                self.project_root,
                str(self.faster_model_combo.currentData() or "medium"),
                self.faster_model_path_edit.text().strip(),
            )
            faster_ready = bool(faster_installed and faster_path)
        except Exception:
            faster_installed, faster_path, faster_ready = False, None, False

        requested = str(self.engine_combo.currentData() or "auto")
        if requested == "faster-whisper":
            file_engine = "faster-whisper" if faster_ready else "faster-whisper принудительно выбран, но не готов"
        elif requested == "whispercpp":
            file_engine = "Whisper.cpp"
        else:
            file_engine = "faster-whisper" if faster_ready else "Whisper.cpp (резерв Авто)"
        whisper_file = self.model_combo.currentData()
        if file_engine.startswith("Whisper.cpp") and not whisper_file:
            file_engine += " — файл .bin не найден"

        sherpa_ready = False
        sherpa_model = None
        vosk_ready = False
        try:
            from transcription.live_streaming import is_sherpa_available, resolve_t_one_model
            sherpa_model = resolve_t_one_model(self.project_root)
            sherpa_ready = bool(sherpa_model and is_sherpa_available())
        except Exception:
            pass
        try:
            from model_paths import resolve_vosk_model_path
            from importlib.util import find_spec
            vosk_root = resolve_vosk_model_path(self.project_root)
            vosk_ready = bool(
                find_spec("vosk")
                and all((Path(vosk_root) / name).is_file() for name in
                        ("am/final.mdl", "graph/HCLr.fst", "graph/Gr.fst", "graph/phones/word_boundary.int"))
            )
        except Exception:
            pass
        live_choice = str(self.dictation_engine_combo.currentData() or "auto")
        if live_choice == "sherpa":
            live_engine = "Sherpa/T-one" if sherpa_ready else "Sherpa/T-one выбран, но библиотека или модель отсутствует"
        elif live_choice == "vosk":
            live_engine = "Vosk" if vosk_ready else "Vosk выбран, но библиотека или модель отсутствует"
        elif live_choice == "whisper":
            live_engine = "Whisper по коротким окнам"
        else:
            live_engine = "Sherpa/T-one" if sherpa_ready else ("Vosk" if vosk_ready else "Whisper по коротким окнам")

        diarization_enabled = self.diarization_check.isChecked()
        from transcription.onnx_diarization import available as onnx_diarization_ready
        onnx_ready = onnx_diarization_ready(self.project_root)
        try:
            from transcription.speaker_diarization import diarization_model_path, is_pyannote_available, is_diarization_model_complete
            pyannote_installed = is_pyannote_available(self.project_root)
            pyannote_model = is_diarization_model_complete(diarization_model_path(self.project_root))
        except Exception:
            pyannote_installed = pyannote_model = False
        if not diarization_enabled:
            diarization_status = "выключена в настройках"
        elif onnx_ready:
            diarization_status = "готова: локальные ONNX-модели разделения речи и голосовых признаков"
        elif pyannote_installed and pyannote_model:
            diarization_status = "pyannote и локальная модель найдены; диаризация работает локально"
        elif not pyannote_installed:
            diarization_status = "не готова: установите Install_Speaker_Diarization.bat"
        else:
            diarization_status = "не готова: нет локальной speaker-diarization-community-1"

        lines = [
            f"Файлы: {file_engine}.",
            f"Диктовка: {live_engine}.",
            f"Автоматические спикеры: {diarization_status}. Диаризация выполняется pyannote отдельно от ИИ-обработки.",
        ]
        if file_engine.startswith("faster-whisper"):
            lines.append(f"CTranslate2-модель: {faster_path if faster_path else 'не найдена'}.")
        elif file_engine.startswith("Whisper.cpp"):
            lines.append(
                f"Активный файл .bin: {Path(whisper_file).name if whisper_file else 'не выбран'}. "
                "CUDA / FP16 / batch для Whisper.cpp не используются."
            )
        if requested == "auto" and not faster_ready:
            if not faster_installed:
                lines.append("Чтобы настройки GPU, compute и batch реально влияли на файловое распознавание, установите faster-whisper.")
            else:
                lines.append("Библиотека faster-whisper есть, но локальная CTranslate2-модель выбранного размера не найдена; работает Whisper.cpp.")
        if live_engine.startswith("Whisper"):
            lines.append("Для минимальной задержки установите sherpa-onnx и модель T-one либо полноценную модель Vosk.")
        self.effective_backend_label.setText("\n".join(lines))

    def browse_faster_model(self):
        selected = QFileDialog.getExistingDirectory(
            self, "Выберите папку локальной модели faster-whisper",
            self.faster_model_path_edit.text().strip() or str(self.models_root / "faster-whisper"),
        )
        if selected:
            self.faster_model_path_edit.setText(selected)

    def _performance_preset_changed(self, *_):
        preset = self.performance_combo.currentData()
        presets = {
            "speed": ("small", 4, "int8"),
            "balanced": ("medium", 2, "auto"),
            "quality": ("large-v3", 1, "auto"),
        }
        if preset in presets:
            model, batch, compute = presets[preset]
            model_index = self.faster_model_combo.findData(model)
            if model_index >= 0:
                self.faster_model_combo.setCurrentIndex(model_index)
            compute_index = self.compute_combo.findData(compute)
            if compute_index >= 0:
                self.compute_combo.setCurrentIndex(compute_index)
            self.batch_spin.setValue(batch)
            requested = str(self.engine_combo.currentData() or "auto")
            if requested in {"auto", "whispercpp"}:
                self._select_whispercpp_model_for_recommendation(model)
            # Profiles are intended as one-click operational choices, not merely visual presets.
            # Save immediately so the next queue task uses the selected values.
            self.save_preferences()
        self._refresh_backend_status()

    def refresh_models(self):
        current_path = None
        try:
            current_path = self.model_path_getter()
        except Exception:
            current_path = None
        current_resolved = str(Path(current_path).resolve()) if current_path else None

        self.model_combo.clear()
        self.dictation_model_combo.clear()
        settings = load_settings(self.project_root)
        preferred_dictation = str(settings.get("dictation_model_path", "") or "")
        engine_index = self.dictation_engine_combo.findData(settings.get("dictation_engine", "auto"))
        self.dictation_engine_combo.setCurrentIndex(engine_index if engine_index >= 0 else 0)
        models = list(available_whisper_models(*model_roots(self.project_root)))
        auto_model = pick_dictation_model(models)
        self.dictation_model_combo.addItem(f"Автовыбор · {auto_model.name if auto_model else 'модель не найдена'}", "")
        for model_path in models:
            size_gb = model_path.stat().st_size / (1024 ** 3)
            origin = "папка программы" if model_path.is_relative_to(self.models_root) else "папка пользователя"
            label = f"{model_path.name}  ·  {size_gb:.2f} ГБ  ·  {origin}"
            self.model_combo.addItem(label, str(model_path))
            if current_resolved == str(model_path):
                self.model_combo.setCurrentIndex(self.model_combo.count() - 1)
            if is_multilingual(model_path):
                self.dictation_model_combo.addItem(label, str(model_path))
                if preferred_dictation and str(model_path) == str(Path(preferred_dictation).expanduser().resolve()):
                    self.dictation_model_combo.setCurrentIndex(self.dictation_model_combo.count() - 1)

        if current_resolved and is_whisper_model(current_resolved) and current_resolved not in [
            self.model_combo.itemData(i) for i in range(self.model_combo.count())
        ]:
            p = Path(current_resolved)
            size_gb = p.stat().st_size / (1024 ** 3)
            self.model_combo.addItem(f"{p.name}  ·  {size_gb:.2f} ГБ  ·  вне папки models", str(p))
            self.model_combo.setCurrentIndex(self.model_combo.count() - 1)

        if models:
            self.model_details.setText(
                f"Найдено моделей: {len(models)}. Активная модель отмечена в списке. "
                "Файлы меньше 10 МБ не показываются как полноценные модели Whisper. Потоковая T-one-модель "
                "размещается в models/sherpa-onnx/sherpa-onnx-streaming-t-one-russian-2025-09-08. "
                "Для её установки запустите Install_Live_Dictation.bat."
            )
        else:
            self.model_details.setText(
                "В папке models пока не найдено файлов .bin размером от 10 МБ. "
                "Скопируйте ggml-small.bin или ggml-medium.bin в models/whisper либо установите потоковую "
                "модель T-one через Install_Live_Dictation.bat."
            )
        self.status_label.setText(f"Папка моделей: {self.models_root}")
        self._refresh_backend_status()

    def install_models(self):
        """Launch the unified Windows model installer in its own console window."""
        installer = self.project_root / "Install_Models.bat"
        if not installer.is_file():
            QMessageBox.information(
                self, "Основные модели уже в программе",
                "В этой версии Windows основные модели речи установлены вместе с приложением. "
                "Для автоматического разделения на спикеров запустите Install_Speaker_Diarization.bat "
                "в папке СПИКЕР. Если файлы программы повреждены, переустановите СПИКЕР из Setup.exe.",
            )
            return
        if os.name != "nt":
            QMessageBox.information(
                self, "Установка моделей",
                "На Windows запустите Install_Models.bat из папки СПИКЕР. "
                "В текущей системе этот установщик рассчитан на Windows и Python 3.11 x64.",
            )
            return
        try:
            os.startfile(str(installer))
        except OSError:
            QMessageBox.warning(self, "Не удалось запустить установщик", "Запустите Install_Models.bat вручную из папки СПИКЕР.")

    def open_models_folder(self):
        try:
            self.models_root.mkdir(parents=True, exist_ok=True)
        except OSError:
            QMessageBox.warning(self, "Папка моделей", f"Нет доступа к папке: {self.models_root}")
            return
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
            settings["dictation_engine"] = str(self.dictation_engine_combo.currentData() or "auto")
            settings.update({
                "transcription_engine": str(self.engine_combo.currentData() or "auto"),
                "performance_mode": str(self.performance_combo.currentData() or "auto"),
                "compute_device": str(self.device_combo.currentData() or "auto"),
                "compute_type": str(self.compute_combo.currentData() or "auto"),
                "faster_whisper_model": str(self.faster_model_combo.currentData() or "medium"),
                "faster_whisper_model_path": self.faster_model_path_edit.text().strip(),
                "batch_size": self.batch_spin.value(),
                "vad_filter": self.vad_check.isChecked(),
                "word_timestamps": self.word_timestamps_check.isChecked(),
                "audio_normalize": self.normalize_check.isChecked(),
                "audio_profile": str(self.audio_profile_combo.currentData() or "speech"),
                "audio_stream_index": self.audio_stream_spin.value(),
                "diarization_enabled": self.diarization_check.isChecked(),
                "show_speakers": self.show_speakers_check.isChecked(),
                "speaker_min": self.speaker_min_spin.value(),
                "speaker_max": self.speaker_max_spin.value(),
                "context_terms": self.context_terms_edit.text().strip(),
            })
            save_settings(self.project_root, settings)
            model_name = Path(selected_model).name if selected_model else "не выбрана"
            dictation_name = Path(settings["dictation_model_path"]).name if settings["dictation_model_path"] else "автовыбор"
            self.status_label.setText(
                f"Настройки сохранены для следующих задач. Файлы: {model_name}; диктовка: {dictation_name}; "
                f"live-движок: {settings['dictation_engine']}; CPU-потоки: {settings['threads']}; "
                f"движок: {settings['transcription_engine']}; устройство: {settings['compute_device']}; "
                f"модель: {settings['faster_whisper_model']}."
            )
            self._refresh_backend_status()
        except Exception as exc:
            self.status_label.setText(f"Не удалось сохранить настройки: {exc}")

    def set_busy(self, busy: bool):
        """Prevent switching the model during active native inference."""
        self.model_combo.setEnabled(not busy)
        self.dictation_model_combo.setEnabled(not busy)
        self.dictation_engine_combo.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.open_models_button.setEnabled(not busy)
        self.install_models_button.setEnabled(not busy)
        self.threads_spin.setEnabled(not busy)
        self.language_combo.setEnabled(not busy)
        for widget in (
            self.engine_combo, self.performance_combo, self.device_combo, self.compute_combo,
            self.faster_model_combo, self.faster_model_path_edit, self.browse_faster_model_button,
            self.batch_spin, self.context_terms_edit, self.vad_check, self.audio_profile_combo,
            self.audio_stream_spin, self.word_timestamps_check,
            self.normalize_check, self.diarization_check, self.show_speakers_check,
            self.speaker_min_spin, self.speaker_max_spin, self.diagnostics_button,
        ):
            widget.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        if busy:
            self.status_label.setText("Параметры нельзя применять во время активной обработки.")
        else:
            self.status_label.setText(f"Папка моделей: {self.models_root}")
