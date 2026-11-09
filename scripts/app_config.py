# -*- coding: utf-8 -*-
"""Small persistent configuration helpers for Spiker."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app_paths import get_user_data_root


def load_settings(project_root: Path) -> dict:
    root = Path(project_root)
    path = get_user_data_root(root) / "data" / "settings.json"
    defaults = {
        "threads": 4, "language": "ru", "dictation_model_path": "",
        "dictation_engine": "auto", "sherpa_model_path": "",
        "transcription_engine": "auto", "performance_mode": "auto",
        "compute_device": "auto", "compute_type": "auto",
        "faster_whisper_model": "medium", "faster_whisper_model_path": "",
        "batch_size": 1, "vad_filter": True, "word_timestamps": True,
        "audio_normalize": False, "audio_profile": "speech", "audio_stream_index": 0,
        "context_terms": "", "diarization_enabled": True,
        "speaker_min": 0, "speaker_max": 0, "show_speakers": True,
        "microphone_name": "", "ai_provider": "builtin", "ai_local_url": "http://127.0.0.1:11434/v1",
        "ai_local_model": "qwen2.5:0.5b", "ai_api_base_url": "https://api.openai.com/v1",
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
            if raw.get("dictation_engine") in {"auto", "sherpa", "vosk", "whisper"}:
                defaults["dictation_engine"] = raw["dictation_engine"]
            if isinstance(raw.get("sherpa_model_path"), str):
                defaults["sherpa_model_path"] = raw["sherpa_model_path"][:1000]
            choices = {
                "transcription_engine": {"auto", "whispercpp", "faster-whisper"},
                "performance_mode": {"auto", "speed", "balanced", "quality", "manual"},
                "compute_device": {"auto", "cpu", "cuda"},
                "compute_type": {"auto", "int8", "float16", "int8_float16", "float32"},
                "faster_whisper_model": {"small", "medium", "large-v3-turbo", "large-v3"},
            }
            for key, allowed in choices.items():
                if raw.get(key) in allowed:
                    defaults[key] = raw[key]
            if raw.get("audio_profile") in {"speech", "meeting", "music", "preserve"}:
                defaults["audio_profile"] = raw["audio_profile"]
            if isinstance(raw.get("audio_stream_index"), int):
                defaults["audio_stream_index"] = max(0, min(31, raw["audio_stream_index"]))
            for key in ("faster_whisper_model_path", "context_terms"):
                if isinstance(raw.get(key), str):
                    defaults[key] = raw[key][:4000 if key == "context_terms" else 1000]
            for key in ("vad_filter", "word_timestamps", "audio_normalize", "diarization_enabled", "show_speakers"):
                if isinstance(raw.get(key), bool):
                    defaults[key] = raw[key]
            for key, low, high in (("batch_size", 1, 32), ("speaker_min", 0, 20), ("speaker_max", 0, 20)):
                if isinstance(raw.get(key), int):
                    defaults[key] = max(low, min(high, raw[key]))
            if raw.get("ai_provider") in {"local", "compatible", "builtin", "api"}:
                defaults["ai_provider"] = raw["ai_provider"]
            for key in ("microphone_name", "ai_local_url", "ai_local_model", "ai_api_base_url", "ai_api_model"):
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
        "threads": max(1, min(64, int(settings.get("threads", current["threads"])) )) ,
        "language": settings.get("language", current["language"])
            if settings.get("language", current["language"]) in {"ru", "en", "auto"} else current["language"],
        "dictation_model_path": str(settings.get("dictation_model_path", current.get("dictation_model_path", "")) or ""),
        "dictation_engine": settings.get("dictation_engine", current.get("dictation_engine", "auto"))
            if settings.get("dictation_engine", current.get("dictation_engine", "auto")) in {"auto", "sherpa", "vosk", "whisper"}
            else current.get("dictation_engine", "auto"),
        "sherpa_model_path": str(settings.get("sherpa_model_path", current.get("sherpa_model_path", "")) or "")[:1000],
    })
    allowed_choices = {
        "transcription_engine": {"auto", "whispercpp", "faster-whisper"},
        "performance_mode": {"auto", "speed", "balanced", "quality", "manual"},
        "compute_device": {"auto", "cpu", "cuda"},
        "compute_type": {"auto", "int8", "float16", "int8_float16", "float32"},
        "faster_whisper_model": {"small", "medium", "large-v3-turbo", "large-v3"},
    }
    for key, allowed in allowed_choices.items():
        value = settings.get(key, current.get(key))
        if value in allowed:
            current[key] = value
    for key, limit in (("faster_whisper_model_path", 1000), ("context_terms", 4000)):
        value = settings.get(key, current.get(key, ""))
        if isinstance(value, str):
            current[key] = value[:limit]
    if settings.get("audio_profile", current.get("audio_profile")) in {"speech", "meeting", "music", "preserve"}:
        current["audio_profile"] = settings.get("audio_profile", current.get("audio_profile", "speech"))
    try:
        current["audio_stream_index"] = max(0, min(31, int(settings.get("audio_stream_index", current.get("audio_stream_index", 0)))))
    except (TypeError, ValueError):
        pass
    for key in ("vad_filter", "word_timestamps", "audio_normalize", "diarization_enabled", "show_speakers"):
        value = settings.get(key, current.get(key))
        if isinstance(value, bool):
            current[key] = value
    for key, low, high in (("batch_size", 1, 32), ("speaker_min", 0, 20), ("speaker_max", 0, 20)):
        try:
            current[key] = max(low, min(high, int(settings.get(key, current.get(key, low)))))
        except (TypeError, ValueError):
            pass
    for key in ("microphone_name", "ai_provider", "ai_local_url", "ai_local_model", "ai_api_base_url", "ai_api_model"):
        value = settings.get(key, current.get(key))
        if key == "ai_provider" and value not in {"local", "compatible", "builtin", "api"}:
            continue
        if isinstance(value, str) and value.strip():
            current[key] = value.strip()
    current.pop("ai_api_key", None)
    atomic_write_json(get_user_data_root(root) / "data" / "settings.json", current)
