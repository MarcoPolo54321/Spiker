"""Offline narration workspace with import, audition and WAV export."""
from datetime import datetime
from pathlib import Path
import shutil
from PySide6.QtCore import QThread, Signal, QUrl, Qt
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QComboBox, QProgressBar, QFileDialog, QMessageBox, QFrame, QSlider, QSizePolicy
from app_paths import get_user_data_root
from speech_synthesis import VOICES, synthesize

class SpeechWorker(QThread):
    progress = Signal(int)
    ready = Signal(str)
    failed = Signal(str)
    def __init__(self, text, root, output, voice, voice2, speed, parent):
        super().__init__(parent)
        self.args = text, root, output, voice, speed
        self.speaker_voices = {'1': voice, '2': voice2}
    def run(self):
        try:
            path = synthesize(*self.args, cancelled=self.isInterruptionRequested, progress=self.progress.emit,
                              speaker_voices=self.speaker_voices)
            self.ready.emit(str(path))
        except Exception as exc:
            self.failed.emit(str(exc))

class SpeechPage(QWidget):
    def __init__(self, root_path, on_back, parent=None):
        super().__init__(parent)
        self.root_path = Path(root_path)
        self.worker = None
        self.audio_path = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 20)
        layout.setSpacing(12)
        header = QHBoxLayout()
        back = QPushButton('←  Назад')
        back.setProperty('role', 'back')
        back.clicked.connect(on_back)
        back.setMinimumHeight(38)
        header.addWidget(back, 0,)
        title_stack = QVBoxLayout()
        title = QLabel('Озвучка')
        title.setObjectName('dialogTitle')
        subtitle = QLabel('Подготовьте речь из текста и сохраните её в удобном формате.')
        subtitle.setObjectName('mutedLabel')
        subtitle.setWordWrap(True)
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack, 1)
        layout.addLayout(header)

        controls = QFrame()
        controls.setObjectName('panel')
        control_layout = QVBoxLayout(controls)
        control_layout.setContentsMargins(18, 14, 18, 14)
        control_layout.setSpacing(10)
        row = QHBoxLayout()
        voice_column = QVBoxLayout()
        voice_label = QLabel('ГОЛОС СПИКЕРА 1')
        voice_label.setObjectName('sectionLabel')
        voice_column.addWidget(voice_label)
        self.voice = QComboBox()
        self.voice.setObjectName('modelCombo')
        self.voice.setMinimumHeight(40)
        for key, name in VOICES.items(): self.voice.addItem(name, key)
        voice_column.addWidget(self.voice)
        row.addLayout(voice_column, 2)
        voice2_column = QVBoxLayout()
        voice2_label = QLabel('ГОЛОС СПИКЕРА 2')
        voice2_label.setObjectName('sectionLabel')
        voice2_column.addWidget(voice2_label)
        self.voice2 = QComboBox()
        self.voice2.setObjectName('modelCombo')
        self.voice2.setMinimumHeight(40)
        for key, name in VOICES.items(): self.voice2.addItem(name, key)
        self.voice2.setCurrentIndex(1 if self.voice.currentData() == 'irina' else 0)
        self.voice.currentIndexChanged.connect(self._sync_second_voice)
        voice2_column.addWidget(self.voice2)
        row.addLayout(voice2_column, 2)
        speed_column = QVBoxLayout()
        speed_header = QHBoxLayout()
        speed_label = QLabel('СКОРОСТЬ РЕЧИ')
        speed_label.setObjectName('sectionLabel')
        speed_header.addWidget(speed_label)
        speed_header.addStretch(1)
        self.speed_value = QLabel('90%')
        self.speed_value.setObjectName('speedValue')
        self.speed_value.setMinimumWidth(48)
        self.speed_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        speed_header.addWidget(self.speed_value)
        speed_column.addLayout(speed_header)
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setObjectName('speechSpeedSlider')
        self.speed.setRange(60, 140)
        self.speed.setSingleStep(5)
        self.speed.setPageStep(10)
        self.speed.setValue(90)
        self.speed.valueChanged.connect(self._speed_changed)
        self.speed.setToolTip('Скорость озвучивания: от 60% до 140%')
        speed_column.addWidget(self.speed)
        speed_hint = QLabel('Меньшая скорость обычно делает фразы разборчивее.')
        speed_hint.setObjectName('mutedLabel')
        speed_column.addWidget(speed_hint)
        row.addLayout(speed_column, 3)
        control_layout.addLayout(row)
        file_row = QHBoxLayout()
        self.load_button = QPushButton('Загрузить TXT / MD / DOCX')
        self.load_button.setProperty('role', 'tertiary')
        self.load_button.clicked.connect(self.import_text)
        file_row.addWidget(self.load_button)
        file_row.addStretch(1)
        self.input_count = QLabel('0 символов')
        self.input_count.setObjectName('mutedLabel')
        file_row.addWidget(self.input_count)
        control_layout.addLayout(file_row)
        dialogue_hint = QLabel('Для диалога укажите реплики строками «Спикер 1: …» и «Спикер 2: …» — голоса переключатся автоматически.')
        dialogue_hint.setObjectName('mutedLabel')
        dialogue_hint.setWordWrap(True)
        control_layout.addWidget(dialogue_hint)
        layout.addWidget(controls)

        self.editor = QTextEdit(); self.editor.setPlaceholderText('Вставьте текст или передайте результат из ИИ-обработки…'); layout.addWidget(self.editor, 1)
        self.editor.setObjectName('speechTextEditor')
        self.editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.editor.textChanged.connect(self._update_input_count)
        self.progress = QProgressBar(); self.progress.setValue(0); layout.addWidget(self.progress)
        row = QHBoxLayout()
        self.generate = QPushButton('Озвучить'); self.generate.setProperty('role', 'primary'); self.generate.clicked.connect(self.start)
        self.cancel = QPushButton('Отменить'); self.cancel.setEnabled(False); self.cancel.clicked.connect(self.stop_generation)
        self.play = QPushButton('▶ Слушать'); self.play.setEnabled(False); self.play.clicked.connect(self.play_audio)
        stop = QPushButton('■ Стоп'); stop.clicked.connect(lambda: self.player.stop())
        self.export = QPushButton('Сохранить WAV / MP3…'); self.export.setEnabled(False); self.export.clicked.connect(self.save_audio)
        for button in (self.generate, self.cancel, self.play, stop, self.export): row.addWidget(button)
        layout.addLayout(row)
        self.status = QLabel('Готово'); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.player = QMediaPlayer(self); self.audio = QAudioOutput(self); self.player.setAudioOutput(self.audio)
        self.player.errorOccurred.connect(lambda *_: self.status.setText(self.player.errorString()))
        self._update_input_count()

    def _speed_changed(self, value):
        self.speed_value.setText(f'{value}%')

    def _sync_second_voice(self, *_):
        preferred = 'ruslan' if self.voice.currentData() == 'irina' else 'irina'
        index = self.voice2.findData(preferred)
        if index >= 0:
            self.voice2.setCurrentIndex(index)

    def set_speaker_voices(self, voice_map):
        """Apply saved voice assignments for the first two diarized speakers."""
        for speaker_number, combo in (("1", self.voice), ("2", self.voice2)):
            voice = str((voice_map or {}).get(speaker_number, ""))
            index = combo.findData(voice)
            if index >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)
        if "2" not in (voice_map or {}) and "1" in (voice_map or {}):
            self._sync_second_voice()

    def _update_input_count(self):
        count = len(self.editor.toPlainText())
        self.input_count.setText(f'{count:,} символов'.replace(',', ' '))
    def import_text(self):
        name, _ = QFileDialog.getOpenFileName(self, 'Открыть текст', '', 'Текст (*.txt *.md *.docx)')
        if not name: return
        try:
            if name.lower().endswith('.docx'):
                from docx import Document
                text = '\n'.join(p.text for p in Document(name).paragraphs)
            elif name.lower().endswith('.md'):
                text = Path(name).read_text(encoding='utf-8-sig')
            else:
                text = Path(name).read_text(encoding='utf-8-sig')
            self.editor.setPlainText(text)
        except Exception as exc: QMessageBox.warning(self, 'Не удалось прочитать файл', str(exc))
    def start(self):
        if self.worker and self.worker.isRunning(): return
        text = self.editor.toPlainText().strip()
        if not text: self.status.setText('Введите текст.'); return
        self.player.stop()
        output = get_user_data_root(self.root_path) / 'results/Озвучка' / (datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f') + '.wav')
        self.worker = SpeechWorker(text, self.root_path, output, self.voice.currentData(), self.voice2.currentData(), self.speed.value() / 100.0, self)
        self.worker.progress.connect(self.progress.setValue); self.worker.ready.connect(self.done)
        self.worker.failed.connect(self.status.setText); self.worker.finished.connect(self.finished)
        self.generate.setEnabled(False); self.cancel.setEnabled(True); self.progress.setValue(0)
        self.status.setText('Готовим голос и озвучиваем текст…'); self.worker.start()
    def stop_generation(self):
        if self.worker: self.worker.requestInterruption()
        self.status.setText('Остановка после текущего короткого фрагмента…')
    def done(self, path):
        self.audio_path = Path(path); self.play.setEnabled(True); self.export.setEnabled(True)
        self.status.setText('Готово: ' + path)
    def finished(self):
        self.generate.setEnabled(True); self.cancel.setEnabled(False)
        self.worker.deleteLater(); self.worker = None
    def play_audio(self):
        if self.audio_path:
            self.player.setSource(QUrl.fromLocalFile(str(self.audio_path))); self.player.play()
    def save_audio(self):
        if not self.audio_path: return
        default = self.audio_path.with_suffix('.mp3')
        name, selected = QFileDialog.getSaveFileName(
            self, 'Сохранить озвучку', str(default), 'MP3 (*.mp3);;WAV (*.wav)'
        )
        if not name:
            return
        target = Path(name)
        if target.suffix.lower() == '.mp3' or selected.startswith('MP3'):
            if target.suffix.lower() != '.mp3':
                target = target.with_suffix('.mp3')
            try:
                import subprocess
                import imageio_ffmpeg
                subprocess.run(
                    [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(self.audio_path),
                     '-vn', '-codec:a', 'libmp3lame', '-qscale:a', '3', str(target)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
            except Exception as exc:
                QMessageBox.warning(self, 'Не удалось сохранить MP3', str(exc))
                return
        elif target.resolve() != self.audio_path.resolve():
            try:
                shutil.copy2(self.audio_path, target)
            except OSError as exc:
                QMessageBox.warning(self, 'Не удалось сохранить WAV', str(exc))
                return
        self.status.setText(f'Файл сохранён: {target}')
    def prepare_for_shutdown(self, timeout_ms=0):
        self.player.stop()
        if not self.worker or not self.worker.isRunning(): return True
        self.worker.requestInterruption()
        return self.worker.wait(timeout_ms)
