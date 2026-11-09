"""Structured meeting-intelligence helpers with source-linked transcript segments.

This module never invents transcript evidence. It prepares stable segment references
for the language model and renders only references that exist in the source.
"""
from __future__ import annotations

import json
import re
from typing import Any

_SEGMENT_LINE_RE = re.compile(
    r"^\[SEGMENT_ID=(?P<id>[A-Z0-9_-]+)\] \[(?P<start>\d{2}:\d{2}:\d{2})–(?P<end>\d{2}:\d{2}:\d{2})\] "
    r"\[SPEAKER_ID=(?P<speaker>[^\]]*)\] (?P<text>.*)$"
)


def format_clock(seconds: float) -> str:
    value = max(0, int(float(seconds or 0)))
    hours, rem = divmod(value, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def build_timestamped_transcript(segments: list[dict], speaker_names: dict | None = None) -> tuple[str, list[dict]]:
    """Build one source line per segment and a speaker roster for AI prompts."""
    names = speaker_names or {}
    rows: list[str] = []
    roster: dict[str, str] = {}
    refs: list[dict] = []
    for index, item in enumerate(sorted(
        (row for row in (segments or []) if isinstance(row, dict) and str(row.get("text", "")).strip()),
        key=lambda row: (float(row.get("start", 0) or 0), float(row.get("end", 0) or 0)),
    ), start=1):
        segment_id = str(item.get("segment_id") or f"SEG_{index:06d}")
        start = max(0.0, float(item.get("start", 0) or 0))
        end = max(start, float(item.get("end", start) or start))
        speaker_id = str(item.get("speaker_id", "") or "")
        speaker_name = str(names.get(speaker_id) or speaker_id or "Не определён")
        if speaker_id:
            roster[speaker_id] = speaker_name
        rows.append(
            f"[SEGMENT_ID={segment_id}] [{format_clock(start)}–{format_clock(end)}] "
            f"[SPEAKER_ID={speaker_id or 'unassigned'}] {str(item.get('text', '')).strip()}"
        )
        refs.append({
            "segment_id": segment_id,
            "start": round(start, 3),
            "end": round(end, 3),
            "speaker_id": speaker_id,
            "speaker_name": speaker_name,
        })
    context = [{"speaker_id": key, "name": value} for key, value in roster.items()]
    return "\n".join(rows), context


def extract_segment_reference_map(source_text: str) -> dict[str, dict]:
    result = {}
    for line in (source_text or "").splitlines():
        match = _SEGMENT_LINE_RE.match(line.strip())
        if not match:
            continue
        start_parts = [int(part) for part in match.group("start").split(":")]
        end_parts = [int(part) for part in match.group("end").split(":")]
        start = start_parts[0] * 3600 + start_parts[1] * 60 + start_parts[2]
        end = end_parts[0] * 3600 + end_parts[1] * 60 + end_parts[2]
        speaker_id = match.group("speaker").strip()
        result[match.group("id")] = {
            "start": start, "end": end,
            "speaker_id": "" if speaker_id == "unassigned" else speaker_id,
        }
    return result


def _parse_json_payload(raw: str) -> dict | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        left, right = text.find("{"), text.rfind("}")
        if left < 0 or right <= left:
            return None
        try:
            value = json.loads(text[left:right + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def validate_structured_meeting_result(raw: str, source_text: str) -> tuple[dict | None, list[str]]:
    """Parse the structured result and discard references not present in source."""
    data = _parse_json_payload(raw)
    if data is None:
        return None, ["Модель вернула невалидный JSON; показан исходный ответ без автоматической проверки ссылок."]
    reference_map = extract_segment_reference_map(source_text)
    warnings: list[str] = []
    allowed = set(reference_map)
    known_speaker_ids = {str(ref.get("speaker_id") or "") for ref in reference_map.values() if ref.get("speaker_id")}
    for collection in ("topics", "decisions", "action_items", "open_questions"):
        values = data.get(collection, [])
        if not isinstance(values, list):
            data[collection] = []
            warnings.append(f"Поле {collection} имело неверный тип и было пропущено.")
            continue
        cleaned = []
        for item in values:
            if not isinstance(item, dict):
                continue
            refs = item.get("segment_ids", [])
            if not isinstance(refs, list):
                refs = []
            valid_refs = [str(value) for value in refs if str(value) in allowed]
            invalid_count = len(refs) - len(valid_refs)
            if invalid_count:
                warnings.append(f"В {collection} отброшено неподтверждённых ссылок: {invalid_count}.")
            item["segment_ids"] = valid_refs
            if collection == "action_items":
                assigned_speaker = str(item.get("responsible_speaker_id") or "").strip()
                if assigned_speaker and assigned_speaker not in known_speaker_ids:
                    item["responsible_speaker_id"] = ""
                    item["responsible_name"] = ""
                    warnings.append("В задаче удалён ответственный, которого нет среди ID участников исходной записи.")
            if allowed and not valid_refs:
                # Do not present an ungrounded claim as source-verified.
                item["verification"] = "Нет подтверждённой ссылки на сегмент"
            else:
                item["verification"] = "Ссылка на исходную расшифровку" if valid_refs else "Источник без временной разметки"
            cleaned.append(item)
        data[collection] = cleaned
    data.setdefault("summary", "")
    return data, list(dict.fromkeys(warnings))


def render_structured_meeting_markdown(data: dict, source_text: str, warnings: list[str] | None = None) -> str:
    refs = extract_segment_reference_map(source_text)
    lines = ["# Структурированный протокол встречи", ""]
    summary = str(data.get("summary", "") or "").strip()
    if summary:
        lines.extend(["## Краткое содержание", summary, ""])

    def emit_collection(title: str, key: str, text_keys: tuple[str, ...], extra_keys: tuple[str, ...] = ()):
        lines.extend([f"## {title}", ""])
        items = data.get(key, []) if isinstance(data.get(key, []), list) else []
        if not items:
            lines.extend(["_Не обнаружено или не указано в записи._", ""])
            return
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            text = next((str(item.get(name, "")).strip() for name in text_keys if str(item.get(name, "")).strip()), "Без описания")
            lines.append(f"{index}. **{text}**")
            for key_name in extra_keys:
                value = str(item.get(key_name, "") or "").strip()
                if value:
                    label = {
                        "responsible_name": "Ответственный", "responsible_speaker_id": "ID участника",
                        "due_date": "Срок", "speaker_name": "Участник", "confidence": "Уверенность",
                    }.get(key_name, key_name)
                    lines.append(f"   - {label}: {value}")
            segment_ids = [str(value) for value in item.get("segment_ids", []) if str(value) in refs]
            if segment_ids:
                links = []
                for segment_id in segment_ids:
                    ref = refs[segment_id]
                    stamp = f"{format_clock(ref['start'])}–{format_clock(ref['end'])}"
                    links.append(f"`{stamp}` ({segment_id})")
                lines.append("   - Источник: " + ", ".join(links))
            else:
                lines.append("   - Источник: не привязан к конкретному сегменту")
            verification = str(item.get("verification", "") or "")
            if verification and verification != "Ссылка на исходную расшифровку":
                lines.append(f"   - Проверка: {verification}")
        lines.append("")

    emit_collection("Темы", "topics", ("title", "topic", "summary"), ("speaker_name",))
    emit_collection("Принятые решения", "decisions", ("text", "decision", "title"), ("confidence",))
    emit_collection("Задачи", "action_items", ("task", "text", "action"), ("responsible_name", "responsible_speaker_id", "due_date"))
    emit_collection("Открытые вопросы", "open_questions", ("question", "text", "title"), ("speaker_name",))
    if warnings:
        lines.extend(["## Примечания проверки", ""])
        lines.extend(f"- {message}" for message in warnings)
        lines.append("")
    lines.append("_Результат создан ИИ. Проверьте формулировки и ссылки на исходные фрагменты перед использованием как официального протокола._")
    return "\n".join(lines).strip() + "\n"
