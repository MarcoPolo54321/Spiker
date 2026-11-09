# -*- coding: utf-8 -*-
"""Pure helpers for subtitle formatting from real Whisper segment timestamps."""
from __future__ import annotations


def format_timestamp(seconds: float, vtt: bool = False) -> str:
    milliseconds = max(0, int(round(float(seconds or 0) * 1000)))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{milliseconds:03d}"


def render_subtitles(segments, vtt: bool = False, speaker_names: dict | None = None) -> str:
    """Render normalized start/end/text dictionaries as SRT or WebVTT, retaining speaker labels."""
    speaker_names = speaker_names or {}
    valid = []
    for item in segments or []:
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            continue
        try:
            start = max(0.0, float(item.get("start", 0)))
            end = max(start + 0.05, float(item.get("end", start + 0.5)))
        except (TypeError, ValueError):
            continue
        text = str(item.get("text", "")).strip()
        speaker_id = str(item.get("speaker_id", "") or "")
        if speaker_id:
            text = f"{speaker_names.get(speaker_id) or speaker_id}: {text}"
        valid.append((start, end, text))
    valid.sort(key=lambda item: (item[0], item[1]))
    if not valid:
        return ""
    lines = ["WEBVTT", ""] if vtt else []
    for idx, (start, end, text) in enumerate(valid, 1):
        if not vtt:
            lines.append(str(idx))
        lines.append(f"{format_timestamp(start, vtt)} --> {format_timestamp(end, vtt)}")
        lines.extend([text.replace("\r", " ").strip(), ""])
    return "\n".join(lines).rstrip() + "\n"
