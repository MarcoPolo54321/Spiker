"""Robust media preparation for local Whisper transcription.

Inspired by the AudioPreparationService pattern in Spiker 0.3.5: decode any supported
media once into mono 16 kHz / 16-bit PCM WAV, use a unique temporary filename, validate
its header, and make preparation cancellable. FFmpeg comes from the pinned
imageio-ffmpeg package; no separate system-wide installation is required.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

LOGGER = logging.getLogger("processing.audio")
TEMP_ROOT = Path(tempfile.gettempdir()) / "Spiker" / "audio"


@dataclass(frozen=True)
class PreparedAudio:
    path: Path
    duration_seconds: float
    temporary: bool


def _cancelled(cancel_callback: Callable[[], bool] | None) -> bool:
    return bool(cancel_callback and cancel_callback())


def _wav_info(path: Path) -> tuple[int, int, int, int]:
    try:
        with wave.open(str(path), "rb") as wf:
            if wf.getcomptype() != "NONE":
                raise ValueError("WAV использует сжатие; ожидался PCM.")
            return wf.getnchannels(), wf.getsampwidth(), wf.getframerate(), wf.getnframes()
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"Не удалось прочитать подготовленный WAV: {path.name}") from exc


def prepare_media_audio(
    source_path: str | os.PathLike[str],
    stage_callback: Callable[[str], None] | None = None,
    cancel_callback: Callable[[], bool] | None = None,
) -> PreparedAudio:
    """Return validated mono 16kHz PCM audio. Existing compliant WAV is reused."""
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Исходный аудио-/видеофайл не найден: {source}")
    if source.stat().st_size == 0:
        raise ValueError("Выбранный файл пустой.")
    if _cancelled(cancel_callback):
        raise InterruptedError("Подготовка аудио отменена пользователем.")

    # The no-conversion path avoids copying a WAV already in Whisper's expected format.
    if source.suffix.lower() == ".wav":
        try:
            channels, sample_width, sample_rate, frames = _wav_info(source)
            if channels == 1 and sample_width == 2 and sample_rate == 16000 and frames > 0:
                duration = frames / sample_rate
                LOGGER.info("Audio already in Whisper format: %s (%.2fs)", source, duration)
                if stage_callback:
                    stage_callback("Аудио уже подготовлено; запускаем распознавание…")
                return PreparedAudio(source, duration, False)
        except ValueError:
            # A nonstandard/corrupt WAV may still be decodable by FFmpeg; let it try below.
            pass

    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="prepared_", suffix=".wav", dir=TEMP_ROOT)
    os.close(fd)
    output = Path(temp_name)
    output.unlink(missing_ok=True)  # FFmpeg must create the target itself.

    try:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            raise RuntimeError(
                "Не найден встроенный FFmpeg. Откройте «Обновить или восстановить библиотеки.bat» "
                "и проверьте logs\\install.log."
            ) from exc

        if stage_callback:
            stage_callback("Подготавливаем аудио: извлекаем дорожку и приводим к PCM 16 кГц…")

        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", "-f", "wav", "-progress", "pipe:1", "-stats_period", "0.5",
            str(output),
        ]
        create_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        started = time.perf_counter()
        # Keep FFmpeg's stderr out of the console; read it from a temporary file after exit.
        with tempfile.TemporaryFile(mode="w+b") as err_stream:
            process = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=err_stream, text=True, encoding="utf-8", errors="replace",
                bufsize=1, creationflags=create_flags,
            )
            try:
                assert process.stdout is not None
                for line in process.stdout:
                    if _cancelled(cancel_callback):
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        raise InterruptedError("Подготовка аудио отменена пользователем.")
                    if line.startswith("progress=") and stage_callback:
                        stage_callback("Подготавливаем аудио…")
                return_code = process.wait()
            except BaseException:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                raise
            err_stream.seek(0)
            error_text = err_stream.read().decode("utf-8", errors="replace").strip()

        if return_code != 0:
            LOGGER.error("FFmpeg failed (exit=%s) for %s: %s", return_code, source, error_text[-5000:])
            if "matches no streams" in error_text.lower() or "does not contain any stream" in error_text.lower():
                detail = "В файле не найдена аудиодорожка. Проверьте, что видео содержит звук."
            else:
                detail = error_text[-1800:] or f"Код завершения FFmpeg: {return_code}"
            raise RuntimeError(f"Не удалось подготовить аудио из файла «{source.name}».\n{detail}")

        if not output.is_file() or output.stat().st_size <= 44:
            raise RuntimeError("FFmpeg завершился, но не создал аудиоданные. Файл может не содержать звук.")
        channels, sample_width, sample_rate, frames = _wav_info(output)
        if channels != 1 or sample_width != 2 or sample_rate != 16000 or frames <= 0:
            raise RuntimeError(
                f"Неверный формат WAV после подготовки: каналов={channels}, байт/сэмпл={sample_width}, "
                f"частота={sample_rate}, кадров={frames}."
            )
        duration = frames / sample_rate
        LOGGER.info("Prepared media: %s -> %s (%.2fs, %.2f MB, %.2fs)",
                    source, output, duration, output.stat().st_size / 1024 / 1024,
                    time.perf_counter() - started)
        if stage_callback:
            stage_callback(f"Аудио готово ({int(duration // 60):02d}:{int(duration % 60):02d}); загружаем Whisper…")
        return PreparedAudio(output, duration, True)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
