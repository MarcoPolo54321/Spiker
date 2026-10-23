# -*- coding: utf-8 -*-
"""Small persistent configuration helpers for Spiker."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path

def load_settings(project_root: Path) -> dict:
    root = Path(project_root)
    path = root / "data" / "settings.json"
    defaults = {
        "threads": 4, "language": "ru", "dictation_model_path": "",
        "ai_provider": "local",
        "ai_local_url": "http://127.0.0.1:11434/v1",
        "ai_local_model": "qwen3.5:4b",
        "ai_api_base_url": "https://api.openai.com/v1",
        "ai_api_model": "gpt-4.1-mini",
    }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            if isinstance(raw.get("threads"), int):
                defaults["threads"] = max(1, min(64, raw["threads"]))
            if raw.get("language") in {"ru", "en", "auto"}:
                defaults["language"] = raw["language"]
            if isinstance(raw.get("dictation_model_path"), str):
                defaults["dictation_model_path"] = raw["dictation_model_path"]
            if raw.get("ai_provider") in {"local", "api"}:
                defaults["ai_provider"] = raw["ai_provider"]
            for key in ("ai_local_url", "ai_local_model", "ai_api_base_url", "ai_api_model"):
                if isinstance(raw.get(key), str) and raw[key].strip():
                    defaults[key] = raw[key].strip()
    except (OSError, json.JSONDecodeError):
        pass
    return defaults

def atomic_write_json(path: Path, payload) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.stem + "_", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except OSError:
            pass

def save_settings(project_root: Path, settings: dict) -> None:
    root = Path(project_root)
    current = load_settings(root)
    current.update({
        "threads": max(1, min(64, int(settings.get("threads", current["threads"])))),
        "language": settings.get("language", current["language"])
            if settings.get("language", current["language"]) in {"ru", "en", "auto"} else current["language"],
        "dictation_model_path": str(settings.get("dictation_model_path", current.get("dictation_model_path", "")) or ""),
    })
    for key in ("ai_provider", "ai_local_url", "ai_local_model", "ai_api_base_url", "ai_api_model"):
        value = settings.get(key, current.get(key))
        if key == "ai_provider" and value not in {"local", "api"}:
            continue
        if isinstance(value, str) and value.strip():
            current[key] = value.strip()
    # API keys must never be stored in this JSON file; the AI page uses OS credential storage.
    current.pop("ai_api_key", None)
    atomic_write_json(root / "data" / "settings.json", current)

