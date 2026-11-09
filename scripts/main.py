# ---------------------------------------------- БИБЛИОТЕКИ ------------------------------------------------------------
import json, sys, os, tempfile, wave, logging, queue as queue_module, time, threading, re
from pathlib import Path

# The original UI uses paths relative to the scripts directory. Set that
# directory explicitly so launching from a shortcut/other working directory works.
if getattr(sys, "frozen", False):
    _project_root = Path(sys.executable).resolve().parent
else:
    _project_root = Path(__file__).resolve().parents[1]
_scripts_dir = _project_root / "scripts"
sys.path.insert(0, str(_scripts_dir))
from app_logging import configure_logging
from app_config import load_settings
from app_paths import get_user_data_root
from model_bundle import unpack_companion_models
from time_utils import format_duration as _format_duration
configure_logging(_project_root)
unpack_companion_models(_project_root)
if _scripts_dir.is_dir():
    os.chdir(_scripts_dir)

from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QTimer, QTime, QThread, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog, QMessageBox, QFileDialog, QTabWidget

from UI.Main_menu_script import Ui_MainWindow
from UI.theme import APP_STYLESHEET, apply_window_theme
from Queue_page import QueuePage
from UI.Settings_page import SettingsPage
from UI.AI_page import AIProcessingPage
from UI.Info_menu_script import Ui_Dialog_info
from UI.UserGuide import UserGuidePage
from UI.Dictation_audio_menu_script import Ui_Dialog_dict_audio

# Heavy recognition/media libraries are imported on demand, not during application startup.
# This keeps the home screen responsive even before a model or audio device is used.
# ----------------------------------------------------------------------------------------------------------------------

    # Модель Vosk загружается только при запуске диктовки с микрофона.
    # Для транскрибации файлов при наличии ggml-medium.bin используется Whisper.
_vosk_preferred = _project_root / "models" / "vosk" / "vosk-model-small-ru-0.22"
_vosk_legacy = _project_root / "model" / "vosk-model-small-ru-0.22"
try:
    # Consolidate the old root-level Vosk location under models/ on startup.
    # Only the known Vosk directory is moved; other legacy-folder contents remain untouched.
    from model_paths import native_model_path, resolve_vosk_model_path
    model_path = str(resolve_vosk_model_path(_project_root))
except Exception:
    # If migration support itself cannot run, retain backwards compatibility.
    model_path = str(_vosk_preferred if _vosk_preferred.exists() or not _vosk_legacy.exists() else _vosk_legacy)
model = None


def get_vosk_model():
    """Lazily load Vosk only when a complete optional Vosk model is installed."""
    global model
    if model is None:
        required = ("am/final.mdl", "graph/HCLr.fst", "graph/Gr.fst", "graph/phones/word_boundary.int")
        missing = [name for name in required if not (Path(model_path) / name).is_file()]
        if missing:
            raise FileNotFoundError(
                "Полная модель Vosk не найдена. Для диктовки положите ggml-small.bin или ggml-medium.bin "
                "в папку models и выберите её в настройках. Если хотите использовать Vosk, установите полную "
                "модель в models/vosk/vosk-model-small-ru-0.22."
            )
        from vosk import Model
        model = Model(native_model_path(model_path))
    return model


def get_whisper_model_path():
    """Lightweight model-path lookup used by Settings without importing recognition libraries."""
    candidates = []
    user_data_root = get_user_data_root(_project_root)
    config_path = user_data_root / "data" / "model_paths" / "whisper_model.txt"
    legacy_config_path = _project_root / "models" / "whisper" / "model_path.txt"
    if not config_path.is_file() and legacy_config_path.is_file():
        config_path = legacy_config_path
    try:
        configured = config_path.read_text(encoding="utf-8").strip()
        if configured:
            candidates.append(Path(configured).expanduser())
    except OSError:
        pass
    candidates.extend([
        user_data_root / "models" / "whisper" / "ggml-small.bin",
        user_data_root / "models" / "whisper" / "ggml-medium.bin",
        _project_root / "models" / "whisper" / "ggml-small.bin",
        _project_root / "models" / "whisper" / "ggml-medium.bin",
        _project_root / "models" / "ggml-small.bin",
        _project_root / "ggml-medium.bin",
    ])
    for models_root in (user_data_root / "models", _project_root / "models"):
        if not models_root.is_dir():
            continue
        try:
            candidates.extend(sorted(
                (item for item in models_root.rglob("*.bin")
                 if "faster-whisper" not in {part.lower() for part in item.parts}),
                key=lambda item: item.name.lower(),
            ))
        except OSError:
            pass
    seen = set()
    for candidate in candidates:
        try:
            path = Path(candidate).resolve()
            if path in seen:
                continue
            seen.add(path)
            if path.is_file() and path.stat().st_size >= 10 * 1024 * 1024:
                return path
        except OSError:
            continue
    return None


def set_whisper_model_path_lazy(path):
    from transcription.wav_to_text import set_whisper_model_path
    return set_whisper_model_path(path)


