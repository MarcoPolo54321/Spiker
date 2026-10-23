"""Local transcription with Whisper (preferred when a local ggml model exists) or Vosk."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import wave
import threading
import gc
from pathlib import Path
from typing import Callable

from vosk import KaldiRecognizer, Model

PROJECT_ROOT = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2])
_VOSK_PREFERRED = PROJECT_ROOT / "models" / "vosk" / "vosk-model-small-ru-0.22"
_VOSK_LEGACY = PROJECT_ROOT / "model" / "vosk-model-small-ru-0.22"
try:
    from model_paths import resolve_vosk_model_path
    VOSK_MODEL_PATH = resolve_vosk_model_path(PROJECT_ROOT)
except Exception:
    # Backwards-compatible fallback for direct use outside the regular launcher.
    VOSK_MODEL_PATH = _VOSK_PREFERRED if _VOSK_PREFERRED.exists() or not _VOSK_LEGACY.exists() else _VOSK_LEGACY
WHISPER_MODEL_CANDIDATES = (
    PROJECT_ROOT / "models" / "whisper" / "ggml-small.bin",
    PROJECT_ROOT / "models" / "whisper" / "ggml-base.bin",
    PROJECT_ROOT / "models" / "whisper" / "ggml-tiny.bin",
    PROJECT_ROOT / "models" / "whisper" / "ggml-medium.bin",
    PROJECT_ROOT / "models" / "ggml-small.bin",
    PROJECT_ROOT / "models" / "ggml-base.bin",
    PROJECT_ROOT / "models" / "ggml-tiny.bin",
    PROJECT_ROOT / "models" / "ggml-medium.bin",
    PROJECT_ROOT / "ggml-small.bin",
    PROJECT_ROOT / "ggml-medium.bin",
)
WHISPER_MODEL_CONFIG = PROJECT_ROOT / "models" / "whisper" / "model_path.txt"
_TEMP_ROOT = Path(tempfile.gettempdir()) / "Spiker" / "audio"
# Keep the loaded Whisper model alive between files to avoid reloading ~1.5 GB each time.
_WHISPER_MODEL_CACHE: dict[str, object] = {}
_WHISPER_MODEL_LOCK = threading.RLock()
_WHISPER_SLOT_LOCKS: dict[str, threading.RLock] = {}
LOGGER = __import__("logging").getLogger("processing.whisper")


def set_whisper_model_path(model_path: str | Path) -> Path:
    """Remember a user-selected local Whisper model without copying a multi-GB file."""
    path = Path(model_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Файл модели не найден: {path}")
    if path.stat().st_size < 10 * 1024 * 1024:
        raise ValueError(
            f"Выбранный файл слишком маленький для модели Whisper: {path}\n"
            "Проверьте, что это настоящая модель Whisper, а не архив или HTML-страница."
        )
    WHISPER_MODEL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    previous = ""
    try:
        previous = WHISPER_MODEL_CONFIG.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    WHISPER_MODEL_CONFIG.write_text(str(path), encoding="utf-8")
    if previous and Path(previous).expanduser().resolve() != path:
        with _WHISPER_MODEL_LOCK:
            for key in [key for key in _WHISPER_MODEL_CACHE if key.split("|", 1)[1].startswith(str(previous))]:
                _WHISPER_MODEL_CACHE.pop(key, None)
        gc.collect()
    return path


def find_whisper_model() -> Path | None:
    """Find the configured/local Whisper model; never download one silently."""
    candidates = []
    try:
        saved = WHISPER_MODEL_CONFIG.read_text(encoding="utf-8").strip()
        if saved:
            candidates.append(Path(saved).expanduser())
    except OSError:
        pass
    candidates.extend(WHISPER_MODEL_CANDIDATES)
    # Discover additional Whisper models under ./models without downloading anything.
    models_root = PROJECT_ROOT / "models"
    if models_root.is_dir():
        try:
            candidates.extend(sorted(
                (item for item in models_root.rglob("*.bin") if item.is_file()),
                key=lambda item: (
                    0 if any(tag in item.name.lower() for tag in ("tiny", "base", "small")) else
                    1 if "medium" in item.name.lower() else 2,
                    item.name.lower(),
                ),
            ))
        except OSError:
            pass

    checked = set()
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
            if candidate in checked:
                continue
            checked.add(candidate)
            if candidate.is_file():
                if candidate.stat().st_size < 10 * 1024 * 1024:
                    LOGGER.warning("Ignoring suspiciously small Whisper model candidate: %s", candidate)
                    continue
                return candidate
        except OSError:
            continue
    return None


def preload_whisper_model(
    model_path: str | Path,
    n_threads: int | None = None,
    language: str = "ru",
    model_slot: str = "file",
) -> None:
    """Load and cache a native model in the selected workflow slot without decoding audio."""
    try:
        from pywhispercpp.model import Model as WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Библиотека pywhispercpp не установлена. Запустите Launch_Spiker.bat и проверьте logs\\install.log."
        ) from exc
    path = Path(model_path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size < 10 * 1024 * 1024:
        raise FileNotFoundError(f"Локальная модель Whisper не найдена или повреждена: {path}")
    default_threads = max(1, min((os.cpu_count() or 4) - 1, 4))
    threads = max(1, min(int(n_threads or default_threads), os.cpu_count() or 64))
    language = language if language in {"ru", "en", "auto"} else "ru"
    model_slot = model_slot if model_slot in {"file", "dictation"} else "file"
    cache_key = f"{model_slot}|{path}|threads={threads}|language={language}"
    with _WHISPER_MODEL_LOCK:
        slot_lock = _WHISPER_SLOT_LOCKS.setdefault(model_slot, threading.RLock())
    with slot_lock:
        with _WHISPER_MODEL_LOCK:
            if cache_key in _WHISPER_MODEL_CACHE:
                return
            for stale_key in [key for key in _WHISPER_MODEL_CACHE if key.startswith(model_slot + "|")]:
                _WHISPER_MODEL_CACHE.pop(stale_key, None)
            gc.collect()
            native_log = PROJECT_ROOT / "logs" / f"whisper_native_{model_slot}.log"
            native_log.parent.mkdir(parents=True, exist_ok=True)
            _WHISPER_MODEL_CACHE[cache_key] = WhisperModel(
                str(path),
                language=language,
                n_threads=threads,
                print_realtime=False,
                print_progress=False,
                no_context=False,
                redirect_whispercpp_logs_to=str(native_log),
                context_params={"use_gpu": False, "flash_attn": False},
            )


def transcribe_with_whisper(
    source: Path,
    model_path: Path,
    segment_callback: Callable[[float, str, str], None] | None = None,
    abort_callback: Callable[[], bool] | None = None,
    stage_callback: Callable[[str], None] | None = None,
    duration_seconds: float | None = None,
    n_threads: int | None = None,
    language: str = "ru",
    model_slot: str = "file",
    pause_callback: Callable[[], bool] | None = None,
    timestamp_callback: Callable[[dict], None] | None = None,
) -> str:
    """Transcribe a prepared mono 16 kHz WAV with segment streaming and cancellation.

    The model is cached between files (as in the reference app's long-lived service).
    pywhispercpp calls ``new_segment_callback`` as each segment is decoded and supports
    ``abort_callback`` to stop an in-flight recognition run.
    """
    try:
        from pywhispercpp.model import Model as WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Библиотека pywhispercpp не установлена. Запустите Launch_Spiker.bat "
            "и проверьте logs\\install.log."
        ) from exc

    source = Path(source).expanduser().resolve()
    model_path = Path(model_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Подготовленный WAV-файл не найден: {source}")
    if not model_path.is_file() or model_path.stat().st_size < 10 * 1024 * 1024:
        raise FileNotFoundError(f"Локальная модель Whisper не найдена или повреждена: {model_path}")

    started = time.perf_counter()
    default_threads = max(1, min((os.cpu_count() or 4) - 1, 4))
    threads = max(1, min(int(n_threads or default_threads), os.cpu_count() or 64))
    language = language if language in {"ru", "en", "auto"} else "ru"
    model_slot = model_slot if model_slot in {"file", "dictation"} else "file"
    cache_key = f"{model_slot}|{model_path}|threads={threads}|language={language}"
    partial_parts: list[str] = []
    last_progress_second = -1.0

    def is_aborted() -> bool:
        try:
            return bool(abort_callback and abort_callback())
        except Exception:
            return False

    try:
        if stage_callback:
            stage_callback("Загружаем модель Whisper… При первом запуске это может занять время.")

        with _WHISPER_MODEL_LOCK:
            slot_lock = _WHISPER_SLOT_LOCKS.setdefault(model_slot, threading.RLock())

        # One native context per workflow: file queue and live dictation can run independently.
        # Reuse the context for subsequent tasks within the same slot to avoid repeated model loads.
        with slot_lock:
            with _WHISPER_MODEL_LOCK:
                whisper = _WHISPER_MODEL_CACHE.get(cache_key)
                if whisper is None:
                    for stale_key in [key for key in _WHISPER_MODEL_CACHE if key.startswith(model_slot + "|")]:
                        _WHISPER_MODEL_CACHE.pop(stale_key, None)
                    gc.collect()
                    native_log = PROJECT_ROOT / "logs" / f"whisper_native_{model_slot}.log"
                    native_log.parent.mkdir(parents=True, exist_ok=True)
                    whisper = WhisperModel(
                        str(model_path),
                        language=language,
                        n_threads=threads,
                        print_realtime=False,
                        print_progress=False,
                        no_context=False,
                        redirect_whispercpp_logs_to=str(native_log),
                        context_params={"use_gpu": False, "flash_attn": False},
                    )
                    _WHISPER_MODEL_CACHE[cache_key] = whisper

            if stage_callback:
                stage_callback("Распознаём речь; готовые фрагменты будут появляться по мере обработки…")

            def on_segment(segment) -> None:
                nonlocal last_progress_second
                text = str(getattr(segment, "text", "") or "").strip()
                if not text:
                    return
                partial_parts.append(text)
                # whisper.cpp Segment.t0/t1 are timestamps in centiseconds.
                try:
                    end_seconds = max(0.0, float(getattr(segment, "t1", 0)) / 100.0)
                except (TypeError, ValueError):
                    end_seconds = 0.0
                try:
                    start_seconds = max(0.0, float(getattr(segment, "t0", 0)) / 100.0)
                except (TypeError, ValueError):
                    start_seconds = max(0.0, end_seconds - 1.0)
                if timestamp_callback:
                    try:
                        timestamp_callback({"start": start_seconds, "end": max(start_seconds, end_seconds), "text": text})
                    except Exception:
                        LOGGER.exception("Timestamp callback failed while decoding a segment")
                if segment_callback:
                    denominator = max(0.1, float(duration_seconds or 0.0))
                    fraction = min(0.99, max(0.0, end_seconds / denominator)) if duration_seconds else 0.0
                    try:
                        segment_callback(fraction, " ".join(partial_parts), text)
                    except Exception:
                        LOGGER.exception("Progress callback failed while decoding a segment")
                if end_seconds > last_progress_second:
                    last_progress_second = end_seconds
                    LOGGER.info("Whisper segment: %.2fs, chars=%d", end_seconds, len(text))

            def wait_if_paused() -> None:
                notified = False
                while pause_callback is not None:
                    try:
                        paused = bool(pause_callback())
                    except Exception:
                        paused = False
                    if not paused or is_aborted():
                        break
                    if not notified and stage_callback:
                        stage_callback("Пауза: завершается текущий фрагмент; распознавание остановлено на границе сегмента.")
                        notified = True
                    time.sleep(0.15)
                if notified and stage_callback and not is_aborted():
                    stage_callback("Продолжаем распознавание…")

            # Check pause only at segment boundaries; abort_callback can stop native inference.
            original_on_segment = on_segment
            def on_segment_with_pause(segment):
                original_on_segment(segment)
                wait_if_paused()

            segments = whisper.transcribe(
                str(source),
                new_segment_callback=on_segment_with_pause,
                abort_callback=is_aborted,
                no_context=(model_slot == "dictation"),
                print_progress=False,
                print_realtime=False,
            ) or []

        if is_aborted():
            raise InterruptedError("Транскрибация отменена пользователем.")
        parts = [str(getattr(segment, "text", "") or "").strip() for segment in segments]
        text = " ".join(part for part in parts if part).strip()
        if not text:
            raise RuntimeError(
                "Whisper не обнаружил речь в файле. Проверьте звук, громкость и выбранную дорожку."
            )
        elapsed = time.perf_counter() - started
        LOGGER.info("Whisper completed: model=%s duration=%.2fs elapsed=%.2fs chars=%d",
                    model_path.name, duration_seconds or 0.0, elapsed, len(text))
        return text
    except InterruptedError:
        LOGGER.warning("Whisper run cancelled: %s", source)
        raise
    except Exception as exc:
        LOGGER.exception("Whisper failed for %s with model %s", source, model_path)
        raise RuntimeError(
            f"Whisper не смог обработать аудио.\nФайл: {source.name}\nМодель: {model_path.name}\nПричина: {exc}"
        ) from exc


def transcribe_with_vosk(source: Path) -> str:
    required = (
        "am/final.mdl",
        "graph/HCLr.fst",
        "graph/Gr.fst",
        "graph/words.txt",
    )
    missing = [relative for relative in required if not (VOSK_MODEL_PATH / relative).is_file()]
    if missing:
        missing_list = "\n".join(f"• {item}" for item in missing)
        raise FileNotFoundError(
            f"Модель Vosk неполная: {VOSK_MODEL_PATH}\n"
            f"Не найдены файлы:\n{missing_list}\n\n"
            "Для транскрибации файлов положите ggml-small.bin или ggml-medium.bin в models\\whisper.\n"
            "Для диктовки с микрофона нужна полная модель Vosk."
        )

    model = Model(str(VOSK_MODEL_PATH))
    start = time.perf_counter()
    try:
        with wave.open(str(source), "rb") as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                raise ValueError("Для распознавания нужен WAV PCM, моно, 16 бит.")
            recognizer = KaldiRecognizer(model, wf.getframerate())
            recognizer.SetWords(True)
            chunks = []
            while True:
                data = wf.readframes(4000)
                if not data:
                    break
                if recognizer.AcceptWaveform(data):
                    partial = json.loads(recognizer.Result())
                    if partial.get("text"):
                        chunks.append(partial["text"])
            final = json.loads(recognizer.FinalResult()).get("text", "")
            if final:
                chunks.append(final)
    except wave.Error as exc:
        raise ValueError(f"Файл не является корректным WAV: {source.name}") from exc

    elapsed = time.perf_counter() - start
    print(f"Время транскрибации Vosk: {int(elapsed // 60)} мин {int(elapsed % 60)} сек.")
    return " ".join(chunks).strip()


def transcribe_audio(file_path, n_threads: int | None = None, language: str = "ru",
                     model_slot: str = "file", model_path: str | Path | None = None):
    source = Path(file_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Аудиофайл не найден: {source}")
    if source.stat().st_size == 0:
        raise ValueError("Аудиофайл пустой.")

    whisper_model = Path(model_path).expanduser().resolve() if model_path else find_whisper_model()
    if whisper_model is not None:
        return transcribe_with_whisper(
            source, whisper_model, n_threads=n_threads, language=language, model_slot=model_slot
        )
    return transcribe_with_vosk(source)


def add_punctuation_and_capitalize(text):
    """Lightweight normalization without downloading NLTK tokenizers."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    if text[-1] not in ".!?…":
        text += "."
    return text


def start_model(audio_file_path, n_threads: int | None = None, language: str = "ru"):
    """Transcribe audio and return a unique UTF-8 text file path."""
    source = Path(audio_file_path).expanduser().resolve()
    try:
        text = add_punctuation_and_capitalize(transcribe_audio(source, n_threads=n_threads, language=language))
        _TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        fd, output = tempfile.mkstemp(prefix="transcript_", suffix=".txt", dir=_TEMP_ROOT)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as text_file:
            text_file.write(text)
        return output
    finally:
        try:
            if source.parent == _TEMP_ROOT.resolve() and source.suffix.lower() == ".wav":
                source.unlink(missing_ok=True)
        except OSError:
            pass
