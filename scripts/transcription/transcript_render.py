"""Stable text rendering helpers for timestamped transcript segments."""
from __future__ import annotations


def _format_timestamp(seconds: float) -> str:
    value = max(0, int(float(seconds or 0)))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def render_transcript_segments(
    segments: list[dict], *, show_speakers: bool = True, speaker_names: dict | None = None,
    show_timestamps: bool = False,
) -> str:
    names = speaker_names or {}
    rows = []
    for item in sorted(
        (value for value in (segments or []) if isinstance(value, dict) and str(value.get("text", "")).strip()),
        key=lambda value: (float(value.get("start", 0.0) or 0.0), float(value.get("end", 0.0) or 0.0)),
    ):
        text = str(item.get("text", "")).strip()
        speaker_id = str(item.get("speaker_id", "") or "")
        prefix = ""
        if show_timestamps:
            try:
                start = _format_timestamp(float(item.get("start", 0.0) or 0.0))
                end = _format_timestamp(float(item.get("end", item.get("start", 0.0)) or 0.0))
                prefix = f"[{start}–{end}] "
            except (TypeError, ValueError):
                prefix = ""
        if show_speakers and speaker_id:
            label = str(names.get(speaker_id) or speaker_id)
            rows.append(f"{prefix}{label}: {text}")
        else:
            rows.append(f"{prefix}{text}")
    return "\n\n".join(rows)


def speaker_summary(segments: list[dict], speaker_names: dict | None = None) -> dict:
    """Summarize speech duration using interval unions per speaker.

    Overlapping recognition segments for the same participant must not inflate their
    speaking time. Simultaneous speech by different participants remains counted for
    both, because each participant is independently speaking during that interval.
    """
    names = speaker_names or {}
    intervals: dict[str, list[tuple[float, float]]] = {}
    for item in segments or []:
        if not isinstance(item, dict):
            continue
        speaker = str(item.get("speaker_id", "") or "").strip()
        if not speaker:
            continue
        try:
            start = max(0.0, float(item.get("start", 0)))
            end = max(start, float(item.get("end", start)))
        except (TypeError, ValueError):
            continue
        if end > start:
            intervals.setdefault(speaker, []).append((start, end))

    durations: dict[str, float] = {}
    for speaker, rows in intervals.items():
        merged: list[list[float]] = []
        for start, end in sorted(rows):
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        durations[speaker] = sum(end - start for start, end in merged)

    total = sum(durations.values())
    return {
        speaker: {
            "name": str(names.get(speaker) or speaker),
            "duration_seconds": round(duration, 2),
            "share": round(100.0 * duration / total, 1) if total else 0.0,
        }
        for speaker, duration in sorted(durations.items())
    }