class FileTranscriptionWorker(QThread):
    """File transcription worker with resumable segment checkpoints."""
    succeeded = Signal(str, str)
    failed = Signal(str, str)
    progress_changed = Signal(int, str, str, float)
    segments_changed = Signal(list)
    segment_added = Signal(dict)

    def __init__(self, file_path, resume_from_seconds=0.0, prefix_text="", prefix_segments=None):
        super().__init__()
        self.file_path = str(file_path)
        self.resume_from_seconds = max(0.0, float(resume_from_seconds or 0.0))
        self.prefix_text = str(prefix_text or "")
        self.segments = [dict(item) for item in (prefix_segments or []) if isinstance(item, dict) and "text" in item]
        self.latest_text = self.prefix_text
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._checkpoint_seconds = self.resume_from_seconds
        self.speaker_stats = {}
        self.speaker_note = ""
        self.backend_used = "whispercpp"

    def cancel(self):
        self.requestInterruption()
        self.resume()

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def is_paused(self):
        return not self._pause_event.is_set() and not self.isInterruptionRequested()

    @staticmethod
    def _word_key(word):
        return re.sub(r"^[^\w]+|[^\w]+$", "", word, flags=re.UNICODE).casefold()

    @classmethod
    def _merge_prefix(cls, prefix, candidate, max_overlap=12):
        left = (prefix or "").split()
        right = (candidate or "").split()
        if not right:
            return " ".join(left)
        overlap = 0
        limit = min(max_overlap, len(left), len(right))
        for count in range(limit, 0, -1):
            a = [cls._word_key(word) for word in left[-count:]]
            b = [cls._word_key(word) for word in right[:count]]
            if all(a) and a == b:
                overlap = count
                break
        if overlap:
            for offset in range(overlap):
                candidate_word = right[offset]
                idx = len(left) - overlap + offset
                mark = re.search(r"([,;:!?…]+)$", candidate_word)
                if mark and not re.search(r"[,;:!?…]+$", left[idx]):
                    left[idx] += mark.group(1)
        return " ".join(left + right[overlap:]).strip()

    @staticmethod
    def _make_resume_slice(source_wav: Path, start_seconds: float) -> tuple[Path, float, float]:
        """Create a cropped PCM WAV from a checkpoint, keeping a one-second overlap."""
        temp_root = Path(tempfile.gettempdir()) / "Spiker" / "audio"
        temp_root.mkdir(parents=True, exist_ok=True)
        with wave.open(str(source_wav), "rb") as input_wav:
            channels = input_wav.getnchannels()
            sample_width = input_wav.getsampwidth()
            sample_rate = input_wav.getframerate()
            total_frames = input_wav.getnframes()
            if channels != 1 or sample_width != 2 or sample_rate != 16000:
                raise ValueError("Подготовленный WAV должен быть mono PCM 16 кГц / 16 бит.")
            start_frame = min(total_frames, max(0, int(start_seconds * sample_rate)))
            input_wav.setpos(start_frame)
            fd, name = tempfile.mkstemp(prefix="resume_", suffix=".wav", dir=temp_root)
            os.close(fd)
            output_path = Path(name)
            try:
                with wave.open(str(output_path), "wb") as output_wav:
                    output_wav.setnchannels(channels)
                    output_wav.setsampwidth(sample_width)
                    output_wav.setframerate(sample_rate)
                    output_wav.setcomptype("NONE", "not compressed")
                    while True:
                        block = input_wav.readframes(16000 * 8)
                        if not block:
                            break
                        output_wav.writeframesraw(block)
                slice_duration = max(0.0, (total_frames - start_frame) / sample_rate)
                return output_path, start_frame / sample_rate, slice_duration
            except BaseException:
                output_path.unlink(missing_ok=True)
                raise

    def run(self):
        from transcription.audio_preparation import prepare_media_audio
        from transcription.wav_to_text import find_whisper_model, transcribe_with_whisper, add_punctuation_and_capitalize
        from transcription.faster_whisper_backend import is_faster_whisper_available, resolve_faster_model, transcribe_with_faster_whisper, resolve_audio_profile_options
        from transcription.speaker_diarization import apply_speaker_diarization
        logger = logging.getLogger("processing")
        prepared = None
        resume_slice = None
        logger.info("File transcription started: %s resume_from=%.2fs", self.file_path, self.resume_from_seconds)
        try:
            preferences = load_settings(_project_root)
            engine = str(preferences.get("transcription_engine", "auto"))
            faster_model = resolve_faster_model(
                _project_root,
                preferences.get("faster_whisper_model", "medium"),
                preferences.get("faster_whisper_model_path", ""),
            )
            use_faster = engine == "faster-whisper" or (
                engine == "auto" and faster_model is not None and is_faster_whisper_available()
            )
            if engine == "faster-whisper" and not is_faster_whisper_available():
                raise RuntimeError("faster-whisper не установлен. Запустите Install_Faster_Whisper.bat.")
            if use_faster and faster_model is None:
                raise FileNotFoundError(
                    "Локальная модель faster-whisper не найдена. Поместите CTranslate2-модель "
                    "в models/faster-whisper/<имя> или выберите «Авто» для резервного Whisper.cpp."
                )
            model_path = None if use_faster else find_whisper_model()
            if not use_faster and model_path is None:
                raise FileNotFoundError(
                    "Модель Whisper.cpp не найдена. Выберите файл ggml-small.bin или ggml-medium.bin и повторите запуск."
                )
            self.backend_used = "faster-whisper" if use_faster else "whispercpp"
            if self.isInterruptionRequested():
                raise InterruptedError("Транскрибация отменена пользователем.")

            audio_profile = preferences.get("audio_profile", "speech")
            effective_vad, effective_normalize = resolve_audio_profile_options(
                audio_profile, bool(preferences.get("vad_filter", True)),
                bool(preferences.get("audio_normalize", False)),
            )
            logger.info("Audio profile selected: %s (vad=%s normalize=%s stream=%s)",
                        audio_profile, effective_vad, effective_normalize, preferences.get("audio_stream_index", 0))
            prepared = prepare_media_audio(
                self.file_path,
                stage_callback=lambda message: self.progress_changed.emit(
                    -1, message, self.prefix_text, self._checkpoint_seconds
                ),
                cancel_callback=self.isInterruptionRequested,
                normalize=effective_normalize,
                audio_stream_index=preferences.get("audio_stream_index", 0),
            )
            full_duration = max(0.0, float(prepared.duration_seconds))
            resume_at = min(full_duration, self.resume_from_seconds)
            prefix_text = self.prefix_text.strip()

            if resume_at > 0 and prefix_text and resume_at < full_duration:
                crop_start = max(0.0, resume_at - 1.0)
                resume_slice, crop_start, recognition_duration = self._make_resume_slice(prepared.path, crop_start)
                recognition_path = resume_slice
                initial_message = (
                    f"Продолжаем с {_format_duration(resume_at)} из {_format_duration(full_duration)}; "
                    "сохранённый текст не будет потерян."
                )
            else:
                crop_start = 0.0
                recognition_duration = full_duration
                recognition_path = prepared.path
                if resume_at > 0:
                    prefix_text = ""
                    self._checkpoint_seconds = 0.0
                    resume_at = 0.0
                    self.progress_changed.emit(0, "Не удалось восстановить контрольную точку; начинаем заново.", "", 0.0)
                initial_message = "Подготовка завершена. Загружаем движок распознавания…"

            self.progress_changed.emit(
                int(min(99, max(0, 100 * resume_at / max(full_duration, 1.0)))),
                initial_message, prefix_text, resume_at
            )

            def report_segment(fraction, partial_text, latest_text):
                local_seconds = min(recognition_duration, max(0.0, float(fraction) * recognition_duration))
                global_seconds = min(full_duration, crop_start + local_seconds)
                self._checkpoint_seconds = max(self._checkpoint_seconds, global_seconds)
                combined = self._merge_prefix(prefix_text, partial_text)
                self.latest_text = combined
                percent = min(99, max(1, int(global_seconds / max(full_duration, 0.1) * 99)))
                label = f"Распознавание {_format_duration(global_seconds)} / {_format_duration(full_duration)} · {self.backend_used}"
                self.progress_changed.emit(percent, label, combined, self._checkpoint_seconds)

            def report_timestamp_segment(segment):
                """Persist source-relative segment and optional word timestamps."""
                try:
                    local_start = max(0.0, float(segment.get("start", 0.0)))
                    local_end = max(local_start, float(segment.get("end", 0.0)))
                    start = crop_start + local_start
                    end = crop_start + local_end
                    segment_text = str(segment.get("text", "")).strip()
                    if not segment_text:
                        return
                    if resume_at > 0 and end <= resume_at + 0.03:
                        return
                    norm = re.sub(r"[^\w]+", "", segment_text.casefold(), flags=re.UNICODE)
                    for existing in reversed(self.segments[-12:]):
                        old_norm = re.sub(r"[^\w]+", "", str(existing.get("text", "")).casefold(), flags=re.UNICODE)
                        try:
                            overlap = min(end, float(existing.get("end", 0))) - max(start, float(existing.get("start", 0)))
                            old_duration = max(0.01, float(existing.get("end", 0)) - float(existing.get("start", 0)))
                        except (TypeError, ValueError):
                            overlap, old_duration = 0.0, 1.0
                        if norm and norm == old_norm and overlap / old_duration >= 0.35:
                            return
                    item = {"start": round(start, 3), "end": round(max(start, end), 3), "text": segment_text}
                    if isinstance(segment.get("words"), list):
                        item["words"] = [
                            {
                                **word,
                                "start": round(crop_start + max(0.0, float(word.get("start", 0.0))), 3),
                                "end": round(crop_start + max(float(word.get("start", 0.0)), float(word.get("end", 0.0))), 3),
                            }
                            for word in segment["words"] if isinstance(word, dict)
                        ]
                    self.segments.append(item)
                    self.segments.sort(key=lambda value: (float(value.get("start", 0)), float(value.get("end", 0))))
                    self.segment_added.emit(dict(item))
                    self.segments_changed.emit([dict(value) for value in self.segments])
                except Exception:
                    logger.exception("Could not store timestamped transcript segment")

            if use_faster:
                raw_text = transcribe_with_faster_whisper(
                    recognition_path, faster_model,
                    device=preferences.get("compute_device", "auto"),
                    compute_type=preferences.get("compute_type", "auto"),
                    batch_size=preferences.get("batch_size", 1),
                    cpu_threads=preferences.get("threads", 4),
                    language=preferences.get("language", "ru"),
                    vad_filter=effective_vad,
                    word_timestamps=preferences.get("word_timestamps", True) or preferences.get("diarization_enabled", True),
                    initial_prompt=preferences.get("context_terms", ""),
                    duration_seconds=recognition_duration,
                    segment_callback=report_segment,
                    abort_callback=self.isInterruptionRequested,
                    pause_callback=self.is_paused,
                    stage_callback=lambda message: self.progress_changed.emit(-1, message, prefix_text, self._checkpoint_seconds),
                    timestamp_callback=report_timestamp_segment,
                )
            else:
                raw_text = transcribe_with_whisper(
                    recognition_path, model_path,
                    segment_callback=report_segment,
                    abort_callback=self.isInterruptionRequested,
                    stage_callback=lambda message: self.progress_changed.emit(-1, message, prefix_text, self._checkpoint_seconds),
                    duration_seconds=recognition_duration,
                    n_threads=preferences.get("threads", 4),
                    language=preferences.get("language", "ru"),
                    model_slot="file",
                    pause_callback=self.is_paused,
                    timestamp_callback=report_timestamp_segment,
                )
            if self.isInterruptionRequested():
                raise InterruptedError("Транскрибация остановлена пользователем.")
            text = add_punctuation_and_capitalize(self._merge_prefix(prefix_text, raw_text))
            if not text.strip():
                raise RuntimeError("Движок завершил работу, но не вернул текст. Проверьте, есть ли речь в записи.")

            if preferences.get("diarization_enabled", True):
                try:
                    if self.backend_used == "faster-whisper":
                        from transcription.faster_whisper_backend import release_faster_whisper_cache
                        release_faster_whisper_cache(device=preferences.get("compute_device", "auto") if preferences.get("compute_device") != "auto" else None)
                    self.progress_changed.emit(99, "Распознавание завершено. Освобождаем ресурсы и определяем участников…", text, full_duration)
                    self.segments, self.speaker_stats = apply_speaker_diarization(
                        prepared.path, self.segments, _project_root,
                        hf_token=os.environ.get("HF_TOKEN", ""),
                        min_speakers=preferences.get("speaker_min") or None,
                        max_speakers=preferences.get("speaker_max") or None,
                        device=preferences.get("compute_device", "auto"),
                        stage_callback=lambda message: self.progress_changed.emit(99, message, text, full_duration),
                        cancel_callback=self.isInterruptionRequested,
                    )
                    self.speaker_note = f"Определено участников: {int(self.speaker_stats.get('_meta', {}).get('speakers_detected', len(self.speaker_stats)))}."
                except InterruptedError:
                    raise
                except Exception as exc:
                    self.speaker_note = f"Диаризация не выполнена: {exc}"
                    logger.warning(self.speaker_note)
                    self.progress_changed.emit(99, self.speaker_note, text, full_duration)
            else:
                self.speaker_note = "Диаризация отключена в настройках."

            self.latest_text = text
            self.segments_changed.emit([dict(item) for item in self.segments])
            logger.info("File transcription completed: source=%s duration=%.2fs chars=%d backend=%s speakers=%d",
                        self.file_path, full_duration, len(text), self.backend_used, len(self.speaker_stats))
            self.progress_changed.emit(100, "Готово" + (f" · {self.speaker_note}" if self.speaker_note else ""), text, full_duration)
            self.succeeded.emit(text, self.file_path)
        except InterruptedError as exc:
            logger.info("File transcription stopped at checkpoint %.2fs: %s", self._checkpoint_seconds, self.file_path)
            self.failed.emit(str(exc), self.file_path)
        except Exception as exc:
            logger.exception("File transcription failed: %s", self.file_path)
            logging.getLogger("app.transcription_errors").exception(
                "File transcription error for %s: %s", self.file_path, exc
            )
            self.failed.emit(str(exc), self.file_path)
        finally:
            if resume_slice is not None:
                try:
                    resume_slice.unlink(missing_ok=True)
                except OSError:
                    logger.exception("Could not remove resume audio slice: %s", resume_slice)
            if prepared is not None and prepared.temporary:
                try:
                    prepared.path.unlink(missing_ok=True)
                    logger.info("Temporary prepared audio removed: %s", prepared.path)
                except OSError:
                    logger.exception("Could not remove temporary prepared audio: %s", prepared.path)

