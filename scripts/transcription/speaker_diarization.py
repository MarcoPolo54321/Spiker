"""Optional offline pyannote speaker diarization with conservative attribution.

Community-1 provides both regular diarization (including overlap) and exclusive
speaker turns. The regular result is retained as overlap metadata; the exclusive
result is used to map words to a single speaker where a single-speaker transcript
is required. Ambiguous/no-overlap words are left unassigned rather than guessed.
"""
from __future__ import annotations

import logging
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

LOGGER = logging.getLogger("processing.diarization")
DEFAULT_MODEL_DIR_NAME = "speaker-diarization-community-1"
MIN_ASSIGNMENT_COVERAGE = 0.25
from app_paths import get_user_data_root


def diarization_model_path(project_root: Path) -> Path:
    root = Path(project_root)
    user_model = get_user_data_root(root) / "models" / "pyannote" / DEFAULT_MODEL_DIR_NAME
    legacy_model = root / "models" / "pyannote" / DEFAULT_MODEL_DIR_NAME
    return legacy_model if legacy_model.is_dir() and not user_model.exists() else user_model


def is_diarization_model_complete(model_dir: Path) -> bool:
    """Validate the local Community-1 folder before starting a costly inference run."""
    model_dir = Path(model_dir)
    if not (model_dir / "config.yaml").is_file():
        return False
    for name in ("segmentation", "embedding", "plda"):
        folder = model_dir / name
        if not folder.is_dir() or not any(path.is_file() for path in folder.rglob("*")):
            return False
    return True


def _external_runtime(project_root: Path | None) -> tuple[Path, Path] | None:
    if project_root is None:
        return None
    root = Path(project_root)
    python = get_user_data_root(root) / ".venv-diarization" / "Scripts" / "python.exe"
    legacy_python = root / ".venv-diarization" / "Scripts" / "python.exe"
    helper = root / "scripts" / "diarization_worker.py"
    if not python.is_file() and legacy_python.is_file():
        python = legacy_python
    if python.is_file() and helper.is_file():
        return python, helper
    return None


def is_pyannote_available(project_root: Path | None = None) -> bool:
    try:
        from pyannote.audio import Pipeline  # noqa: F401
        return True
    except Exception:
        return _external_runtime(project_root) is not None


