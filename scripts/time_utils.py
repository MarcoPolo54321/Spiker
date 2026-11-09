"""Formatting helpers shared by UI and background workers."""
from __future__ import annotations

import math


def format_duration(seconds: float) -> str:
    """Format a non-negative duration as MM:SS or HH:MM:SS.

    Invalid, non-finite and negative values safely render as 00:00.
    """
    try:
        value = float(seconds)
        if not math.isfinite(value):
            value = 0.0
        total = max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        total = 0

    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