# --------------------------------------------- НАДИКТОВКА -------------------------------------------------------------
class AudioProcessor(QThread):
    """Capture mono PCM from the microphone and forward it without touching widgets."""
    recognized_text = Signal(str)
    partial_text = Signal(str)
    level_changed = Signal(int)

    def __init__(self, model, recognition, stream, ui=None, parent=None,
                 use_whisper=False, use_streaming=False, chunk_queue=None, chunk_seconds=5,
                 capture_done_event=None):
        super().__init__(parent)
        self.model = model
        self.recognition = recognition
        self.stream = stream
        self.ui = ui
        self.is_recording = True
        self.use_whisper = bool(use_whisper)
        self.use_streaming = bool(use_streaming)
        self.frames = []
        self.read_error = None
        self.audio_truncated = False
        self.chunk_queue = chunk_queue
        self.capture_done_event = capture_done_event or threading.Event()
        self.chunk_seconds = max(0.1, float(chunk_seconds))
        self.read_frames = 1600 if self.use_streaming else 4000  # 100 ms for online ASR.
        self._pending_pcm = bytearray()
        self.discard_pending = False
        self._chunk_bytes = max(2, int(16000 * 2 * self.chunk_seconds))

    def _queue_audio(self, chunk):
        if self.chunk_queue is None:
            return
        try:
            # Fast path: never block regular microphone reads while the decoder is keeping up.
            self.chunk_queue.put_nowait(chunk)
            return
        except queue_module.Full:
            # Stop the hardware stream before waiting for one final queue slot. This prevents
            # PortAudio from accumulating unread frames while the decoder catches up.
            self.read_error = (
                "Потоковый распознаватель отстал примерно на 12 секунд. "
                "Запись автоматически остановлена; уже поставленные в очередь фрагменты будут обработаны."
            )
            self.is_recording = False
            try:
                if self.stream is not None and self.stream.is_active():
                    self.stream.stop_stream()
            except Exception:
                logging.getLogger("app.transcription_errors").debug(
                    "Could not stop microphone stream after live backlog overflow", exc_info=True
                )
            try:
                # Preserve the frame that detected overflow. Since capture has stopped, this
                # one bounded wait does not create further microphone backlog.
                self.chunk_queue.put(chunk, timeout=5.0)
            except queue_module.Full:
                self.audio_truncated = True
                self.read_error += (
                    " Последний аудиоблок также не удалось передать декодеру; "
                    "в конце расшифровки может отсутствовать короткий фрагмент."
                )

    def run(self):
        try:
            while self.is_recording:
                try:
                    data = self.stream.read(self.read_frames, exception_on_overflow=False)
                except Exception as exc:
                    if self.is_recording:
                        self.read_error = str(exc)
                    break
                if not data:
                    continue
                import audioop
                self.level_changed.emit(min(100, int(audioop.rms(data, 2) / 32768 * 400)))
                if self.use_streaming:
                    # Online ASR receives each ~100 ms frame immediately.
                    self._queue_audio(bytes(data))
                elif self.use_whisper:
                    self._pending_pcm.extend(data)
                    while len(self._pending_pcm) >= self._chunk_bytes:
                        chunk = bytes(self._pending_pcm[:self._chunk_bytes])
                        del self._pending_pcm[:self._chunk_bytes]
                        self._queue_audio(chunk)
                        if not self.is_recording:
                            break
                else:
                    if self.recognition.AcceptWaveform(data):
                        answer = json.loads(self.recognition.Result())
                        if answer.get("text"):
                            self.recognized_text.emit(answer["text"])
                        self.partial_text.emit("")
                    else:
                        answer = json.loads(self.recognition.PartialResult())
                        self.partial_text.emit(str(answer.get("partial", "") or ""))
        finally:
            if (self.use_whisper or self.use_streaming) and self.chunk_queue is not None:
                if self._pending_pcm and not self.discard_pending:
                    self._queue_audio(bytes(self._pending_pcm))
                self._pending_pcm.clear()
                # The consumer polls for capture completion and drains everything already queued.
                # Never block the microphone thread trying to insert a sentinel into a full queue.
                self.capture_done_event.set()


    def stop(self, discard_pending: bool = False):
        self.is_recording = False
        self.discard_pending = bool(discard_pending)
        if self.stream is not None:
            try:
                self.stream.stop_stream()
            except Exception:
                pass
            try:
                self.stream.close()
            except Exception:
                pass


class WhisperDictationWorker(QThread):
    """Low-latency Whisper dictation: 2-second steps with 1-second acoustic overlap."""
    ready = Signal()
    text_updated = Signal(str)
    status_changed = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, chunk_queue, parent=None, capture_done_event=None):
        super().__init__(parent)
        self.chunk_queue = chunk_queue
        self.capture_done_event = capture_done_event or threading.Event()
        self._committed_text = ""
        self._tail_pcm = b""
        self._stop_requested = False

    def cancel(self):
        """Interrupt native decoding at the next Whisper segment boundary and discard queued audio."""
        self._stop_requested = True
        self.requestInterruption()
        self.capture_done_event.set()
        while True:
            try:
                self.chunk_queue.get_nowait()
            except queue_module.Empty:
                break

    @staticmethod
    def _normal_word(word: str) -> str:
        return re.sub(r"^[^\w]+|[^\w]+$", "", word, flags=re.UNICODE).casefold()

    @classmethod
    def _merge_window_text(cls, committed: str, candidate: str, max_overlap: int = 8) -> str:
        """Merge rolling-window hypotheses without duplicating speech in the 1-second overlap."""
        committed_words = (committed or "").split()
        candidate_words = (candidate or "").split()
        if not candidate_words:
            return " ".join(committed_words)
        limit = min(max_overlap, len(committed_words), len(candidate_words))
        overlap = 0
        for count in range(limit, 0, -1):
            left = [cls._normal_word(w) for w in committed_words[-count:]]
            right = [cls._normal_word(w) for w in candidate_words[:count]]
            if left == right and all(left):
                overlap = count
                break
        if overlap:
            # Keep punctuation from the re-decoded overlap (the hypothesis may add a comma,
            # sentence boundary or closing quote on a word already in the committed prefix).
            for offset in range(overlap):
                source_word = candidate_words[offset]
                target_index = len(committed_words) - overlap + offset
                punctuation = re.search(r"([,;:!?…]+[»”\"']*)$", source_word)
                if punctuation and not re.search(r"[,;:!?…]+[»”\"']*$", committed_words[target_index]):
                    committed_words[target_index] += punctuation.group(1)
        merged = committed_words + candidate_words[overlap:]
        return " ".join(merged).strip()

    def run(self):
        from transcription.wav_to_text import (
            add_punctuation_and_capitalize, find_whisper_model, preload_whisper_model,
            transcribe_with_whisper,
        )
        work_dir = Path(tempfile.gettempdir()) / "Spiker" / "audio"
        work_dir.mkdir(parents=True, exist_ok=True)
        settings = load_settings(_project_root)
        configured = str(settings.get("dictation_model_path", "") or "").strip()
        model_path = Path(configured).expanduser() if configured else None
        if model_path is None or not model_path.is_file():
            fast_candidates = []
            for models_root in (get_user_data_root(_project_root) / "models", _project_root / "models"):
                if models_root.is_dir():
                    fast_candidates.extend(
                        path for path in models_root.rglob("*.bin")
                        if any(tag in path.name.lower() for tag in ("tiny", "base", "small"))
                        and "faster-whisper" not in {part.lower() for part in path.parts}
                    )
            model_path = (
                sorted(fast_candidates, key=lambda path: (path.name.lower(), str(path).lower()))[0]
                if fast_candidates else find_whisper_model()
            )
        if model_path is None or not Path(model_path).is_file():
            self.failed.emit("Не найдена модель для диктовки. Выберите модель в настройках.")
            return

        chunk_index = 0
        try:
            self.status_changed.emit(
                f"Загружаем модель диктовки: {Path(model_path).name}. Запись продолжается; "
                "после загрузки текст будет появляться по мере декодирования речевых сегментов."
            )
            preload_whisper_model(
                model_path, n_threads=settings.get("threads", 4),
                language=settings.get("language", "ru"), model_slot="dictation",
            )
            if self.isInterruptionRequested():
                raise InterruptedError("Распознавание прервано пользователем.")
            self.status_changed.emit("Модель готова. Анализируем короткие фрагменты с перекрытием…")
            self.ready.emit()
            while not self.isInterruptionRequested():
                try:
                    chunk = self.chunk_queue.get(timeout=0.1)
                except queue_module.Empty:
                    if self.capture_done_event.is_set():
                        break
                    continue
                if self.isInterruptionRequested():
                    break
                if chunk is None:
                    break
                if not chunk:
                    continue
                chunk_index += 1

                # The previous second is intentionally repeated to preserve words across
                # packet edges; duplicate text is removed using the common suffix/prefix.
                tail_bytes = 16000 * 2
                window_pcm = self._tail_pcm + chunk
                self._tail_pcm = chunk[-tail_bytes:] if len(chunk) > tail_bytes else chunk

                fd, temp_name = tempfile.mkstemp(
                    prefix=f"dictation_{chunk_index:04d}_", suffix=".wav", dir=work_dir
                )
                os.close(fd)
                temp_wav = Path(temp_name)
                try:
                    with wave.open(str(temp_wav), "wb") as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(16000)
                        wav_file.writeframes(window_pcm)
                    duration = len(window_pcm) / (16000 * 2)

                    def on_segment(_fraction, window_partial, _segment_text):
                        # Publish decoded speech segments before the entire rolling window finishes.
                        preview = self._merge_window_text(self._committed_text, str(window_partial))
                        if preview:
                            self.text_updated.emit(preview)

                    text = transcribe_with_whisper(
                        temp_wav, Path(model_path),
                        segment_callback=on_segment,
                        duration_seconds=duration,
                        n_threads=settings.get("threads", 4),
                        language=settings.get("language", "ru"),
                        model_slot="dictation",
                        abort_callback=self.isInterruptionRequested,
                    ).strip()
                    if self.isInterruptionRequested():
                        raise InterruptedError("Распознавание прервано пользователем.")
                    if text:
                        self._committed_text = self._merge_window_text(self._committed_text, text)
                        self.text_updated.emit(self._committed_text)
                except RuntimeError as exc:
                    # Silence-only windows are normal in continuous dictation.
                    if "не обнаружил речь" not in str(exc).lower():
                        raise
                finally:
                    temp_wav.unlink(missing_ok=True)
            if self.isInterruptionRequested():
                self.cancelled.emit(self._committed_text)
                return
            result = add_punctuation_and_capitalize(self._committed_text)
            self.succeeded.emit(result)
        except InterruptedError:
            self.cancelled.emit(self._committed_text)
        except Exception as exc:
            logging.getLogger("app.transcription_errors").exception("Live dictation failed")
            self.failed.emit(str(exc))


