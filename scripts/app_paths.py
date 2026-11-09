"""Canonical application path helpers for source and frozen Windows builds."""
from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path


def get_app_root() -> Path:
    """Return the folder containing the portable/installed app, or source root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # This file is stored at <project>/scripts/app_paths.py.
    return Path(__file__).resolve().parents[1]


def _copy_missing_files(source: Path, destination: Path) -> None:
    """Migrate legacy user files without replacing anything already in the new location."""
    if not source.is_dir():
        return
    transient_dirs = {"waveform_cache", "matplotlib", "__pycache__", "tmp", "temp"}
    for current, directories, filenames in os.walk(source):
        directories[:] = [name for name in directories if name.casefold() not in transient_dirs]
        current_path = Path(current)
        for filename in filenames:
            item = current_path / filename
            try:
                relative = item.relative_to(source)
                target = destination / relative
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
            except OSError:
                # A locked cache/log should not prevent application startup.
                continue


def documents_folder() -> Path:
    """Respect redirected Windows Documents (including OneDrive)."""
    if os.name == 'nt':
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
            return Path(buffer.value)
    return Path.home() / 'Documents'


@lru_cache(maxsize=8)
def get_user_data_root(app_root: str | Path | None = None) -> Path:
    """Private data is separate from binaries in every distribution mode."""
    override = os.environ.get('SPIKER_DATA_DIR', '').strip()
    if override:
        return Path(override).expanduser().resolve()
    destination = documents_folder() / 'Spiker'
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / '.storage-v2'
    root = Path(app_root).resolve() if app_root else get_app_root()
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'Spiker'
    # Retry every startup until each legacy item has arrived. Copy only missing files,
    # so this remains safe if Documents is temporarily unavailable during migration.
    for source in (local, root / 'user-data', root):
        if source.resolve() != destination.resolve():
            for name in ('data', 'results', 'logs'):
                _copy_missing_files(source / name, destination / name)
    if not marker.exists():
        marker.write_text('User data lives in Documents/Spiker.\n', encoding='utf-8')
    return destination
