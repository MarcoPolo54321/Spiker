"""Resolve the shipped FFmpeg without spawning a console probe."""
from functools import lru_cache
import os
from pathlib import Path
import shutil
import subprocess


@lru_cache(maxsize=1)
def ffmpeg_executable():
    explicit = os.environ.get("IMAGEIO_FFMPEG_EXE", "").strip()
    if explicit:
        return explicit
    import imageio_ffmpeg
    folder = Path(imageio_ffmpeg.__file__).resolve().parent / "binaries"
    for candidate in sorted(folder.glob("ffmpeg-*.exe" if os.name == "nt" else "ffmpeg-*")):
        if candidate.is_file():
            return str(candidate)
    system = shutil.which("ffmpeg")
    if system:
        return system
    raise FileNotFoundError("FFmpeg не найден. Восстановите файлы сборки СПИКЕР.")


def hidden_process_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