class SherpaDictationWorker(QThread):
    """True streaming Russian dictation; decodes each microphone frame without WAV files."""
    ready = Signal()
    text_updated = Signal(str)
    text_parts_updated = Signal(str, str)
    status_changed = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, chunk_queue, model_dir: Path, num_threads: int = 2, parent=None, capture_done_event=None):
        super().__init__(parent)
        self.chunk_queue = chunk_queue
        self.capture_done_event = capture_done_event or threading.Event()
        self.model_dir = Path(model_dir)
        self.num_threads = max(1, int(num_threads or 2))

    def cancel(self):
        self.requestInterruption()
        self.capture_done_event.set()
        while True:
            try:
                self.chunk_queue.get_nowait()
            except queue_module.Empty:
                break

    def run(self):
        try:
            from transcription.live_streaming import create_t_one_recognizer, SherpaStreamingSession
            self.status_changed.emit("Загружаем потоковую модель T-one…")
            recognizer = create_t_one_recognizer(self.model_dir, self.num_threads)
            session = SherpaStreamingSession(recognizer, sample_rate=16000)
            self.status_changed.emit("Потоковая модель готова. Речь распознаётся по мере поступления аудио.")
            self.ready.emit()
            last_text = ""
            last_parts = None
            while not self.isInterruptionRequested():
                try:
                    chunk = self.chunk_queue.get(timeout=0.1)
                except queue_module.Empty:
                    if self.capture_done_event.is_set():
                        break
                    continue
                if self.isInterruptionRequested():
                    break
                if chunk is None:
                    break
                preview, endpoint = session.feed_pcm16(chunk)
                if preview and preview != last_text:
                    self.text_updated.emit(preview)
                    last_text = preview
                parts = (session.committed_text, session.partial_text)
                if parts != last_parts:
                    self.text_parts_updated.emit(parts[0], parts[1])
                    last_parts = parts
                if endpoint:
                    self.status_changed.emit("Фраза зафиксирована. Продолжаю слушать…")
            if self.isInterruptionRequested():
                preserved = " ".join(part for part in (session.committed_text, session.partial_text) if part).strip()
                self.cancelled.emit(preserved)
                return
            result = session.finish().strip()
            try:
                from transcription.wav_to_text import add_punctuation_and_capitalize
                result = add_punctuation_and_capitalize(result)
            except Exception:
                pass
            if result:
                self.text_updated.emit(result)
                self.text_parts_updated.emit(result, "")
            self.succeeded.emit(result)
        except Exception as exc:
            logging.getLogger("app.transcription_errors").exception("Sherpa live dictation failed")
            self.failed.emit(str(exc))


