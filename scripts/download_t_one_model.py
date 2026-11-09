"""Download and safely unpack the optional sherpa-onnx Russian T-one model."""
from __future__ import annotations

import hashlib
import json
import sys
import argparse
import tarfile
from pathlib import Path

from archive_utils import safe_extract_tar
from transcription.live_streaming import DEFAULT_MODEL_DIR, MODEL_URL
from app_paths import get_user_data_root
from install_models import _download

_ROOT = Path(__file__).resolve().parents[1]
_LOCK = json.loads((_ROOT / "models" / "verified-assets.json").read_text(encoding="utf-8"))
_T_ONE_HASHES = _LOCK["model_files"]["t_one"]


def _verify_t_one_model(model_dir: Path) -> bool:
    if not model_dir.is_dir():
        return False
    actual_files = {path.name for path in model_dir.iterdir() if path.is_file()}
    if actual_files != set(_T_ONE_HASHES):
        return False
    for name, expected in _T_ONE_HASHES.items():
        path = model_dir / name
        if not path.is_file():
            return False
        digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        if digest.lower() != expected.lower():
            return False
    return True


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", type=Path, help="Explicit model destination (used by release builds).")
    args = parser.parse_args()
    target_root = args.target_root or (get_user_data_root(root) / "models" / "sherpa-onnx")
    target_root = target_root.expanduser().resolve()
    target = target_root / DEFAULT_MODEL_DIR
    model_file = target / "model.onnx"
    tokens_file = target / "tokens.txt"
    try:
        already_ready = (
            model_file.is_file() and model_file.stat().st_size >= 100 * 1024 * 1024
            and tokens_file.is_file() and tokens_file.stat().st_size >= 100
            and _verify_t_one_model(target)
        )
    except OSError:
        already_ready = False
    if already_ready:
        print(f"Модель уже установлена и прошла проверку: {target}")
        return 0
    target_root.mkdir(parents=True, exist_ok=True)
    archive_path = target_root / (DEFAULT_MODEL_DIR + ".tar.bz2")
    print("Загрузка русской потоковой модели T-one (файл модели около 138 МБ)…")
    try:
        _download(MODEL_URL, archive_path, min_bytes=100 * 1024 * 1024, retries=5)
        print("Распаковка модели…")
        with tarfile.open(archive_path, "r:bz2") as archive:
            safe_extract_tar(archive, target_root, max_total_bytes=256 * 1024**2)
        if not (model_file.is_file() and model_file.stat().st_size >= 100 * 1024 * 1024
                and tokens_file.is_file() and tokens_file.stat().st_size >= 100
                and _verify_t_one_model(target)):
            raise RuntimeError("T-one распакована неполно или её SHA-256 не совпадает с закреплённой моделью.")
        archive_path.unlink(missing_ok=True)
        print(f"Модель T-one установлена: {target}")
        return 0
    except Exception as exc:
        archive_path.with_name(archive_path.name + ".part").unlink(missing_ok=True)
        print(f"Ошибка загрузки/установки модели: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
