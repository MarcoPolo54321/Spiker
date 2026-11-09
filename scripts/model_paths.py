# -*- coding: utf-8 -*-
"""Canonical model locations and safe migration from the legacy Vosk folder."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from app_paths import get_user_data_root

LOGGER = logging.getLogger("spiker.models")
VOSK_FOLDER_NAME = "vosk-model-small-ru-0.22"


def resolve_vosk_model_path(project_root: str | Path) -> Path:
    """Return canonical Vosk model path, migrating the known legacy folder if safe.

    Bundled location: ``<project>/models/vosk/vosk-model-small-ru-0.22``.
    User-installed location: ``<user-data>/models/vosk/vosk-model-small-ru-0.22``.
    Legacy location: ``<project>/model/vosk-model-small-ru-0.22``.

    Only the specifically named Vosk model directory is moved. Other files inside
    the legacy ``model`` folder are never deleted. If moving fails, keep using the
    legacy location so an existing installation remains usable.
    """
    root = Path(project_root).expanduser()
    if not root.is_absolute():
        root = root.resolve()
    canonical = root / "models" / "vosk" / VOSK_FOLDER_NAME
    user_model = get_user_data_root(root) / "models" / "vosk" / VOSK_FOLDER_NAME
    legacy_root = root / "model"
    legacy = legacy_root / VOSK_FOLDER_NAME

    if canonical.exists():
        return canonical
    if user_model.exists():
        return user_model
    if not legacy.is_dir():
        return user_model

    try:
        target = user_model if user_model != canonical else canonical
        target.parent.mkdir(parents=True, exist_ok=True)
        # Use the writable user model directory when the install folder is protected.
        legacy.rename(target)
        LOGGER.info("Migrated legacy Vosk model to canonical path: %s", target)
        try:
            legacy_root.rmdir()  # remove only if now empty
        except OSError:
            pass
        return target
    except OSError as exc:
        LOGGER.warning(
            "Could not migrate legacy Vosk model (%s); continuing from legacy path: %s",
            exc, legacy,
        )
        return legacy


def native_model_path(path: str | Path) -> str:
    """Return a Windows short path for native libraries that cannot open Unicode paths.

    Some C/C++ speech runtimes receive UTF-8 bytes through ``char*`` APIs, then
    interpret them using the Windows ANSI code page. A per-user install under a
    Cyrillic profile name can therefore look like a missing model. GetShortPathNameW
    maps existing files to their 8.3 alias while Python continues to use long paths.
    """
    resolved_path = Path(path).expanduser().resolve()
    resolved = str(resolved_path)
    if os.name != "nt":
        return resolved
    try:
        import ctypes
        from ctypes import wintypes

        get_short_path = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
        get_short_path.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
        get_short_path.restype = wintypes.DWORD
        # Keep ordinary ASCII names intact (including `model.onnx`) and shorten
        # only path components that contain characters the native runtime cannot
        # represent in the active ANSI code page.
        parts = resolved_path.parts
        current = parts[0]
        for component in parts[1:]:
            candidate = os.path.join(current, component)
            if any(ord(character) > 127 for character in component):
                buffer = ctypes.create_unicode_buffer(32768)
                length = get_short_path(candidate, buffer, len(buffer))
                current = buffer.value if length and length < len(buffer) and buffer.value else candidate
            else:
                current = candidate
        if current.isascii():
            return current
        # Volumes such as D: often disable 8.3 names. Native char* APIs still
        # need ASCII, so expose the directory through a stable per-user junction.
        import hashlib
        import _winapi
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'Spiker' / 'native-models'
        base.mkdir(parents=True, exist_ok=True)
        buffer = ctypes.create_unicode_buffer(32768)
        length = get_short_path(str(base), buffer, len(buffer))
        ascii_base = Path(buffer.value) if length else base
        if not str(ascii_base).isascii():
            # Some Windows volumes disable 8.3 aliases. The profile folder may
            # contain Cyrillic too, so use the standard ASCII Public Documents
            # location for model-only junctions as a last fallback.
            public_root = Path(os.environ.get('PUBLIC', r'C:\Users\Public'))
            ascii_base = public_root / 'Documents' / 'Spiker' / 'native-models'
            ascii_base.mkdir(parents=True, exist_ok=True)
            if not str(ascii_base).isascii():
                raise OSError('Windows не предоставила доступный ASCII-путь для локальных моделей.')
        folder = resolved_path if resolved_path.is_dir() else resolved_path.parent
        alias = ascii_base / hashlib.sha256(str(folder).encode('utf-8')).hexdigest()[:20]
        if not alias.exists():
            try:
                _winapi.CreateJunction(str(folder), str(alias))
            except FileExistsError:
                pass
        if alias.resolve() != folder.resolve():
            raise OSError('Конфликт пути модели.')
        return str(alias if resolved_path.is_dir() else alias / resolved_path.name)
    except Exception:
        LOGGER.debug("Could not resolve a short Windows model path for %s", resolved, exc_info=True)
    return resolved
