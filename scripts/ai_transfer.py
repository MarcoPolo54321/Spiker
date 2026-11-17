"""Choose what metadata is sent before putting recognized text in the AI editor."""
from __future__ import annotations

import re

from meeting_intelligence import build_timestamped_transcript
from transcription.transcript_render import render_transcript_segments


_TIME = r"\[\d{1,3}:\d{2}(?::\d{2})?\s*[–—-]\s*\d{1,3}:\d{2}(?::\d{2})?\]"
_TECH = r"\[SEGMENT_ID=[^\]\r\n]*\]"
_SPEAKER = r"\[SPEAKER_ID=([^\]\r\n]*)\]"


def _known_speakers(segments, names):
    return {sid: str(names.get(sid) or sid) for item in segments
            if isinstance(item, dict) and (sid := str(item.get("speaker_id") or ""))}


def _prefix_pattern(roster):
    # Only recognize rendered metadata at the start of a line. Keep ordinary
    # colons, dates and prose (including time references mentioned by a speaker).
    generated = sorted(set(roster) | set(roster.values()), key=len, reverse=True)
    labels = "|".join(map(re.escape, generated))
    label = rf"(?:{labels}|Спикер\s+\d+):" if labels else r"Спикер\s+\d+:"
    return re.compile(rf"^(?:(?P<tech>{_TECH})[ \t]+)?(?:(?P<time>{_TIME})[ \t]+)?"
                      rf"(?:(?P<speaker>{_SPEAKER}|{label})[ \t]+)?", re.I)


def available_annotations(text, segments=(), names=None, *, edited=False):
    roster = _known_speakers(segments, names or {})
    if segments and not edited:
        return any(isinstance(segment, dict) and "start" in segment for segment in segments), bool(roster)
    pattern = _prefix_pattern(roster)
    prefixes = [pattern.match(line) for line in str(text).split("\n")]
    return any(m.group("time") for m in prefixes), any(m.group("speaker") for m in prefixes)


def transfer_payload(text, segments=(), names=None, *, edited=False, timestamps=False, speakers=False):
    """Keep edits authoritative and don't pass disabled fields via hidden context."""
    segments, names = segments or (), names or {}
    roster = _known_speakers(segments, names)
    context = [{"speaker_id": sid, "name": name} for sid, name in roster.items()] if speakers else []
    if segments and not edited:
        if timestamps and speakers:
            return build_timestamped_transcript(segments, names)
        return render_transcript_segments(
            segments, show_speakers=speakers, speaker_names=names, show_timestamps=timestamps
        ), context
    prefix = _prefix_pattern(roster)

    def clean(line):
        match = prefix.match(line)
        if not match or not match.group(0):
            return line
        parts = []
        if timestamps and match.group("time"):
            parts.append(match.group("time"))
        if speakers and match.group("speaker"):
            raw = match.group("speaker")
            internal = re.fullmatch(_SPEAKER, raw)
            if internal:
                sid = internal.group(1)
                if sid != "unassigned":
                    parts.append(f"{roster.get(sid, sid)}:")
            else:
                parts.append(raw)
        return " ".join([*parts, line[match.end():]])

    return "\n".join(clean(line) for line in str(text).split("\n")).strip(), context


def ask_transfer_options(parent, *, has_timestamps, has_speakers):
    from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout
    from UI.theme import apply_window_theme

    dialog = QDialog(parent)
    dialog.setWindowTitle("Передача текста в ИИ")
    apply_window_theme(dialog)
    layout = QVBoxLayout(dialog)
    note = QLabel("По умолчанию передаётся только текст. Можно добавить разметку, если она нужна для анализа."
                  if has_timestamps or has_speakers else "В этом тексте нет тайм-кодов и меток участников.")
    note.setWordWrap(True)
    layout.addWidget(note)
    time = QCheckBox("Добавить тайм-коды")
    people = QCheckBox("Добавить метки спикеров")
    time.setEnabled(has_timestamps)
    people.setEnabled(has_speakers)
    layout.addWidget(time)
    layout.addWidget(people)
    buttons = QDialogButtonBox()
    send = buttons.addButton("Передать текст", QDialogButtonBox.ButtonRole.AcceptRole)
    send.setDefault(True)
    buttons.addButton("Отмена", QDialogButtonBox.ButtonRole.RejectRole)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.setMinimumWidth(420)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return time.isChecked(), people.isChecked()
