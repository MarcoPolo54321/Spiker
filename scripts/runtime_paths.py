"""Load optional ML runtimes installed next to a frozen Windows application.

PyInstaller bundles the stable GUI and core ASR runtime. Larger/optional packages such
as pyannote.audio can be installed into .venv311 beside Spiker.exe; this module exposes
that site-packages directory and registers native DLL folders before importing them.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from app_paths import get_user_data_root

LOGGER = logging.getLogger("startup.runtime_paths")
_DLL_HANDLES = []


def extend_optional_runtime_paths(app_root: str | Path) -> list[Path]:
    root = Path(app_root).resolve()
    user_data = get_user_data_root(root)
    candidates = [
        root / ".venv311" / "Lib" / "site-packages",
        root / ".runtime_ml" / "Lib" / "site-packages",
        root / "runtime_ml" / "Lib" / "site-packages",
        user_data / ".venv-models" / "Lib" / "site-packages",
        Path(os.environ.get("LOCALAPPDATA", str(user_data.parent))) / "Spiker/.venv-models/Lib/site-packages",
    ]
    added: list[Path] = []
    for site_packages in candidates:
        if not site_packages.is_dir():
            continue
        value = str(site_packages)
        if value not in sys.path:
            sys.path.append(value)
            added.append(site_packages)
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            dll_candidates = [
                site_packages / "torch" / "lib",
                site_packages / "ctranslate2",
                site_packages / "onnxruntime" / "capi",
                site_packages / "nvidia" / "cublas" / "bin",
                site_packages / "nvidia" / "cudnn" / "bin",
                site_packages / "nvidia" / "cuda_runtime" / "bin",
            ]
            for dll_dir in dll_candidates:
                if dll_dir.is_dir():
                    try:
                        _DLL_HANDLES.append(os.add_dll_directory(str(dll_dir)))
                    except OSError:
                        LOGGER.warning("Could not register optional DLL directory: %s", dll_dir, exc_info=True)
    if added:
        LOGGER.info("Optional ML runtime paths added: %s", [str(item) for item in added])
    return added
