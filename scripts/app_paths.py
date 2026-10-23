"""Canonical application path helpers for source and frozen Windows builds."""
from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    """Return the folder containing the portable/installed app, or source root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # This file is stored at <project>/scripts/app_paths.py.
    return Path(__file__).resolve().parents[1]
