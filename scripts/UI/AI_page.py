# -*- coding: utf-8
"""AI post-processing page: local Ollama first, optional OpenAI-compatible API."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTextEdit, QFrame, QProgressBar, QFileDialog,
    QMessageBox, QSplitter,
)

from app_config import load_settings, save_settings
from ai_provider import process_transcript, probe_provider

LOGGER = logging.getLogger("app.ai")


class AIWorker(QThread):
    progress = Signal(int, str)
    output_ready = Signal(str)
    models_ready = Signal(list)
    error = Signal(str)
    probe_done = Signal(str)

    def __init__(self, mode: str, config: dict, job: dict | None = None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.config = dict(config)
        self.job = dict(job or {})

    def run(self):
        try:
            provider = self.config.get("provider", "local")
            base_url = self.config.get("base_url", "http://127.0.0.1:11434/v1")
            api_key = self.config.get("api_key", "")
            if self.mode == "probe":
                models = probe_provider(provider, base_url, api_key)
                self.models_ready.emit(models)
                self.probe_done.emit("Подключение проверено. " + (f"Найдено моделей: {len(models)}." if models else "Сервер доступен, но список моделей пуст или недоступен."))
                return
            text = process_transcript(
                provider=provider,
                base_url=base_url,
                model=str(self.config.get("model", "")).strip(),
                api_key=api_key,
                task=str(self.job.get("task", "summary")),
                source_text=str(self.job.get("source_text", "")),
                custom_instruction=str(self.job.get("custom_instruction", "")),
                progress=lambda percent, message: self.progress.emit(percent, message),
                cancelled=self.isInterruptionRequested,
            )
            if self.isInterruptionRequested():
                self.error.emit("Обработка отменена.")
            else:
                self.output_ready.emit(text)
        except InterruptedError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            LOGGER.exception("AI provider operation failed")
            self.error.emit(str(exc))


class AIProcessingPage(QWidget):
    """AI workspace connected to transcription results but usable with pasted text too."""

    def __init__(self, project_root: Path, on_back=None, parent=None):
        super().__init__(parent)
        self.project_root = Path(project_root)
        self.on_back = on_back
        self.results_dir = self.project_root / "results" / "ai"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.source_name = ""
        self._worker: AIWorker | None = None
        self._last_result = ""
        self._last_task = "summary"
        self._last_provider = "local"
        self.setObjectName("aiProcessingPage")
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        back = QPushButton("←  Назад")
        back.setProperty("role", "back")
        back.setMinimumHeight(34)
        back.clicked.connect(self.on_back or (lambda: None))
        header.addWidget(back, 0, Qt.AlignmentFlag.AlignTop)
        title_stack = QVBoxLayout()
        title = QLabel("ИИ-обработка")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("Анализируйте расшифровку локально или через выбранный API. Оригинал не перезаписывается.")
        subtitle.setObjectName("mutedLabel")
        subtitle.setWordWrap(True)
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack, 1)
        root.addLayout(header)

        provider_card = QFrame()
        provider_card.setObjectName("panel")
        pv = QVBoxLayout(provider_card)
        pv.setContentsMargins(12, 9, 12, 9)
        pv.setSpacing(6)
        section = QLabel("ПРОВАЙДЕР И МОДЕЛЬ")
        section.setObjectName("sectionLabel")
        pv.addWidget(section)

        # Provider and model share one row; this keeps the AI workspace usable in a 720px-tall window.
        choices_row = QHBoxLayout()
        choices_row.setSpacing(12)
        provider_column = QVBoxLayout()
        provider_column.setSpacing(3)
        provider_label = QLabel("Провайдер")
        provider_label.setObjectName("aiFieldLabel")
        provider_column.addWidget(provider_label)
        self.provider_combo = QComboBox()
        self.provider_combo.setObjectName("aiProviderCombo")
        self.provider_combo.addItem("Локальный ИИ · Ollama (офлайн)", "local")
        self.provider_combo.addItem("Внешний API · OpenAI-совместимый", "api")
        self.provider_combo.setMinimumHeight(34)
        provider_column.addWidget(self.provider_combo)
        choices_row.addLayout(provider_column, 1)

        model_column = QVBoxLayout()
        model_column.setSpacing(3)
        model_label = QLabel("Модель")
        model_label.setObjectName("aiFieldLabel")
        model_column.addWidget(model_label)
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("aiModelCombo")
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumHeight(34)
        self.model_combo.setToolTip("Выберите установленную модель или введите её точный тег Ollama. Для qwen3.8:27b см. предупреждение о памяти.")
        self.model_combo.addItems(["qwen3.5:4b", "qwen3.5:9b", "qwen3.8:27b", "qwen3:8b", "llama3.1:8b"])
        self.model_combo.setToolTip(
            "Выберите установленную модель Ollama или введите её точный тег. "
            "qwen3.8:27b занимает около 18 ГБ на диске и может требовать больше оперативной памяти, чем доступно на этом компьютере."
        )
        for i in range(self.model_combo.count()):
            tag = self.model_combo.itemText(i)
            if tag == "qwen3.8:27b":
                self.model_combo.setItemData(
                    i,
                    "Около 18 ГБ на диске. При 16 ГБ RAM и 8–12 ГБ VRAM возможна нехватка памяти или медленная работа.",
                    Qt.ItemDataRole.ToolTipRole,
                )
        model_column.addWidget(self.model_combo)
        choices_row.addLayout(model_column, 1)
        pv.addLayout(choices_row)

        address_row = QHBoxLayout()
        address_row.setSpacing(10)
        address_label = QLabel("Адрес сервера")
        address_label.setObjectName("aiFieldLabel")
        address_label.setMinimumWidth(92)
        address_row.addWidget(address_label)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setObjectName("aiBaseUrlEdit")
        self.base_url_edit.setPlaceholderText("http://127.0.0.1:11434/v1")
        self.base_url_edit.setMinimumHeight(32)
        address_row.addWidget(self.base_url_edit, 1)
        pv.addLayout(address_row)

        self.api_key_row_widget = QWidget()
        key_row = QHBoxLayout(self.api_key_row_widget)
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.setSpacing(10)
        self.api_key_label = QLabel("API-ключ")
        self.api_key_label.setObjectName("aiFieldLabel")
        self.api_key_label.setMinimumWidth(92)
        key_row.addWidget(self.api_key_label)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setObjectName("aiApiKeyEdit")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Ключ хранится в системном хранилище, если доступно")
        self.api_key_edit.setToolTip("Ключ не записывается в settings.json. Он сохраняется через системное хранилище, если оно доступно.")
        self.api_key_edit.setMinimumHeight(32)
        key_row.addWidget(self.api_key_edit, 1)
        pv.addWidget(self.api_key_row_widget)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.probe_button = QPushButton("Проверить подключение / обновить модели")
        self.probe_button.setObjectName("aiProbeButton")
        self.probe_button.setProperty("role", "secondary")
        self.probe_button.setMinimumHeight(34)
        self.probe_button.clicked.connect(self.probe_connection)
        buttons.addWidget(self.probe_button, 1)
        self.save_settings_button = QPushButton("Сохранить настройки")
        self.save_settings_button.setObjectName("aiSaveButton")
        self.save_settings_button.setProperty("role", "tertiary")
        self.save_settings_button.setMinimumHeight(34)
        self.save_settings_button.clicked.connect(self.save_ai_settings)
        buttons.addWidget(self.save_settings_button, 1)
        pv.addLayout(buttons)
        self.provider_note = QLabel("Локальный режим обращается к Ollama на этом компьютере. Для офлайн-работы заранее установите Ollama и скачайте модель.")
        self.provider_note.setObjectName("mutedLabel")
        self.provider_note.setWordWrap(True)
        self.provider_note.setMaximumHeight(34)
        pv.addWidget(self.provider_note)
        root.addWidget(provider_card)


        split = QSplitter(Qt.Orientation.Horizontal)
        source_panel = QFrame()
        source_panel.setObjectName("panel")
        sv = QVBoxLayout(source_panel)
        sv.setContentsMargins(14, 12, 14, 12)
        source_header = QHBoxLayout()
        source_label = QLabel("ИСХОДНАЯ РАСШИФРОВКА")
        source_label.setObjectName("sectionLabel")
        source_header.addWidget(source_label)
        source_header.addStretch(1)
        self.open_text_button = QPushButton("Открыть TXT…")
        self.open_text_button.setProperty("role", "tertiary")
        self.open_text_button.clicked.connect(self.load_text_file)
        source_header.addWidget(self.open_text_button)
        sv.addLayout(source_header)
        self.source_editor = QTextEdit()
        self.source_editor.setObjectName("aiSourceEditor")
        self.source_editor.setMinimumHeight(150)
        self.source_editor.setPlaceholderText("Выберите готовую задачу в очереди и нажмите «Обработать с ИИ» или вставьте сюда текст. Длинные расшифровки обрабатываются фрагментами.")
        sv.addWidget(self.source_editor, 1)
        self.source_info = QLabel("Источник не выбран. Вставьте текст или импортируйте TXT.")
        self.source_info.setObjectName("mutedLabel")
        self.source_info.setWordWrap(True)
        sv.addWidget(self.source_info)
        split.addWidget(source_panel)

        output_panel = QFrame()
        output_panel.setObjectName("panel")
        ov = QVBoxLayout(output_panel)
        ov.setContentsMargins(14, 12, 14, 12)
        output_header = QHBoxLayout()
        result_label = QLabel("РЕЗУЛЬТАТ ИИ")
        result_label.setObjectName("sectionLabel")
        output_header.addWidget(result_label)
        output_header.addStretch(1)
        self.export_button = QPushButton("Экспорт результата…")
        self.export_button.setProperty("role", "secondary")
        self.export_button.clicked.connect(self.export_result)
        output_header.addWidget(self.export_button)
        ov.addLayout(output_header)
        self.output_editor = QTextEdit()
        self.output_editor.setObjectName("aiOutputEditor")
        self.output_editor.setMinimumHeight(150)
        self.output_editor.setPlaceholderText("Здесь появится результат. Его можно отредактировать и сохранить отдельно от оригинала.")
        ov.addWidget(self.output_editor, 1)
        split.addWidget(output_panel)
        split.setSizes([500, 500])
        split.setChildrenCollapsible(False)
        split.setHandleWidth(5)
        root.addWidget(split, 1)

        actions = QHBoxLayout()
        self.task_combo = QComboBox()
        self.task_combo.addItem("Исправить текст и пунктуацию", "clean")
        self.task_combo.addItem("Краткое содержание", "summary")
        self.task_combo.addItem("Подробный конспект", "detailed")
        self.task_combo.addItem("Протокол встречи", "meeting")
        self.task_combo.addItem("Извлечь задачи и решения", "actions")
        self.task_combo.addItem("Ответить на вопросы по записи", "qa")
        self.task_combo.addItem("Своя инструкция", "custom")
        self.task_combo.setObjectName("aiTaskCombo")
        self.task_combo.setMinimumHeight(36)
        actions.addWidget(self.task_combo, 2)
        self.custom_instruction = QLineEdit()
        self.custom_instruction.setPlaceholderText("Своя инструкция: например, выдели все факты по каждому проекту…")
        actions.addWidget(self.custom_instruction, 3)
        self.run_button = QPushButton("Обработать с ИИ")
        self.run_button.setProperty("role", "primary")
        self.run_button.setMinimumHeight(38)
        icon_path = self.project_root / "icons" / "ai_processing.png"
        if icon_path.is_file():
            self.run_button.setIcon(QIcon(str(icon_path)))
            self.run_button.setIconSize(QSize(26, 26))
        self.run_button.clicked.connect(self.start_processing)
        actions.addWidget(self.run_button)
        self.cancel_button = QPushButton("Отменить")
        self.cancel_button.setProperty("role", "tertiary")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_processing)
        actions.addWidget(self.cancel_button)
        root.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.status = QLabel("Готово. Для локальной обработки интернет не нужен, если сервер и модель уже установлены.")
        self.status.setObjectName("mutedLabel")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.provider_combo.currentIndexChanged.connect(self._provider_changed)
        self.model_combo.currentTextChanged.connect(self._model_changed)
        self.task_combo.currentIndexChanged.connect(self._task_changed)
        self._load_ai_settings()
        self._provider_changed()
        self._task_changed()

    def _load_ai_settings(self):
        settings = load_settings(self.project_root)
        provider = settings.get("ai_provider", "local")
        idx = self.provider_combo.findData(provider)
        self.provider_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.base_url_edit.setText(settings.get("ai_local_url", "http://127.0.0.1:11434/v1") if provider == "local" else settings.get("ai_api_base_url", "https://api.openai.com/v1"))
        model = settings.get("ai_local_model", "qwen3.5:4b") if provider == "local" else settings.get("ai_api_model", "gpt-4.1-mini")
        self.model_combo.setCurrentText(model)
        self._load_key_to_placeholder()
        self._refresh_provider_note()

    def _provider_changed(self, *_):
        local = self.provider_combo.currentData() == "local"
        current = self.base_url_edit.text().strip()
        if local and not (current.startswith("http://127.0.0.1") or current.startswith("http://localhost")):
            self.base_url_edit.setText("http://127.0.0.1:11434/v1")
            self.model_combo.setCurrentText("qwen3.5:4b")
        elif not local and ("localhost" in current or "127.0.0.1" in current or not current):
            self.base_url_edit.setText("https://api.openai.com/v1")
            self.model_combo.setCurrentText("gpt-4.1-mini")
        self.api_key_row_widget.setVisible(not local)
        self._refresh_provider_note()
        self._load_key_to_placeholder()

    def _model_changed(self, *_):
        self._refresh_provider_note()

    def _refresh_provider_note(self):
        local = self.provider_combo.currentData() == "local"
        if local:
            note = "Локальная обработка выполняется через Ollama. Модель нужно установить заранее; после загрузки модель работает без облачного API."
            if self.model_combo.currentText().strip().lower() == "qwen3.8:27b":
                note += " Внимание: модель занимает около 18 ГБ на диске и может быть тяжёлой для 16 ГБ RAM / 8–12 ГБ VRAM."
        else:
            note = "API отправляет выбранный текст внешнему поставщику после подтверждения. Ключ не хранится в settings.json; используется системное хранилище, если доступно."
        self.provider_note.setText(note)

    def _load_key_to_placeholder(self):
        self.api_key_edit.clear()
        if self.provider_combo.currentData() == "local":
            return
        try:
            import keyring
            key = keyring.get_password("Spiker.AI", self.base_url_edit.text().strip() or "https://api.openai.com/v1")
            if key:
                self.api_key_edit.setPlaceholderText("Ключ сохранён в системном хранилище; введите новый для замены")
            else:
                self.api_key_edit.setPlaceholderText("Введите API-ключ (не записывается в settings.json)")
        except Exception:
            self.api_key_edit.setPlaceholderText("Хранилище ОС недоступно; ключ действует только до закрытия программы")

    def _provider_config(self):
        local = self.provider_combo.currentData() == "local"
        url = self.base_url_edit.text().strip()
        key = self.api_key_edit.text().strip()
        if not key and not local:
            try:
                import keyring
                key = keyring.get_password("Spiker.AI", url) or ""
            except Exception:
                key = ""
        return {"provider": "local" if local else "api", "base_url": url, "model": self.model_combo.currentText().strip(), "api_key": key}

    def save_ai_settings(self):
        config = self._provider_config()
        provider = config["provider"]
        settings = {
            "ai_provider": provider,
            "ai_local_url": config["base_url"] if provider == "local" else "http://127.0.0.1:11434/v1",
            "ai_api_base_url": config["base_url"] if provider == "api" else "https://api.openai.com/v1",
            "ai_local_model": config["model"] if provider == "local" else "qwen3.5:4b",
            "ai_api_model": config["model"] if provider == "api" else "gpt-4.1-mini",
        }
        save_settings(self.project_root, settings)
        key_status = ""
        if provider == "api" and self.api_key_edit.text().strip():
            try:
                import keyring
                keyring.set_password("Spiker.AI", config["base_url"], self.api_key_edit.text().strip())
                self.api_key_edit.clear()
                self._load_key_to_placeholder()
                key_status = " API-ключ сохранён в системном хранилище."
            except Exception as exc:
                key_status = " Не удалось сохранить ключ в системное хранилище; он останется только в текущем сеансе. " + str(exc)
        self.status.setText("Настройки ИИ сохранены." + key_status)

    def probe_connection(self):
        if self._worker is not None and self._worker.isRunning():
            return
        config = self._provider_config()
        self.probe_button.setEnabled(False)
        self.status.setText("Проверяем подключение и доступные модели…")
        self._worker = AIWorker("probe", config, parent=self)
        self._worker.models_ready.connect(self._models_found)
        self._worker.probe_done.connect(self._probe_done)
        self._worker.error.connect(self._operation_error)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def _models_found(self, models: list):
        current = self.model_combo.currentText().strip()
        provider = self.provider_combo.currentData()
        discovered = [str(model).strip() for model in models if str(model).strip()]
        if provider == "local":
            # Keep the common local tags selectable even when they are not installed yet.
            # Actual installed tags come from Ollama; no model is downloaded by this refresh.
            presets = ["qwen3.5:4b", "qwen3.5:9b", "qwen3.8:27b", "qwen3:8b", "llama3.1:8b"]
            entries = list(dict.fromkeys(presets + discovered))
        else:
            entries = list(dict.fromkeys(discovered))
            if current and current not in entries:
                entries.insert(0, current)

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(entries)
        self.model_combo.setEditable(True)
        discovered_set = set(discovered)
        for i in range(self.model_combo.count()):
            tag = self.model_combo.itemText(i).strip()
            if provider == "local" and tag not in discovered_set:
                tip = f"Не обнаружена в текущем списке Ollama. Если нужна эта модель, установите её отдельно: ollama pull {tag}."
            elif provider == "local":
                tip = "Модель обнаружена в списке Ollama на этом компьютере."
            else:
                tip = "Модель из ответа выбранного API-провайдера." if tag in discovered_set else "Введите точный идентификатор модели, доступной у выбранного API-провайдера."
            if tag == "qwen3.8:27b":
                tip += " Размер на диске около 18 ГБ; при 16 ГБ RAM и 8–12 ГБ VRAM возможна нехватка памяти или медленная работа."
            self.model_combo.setItemData(i, tip, Qt.ItemDataRole.ToolTipRole)
        if current:
            self.model_combo.setCurrentText(current)
        self.model_combo.blockSignals(False)
        self._refresh_provider_note()

    def _probe_done(self, message: str):
        self.status.setText(message)
        self.save_ai_settings()

    def set_source_text(self, text: str, source_name: str = ""):
        self.source_name = source_name or ""
        self.source_editor.setPlainText(text or "")
        name = Path(self.source_name).name if self.source_name else "Вставленный текст"
        self.source_info.setText(f"Источник: {name} · {len(text or ''):,} символов. Оригинал не изменяется.".replace(",", " "))
        if not (text or "").strip():
            self.status.setText("Получен пустой текст. Вставьте расшифровку или выберите TXT-файл.")

    def load_text_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Открыть расшифровку", str(self.project_root / "results"), "Текст (*.txt *.md);;Все файлы (*.*)")
        if not filename:
            return
        try:
            text = Path(filename).read_text(encoding="utf-8-sig")
            self.set_source_text(text, filename)
        except OSError as exc:
            QMessageBox.warning(self, "Не удалось открыть файл", str(exc))

    def _task_changed(self, *_):
        current = self.task_combo.currentData()
        self.custom_instruction.setVisible(current in {"custom", "qa"})
        if current == "qa":
            self.custom_instruction.setPlaceholderText("Напишите вопрос по записи…")
        else:
            self.custom_instruction.setPlaceholderText("Своя инструкция: например, выдели все факты по каждому проекту…")

    def start_processing(self):
        if self._worker is not None and self._worker.isRunning():
            return
        text = self.source_editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Нет исходного текста", "Вставьте расшифровку или передайте результат из очереди.")
            return
        config = self._provider_config()
        if not config["model"]:
            QMessageBox.information(self, "Не выбрана модель", "Укажите имя установленной локальной модели или модель API.")
            return
        if config["provider"] == "api" and not config["api_key"]:
            QMessageBox.warning(self, "Нет API-ключа", "Введите ключ API. Для Ollama ключ не нужен.")
            return
        if config["provider"] == "api":
            answer = QMessageBox.question(self, "Отправить текст во внешний сервис?", "Вся исходная расшифровка или её фрагменты будут отправлены указанному API-провайдеру. Продолжить?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.save_ai_settings()
        self._last_task = str(self.task_combo.currentData())
        self._last_provider = str(config["provider"])
        self.progress.setValue(0)
        self.run_button.setEnabled(False)
        self.probe_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status.setText("Запускаем обработку…")
        job = {"task": self._last_task, "source_text": text, "custom_instruction": self.custom_instruction.text().strip()}
        self._worker = AIWorker("process", config, job, self)
        self._worker.progress.connect(self._progress_update)
        self._worker.output_ready.connect(self._output_ready)
        self._worker.error.connect(self._operation_error)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def cancel_processing(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self.status.setText("Отмена запрошена. Текущий запрос к модели может завершиться перед остановкой.")
            self.cancel_button.setEnabled(False)

    def _progress_update(self, percent: int, message: str):
        self.progress.setValue(percent)
        self.status.setText(message)

    def _output_ready(self, text: str):
        self._last_result = text
        self.output_editor.setPlainText(text)
        # Save a timestamped history copy automatically so a result is not lost if the page closes.
        try:
            from re import sub
            base_name = sub(r"[^\w.-]+", "_", Path(self.source_name).stem if self.source_name else "transcript", flags=0).strip("._") or "transcript"
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            auto_path = self.results_dir / f"{base_name}_{self._last_task}_{stamp}.md"
            auto_path.write_text(f"# {base_name} — результат ИИ\n\nМодель: {self.model_combo.currentText().strip()}\nРежим: {self._last_provider}\nДата: {datetime.now().astimezone().isoformat(timespec='seconds')}\n\n---\n\n{text}\n", encoding="utf-8", newline="")
            self._last_auto_path = str(auto_path)
            self.status.setText(f"Обработка завершена. Получено {len(text):,} символов. Автокопия: {auto_path.name}".replace(",", " "))
        except OSError as exc:
            self.status.setText(f"Обработка завершена, но не удалось создать резервную копию: {exc}")

    def _operation_error(self, message: str):
        self.status.setText(message)
        if message and "отменена" not in message.lower() and "отмена запрошена" not in message.lower():
            QMessageBox.warning(self, "Ошибка ИИ-обработки", message)

    def _worker_finished(self):
        self.run_button.setEnabled(True)
        self.probe_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        worker = self._worker
        if worker is not None and not worker.isRunning():
            worker.deleteLater()
            self._worker = None

    def export_result(self):
        text = self.output_editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Нет результата", "Сначала выполните обработку ИИ или введите результат вручную.")
            return
        default_stem = Path(self.source_name).stem if self.source_name else "Spiker_AI_result"
        target, selected_filter = QFileDialog.getSaveFileName(
            self, "Экспорт результата ИИ", str(self.results_dir / f"{default_stem}_ai.md"),
            "Markdown (*.md);;Текст (*.txt);;JSON (*.json)"
        )
        if not target:
            return
        path = Path(target)
        try:
            suffix = path.suffix.lower()
            if suffix == ".json":
                payload = {"source": self.source_name, "provider": self._last_provider, "task": self._last_task,
                           "created_at": datetime.now().astimezone().isoformat(timespec="seconds"), "text": text}
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                path.write_text(text, encoding="utf-8", newline="")
            self.status.setText(f"Результат сохранён: {path}")
        except OSError as exc:
            QMessageBox.warning(self, "Ошибка сохранения", str(exc))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                p = Path(url.toLocalFile())
                if p.suffix.lower() in {".txt", ".md"} and p.is_file():
                    try:
                        self.set_source_text(p.read_text(encoding="utf-8-sig"), str(p))
                        break
                    except OSError:
                        pass
        event.acceptProposedAction()

    def prepare_for_shutdown(self, timeout_ms=2500) -> bool:
        """Avoid destroying a QThread while a local/API request is still active."""
        if self._worker is None or not self._worker.isRunning():
            return True
        self._worker.requestInterruption()
        completed = self._worker.wait(timeout_ms)
        if completed:
            self._worker = None
        return completed

    def closeEvent(self, event):
        if not self.prepare_for_shutdown(2500):
            event.ignore()
            return
        super().closeEvent(event)
