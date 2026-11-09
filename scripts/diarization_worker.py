"""Optional external pyannote runner for frozen Windows builds.

The main PyInstaller application stays compact. This helper runs inside an
optional Python 3.11 environment created only when the user enables diarization.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import webbrowser
from pathlib import Path

MODEL_REPO = "pyannote/speaker-diarization-community-1"
MODEL_URL = "https://huggingface.co/pyannote/speaker-diarization-community-1"
MODEL_RELATIVE_PATH = Path("models") / "pyannote" / "speaker-diarization-community-1"
from app_paths import get_user_data_root


def _model_complete(model_dir: Path) -> bool:
    if not (model_dir / "config.yaml").is_file():
        return False
    return all(
        (model_dir / name).is_dir() and any(path.is_file() for path in (model_dir / name).rglob("*"))
        for name in ("segmentation", "embedding", "plda")
    )


def install_model(project_root: Path) -> None:
    print("Автоматическая разбивка на спикеров использует pyannote Community-1.")
    print("Сначала примите условия доступа на Hugging Face:", MODEL_URL)
    try:
        webbrowser.open(MODEL_URL)
    except Exception:
        pass
    input("После принятия условий нажмите Enter…")
    token = getpass.getpass("Вставьте Hugging Face Read token (ввод скрыт; токен не сохраняется): ").strip()
    if not token:
        raise RuntimeError("Токен не указан; модель не установлена.")

    from huggingface_hub import snapshot_download
    from pyannote.audio import Pipeline

    model_dir = get_user_data_root(project_root) / MODEL_RELATIVE_PATH
    model_dir.mkdir(parents=True, exist_ok=True)
    print("Загружаем локальную модель. Это может занять несколько минут…")
    snapshot_download(repo_id=MODEL_REPO, local_dir=str(model_dir), token=token)
    if not _model_complete(model_dir):
        raise RuntimeError(f"Загрузка завершилась, но модель неполная: {model_dir}")
    pipeline = Pipeline.from_pretrained(str(model_dir), token=token)
    if pipeline is None:
        raise RuntimeError("pyannote не смог открыть загруженную модель.")
    del pipeline
    print(f"Модель установлена и проверена: {model_dir}")
    print("Токен не сохранялся. После закрытия окна токен больше не нужен.")


def _turns(annotation) -> list[list]:
    if annotation is None:
        return []
    return [[float(turn.start), float(turn.end), str(label)]
            for turn, _track, label in annotation.itertracks(yield_label=True)]


def run_diarization(args) -> None:
    from pyannote.audio import Pipeline

    model_dir = Path(args.model_dir)
    if not _model_complete(model_dir):
        raise RuntimeError(f"Локальная модель pyannote неполная: {model_dir}")
    pipeline = Pipeline.from_pretrained(str(model_dir))
    if pipeline is None:
        raise RuntimeError("pyannote не вернул pipeline.")

    if args.device in {"cuda", "auto"}:
        try:
            import torch
            if args.device == "cuda" and not torch.cuda.is_available():
                print("CUDA недоступна; используем CPU.", file=sys.stderr)
            elif torch.cuda.is_available():
                pipeline.to(torch.device("cuda"))
        except Exception as exc:
            print(f"CUDA недоступна; используем CPU: {exc}", file=sys.stderr)

    kwargs = {}
    minimum, maximum = max(0, int(args.min_speakers)), max(0, int(args.max_speakers))
    if minimum and maximum and minimum > maximum:
        raise ValueError("Минимальное число спикеров больше максимального.")
    if minimum and maximum and minimum == maximum:
        kwargs["num_speakers"] = minimum
    else:
        if minimum:
            kwargs["min_speakers"] = minimum
        if maximum:
            kwargs["max_speakers"] = maximum

    output = pipeline(str(Path(args.audio)), **kwargs)
    regular = getattr(output, "speaker_diarization", None)
    exclusive = getattr(output, "exclusive_speaker_diarization", None)
    if regular is None and hasattr(output, "itertracks"):
        regular = output
    if exclusive is None:
        exclusive = regular
    payload = {"regular_turns": _turns(regular), "exclusive_turns": _turns(exclusive)}
    if not payload["regular_turns"] and not payload["exclusive_turns"]:
        raise RuntimeError("pyannote не обнаружил голосовых дорожек.")
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-model", metavar="PROJECT_ROOT")
    parser.add_argument("--audio")
    parser.add_argument("--model-dir")
    parser.add_argument("--output")
    parser.add_argument("--min-speakers", type=int, default=0)
    parser.add_argument("--max-speakers", type=int, default=0)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    try:
        if args.install_model:
            project_root = Path(args.install_model).resolve()
        else:
            project_root = Path(args.model_dir).resolve().parents[2]
        mpl_config = get_user_data_root(project_root) / "data" / "matplotlib"
        mpl_config.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(mpl_config))
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        if args.install_model:
            install_model(project_root)
        else:
            if not args.audio or not args.model_dir or not args.output:
                parser.error("--audio, --model-dir и --output обязательны для диаризации")
            run_diarization(args)
    except Exception as exc:
        print(f"Ошибка диаризации: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
