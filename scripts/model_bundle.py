"""Install the companion model archive on first launch of a portable copy."""
from __future__ import annotations

import logging
import zipfile
from pathlib import Path, PurePosixPath
from archive_utils import safe_extract_zip


def unpack_companion_models(app_root: Path) -> bool:
    """Unpack a sibling Spiker-Models archive if the default ASR model is absent.

    The regular installer already lays models out. Portable builds may keep the
    archive next to the extracted application folder; in that case first launch
    installs it automatically into ``app_root/models``.
    """
    root = Path(app_root).resolve()
    if (root / "models" / "whisper" / "ggml-small.bin").is_file():
        return False
    candidates = sorted(root.glob("Spiker-Models-*.zip")) + sorted(root.parent.glob("Spiker-Models-*.zip"))
    archive = next((item for item in candidates if item.is_file()), None)
    if archive is None:
        return False
    try:
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                member = PurePosixPath(info.filename)
                if "\\" in info.filename or member.is_absolute() or ".." in member.parts or not member.parts or member.parts[0] != "models":
                    raise ValueError(f"Недопустимый путь в архиве моделей: {info.filename}")
            safe_extract_zip(bundle, root, allowed_top_level={"models"}, max_total_bytes=12 * 1024**3)
        logging.getLogger("models.bundle").info("Models installed from companion archive %s", archive.name)
        return True
    except Exception:
        logging.getLogger("models.bundle").exception("Could not install companion model archive %s", archive)
        return False