class DictationAudioDialog(QDialog):
    """
        Класс DictationAudioDialog представляет собой диалоговое окно для диктовки аудио и его преобразования в текст.

        Атрибуты класса:
        ----------------
        last_save_path : str
            Переменная класса для хранения последнего пути сохранения файла.

        Атрибуты экземпляра:
        --------------------
        ui : Ui_Dialog_dict_audio
            Интерфейс пользовательского диалога.

        main_window : QMainWindow
            Главное окно приложения.

        timer : QTimer
            Таймер для отслеживания времени записи.

        elapsed_time : QTime
            Время, прошедшее с начала записи.

        record_icon_path : str
            Путь к иконке кнопки записи.

        recording_icon_path : str
            Путь к иконке активной кнопки записи.

        recognition : object
            Объект распознавания речи.

        stream : object
            Аудио поток для записи и считывания данных.

        is_recording : bool
            Флаг для управления состоянием записи аудио.

        audio_processor : AudioProcessor
            Объект для обработки аудио в реальном времени.

        Методы:
        -------
        __init__(self, main_window):
            Инициализирует экземпляр класса, устанавливает заголовок окна и подключает сигналы к соответствующим слотам.

        load_model(self):
            Загружает модель распознавания речи и инициализирует аудио поток.

        listen(self):
            Запускает обработку аудио в отдельном потоке.

        save_file_dialog_dict_window(self, line_edit):
            Открывает диалоговое окно для сохранения файла и проверяет наличие текста для сохранения.

        save_text_to_file_dict_window(self, file_name=None):
            Сохраняет текст диктовки в указанный файл.

        toggle_recording(self):
            Переключает состояние записи аудио, запускает или останавливает процесс записи и обновляет интерфейс.

        update_timer(self):
            Обновляет отображаемое время записи каждую секунду.

        show_context_menu(self, position):
            Отображает контекстное меню для прекращения записи при нажатии правой кнопкой мыши на кнопку записи.

        reset_timer(self):
            Сбрасывает таймер записи и обновляет интерфейс.

        back_to_main(self):
            Закрывает текущее окно и возвращает к главному окну приложения.
        """

    last_save_path = ""  # Переменная класса для хранения последнего пути сохранения

    def __init__(self, main_window):
        super(DictationAudioDialog, self).__init__()
        self.ui = Ui_Dialog_dict_audio()
        self.ui.setupUi(self)
        apply_window_theme(self)
        self.main_window = main_window
        self.setWindowTitle("СПИКЕР — Диктовка")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.elapsed_time = QTime(0, 0, 0)

        self.record_icon_path = "../icons/record_btn.svg"
        self.recording_icon_path = "../icons/record_btn_red.svg"

        self.ui.pushButton_back_to_main.clicked.connect(self.back_to_main)
        self.ui.pushButton_ai_process.clicked.connect(self.open_ai_from_dictation)
        self.ui.textEdit_field_to_text_from_audio.textChanged.connect(
            lambda: self.ui.pushButton_ai_process.setEnabled(
                bool(self.ui.textEdit_field_to_text_from_audio.toPlainText().strip())
            )
        )
        self.ui.pushButton_record_start.clicked.connect(self.toggle_recording)
        self.ui.pushButton_reset_recording.clicked.connect(self.reset_recording)
        self.ui.pushButton_record_start.setIcon(QIcon(self.record_icon_path))
        self.ui.pushButton_record_start.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.pushButton_record_start.customContextMenuRequested.connect(self.show_context_menu)

        self.ui.lineEdit_way_to_save_file.mousePressEvent = lambda event: self.save_file_dialog_dict_window(self.ui.lineEdit_way_to_save_file)
        self.ui.pushButton_save_as.clicked.connect(lambda: self.save_file_dialog_dict_window(self.ui.lineEdit_way_to_save_file))

        self.recognition = None
        self.stream = None
        self.audio_interface = None
        self.is_recording = False
        self.audio_processor = None
        self.whisper_mode = False
        self.live_engine = ""
        self.sherpa_model_dir = None
        self.whisper_worker = None
        self.live_chunk_queue = None
        self.live_capture_done = None
        self.vosk_committed_text = ""
        self.vosk_partial_text = ""
        self._clear_after_live_cancel = False
        self._live_cancel_pending = False
        self._pending_live_cancel_text = ""

        self.ui.pushButton_cancel_dictation.clicked.connect(self.abort_live_dictation)
        self.ui.refresh_microphones.clicked.connect(self.refresh_microphones)
        self.refresh_microphones()
        self.ui.pushButton_ai_process.setEnabled(
            bool(self.ui.textEdit_field_to_text_from_audio.toPlainText().strip())
        )

        # Установить начальный текст для поля с текстовыми подсказками пользователю
        self.ui.lineEdit_words_to_dict_info.setEnabled(False)
        self.ui.lineEdit_words_to_dict_info.setText("   Для начала записи нажмите на кнопку справа")

    def open_ai_from_dictation(self):
        text = self.ui.textEdit_field_to_text_from_audio.toPlainText().strip()
        if not text:
            return
        self.main_window.open_ai_processing(text, "Диктовка")

    def _notify_dictation_busy(self, busy: bool):
        callback = getattr(self.main_window, "_dictation_busy_changed", None)
        if callable(callback):
            callback(bool(busy))

    def set_queue_busy(self, busy: bool):
        # Queue/file recognition and dictation use separate Whisper contexts and may run concurrently.
        live_running = self.whisper_worker is not None and self.whisper_worker.isRunning()
        self.ui.pushButton_record_start.setEnabled(not self.is_recording and not live_running)
        if busy:
            self.ui.lineEdit_words_to_dict_info.setToolTip(
                "Очередь работает параллельно. Для этого загружается отдельный контекст модели, что увеличивает расход ОЗУ."
            )
        else:
            self.ui.lineEdit_words_to_dict_info.setToolTip("")

    def refresh_microphones(self):
        if self.is_recording:
            return
        import pyaudio
        from app_config import load_settings
        selected = self.ui.microphone_combo.currentText() or load_settings(_project_root).get('microphone_name', '')
        self.ui.microphone_combo.clear()
        self.ui.microphone_combo.addItem('По умолчанию Windows', None)
        audio = pyaudio.PyAudio()
        try:
            for index in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(index)
                if info.get('maxInputChannels', 0) > 0:
                    api = audio.get_host_api_info_by_index(int(info['hostApi']))['name']
                    label = str(info['name']) + ' · ' + str(api)
                    self.ui.microphone_combo.addItem(label, index)
            index = self.ui.microphone_combo.findText(selected)
            if index >= 0: self.ui.microphone_combo.setCurrentIndex(index)
        finally:
            audio.terminate()

    def load_model(self):
        """Select an explicitly requested engine or the best locally installed live engine."""
        try:
            import pyaudio
            settings = load_settings(_project_root)
            from transcription.live_streaming import resolve_t_one_model, is_sherpa_available
            engine_preference = str(settings.get("dictation_engine", "auto") or "auto").lower()
            configured_whisper = str(settings.get("dictation_model_path", "") or "").strip()
            whisper_path = Path(configured_whisper).expanduser() if configured_whisper else None
            if whisper_path is not None and not whisper_path.is_file():
                whisper_path = None

            sherpa_path = resolve_t_one_model(
                _project_root, str(settings.get("sherpa_model_path", "") or "")
            )
            sherpa_ready = bool(sherpa_path and is_sherpa_available())
            vosk_ready = False
            try:
                import vosk  # noqa: F401
                required = ("am/final.mdl", "graph/HCLr.fst", "graph/Gr.fst", "graph/phones/word_boundary.int")
                vosk_ready = all((Path(model_path) / item).is_file() for item in required)
            except Exception:
                # An on-disk Vosk model without the Python runtime is not a usable
                # engine. Auto mode should continue to the local Whisper fallback.
                vosk_ready = False

            # Auto follows the documented streaming-first order. Select Whisper explicitly
            # in settings when the user prefers window-based dictation.
            if engine_preference == "sherpa" or (engine_preference == "auto" and sherpa_ready):
                if not sherpa_path:
                    raise FileNotFoundError(
                        "Модель потоковой диктовки T-one не найдена. Запустите Install_Live_Dictation.bat."
                    )
                if not is_sherpa_available():
                    raise RuntimeError(
                        "sherpa-onnx не установлен. Запустите Install_Live_Dictation.bat."
                    )
                self.live_engine = "sherpa"
                self.sherpa_model_dir = sherpa_path
                self.whisper_mode = False
                self.recognition = None
            elif engine_preference == "vosk" or (engine_preference == "auto" and not sherpa_ready and vosk_ready):
                if not vosk_ready:
                    raise FileNotFoundError("Полная модель Vosk не найдена в models/vosk.")
                from vosk import KaldiRecognizer
                self.recognition = KaldiRecognizer(get_vosk_model(), 16000)
                self.live_engine = "vosk"
                self.whisper_mode = False
                self.sherpa_model_dir = None
            else:
                if engine_preference == "whisper" and whisper_path is None:
                    raise FileNotFoundError("Выберите локальную модель Whisper для режима Whisper-диктовки.")
                if whisper_path is None:
                    from transcription.wav_to_text import find_whisper_model
                    whisper_path = find_whisper_model()
                if whisper_path is None or not Path(whisper_path).is_file():
                    raise FileNotFoundError(
                        "Не найдена модель диктовки. Установите T-one через Install_Live_Dictation.bat, "
                        "полную модель Vosk или выберите модель Whisper в настройках."
                    )
                self.live_engine = "whisper"
                self.whisper_mode = True
                self.recognition = None
                self.sherpa_model_dir = None

            from app_config import save_settings
            save_settings(_project_root, {'microphone_name': self.ui.microphone_combo.currentText()})
            self.audio_interface = pyaudio.PyAudio()
            # 100 ms PortAudio frames reduce capture-to-decoder latency for online ASR.
            self.stream = self.audio_interface.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=self.ui.microphone_combo.currentData(),
                frames_per_buffer=1600,
                start=False,
            )
            return True
        except Exception as exc:
            if self.stream is not None:
                try:
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            if self.audio_interface is not None:
                try:
                    self.audio_interface.terminate()
                except Exception:
                    pass
                self.audio_interface = None
            QMessageBox.critical(self, "Не удалось запустить диктовку", f"Не удалось подготовить модель или микрофон.\n\n{exc}")
            return False

    def listen(self):
        if self.audio_processor and self.audio_processor.isRunning():
            self.audio_processor.stop()
            self.audio_processor.wait()
        if self.stream is not None:
            try:
                if not self.stream.is_active():
                    self.stream.start_stream()
            except AttributeError:
                self.stream.start_stream()
        live_model = get_vosk_model() if self.live_engine == "vosk" else None
        self.timer.start(1000)
        self.audio_processor = AudioProcessor(
            live_model, self.recognition, self.stream, self.ui,
            use_whisper=self.live_engine == "whisper",
            use_streaming=self.live_engine == "sherpa",
            chunk_queue=self.live_chunk_queue,
            chunk_seconds=2,
            capture_done_event=self.live_capture_done,
        )
        self.audio_processor.level_changed.connect(self.ui.microphone_level.setValue)
        self.audio_processor.recognized_text.connect(self._append_vosk_text)
        self.audio_processor.partial_text.connect(self._set_vosk_partial_text)
        self.audio_processor.finished.connect(self._on_live_capture_finished)
        self.audio_processor.start()

    def _append_vosk_text(self, text):
        if text.strip():
            self.vosk_committed_text = " ".join(part for part in (self.vosk_committed_text, text.strip()) if part)
        self.vosk_partial_text = ""
        self._render_vosk_live_text()

    def _set_vosk_partial_text(self, text):
        self.vosk_partial_text = (text or "").strip()
        self._render_vosk_live_text()

    def _render_vosk_live_text(self):
        live_text = " ".join(part for part in (self.vosk_committed_text, self.vosk_partial_text) if part).strip()
        editor = self.ui.textEdit_field_to_text_from_audio
        scrollbar = editor.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        editor.setPlainText(live_text)
        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())

    def save_file_dialog_dict_window (self, line_edit):                     # Открывает диалоговое окно сохранения файла
        if not self.ui.textEdit_field_to_text_from_audio.toPlainText():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setText("Поле текста пустое")
            msg.setInformativeText("Хотите сохранить пустой файл перед созданием нового?")
            msg.setWindowTitle("Внимание")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

            if msg.exec() == QMessageBox.StandardButton.Yes:  # Если нажата "Сохранить"
                self.save_text_to_file_dict_window()
                return
            else:          # Если отмена сохранения
                return

        file_name, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", self.last_save_path, "Text Files (*.txt)")
        if file_name:
            self.save_text_to_file_dict_window(file_name)

    def save_text_to_file_dict_window(self, file_name=None):   # Сохраняет файл по выбранному пути
        if file_name is None:
            file_name, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", self.last_save_path,"Text Files (*.txt)")
            if not file_name:
                return
        with open(file_name, 'w', encoding='utf-8', newline='') as file:
            file.write(self.ui.textEdit_field_to_text_from_audio.toPlainText())

        # Обновление пути сохраненного файла в GUI приложения
        self.ui.lineEdit_way_to_save_file.setText(file_name)
        self.last_save_path = file_name                         # Обновление последнего пути сохранения

    def toggle_recording(self):
        if not self.is_recording:
            if not self.load_model():
                return
            self.ui.textEdit_field_to_text_from_audio.clear()
            self.vosk_committed_text = ""
            self.vosk_partial_text = ""
            self.ui.textEdit_field_to_text_from_audio.setReadOnly(True)
            self.ui.pushButton_record_start.setIcon(QIcon(self.recording_icon_path))
            self.ui.lineEdit_way_to_save_file.setEnabled(False)
            self.ui.pushButton_save_as.setEnabled(False)
            self.is_recording = True
            self._clear_after_live_cancel = False
            self.ui.pushButton_cancel_dictation.setEnabled(True)
            self.audio_processor = None
            self.live_chunk_queue = None
            self.live_capture_done = threading.Event()
            if self.live_engine in {"whisper", "sherpa"}:
                # Load the recognizer before opening the capture loop. This avoids an
                # unconsumed audio backlog while native models initialize.
                # Both live decoders have a finite ~12 s backlog budget. The Whisper
                # fallback uses six 2 s windows; T-one uses 120 x 100 ms frames.
                self.live_chunk_queue = queue_module.Queue(maxsize=120 if self.live_engine == "sherpa" else 6)
                if self.live_engine == "sherpa":
                    self.whisper_worker = SherpaDictationWorker(
                        self.live_chunk_queue, self.sherpa_model_dir,
                        num_threads=load_settings(_project_root).get("threads", 2), parent=self,
                        capture_done_event=self.live_capture_done,
                    )
                else:
                    self.whisper_worker = WhisperDictationWorker(
                        self.live_chunk_queue, self, capture_done_event=self.live_capture_done
                    )
                self.whisper_worker.ready.connect(self._start_live_audio_capture)
                self.whisper_worker.finished.connect(self._on_live_worker_finished)
                self.whisper_worker.text_updated.connect(self.on_live_dictation_text)
                if self.live_engine == "sherpa":
                    self.whisper_worker.text_parts_updated.connect(self.on_live_dictation_parts)
                self.whisper_worker.status_changed.connect(self.ui.lineEdit_words_to_dict_info.setText)
                self.whisper_worker.succeeded.connect(self.on_whisper_dictation_succeeded)
                self.whisper_worker.failed.connect(self.on_whisper_dictation_failed)
                self.whisper_worker.cancelled.connect(self.on_whisper_dictation_cancelled)
                self.whisper_worker.start()
            else:
                self.listen()
            self._notify_dictation_busy(True)
            if self.live_engine == "sherpa":
                self.ui.lineEdit_words_to_dict_info.setText(
                    "Подготавливается потоковая диктовка T-one. После загрузки модель будет получать аудио пакетами по 100 мс."
                )
            elif self.live_engine == "whisper":
                self.ui.lineEdit_words_to_dict_info.setText(
                    "Подготавливается Whisper. После загрузки запись будет распознаваться окнами по 2 секунды."
                )
            else:
                self.ui.lineEdit_words_to_dict_info.setText(
                    "Идёт потоковая диктовка Vosk. Промежуточная гипотеза обновляется по мере речи."
                )
            return

        self.timer.stop()
        self.ui.pushButton_record_start.setIcon(QIcon(self.record_icon_path))
        self.ui.lineEdit_way_to_save_file.setEnabled(True)
        self.ui.pushButton_save_as.setEnabled(True)
        self.is_recording = False
        processor = self.audio_processor
        if processor is not None:
            processor.stop()
            processor.wait()
        elif self.live_engine in {"whisper", "sherpa"} and self.live_capture_done is not None:
            self.live_capture_done.set()
        read_error = processor.read_error if processor is not None else None
        if self.audio_interface is not None:
            try:
                self.audio_interface.terminate()
            except Exception:
                pass
            self.audio_interface = None
        self.stream = None

        if self.live_engine in {"whisper", "sherpa"}:
            self.ui.lineEdit_words_to_dict_info.setText(
                "Запись остановлена. Завершаем обработку накопленного аудио…"
            )
            self.ui.pushButton_record_start.setEnabled(False)
            self.ui.pushButton_save_as.setEnabled(False)
            self.ui.pushButton_cancel_dictation.setEnabled(True)
            # The capture thread signals completion after putting its final remainder
            # on the queue. Keep busy state until the decoder drains queued frames.
        else:
            try:
                if self.recognition is not None:
                    final_json = json.loads(self.recognition.FinalResult())
                    final_text = str(final_json.get("text", "") or "").strip()
                    if final_text:
                        self._append_vosk_text(final_text)
            except Exception:
                logging.getLogger("app.transcription_errors").exception("Vosk final result failed")
            self.vosk_partial_text = ""
            self._render_vosk_live_text()
            self.ui.textEdit_field_to_text_from_audio.setReadOnly(False)
            if read_error:
                QMessageBox.warning(self, "Ошибка микрофона", read_error)
            self.ui.lineEdit_words_to_dict_info.setText("Запись остановлена. Можно начать новую.")
            self.ui.pushButton_cancel_dictation.setEnabled(False)
            self._notify_dictation_busy(False)

    def _start_live_audio_capture(self):
        """Start microphone capture only after the selected live decoder is ready."""
        if not self.is_recording:
            if self.live_capture_done is not None:
                self.live_capture_done.set()
            return
        self.listen()

    def _close_microphone_resources(self):
        """Release PortAudio resources after capture has stopped."""
        if self.audio_interface is not None:
            try:
                self.audio_interface.terminate()
            except Exception:
                logging.getLogger("app.transcription_errors").exception("Could not terminate microphone interface")
            self.audio_interface = None
        self.stream = None

    def abort_live_dictation(self, clear_text: bool = False):
        """Force-stop capture/decoding, waiting for both QThreads before releasing state."""
        processor = self.audio_processor
        worker = self.whisper_worker
        processor_running = bool(processor is not None and processor.isRunning())
        worker_running = bool(worker is not None and worker.isRunning())
        if not self.is_recording and not processor_running and not worker_running:
            if clear_text:
                self.reset_timer()
                self.ui.lineEdit_way_to_save_file.clear()
                self.last_save_path = ""
                self.ui.textEdit_field_to_text_from_audio.setReadOnly(False)
                self.ui.pushButton_cancel_dictation.setEnabled(False)
                self.ui.pushButton_record_start.setEnabled(True)
                self.ui.pushButton_save_as.setEnabled(True)
                self.ui.lineEdit_way_to_save_file.setEnabled(True)
                self.ui.pushButton_record_start.setIcon(QIcon(self.record_icon_path))
                self.ui.lineEdit_words_to_dict_info.setText("Запись сброшена. Можно начать новую.")
            return

        self._clear_after_live_cancel = bool(clear_text)
        self._live_cancel_pending = True
        self._pending_live_cancel_text = self.ui.textEdit_field_to_text_from_audio.toPlainText()
        self.is_recording = False
        self.timer.stop()
        self.ui.pushButton_record_start.setEnabled(False)
        self.ui.pushButton_save_as.setEnabled(False)
        self.ui.pushButton_cancel_dictation.setEnabled(False)
        self.ui.lineEdit_way_to_save_file.setEnabled(True)
        self.ui.lineEdit_words_to_dict_info.setText("Прерываем захват и распознавание…")

        if processor is not None and processor.isRunning():
            processor.stop(discard_pending=True)
            processor.wait(2500)
        if self.live_capture_done is not None:
            self.live_capture_done.set()

        # Cancel the decoder after capture was asked to stop. Its worker drains no more
        # audio, and its QThread.finished event participates in the same finalization gate.
        if worker is not None and worker.isRunning():
            try:
                worker.cancel()
            except Exception:
                logging.getLogger("app.transcription_errors").exception(
                    "Could not request live decoder cancellation"
                )

        self._maybe_finish_live_cancellation()

    def _maybe_finish_live_cancellation(self):
        """Finalize only after microphone and decoder threads have actually exited."""
        if not self._live_cancel_pending:
            return
        processor = self.audio_processor
        worker = self.whisper_worker
        if processor is not None and processor.isRunning():
            return
        if worker is not None and worker.isRunning():
            return
        if processor is not None:
            self.audio_processor = None
        if worker is not None:
            self.whisper_worker = None
        preserved = self._pending_live_cancel_text
        self._finish_live_cancellation(preserved)

    def _on_live_capture_finished(self):
        processor = self.sender()
        if processor is self.audio_processor and not self.is_recording and not self._live_cancel_pending:
            self.audio_processor = None
        self._maybe_finish_live_cancellation()

    def _finish_live_cancellation(self, preserved_text: str = ""):
        self._live_cancel_pending = False
        self._pending_live_cancel_text = ""
        self.is_recording = False
        self.timer.stop()
        self._close_microphone_resources()
        worker = self.whisper_worker
        worker_still_running = bool(worker is not None and worker.isRunning())
        processor = self.audio_processor
        capture_still_running = bool(processor is not None and processor.isRunning())
        if processor is not None and not capture_still_running:
            self.audio_processor = None
        if not worker_still_running:
            self.whisper_worker = None
        self.live_chunk_queue = None
        self.live_capture_done = None
        all_workers_stopped = not (worker_still_running or capture_still_running)
        self.ui.pushButton_record_start.setEnabled(all_workers_stopped)
        self.ui.pushButton_record_start.setIcon(QIcon(self.record_icon_path))
        self.ui.pushButton_cancel_dictation.setEnabled(False)
        self.ui.pushButton_save_as.setEnabled(True)
        self.ui.lineEdit_way_to_save_file.setEnabled(True)
        self.ui.textEdit_field_to_text_from_audio.setReadOnly(False)
        if self._clear_after_live_cancel:
            self._clear_after_live_cancel = False
            self.reset_timer()
            self.ui.lineEdit_way_to_save_file.clear()
            self.last_save_path = ""
            self.ui.lineEdit_words_to_dict_info.setText("Запись сброшена и распознавание прервано.")
        else:
            self.ui.textEdit_field_to_text_from_audio.setPlainText(str(preserved_text or ""))
            self.ui.lineEdit_words_to_dict_info.setText("Распознавание прервано. Уже полученный текст сохранён в поле.")
        self._notify_dictation_busy(False)

    def _on_live_worker_finished(self):
        worker = self.sender()
        if worker is self.whisper_worker:
            self.whisper_worker = None
        if self._live_cancel_pending:
            self._maybe_finish_live_cancellation()
        elif not self.is_recording:
            self.ui.pushButton_record_start.setEnabled(True)

    def on_whisper_dictation_cancelled(self, text):
        self._pending_live_cancel_text = str(text or self._pending_live_cancel_text or "")
        self._maybe_finish_live_cancellation()

    def on_live_dictation_text(self, text):
        # Stable phrases and the current hypothesis are rendered from the live engine.
        vertical = self.ui.textEdit_field_to_text_from_audio.verticalScrollBar()
        was_at_bottom = vertical.value() >= vertical.maximum() - 4
        self.ui.textEdit_field_to_text_from_audio.setPlainText(text)
        if was_at_bottom:
            vertical.setValue(vertical.maximum())

    def on_live_dictation_parts(self, committed_text, partial_text):
        """Keep stable phrases distinct from the currently changing speech hypothesis."""
        parts = []
        committed = str(committed_text or "").strip()
        partial = str(partial_text or "").strip()
        if committed:
            parts.append(committed)
        if partial:
            parts.append("… " + partial)
        vertical = self.ui.textEdit_field_to_text_from_audio.verticalScrollBar()
        was_at_bottom = vertical.value() >= vertical.maximum() - 4
        self.ui.textEdit_field_to_text_from_audio.setPlainText("\n\n".join(parts))
        if was_at_bottom:
            vertical.setValue(vertical.maximum())

    def on_whisper_dictation_succeeded(self, text):
        self.is_recording = False
        self.timer.stop()
        self.ui.pushButton_record_start.setIcon(QIcon(self.record_icon_path))
        self.ui.lineEdit_way_to_save_file.setEnabled(True)
        self.ui.textEdit_field_to_text_from_audio.setReadOnly(False)
        capture_error = getattr(self.audio_processor, "read_error", None) if self.audio_processor else None
        # A decoder can finish because the capture thread hit its backlog limit or a
        # microphone read error. Close the still-open device so the next take can start.
        if self.audio_interface is not None:
            try:
                if self.stream is not None and self.stream.is_active():
                    self.stream.stop_stream()
                if self.stream is not None:
                    self.stream.close()
            except Exception:
                logging.getLogger("app.transcription_errors").exception("Could not close dictation microphone")
        self._close_microphone_resources()
        if text.strip():
            self.ui.textEdit_field_to_text_from_audio.setPlainText(text)
        if capture_error:
            self.ui.lineEdit_words_to_dict_info.setText(
                "Диктовка остановлена: распознаватель не успевал обрабатывать аудио. "
                "Сохранён текст всех фрагментов, которые удалось обработать."
            )
            QMessageBox.warning(self, "Перегрузка потоковой диктовки", capture_error)
        elif text.strip():
            engine_label = {"sherpa": "T-one", "whisper": "Whisper", "vosk": "Vosk"}.get(self.live_engine, "Движок")
            self.ui.lineEdit_words_to_dict_info.setText(
                f"Готово ({engine_label}). Распознанный текст можно исправить и сохранить."
            )
        else:
            self.ui.lineEdit_words_to_dict_info.setText(
                "Распознавание завершено, но речь не обнаружена. Можно начать новую запись."
            )
        self.ui.pushButton_record_start.setEnabled(not (self.whisper_worker is not None and self.whisper_worker.isRunning()))
        self.ui.pushButton_cancel_dictation.setEnabled(False)
        self.ui.pushButton_save_as.setEnabled(True)
        self.live_chunk_queue = None
        self.live_capture_done = None
        self._notify_dictation_busy(False)

    def on_whisper_dictation_failed(self, message):
        # A model-load/runtime failure must also stop microphone capture; otherwise the
        # producer would keep queueing audio without a consumer.
        if self.is_recording:
            self.timer.stop()
            self.is_recording = False
            processor = self.audio_processor
            if processor is not None:
                processor.stop()
                processor.wait(2500)
            elif self.live_capture_done is not None:
                self.live_capture_done.set()
            self._close_microphone_resources()
            self.ui.pushButton_record_start.setIcon(QIcon(self.record_icon_path))
        self.timer.stop()
        self.ui.textEdit_field_to_text_from_audio.setReadOnly(False)
        QMessageBox.critical(self, "Ошибка потокового распознавания", message)
        self.ui.lineEdit_words_to_dict_info.setText("Ошибка потокового распознавания. Уже показанный текст сохранён в поле.")
        self.ui.pushButton_record_start.setEnabled(not (self.whisper_worker is not None and self.whisper_worker.isRunning()))
        self.ui.pushButton_cancel_dictation.setEnabled(False)
        self.ui.pushButton_save_as.setEnabled(True)
        self.live_chunk_queue = None
        self.live_capture_done = None
        self._notify_dictation_busy(False)

    def update_timer(self):                                  # Обновление таймера по надиктовке
        self.elapsed_time = self.elapsed_time.addSecs(1)
        self.ui.label_time_audio.setText(self.elapsed_time.toString("hh:mm:ss"))


    def show_context_menu(self, position):           # Отображение диалогового окна о прекращении записи
        if self.ui.label_time_audio.text() != "00:00:00" and not self.timer.isActive():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("Прекратить текущую запись?")
            msg.setWindowTitle("Прекратить запись")
            yes_button = msg.addButton("Да", QMessageBox.YesRole)
            no_button = msg.addButton("Нет", QMessageBox.NoRole)
            msg.exec()
            if msg.clickedButton() == yes_button:
                self.reset_timer()


    def reset_recording(self):
        """Reset the take; actively cancel capture/decoding rather than silently refusing."""
        worker_running = self.whisper_worker is not None and self.whisper_worker.isRunning()
        capture_running = self.audio_processor is not None and self.audio_processor.isRunning()
        if self.is_recording or worker_running or capture_running:
            self.abort_live_dictation(clear_text=True)
            return
        self.ui.textEdit_field_to_text_from_audio.setReadOnly(False)
        self.reset_timer()
        self.ui.pushButton_record_start.setEnabled(True)
        self.ui.pushButton_cancel_dictation.setEnabled(False)
        self.ui.pushButton_record_start.setIcon(QIcon(self.record_icon_path))
        self.ui.lineEdit_words_to_dict_info.setText("Запись сброшена. Можно начать новую.")
        self.ui.lineEdit_way_to_save_file.clear()
        self.last_save_path = ""

    def reset_timer(self):                    # Сбрасывает таймер и отчищает поле для надиктовки
        self.elapsed_time = QTime(0, 0, 0)
        self.ui.label_time_audio.setText(self.elapsed_time.toString("hh:mm:ss"))
        self.ui.lineEdit_way_to_save_file.setEnabled(True)
        self.ui.pushButton_save_as.setEnabled(True)
        self.ui.textEdit_field_to_text_from_audio.clear()
        self.ui.lineEdit_words_to_dict_info.setText("   Для начала записи нажмите на кнопку справа")

    def back_to_main(self):
        self.main_window.show_home_tab()