def _run_external_diarization(
    audio_path: Path,
    model_dir: Path,
    project_root: Path,
    *,
    min_speakers: int | None,
    max_speakers: int | None,
    device: str,
    stage_callback: Callable[[str], None] | None,
    cancel_callback: Callable[[], bool] | None,
) -> tuple[list[tuple[float, float, str]], list[tuple[float, float, str]]]:
    runtime = _external_runtime(project_root)
    if runtime is None:
        raise RuntimeError(
            "Не найден .venv-diarization с pyannote. Запустите Install_Speaker_Diarization.bat "
            "рядом с Spiker.exe, затем установите локальную модель Community-1."
        )
    python, helper = runtime
    runtime_env = os.environ.copy()
    runtime_env["MPLCONFIGDIR"] = str(get_user_data_root(project_root) / "data" / "matplotlib")
    runtime_env["HF_HUB_OFFLINE"] = "1"
    runtime_env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    Path(runtime_env["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="spiker_diarization_") as temp_dir:
        output_path = Path(temp_dir) / "turns.json"
        command = [
            str(python), str(helper), "--audio", str(Path(audio_path).resolve()),
            "--model-dir", str(Path(model_dir).resolve()), "--output", str(output_path),
            "--min-speakers", str(max(0, int(min_speakers or 0))),
            "--max-speakers", str(max(0, int(max_speakers or 0))),
            "--device", device if device in {"auto", "cpu", "cuda"} else "auto",
        ]
        create_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        if stage_callback:
            stage_callback("Запускаем локальный модуль pyannote…")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace", creationflags=create_flags,
                                   env=runtime_env)
        while True:
            try:
                _stdout, stderr = process.communicate(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                if cancel_callback and cancel_callback():
                    process.terminate()
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate(timeout=5)
                    raise InterruptedError("Диаризация отменена пользователем; внешний модуль остановлен.")
        if process.returncode != 0:
            details = (stderr or "").strip()[-2500:]
            raise RuntimeError(f"Внешний модуль pyannote завершился с кодом {process.returncode}: {details}")
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            regular = _normalise_turns(payload.get("regular_turns", []))
            exclusive = _normalise_turns(payload.get("exclusive_turns", []))
        except (OSError, json.JSONDecodeError, AttributeError, TypeError) as exc:
            raise RuntimeError("Внешний модуль pyannote не вернул корректную разметку.") from exc
        return regular, exclusive


def _normalise_turns(turns: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    cleaned = []
    for start, end, label in turns or []:
        try:
            left = max(0.0, float(start))
            right = max(left, float(end))
        except (TypeError, ValueError):
            continue
        label = str(label or "").strip()
        if label and right > left:
            cleaned.append((left, right, label))
    return sorted(cleaned, key=lambda row: (row[0], row[1], row[2]))


def _overlap_by_speaker(start: float, end: float, turns: list[tuple[float, float, str]]) -> dict[str, float]:
    overlaps: dict[str, float] = {}
    for turn_start, turn_end, label in turns:
        overlap = max(0.0, min(end, turn_end) - max(start, turn_start))
        if overlap > 0:
            overlaps[label] = overlaps.get(label, 0.0) + overlap
    return overlaps


def _speaker_for_interval(
    start: float,
    end: float,
    turns: list[tuple[float, float, str]],
    *,
    min_coverage: float = MIN_ASSIGNMENT_COVERAGE,
) -> tuple[str, float]:
    """Return best overlapping speaker and coverage; never guess the nearest speaker."""
    overlaps = _overlap_by_speaker(start, end, turns)
    if not overlaps or end <= start:
        return "", 0.0
    label, overlap = max(overlaps.items(), key=lambda item: item[1])
    coverage = min(1.0, overlap / max(0.001, end - start))
    if coverage < min_coverage:
        return "", coverage
    return label, coverage


def _overlap_candidates(
    start: float, end: float, turns: list[tuple[float, float, str]], label_map: dict[str, str],
) -> list[str]:
    """List all speakers audibly overlapping an interval, preserving crosstalk evidence."""
    overlaps = _overlap_by_speaker(start, end, turns)
    threshold = max(0.08, (end - start) * 0.12)
    return [label_map[label] for label, duration in sorted(overlaps.items(), key=lambda item: item[1], reverse=True)
            if duration >= threshold and label in label_map]


def _split_segment_by_word_speakers(
    item: dict,
    exclusive_turns: list[tuple[float, float, str]],
    regular_turns: list[tuple[float, float, str]],
    label_map: dict[str, str],
) -> list[dict]:
    """Split a recognition segment at word boundaries when the assigned voice changes."""
    words = item.get("words")
    if not isinstance(words, list) or len(words) < 2:
        return []
    groups: list[dict] = []
    for raw_word in words:
        if not isinstance(raw_word, dict):
            continue
        token = str(raw_word.get("word", raw_word.get("text", "")) or "")
        if not token.strip():
            continue
        try:
            start = max(0.0, float(raw_word.get("start", item.get("start", 0.0))))
            end = max(start, float(raw_word.get("end", start)))
        except (TypeError, ValueError):
            continue
        source_label, confidence = _speaker_for_interval(start, end, exclusive_turns)
        speaker_id = label_map.get(source_label, "") if source_label else ""
        candidates = _overlap_candidates(start, end, regular_turns, label_map)
        if groups and groups[-1]["speaker_id"] == speaker_id and groups[-1].get("overlap_speaker_ids", []) == candidates:
            if token and token[0] in ",.!?;:%)]}»…":
                groups[-1]["text"] += token
            else:
                groups[-1]["text"] = (groups[-1]["text"].rstrip() + " " + token.lstrip()).strip()
            groups[-1]["end"] = max(groups[-1]["end"], end)
            groups[-1]["words"].append(dict(raw_word))
            groups[-1]["_confidence_total"] += confidence
            groups[-1]["_confidence_count"] += 1
        else:
            groups.append({
                **{key: value for key, value in item.items() if key not in {
                    "text", "start", "end", "words", "speaker_id", "speaker_confidence", "overlap_speaker_ids"
                }},
                "start": start, "end": end, "text": token, "words": [dict(raw_word)],
                "speaker_id": speaker_id,
                "speaker_confidence": round(confidence, 3),
                "overlap_speaker_ids": candidates,
                "_confidence_total": confidence, "_confidence_count": 1,
            })
    if len(groups) <= 1:
        return []
    for group in groups:
        count = max(1, group.pop("_confidence_count", 1))
        total = group.pop("_confidence_total", 0.0)
        group["speaker_confidence"] = round(total / count, 3)
        group["text"] = str(group.get("text", "")).strip()
    return groups



def _stable_label_map(
    segments: list[dict], turns: list[tuple[float, float, str]], labels: list[str],
) -> dict[str, str]:
    """Reuse old profile IDs by time overlap when a task is diarized again.

    New diarization labels are model-local and may be reordered on a later run.
    This overlap-based, one-to-one match preserves the user's renamed profiles.
    """
    scores: list[tuple[float, str, str]] = []
    for label in labels:
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            old_id = str(segment.get("speaker_id", "") or "").strip()
            if not old_id:
                continue
            try:
                left = max(0.0, float(segment.get("start", 0) or 0))
                right = max(left, float(segment.get("end", left) or left))
            except (TypeError, ValueError):
                continue
            overlap = _overlap_by_speaker(left, right, turns).get(label, 0.0)
            if overlap > 0:
                scores.append((overlap, label, old_id))
    mapped: dict[str, str] = {}
    used_ids: set[str] = set()
    for _score, label, old_id in sorted(scores, reverse=True):
        if label in mapped or old_id in used_ids:
            continue
        mapped[label] = old_id
        used_ids.add(old_id)

    used_numbers = []
    for value in used_ids:
        match = re.fullmatch(r"Спикер\s+(\d+)", value, flags=re.IGNORECASE)
        if match:
            used_numbers.append(int(match.group(1)))
    next_number = max(used_numbers, default=0) + 1
    for label in labels:
        if label in mapped:
            continue
        while f"Спикер {next_number}" in used_ids:
            next_number += 1
        mapped[label] = f"Спикер {next_number}"
        used_ids.add(mapped[label])
        next_number += 1
    return mapped

def _speaker_stats(turns: list[tuple[float, float, str]], label_map: dict[str, str]) -> dict:
    durations: dict[str, float] = {}
    for source_label in label_map:
        intervals = sorted((start, end) for start, end, label in turns if label == source_label)
        merged: list[list[float]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        durations[source_label] = sum(right - left for left, right in merged)
    total_speech = sum(durations.values())
    return {
        label_map[label]: {
            "duration_seconds": round(duration, 2),
            "share": round(100.0 * duration / total_speech, 1) if total_speech else 0.0,
        }
        for label, duration in durations.items()
    }


def assign_speakers_to_segments(
    segments: list[dict],
    turns: list[tuple[float, float, str]],
    *,
    regular_turns: list[tuple[float, float, str]] | None = None,
    min_coverage: float = MIN_ASSIGNMENT_COVERAGE,
) -> tuple[list[dict], dict]:
    """Map diarization to transcript; leave ambiguous intervals unassigned.

    ``turns`` is normally pyannote's exclusive diarization. ``regular_turns`` retains
    overlapping speech metadata. A missing overlap no longer maps to the nearest
    participant: the corresponding segment gets an empty speaker_id.
    """
    exclusive = _normalise_turns(turns)
    regular = _normalise_turns(regular_turns if regular_turns is not None else turns)
    if not exclusive and not regular:
        return [dict(item) for item in segments], {}
    labels_in_order: list[str] = []
    for _start, _end, label in sorted(regular or exclusive, key=lambda row: (row[0], row[1], row[2])):
        if label not in labels_in_order:
            labels_in_order.append(label)
    label_map = _stable_label_map(segments, regular or exclusive, labels_in_order)
    enriched: list[dict] = []
    for raw in sorted((dict(item) for item in segments if isinstance(item, dict)),
                      key=lambda item: (float(item.get("start", 0.0) or 0.0), float(item.get("end", 0.0) or 0.0))):
        try:
            start = max(0.0, float(raw.get("start", 0.0) or 0.0))
            end = max(start, float(raw.get("end", start) or start))
        except (TypeError, ValueError):
            enriched.append(raw)
            continue
        split_rows = _split_segment_by_word_speakers(raw, exclusive, regular, label_map)
        if split_rows:
            enriched.extend(split_rows)
            continue
        source_label, confidence = _speaker_for_interval(start, end, exclusive, min_coverage=min_coverage)
        raw["speaker_id"] = label_map.get(source_label, "") if source_label else ""
        raw["speaker_confidence"] = round(confidence, 3)
        raw["overlap_speaker_ids"] = _overlap_candidates(start, end, regular, label_map)
        enriched.append(raw)
    stats = _speaker_stats(regular or exclusive, label_map)
    stats["_meta"] = {
        "unassigned_segments": sum(1 for item in enriched if not item.get("speaker_id")),
        "overlapping_segments": sum(1 for item in enriched if len(item.get("overlap_speaker_ids", [])) > 1),
        "speakers_detected": len(label_map),
    }
    return enriched, stats


def _annotation_turns(annotation) -> list[tuple[float, float, str]]:
    if annotation is None:
        return []
    turns = []
    for turn, _track, label in annotation.itertracks(yield_label=True):
        turns.append((float(turn.start), float(turn.end), str(label)))
    return _normalise_turns(turns)


def apply_speaker_diarization(
    audio_path: Path,
    segments: list[dict],
    project_root: Path,
    *,
    hf_token: str = "",
    min_speakers: int | None = None,
    max_speakers: int | None = None,
    device: str = "auto",
    stage_callback: Callable[[str], None] | None = None,
    cancel_callback: Callable[[], bool] | None = None,
) -> tuple[list[dict], dict]:
    """Run local Community-1. Native inference cannot be interrupted mid-kernel yet."""
    from transcription.onnx_diarization import available, diarize
    if available(project_root):
        turns = diarize(audio_path, project_root, min_speakers, max_speakers, stage_callback, cancel_callback)
        enriched, stats = assign_speakers_to_segments(segments, turns, regular_turns=turns)
        stats.setdefault('_meta', {})['backend'] = 'sherpa-onnx'
        return enriched, stats
    model_dir = diarization_model_path(project_root)
    if not is_diarization_model_complete(model_dir):
        raise RuntimeError(
            f"Локальная модель диаризации не найдена или неполна: {model_dir}. "
            "Откройте Settings → Менеджер моделей → Диаризация и выполните проверку."
        )
    if cancel_callback and cancel_callback():
        raise InterruptedError("Диаризация отменена пользователем до запуска модели.")
    try:
        from pyannote.audio import Pipeline
    except Exception:
        Pipeline = None
        if _external_runtime(Path(project_root)) is None:
            raise RuntimeError(
                "pyannote.audio недоступен. Запустите Install_Speaker_Diarization.bat рядом с Spiker.exe, "
                "чтобы установить отдельное окружение диаризации."
            )

    if stage_callback:
        stage_callback("Загружаем локальную модель участников…")
    token = (hf_token or "").strip() or None
    kwargs = {}
    minimum = int(min_speakers or 0)
    maximum = int(max_speakers or 0)
    if minimum > 0 and maximum > 0 and minimum > maximum:
        raise ValueError("Минимальное число спикеров не может быть больше максимального.")
    if minimum > 0 and maximum > 0 and minimum == maximum:
        kwargs["num_speakers"] = minimum
    else:
        if minimum > 0:
            kwargs["min_speakers"] = minimum
        if maximum > 0:
            kwargs["max_speakers"] = maximum

    if stage_callback:
        stage_callback("Анализируем голоса и интервалы одновременной речи…")
    if Pipeline is None:
        regular_turns, exclusive_turns = _run_external_diarization(
            audio_path, model_dir, Path(project_root), min_speakers=min_speakers,
            max_speakers=max_speakers, device=device, stage_callback=stage_callback,
            cancel_callback=cancel_callback,
        )
    else:
        try:
            pipeline = Pipeline.from_pretrained(str(model_dir), token=token)
            if pipeline is None:
                raise RuntimeError("pyannote не вернул pipeline.")
        except Exception as exc:
            raise RuntimeError(
                "Не удалось загрузить Community-1 из локальной папки. Проверьте config.yaml и каталоги "
                f"segmentation / embedding / plda. Детали: {exc}"
            ) from exc

        if cancel_callback and cancel_callback():
            raise InterruptedError("Диаризация отменена пользователем до анализа аудио.")
        if device in {"cuda", "auto"}:
            try:
                import torch
                if device == "cuda" and not torch.cuda.is_available():
                    raise RuntimeError("PyTorch не видит CUDA-устройство.")
                if torch.cuda.is_available():
                    pipeline.to(torch.device("cuda"))
            except Exception as exc:
                if device == "cuda":
                    LOGGER.warning("pyannote CUDA unavailable, using CPU: %s", exc)
                    if stage_callback:
                        stage_callback("CUDA недоступна для pyannote; продолжаем на CPU…")
                else:
                    LOGGER.info("pyannote will run on CPU: %s", exc)

        try:
            output = pipeline(str(audio_path), **kwargs)
        except Exception as exc:
            if cancel_callback and cancel_callback():
                raise InterruptedError("Диаризация отменена пользователем после завершения текущего шага.") from exc
            raise RuntimeError(f"pyannote завершил анализ с ошибкой: {exc}") from exc
        if cancel_callback and cancel_callback():
            raise InterruptedError("Диаризация отменена пользователем; результат не применён.")

        regular_annotation = getattr(output, "speaker_diarization", None)
        exclusive_annotation = getattr(output, "exclusive_speaker_diarization", None)
        regular_turns = _annotation_turns(regular_annotation) if regular_annotation is not None else []
        exclusive_turns = _annotation_turns(exclusive_annotation) if exclusive_annotation is not None else []
        if not exclusive_turns:
            exclusive_turns = regular_turns
        if not regular_turns:
            regular_turns = exclusive_turns
    if not exclusive_turns:
        raise RuntimeError("pyannote не обнаружил голосовых дорожек или вернул пустой результат.")

    enriched, stats = assign_speakers_to_segments(
        segments, exclusive_turns, regular_turns=regular_turns,
    )
    LOGGER.info(
        "Diarization completed: speakers=%d turns=%d overlaps=%d unassigned=%d",
        stats.get("_meta", {}).get("speakers_detected", 0), len(regular_turns),
        stats.get("_meta", {}).get("overlapping_segments", 0),
        stats.get("_meta", {}).get("unassigned_segments", 0),
    )
    return enriched, stats
