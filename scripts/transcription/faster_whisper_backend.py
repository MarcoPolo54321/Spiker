"""Optional local faster-whisper backend. Models must already exist on disk."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from model_paths import native_model_path
from app_paths import get_user_data_root
from .hardware_diagnostics import resolve_compute_options

LOGGER = logging.getLogger("processing.faster_whisper")


def resolve_audio_profile_options(audio_profile: str, vad_filter: bool, normalize: bool) -> tuple[bool, bool]:
    """Resolve safe preprocessing choices for speech, meetings, music, or preserved audio."""
    profile = str(audio_profile or "speech").strip().lower()
    if profile in {"music", "preserve"}:
        # VAD often discards quiet vocal/music phrases; preserve mode also disables gain changes.
        return False, False if profile == "preserve" else bool(normalize)
    if profile == "meeting":
        return bool(vad_filter), bool(normalize)
    return bool(vad_filter), bool(normalize)


def _notify_callback(callback, *args, callback_name: str) -> None:
    """Call UI/progress callbacks defensively so a display bug cannot abort ASR."""
    if callback is None:
        return
    try:
        callback(*args)
    except Exception:
        LOGGER.exception("%s callback failed; continuing recognition", callback_name)
_MODEL_CACHE: dict[tuple[str, str, str], object] = {}
_MODEL_LOCK = threading.RLock()


def is_faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def resolve_faster_model(project_root: Path, model_name: str, configured_path: str = "") -> Path | None:
    candidates = []
    if configured_path:
        candidates.append(Path(configured_path).expanduser())
    candidates.extend([
        Path(project_root) / "models" / "faster-whisper" / str(model_name),
        get_user_data_root(project_root) / "models" / "faster-whisper" / str(model_name),
    ])
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved.is_dir() and (resolved / "config.json").is_file():
                return resolved
        except OSError:
            continue
    return None


def transcribe_with_faster_whisper(
    source: Path,
    model_path: Path,
    *,
    device: str = "auto",
    compute_type: str = "auto",
    batch_size: int = 1,
    cpu_threads: int = 4,
    language: str = "ru",
    vad_filter: bool = True,
    word_timestamps: bool = True,
    initial_prompt: str = "",
    duration_seconds: float | None = None,
    segment_callback: Callable[[float, str, str], None] | None = None,
    abort_callback: Callable[[], bool] | None = None,
    pause_callback: Callable[[], bool] | None = None,
    stage_callback: Callable[[str], None] | None = None,
    timestamp_callback: Callable[[dict], None] | None = None,
) -> str:
    try:
        from faster_whisper import WhisperModel, BatchedInferencePipeline
    except Exception as exc:
        raise RuntimeError(
            "faster-whisper не установлен. Запустите Install_Faster_Whisper.bat из папки СПИКЕР."
        ) from exc

    source = Path(source).expanduser().resolve()
    model_path = Path(model_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Подготовленный WAV не найден: {source}")
    if not model_path.is_dir() or not (model_path / "config.json").is_file():
        raise FileNotFoundError(
            f"Локальная модель faster-whisper не найдена: {model_path}. "
            "Поместите заранее скачанную модель CTranslate2 в models/faster-whisper/<имя>."
        )

    selected_device, selected_compute = resolve_compute_options(device, compute_type)
    cache_key = (str(model_path), selected_device, selected_compute)
    _notify_callback(
        stage_callback,
        f"Загружаем faster-whisper: {model_path.name} · {selected_device.upper()} · {selected_compute}…",
        callback_name="stage_callback",
    )
    with _MODEL_LOCK:
        model = _MODEL_CACHE.get(cache_key)
        if model is None:
            try:
                model = WhisperModel(
                    native_model_path(model_path), device=selected_device, compute_type=selected_compute,
                    cpu_threads=max(1, int(cpu_threads)), num_workers=1,
                )
            except Exception as exc:
                if device == "auto" and selected_device == "cuda":
                    LOGGER.warning("CUDA model initialization failed; falling back to CPU INT8: %s", exc)
                    selected_device, selected_compute = "cpu", "int8"
                    cache_key = (str(model_path), selected_device, selected_compute)
                    model = _MODEL_CACHE.get(cache_key)
                    if model is None:
                        model = WhisperModel(
                            native_model_path(model_path), device="cpu", compute_type="int8",
                            cpu_threads=max(1, int(cpu_threads)), num_workers=1,
                        )
                else:
                    raise RuntimeError(f"Не удалось запустить faster-whisper ({selected_device}/{selected_compute}): {exc}") from exc
            _MODEL_CACHE[cache_key] = model

    count = max(1, min(32, int(batch_size or 1)))
    options = {
        "language": None if language == "auto" else language,
        "vad_filter": bool(vad_filter),
        "word_timestamps": bool(word_timestamps),
        "condition_on_previous_text": count == 1,
        "initial_prompt": initial_prompt.strip() or None,
        "beam_size": 5,
    }
    if count > 1:
        # BatchedInferencePipeline decodes independent windows and doesn't carry
        # generated text from the previous window as context. Keep this explicit.
        pipeline = BatchedInferencePipeline(model=model)
        segments_iter, info = pipeline.transcribe(str(source), batch_size=count, **options)
    else:
        segments_iter, info = model.transcribe(str(source), **options)
    LOGGER.info(
        "faster-whisper started: model=%s device=%s compute=%s batch=%d language=%s duration=%.2f",
        model_path.name, selected_device, selected_compute, count, getattr(info, "language", language),
        float(duration_seconds or 0.0),
    )

    pieces: list[str] = []
    try:
        for item in segments_iter:
            if abort_callback and abort_callback():
                raise InterruptedError("Транскрибация остановлена пользователем.")
            while pause_callback is not None and pause_callback():
                if abort_callback and abort_callback():
                    raise InterruptedError("Транскрибация остановлена пользователем.")
                import time
                time.sleep(0.15)
            text = str(getattr(item, "text", "") or "").strip()
            if not text:
                continue
            pieces.append(text)
            start = max(0.0, float(getattr(item, "start", 0.0) or 0.0))
            end = max(start, float(getattr(item, "end", start) or start))
            words = []
            for word in getattr(item, "words", None) or []:
                try:
                    words.append({
                        "start": round(max(0.0, float(word.start)), 3),
                        "end": round(max(float(word.start), float(word.end)), 3),
                        "word": str(word.word or "").strip(),
                        "probability": round(float(word.probability), 4) if word.probability is not None else None,
                    })
                except (AttributeError, TypeError, ValueError):
                    continue
            _notify_callback(
                timestamp_callback,
                {"start": start, "end": end, "text": text, "words": words},
                callback_name="timestamp_callback",
            )
            if segment_callback:
                fraction = min(0.99, max(0.0, end / max(0.1, float(duration_seconds or end or 0.1))))
                _notify_callback(
                    segment_callback, fraction, " ".join(pieces), text,
                    callback_name="segment_callback",
                )
    except Exception as exc:
        message = str(exc).lower()
        is_cuda_oom = any(token in message for token in (
            "out of memory", "cuda error", "cublas_status_alloc_failed", "cuda out of memory"
        ))
        if device == "auto" and selected_device == "cuda" and is_cuda_oom:
            if pieces:
                raise RuntimeError(
                    "Видеопамять закончилась во время распознавания после получения части текста. "
                    "Сохранённые сегменты оставлены; выберите CPU или уменьшите batch и продолжите задачу."
                ) from exc
            LOGGER.warning("CUDA ran out of memory before the first segment; retrying with CPU INT8: %s", exc)
            with _MODEL_LOCK:
                _MODEL_CACHE.pop(cache_key, None)
            try:
                import gc
                gc.collect()
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            _notify_callback(stage_callback,
                "Недостаточно свободной видеопамяти; автоматически повторяем запуск на CPU INT8…",
                callback_name="stage_callback")
            return transcribe_with_faster_whisper(
                source, model_path, device="cpu", compute_type="int8", batch_size=count,
                cpu_threads=cpu_threads, language=language, vad_filter=vad_filter,
                word_timestamps=word_timestamps, initial_prompt=initial_prompt,
                duration_seconds=duration_seconds, segment_callback=segment_callback,
                abort_callback=abort_callback, pause_callback=pause_callback,
                stage_callback=stage_callback, timestamp_callback=timestamp_callback,
            )
        raise
    return " ".join(pieces).strip()


def release_faster_whisper_cache(device: str | None = None) -> int:
    """Release cached faster-whisper models before another heavy ML stage (e.g. pyannote)."""
    import gc
    removed = 0
    with _MODEL_LOCK:
        keys = [key for key in _MODEL_CACHE if device is None or key[1] == device]
        for key in keys:
            _MODEL_CACHE.pop(key, None)
            removed += 1
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    LOGGER.info("Released faster-whisper model cache entries: %d", removed)
    return removed
