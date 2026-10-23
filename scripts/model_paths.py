# -*- coding: utf-8 -*-
"""Canonical model locations and safe migration from the legacy Vosk folder."""
from __future__ import annotations

import logging
from pathlib import Path

LOGGER = logging.getLogger("spiker.models")
VOSK_FOLDER_NAME = "vosk-model-small-ru-0.22"


def resolve_vosk_model_path(project_root: str | Path) -> Path:
    """Return canonical Vosk model path, migrating the known legacy folder if safe.

    Canonical location: ``<project>/models/vosk/vosk-model-small-ru-0.22``.
    Legacy location: ``<project>/model/vosk-model-small-ru-0.22``.

    Only the specifically named Vosk model directory is moved. Other files inside
    the legacy ``model`` folder are never deleted. If moving fails, keep using the
    legacy location so an existing installation remains usable.
    """
    root = Path(project_root).expanduser().resolve()
    canonical = root / "models" / "vosk" / VOSK_FOLDER_NAME
    legacy_root = root / "model"
    legacy = legacy_root / VOSK_FOLDER_NAME

    if canonical.exists():
        return canonical
    if not legacy.is_dir():
        return canonical

    try:
        canonical.parent.mkdir(parents=True, exist_ok=True)
        # rename is normally an atomic directory move because both paths live on
        # the same project volume; unlike copy/delete, it does not duplicate GBs.
        legacy.rename(canonical)
        LOGGER.info("Migrated legacy Vosk model to canonical path: %s", canonical)
        try:
            legacy_root.rmdir()  # remove only if now empty
        except OSError:
            pass
        return canonical
    except OSError as exc:
        LOGGER.warning(
            "Could not migrate legacy Vosk model (%s); continuing from legacy path: %s",
            exc, legacy,
        )
        return legacy
