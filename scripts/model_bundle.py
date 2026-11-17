"""Install the companion model archive on first launch of a portable copy."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from archive_utils import safe_extract_zip


def install_verified_bundle(archive: Path, root: Path, expected_sha: str) -> None:
    if len(expected_sha) != 64:
        raise ValueError("Для пакета моделей отсутствует доверенная контрольная сумма.")
    root.mkdir(parents=True, exist_ok=True)
    with archive.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != expected_sha.lower():
            raise ValueError("Архив моделей не прошёл проверку контрольной суммы.")
        source.seek(0)
        with zipfile.ZipFile(source) as bundle, tempfile.TemporaryDirectory(prefix=".spiker-models-", dir=root) as folder:
            size = sum(info.file_size for info in bundle.infolist())
            if shutil.disk_usage(root).free < size + 64 * 1024**2:
                raise OSError("Недостаточно места для распаковки пакета моделей.")
            stage = Path(folder)
            safe_extract_zip(bundle, stage, allowed_top_level={"models"}, max_total_bytes=24 * 1024**3)
            base = root.resolve()
            files = [file for file in (stage / "models").rglob("*") if file.is_file()]
            if not files:
                raise ValueError("Пакет не содержит моделей СПИКЕР.")
            pairs = [(file, base / file.relative_to(stage)) for file in files]
            if any(base not in target.resolve().parents for _, target in pairs):
                raise ValueError("Целевая папка модели выходит за пределы места установки.")
            for file, target in pairs:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(file, target)


def unpack_companion_models(app_root: Path) -> bool:
    """Unpack sibling model archives if the default ASR model is absent.

    The regular installer already lays models out. Portable builds may keep the
    archive next to the extracted application folder; in that case first launch
    installs it automatically into ``app_root/models``.
    """
    root = Path(app_root).resolve()
    if not (root / "portable.flag").is_file():
        return False
    manifest_file = root / "res" / "model-bundles.json"
    if not manifest_file.is_file():
        return False
    try:
        manifests = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
        changed = False
        for name, digest in manifests.items():
            marker = root / "models" / (name + ".installed")
            if marker.is_file() and marker.read_text(encoding="ascii") == digest:
                continue
            archive = next((base / name for base in (root, root.parent) if (base / name).is_file()), None)
            if archive:
                install_verified_bundle(archive, root, digest)
                marker.write_text(digest, encoding="ascii")
                changed = True
        return changed
    except Exception:
        logging.getLogger("models.bundle").exception("Could not install companion model archives")
        return False