# ----------------------------------------------------------------------------------------------------------------------


# --------------------------------------------- ИНФОРМАЦИЯ -------------------------------------------------------------
class InfoMenu(QDialog):
    """
            Класс InfoMenu представляет собой диалоговое окно с информацией о программе.

            Атрибуты экземпляра:
            --------------------
            ui : Ui_Dialog_info
                Интерфейс пользовательского диалога.

            main_window : QMainWindow
                Главное окно приложения.

            Методы:
            -------
            __init__(self, main_window):
                Инициализирует экземпляр класса, устанавливает заголовок окна и подключает сигнал кнопки к слоту.

            back_to_main(self):
                Закрывает текущее окно и возвращает к главному окну приложения.
            """
    def __init__(self, main_window):
        super(InfoMenu, self).__init__()
        self.ui = Ui_Dialog_info()
        self.ui.setupUi(self)
        apply_window_theme(self)
        self.main_window = main_window
        self.setWindowTitle("СПИКЕР — Справка")

        self.ui.pushButton_back_to_main.clicked.connect(self.back_to_main)
        self.ui.set_compact(self.width() < 860, self.width())

    def resizeEvent(self, event):
        self.ui.set_compact(self.width() < 860, self.width())
        super().resizeEvent(event)

    def back_to_main(self):
        self.main_window.show_home_tab()
# ----------------------------------------------------------------------------------------------------------------------


# --------------------------------------------- ГЛАВНОЕ ОКНО -----------------------------------------------------------
class MainWindow(QMainWindow):
    """Single-window Spiker shell: secondary pages are created on demand for a fast start."""

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("СПИКЕР")

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("appTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        self.tabs.setTabsClosable(False)
        self.tabs.tabBar().hide()
        self.home_page = self.ui.centralwidget
        self.home_page.setParent(None)
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self.home_page, "Главная")
        self.ui.update_responsive_icons(self.width(), self.height())

        self.queue_page = None
        self.queue_is_busy = False
        self.dictation_is_busy = False
        self.dictation_page = None
        self.settings_page = None
        self.info_menu = None
        self.user_guide_page = None
        self.ai_page = None
        self.speech_page = None
        self._closing = False
        try:
            self._drafts = json.loads((get_user_data_root(_project_root) / 'data/last-session.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self._drafts = {}

        self.ui.pushButton_choose_file.clicked.connect(self.open_audio_file_to_text_window)
        self.ui.pushButton_record_audio.clicked.connect(self.open_dictation_audio_dialog)
        self.ui.pushButton_settings.clicked.connect(self.open_settings)
        self.ui.pushButton_ai_card.clicked.connect(lambda: self.open_ai_processing())
        self.ui.pushButton_speech.clicked.connect(lambda: self.open_speech())
        self.ui.pushButton_about_prog.clicked.connect(self.open_info_menu)
        self.ui.pushButton_user_guide.clicked.connect(self.open_user_guide)
        self.statusBar().showMessage("Готово к работе")

    def resizeEvent(self, event):
        if hasattr(self.ui, "dictation_icon") and hasattr(self.ui, "file_icon"):
            self.ui.update_responsive_icons(self.width(), self.height())
        super().resizeEvent(event)

    def _ensure_queue_page(self):
        if self.queue_page is None:
            self.queue_page = QueuePage(_project_root, FileTranscriptionWorker, self.show_home_tab, self.tabs)
            self.queue_page.busy_changed = self._queue_busy_changed
            self.queue_page.external_busy_check = lambda: self.dictation_is_busy
            self.queue_page.ai_requested.connect(self.open_ai_processing)
            self.queue_page.speech_requested.connect(self.open_speech)
            self.tabs.addTab(self.queue_page, "Очередь")
            self.queue_page._render_table()
        return self.queue_page

    def _ensure_ai_page(self):
        if self.ai_page is None:
            self.ai_page = AIProcessingPage(_project_root, self.show_home_tab, self.tabs)
            self.tabs.addTab(self.ai_page, "ИИ-обработка")
            self.ai_page.source_editor.setPlainText(self._drafts.get('ai_source', ''))
            self.ai_page.output_editor.setPlainText(self._drafts.get('ai_result', ''))
        return self.ai_page

    def open_ai_processing(self, source_text="", source_name="", speaker_context=None):
        page = self._ensure_ai_page()
        if source_text:
            page.set_source_text(source_text, source_name, speaker_context=speaker_context)
        self.tabs.setCurrentWidget(page)
        self.statusBar().showMessage("ИИ-обработка текста")

    def _ensure_dictation_page(self):
        if self.dictation_page is None:
            self.dictation_page = DictationAudioDialog(self)
            self.dictation_page.setWindowFlags(Qt.WindowType.Widget)
            self.dictation_page.setParent(self.tabs)
            self.dictation_page.set_queue_busy(self.queue_is_busy)
            self.tabs.addTab(self.dictation_page, "Диктовка")
            self.dictation_page.ui.textEdit_field_to_text_from_audio.setPlainText(self._drafts.get('dictation', ''))
        return self.dictation_page

    def _ensure_settings_page(self):
        if self.settings_page is None:
            self.settings_page = SettingsPage(
                _project_root, self.show_home_tab, get_whisper_model_path,
                set_whisper_model_path_lazy, self.tabs
            )
            self.tabs.addTab(self.settings_page, "Настройки")
        return self.settings_page

    def _ensure_info_page(self):
        if self.info_menu is None:
            self.info_menu = InfoMenu(self)
            self.info_menu.setWindowFlags(Qt.WindowType.Widget)
            self.info_menu.setParent(self.tabs)
            self.tabs.addTab(self.info_menu, "Справка")
        return self.info_menu

    def _queue_busy_changed(self, busy: bool):
        self.queue_is_busy = bool(busy)
        if self.settings_page is not None:
            self.settings_page.set_busy(self.queue_is_busy or self.dictation_is_busy)
        if self.dictation_page is not None:
            self.dictation_page.set_queue_busy(self.queue_is_busy)

    def _dictation_busy_changed(self, busy: bool):
        self.dictation_is_busy = bool(busy)
        if self.settings_page is not None:
            self.settings_page.set_busy(self.queue_is_busy or self.dictation_is_busy)
        if self.queue_page is not None:
            self.queue_page._render_table()


    def show_home_tab(self):
        self.tabs.setCurrentWidget(self.home_page)
        self.statusBar().showMessage("Готово к работе")

    def show_queue_tab(self):
        page = self._ensure_queue_page()
        self.tabs.setCurrentWidget(page)
        self.statusBar().showMessage("Очередь обработки")

    def open_audio_file_to_text_window(self):
        # The file action opens a non-modal queue page; the user may add more files while it runs.
        page = self._ensure_queue_page()
        self.tabs.setCurrentWidget(page)
        self.statusBar().showMessage("Очередь обработки")
        QTimer.singleShot(80, page.add_files_dialog)

    def open_dictation_audio_dialog(self):
        self.tabs.setCurrentWidget(self._ensure_dictation_page())

    def open_settings(self):
        page = self._ensure_settings_page()
        page.set_busy(self.queue_is_busy or self.dictation_is_busy)
        page.refresh_models()
        self.tabs.setCurrentWidget(page)

    def open_info_menu(self):
        self.tabs.setCurrentWidget(self._ensure_info_page())

    def _ensure_user_guide_page(self):
        if self.user_guide_page is None:
            self.user_guide_page = UserGuidePage(self, self.tabs)
            self.tabs.addTab(self.user_guide_page, "Обучение")
        return self.user_guide_page

    def open_user_guide(self):
        page = self._ensure_user_guide_page()
        self.tabs.setCurrentWidget(page)
        self.statusBar().showMessage("Инструкция по работе с приложением")

    def open_speech(self, text=None, speaker_voices=None):
        if self.speech_page is None:
            from UI.Speech_page import SpeechPage
            self.speech_page = SpeechPage(_project_root, self.show_home_tab, self.tabs)
            self.tabs.addTab(self.speech_page, 'Озвучка')
            self.speech_page.editor.setPlainText(self._drafts.get('speech', ''))
        if text is not None:
            self.speech_page.editor.setPlainText(text)
        if speaker_voices:
            self.speech_page.set_speaker_voices(speaker_voices)
        self.tabs.setCurrentWidget(self.speech_page)

    def closeEvent(self, event):
        from shutdown import begin_shutdown
        begin_shutdown(self, event, _project_root)


def _fit_main_window_to_available_screen(app, window):
    """Keep the main window inside the usable screen area at Windows DPI scaling."""
    try:
        screen = app.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        available_width = max(1, int(available.width()))
        available_height = max(1, int(available.height()))

        # Open maximized to the usable area so the start dashboard is visible at once.
        # Its layout compacts on short screens instead of exposing a vertical scrollbar.
        min_width = min(840, max(480, available_width - 32))
        min_height = min(620, max(420, available_height - 48))
        target_width = max(min_width, available_width - 24)
        target_height = max(min_height, available_height - 24)
        window.setMinimumSize(min_width, min_height)
        window.resize(target_width, target_height)

        frame = window.frameGeometry()
        frame.moveCenter(available.center())
        window.move(frame.topLeft())
    except Exception:
        logging.getLogger("startup").exception("Could not fit main window to screen; using default geometry")


# --------------------------------------------- ЗАПУСК ПРИЛОЖЕНИЯ ------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("СПИКЕР")
    app.setStyleSheet(APP_STYLESHEET)
    # Windows taskbar identity/icon must be set before creating the top-level window.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Spiker.Desktop")
        except Exception:
            pass
    app_icon = QIcon(str(_project_root / "Spiker.ico"))
    app.setWindowIcon(app_icon)
    window = MainWindow()
    window.setWindowIcon(app_icon)
    _fit_main_window_to_available_screen(app, window)
    window.show()
    sys.exit(app.exec())
# ----------------------------------------------------------------------------------------------------------------------
