"""Install Spiker speech models into their canonical local folders.

This script deliberately keeps model downloads explicit and validates every install.
It never stores Hugging Face credentials in Spiker settings or files.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import importlib.util
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from app_paths import get_user_data_root
from model_paths import native_model_path
from archive_utils import safe_extract_zip
ASSET_LOCK = json.loads((ROOT / "models" / "verified-assets.json").read_text(encoding="utf-8"))
MODELS = get_user_data_root(ROOT) / "models"
WHISPER_DIR = MODELS / "whisper"
WHISPER_FILE = WHISPER_DIR / "ggml-small.bin"
WHISPER_BUNDLED_FILE = ROOT / "models" / "whisper" / "ggml-small.bin"
WHISPER_URL = (
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/"
    "90a64d80ea254cf67575b41a5971f972c79f7b45/ggml-small.bin"
)
WHISPER_SHA256 = "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b"
VOSK_DIR = MODELS / "vosk" / "vosk-model-small-ru-0.22"
VOSK_URL = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
VOSK_REQUIRED = ("am/final.mdl", "graph/HCLr.fst", "graph/Gr.fst", "graph/phones/word_boundary.int")
FASTER_DIR = MODELS / "faster-whisper" / "small"
FASTER_REPO = "Systran/faster-whisper-small"
FASTER_REVISION = "2ec96c5472da50d38d40c0cfe0602af2e94b4c8a"
FASTER_SHA256 = "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"
_FASTER_CHECK_CACHE: tuple[tuple[int, int], bool] | None = None
FASTER_MODEL_NOTICE = """Model attribution

Model: Systran/faster-whisper-small
Revision: 2ec96c5472da50d38d40c0cfe0602af2e94b4c8a
License: MIT (as identified by the upstream Hugging Face model card)
Source: https://huggingface.co/Systran/faster-whisper-small/tree/2ec96c5472da50d38d40c0cfe0602af2e94b4c8a
model.bin SHA-256: 3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671
"""
SHERPA_DIR = MODELS / "sherpa-onnx" / "sherpa-onnx-streaming-t-one-russian-2025-09-08"
PYANNOTE_DIR = MODELS / "pyannote" / "speaker-diarization-community-1"
PYANNOTE_REPO = "pyannote/speaker-diarization-community-1"
PYANNOTE_URL = f"https://huggingface.co/{PYANNOTE_REPO}"
PYANNOTE_AUDIO_VERSION = "4.0.7"


def _run(*args: str) -> None:
    command = [sys.executable, *args]
    subprocess.run(command, check=True)


def _download(
    url: str,
    destination: Path,
    *,
    expected_sha256: str = "",
    min_bytes: int = 1,
    retries: int = 4,
) -> None:
    """Download with retry/resume support, then validate before atomic placement."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    last_error: Exception | None = None

    for attempt in range(1, max(1, int(retries)) + 1):
        offset = temporary.stat().st_size if temporary.exists() else 0
        headers = {"User-Agent": "Spiker-Model-Installer/3.0.8"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                status = int(getattr(response, "status", response.getcode()))
                # Some mirrors ignore Range and return the full object. Restart safely.
                append = bool(offset and status == 206)
                if offset and not append:
                    offset = 0
                total = int(response.headers.get("Content-Length", "0") or 0) + offset
                received = offset
                digest = hashlib.sha256()
                if append:
                    with temporary.open("rb") as existing:
                        for block in iter(lambda: existing.read(1024 * 1024), b""):
                            digest.update(block)
                mode = "ab" if append else "wb"
                with temporary.open(mode) as output:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        digest.update(block)
                        received += len(block)
                        if total:
                            print(
                                f"\r  Загружено {received / 1024**2:.1f} / {total / 1024**2:.1f} МБ",
                                end="", flush=True,
                            )
                print()

            if received < min_bytes:
                raise RuntimeError(f"Файл слишком мал: {received} байт.")
            actual_hash = digest.hexdigest()
            if expected_sha256 and actual_hash.lower() != expected_sha256.lower():
                raise RuntimeError(f"SHA-256 не совпадает: получено {actual_hash}.")
            temporary.replace(destination)
            return
        except Exception as exc:
            last_error = exc
            if attempt < max(1, int(retries)):
                print(
                    f"\nСбой загрузки (попытка {attempt}/{retries}): {exc}\n"
                    "Сохраняем полученную часть и повторяем…"
                )
                time.sleep(min(2 ** (attempt - 1), 12))
            else:
                break

    temporary.unlink(missing_ok=True)
    raise RuntimeError(f"Не удалось скачать {url} после {retries} попыток: {last_error}") from last_error


def _check_whisper() -> bool:
    try:
        return any(
            path.is_file() and path.stat().st_size >= 100 * 1024 * 1024
            for path in (WHISPER_FILE, WHISPER_BUNDLED_FILE)
        )
    except OSError:
        return False


def _check_faster() -> bool:
    global _FASTER_CHECK_CACHE
    config = FASTER_DIR / "config.json"
    weights = FASTER_DIR / "model.bin"
    required = (config, weights, FASTER_DIR / "tokenizer.json", FASTER_DIR / "vocabulary.txt")
    try:
        if not all(path.is_file() for path in required) or weights.stat().st_size < 100 * 1024 * 1024:
            return False
        stat = weights.stat()
        key = (stat.st_mtime_ns, stat.st_size)
        if _FASTER_CHECK_CACHE is not None and _FASTER_CHECK_CACHE[0] == key:
            return _FASTER_CHECK_CACHE[1]
        digest = hashlib.sha256()
        with weights.open("rb") as model_file:
            for block in iter(lambda: model_file.read(1024 * 1024), b""):
                digest.update(block)
        ready = digest.hexdigest().lower() == FASTER_SHA256
        _FASTER_CHECK_CACHE = (key, ready)
        return ready
    except OSError:
        return False


def _check_t_one() -> bool:
    model = SHERPA_DIR / "model.onnx"
    tokens = SHERPA_DIR / "tokens.txt"
    try:
        if not (model.is_file() and model.stat().st_size >= 100 * 1024 * 1024
                and tokens.is_file() and tokens.stat().st_size >= 100):
            return False
        _verify_locked_model_tree(SHERPA_DIR, "t_one")
        return True
    except (OSError, RuntimeError):
        return False


def _check_vosk() -> bool:
    return all((VOSK_DIR / item).is_file() for item in VOSK_REQUIRED)


def _check_diarization() -> bool:
    """Check the complete local Community-1 pipeline, not only its top-level YAML."""
    if not (PYANNOTE_DIR / "config.yaml").is_file():
        return False
    required_dirs = ("segmentation", "embedding", "plda")
    for name in required_dirs:
        folder = PYANNOTE_DIR / name
        if not folder.is_dir() or not any(path.is_file() for path in folder.rglob("*")):
            return False
    return True


def _pyannote_runtime_info() -> tuple[bool, str]:
    """Import the actual Pipeline class; a namespace package alone is not sufficient."""
    try:
        from importlib.metadata import version
        from pyannote.audio import Pipeline  # noqa: F401
        return True, version("pyannote-audio")
    except Exception as exc:
        return False, str(exc)


def print_status() -> bool:
    checks = [
        ("Whisper.cpp Small", _check_whisper(), str(WHISPER_FILE)),
        ("faster-whisper Small", _check_faster(), str(FASTER_DIR)),
        ("Sherpa-ONNX T-one", _check_t_one(), str(SHERPA_DIR)),
        ("Vosk Russian Small", _check_vosk(), str(VOSK_DIR)),
        ("pyannote Community-1", _check_diarization(), str(PYANNOTE_DIR)),
    ]
    print("\nСостояние локальных моделей СПИКЕР:")
    for name, ready, location in checks:
        print(f"  [{'OK' if ready else '--'}] {name}: {location}")
    def module_ready(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            return False

    pywhispercpp = module_ready("pywhispercpp")
    faster = module_ready("faster_whisper")
    sherpa = module_ready("sherpa_onnx")
    vosk = module_ready("vosk")
    pyannote, pyannote_version = _pyannote_runtime_info()
    file_ready = (_check_whisper() and pywhispercpp) or (_check_faster() and faster)
    live_ready = (_check_t_one() and sherpa) or (_check_vosk() and vosk)
    print("\nБиблиотеки и доступность движков:")
    print(f"  [{'OK' if pywhispercpp else '--'}] pywhispercpp")
    print(f"  [{'OK' if faster and _check_faster() else '--'}] faster-whisper + модель Small")
    print(f"  [{'OK' if sherpa and _check_t_one() else '--'}] sherpa-onnx + T-one")
    print(f"  [{'OK' if vosk and _check_vosk() else '--'}] Vosk + русская модель")
    print(f"  [{'OK' if pyannote and _check_diarization() else '--'}] pyannote.audio {pyannote_version} + Community-1")
    print(f"\nФайловая транскрибация: {'ГОТОВА' if file_ready else 'НЕ ГОТОВА'}")
    print(f"Потоковая диктовка: {'ГОТОВА' if live_ready else 'НЕ ГОТОВА'}")
    print("Диаризация: " + ("ГОТОВА" if pyannote and _check_diarization() else "не установлена (отдельный шаг)"))
    # Optional accelerators must not make the launcher reinstall an otherwise usable app.
    return file_ready and live_ready


def install_whisper() -> None:
    if _check_whisper():
        source = WHISPER_FILE if WHISPER_FILE.is_file() else WHISPER_BUNDLED_FILE
        print(f"Whisper.cpp уже установлен: {source}")
        return
    print("\n1/3. Скачивание Whisper.cpp Small (~466 MiB), проверка SHA-256…")
    _download(WHISPER_URL, WHISPER_FILE, expected_sha256=WHISPER_SHA256, min_bytes=100 * 1024 * 1024)
    print(f"Установлено: {WHISPER_FILE}")


def install_faster_whisper() -> None:
    print("\nУстановка faster-whisper и русскоязычной модели Small (~486 MiB)…")
    if importlib.util.find_spec("faster_whisper") is None:
        _run("-m", "pip", "install", "faster-whisper>=1.1,<2")
    if _check_faster():
        (FASTER_DIR / "MODEL_SOURCE.txt").write_text(FASTER_MODEL_NOTICE, encoding="utf-8")
        print(f"Модель faster-whisper уже установлена: {FASTER_DIR}")
        return
    try:
        if importlib.util.find_spec("huggingface_hub") is None:
            _run("-m", "pip", "install", "huggingface_hub>=0.23")
        from huggingface_hub import snapshot_download
        FASTER_DIR.mkdir(parents=True, exist_ok=True)
        weights = FASTER_DIR / "model.bin"
        if weights.is_file() and weights.stat().st_size >= 100 * 1024 * 1024:
            weights.unlink()
        snapshot_download(
            repo_id=FASTER_REPO,
            revision=FASTER_REVISION,
            local_dir=str(FASTER_DIR),
            allow_patterns=["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"],
        )
    except Exception as exc:
        raise RuntimeError(f"Не удалось установить faster-whisper Small: {exc}") from exc
    if not _check_faster():
        raise RuntimeError(
            f"После загрузки faster-whisper модель неполна или SHA-256 не совпадает ({FASTER_SHA256}): {FASTER_DIR}"
        )
    (FASTER_DIR / "MODEL_SOURCE.txt").write_text(FASTER_MODEL_NOTICE, encoding="utf-8")
    print(f"Установлено: {FASTER_DIR}")


def install_sherpa() -> None:
    print("\n2/3. Установка sherpa-onnx и русской потоковой модели T-one…")
    if importlib.util.find_spec("sherpa_onnx") is None:
        _run("-m", "pip", "install", "sherpa-onnx>=1.12,<2")
    if not _check_t_one():
        _run(str(ROOT / "scripts" / "download_t_one_model.py"))
    if not _check_t_one():
        raise RuntimeError("T-one скачана, но model.onnx или tokens.txt не найдены в целевой папке.")
    print(f"Установлено: {SHERPA_DIR}")


def _safe_extract_zip(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        expected = set(ASSET_LOCK["model_files"]["vosk"])
        root_name = "vosk-model-small-ru-0.22"
        found = set()
        for member in archive.infolist():
            name = member.filename
            if "\\" in name or ":" in name or not name.startswith(root_name + "/"):
                if name.rstrip("/") != root_name:
                    raise RuntimeError(f"Путь не соответствует закреплённой структуре Vosk: {name}")
            relative = name[len(root_name):].lstrip("/").rstrip("/")
            if not relative:
                continue
            if member.is_dir():
                if not any(item.startswith(relative + "/") for item in expected):
                    raise RuntimeError(f"Неожиданная папка в архиве Vosk: {name}")
            elif relative not in expected:
                raise RuntimeError(f"Неожиданный файл в архиве Vosk: {name}")
            else:
                found.add(relative)
        if found != expected:
            raise RuntimeError("В ZIP-архиве Vosk отсутствуют файлы с закреплёнными SHA-256.")
        safe_extract_zip(
            archive, destination,
            allowed_top_level={"vosk-model-small-ru-0.22"},
            max_total_bytes=256 * 1024**2,
        )


def _verify_locked_model_tree(folder: Path, model_key: str) -> None:
    expected_files = ASSET_LOCK["model_files"][model_key]
    for relative, expected_sha256 in expected_files.items():
        path = folder / relative
        if not path.is_file():
            raise RuntimeError(f"Не найдена закреплённая часть модели: {path}")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual.lower() != expected_sha256.lower():
            raise RuntimeError(f"Контрольная сумма не совпала: {path}")


def _validate_vosk_model() -> None:
    if not _check_vosk():
        raise RuntimeError(f"Модель Vosk неполная: {VOSK_DIR}")
    try:
        from vosk import Model
        validated_model = Model(native_model_path(VOSK_DIR))
        del validated_model
    except Exception as exc:
        raise RuntimeError(f"Файлы Vosk найдены, но модель не загружается: {exc}") from exc


def install_vosk(target_root: Path | None = None) -> None:
    global VOSK_DIR
    if target_root is not None:
        VOSK_DIR = Path(target_root).expanduser().resolve() / "vosk-model-small-ru-0.22"
    print("\n3/3. Проверка Vosk и загрузка резервной русской модели (~45 MiB)…")
    if importlib.util.find_spec("vosk") is None:
        _run("-m", "pip", "install", "vosk==0.3.45")
    if _check_vosk():
        _verify_locked_model_tree(VOSK_DIR, "vosk")
        _validate_vosk_model()
        print(f"Vosk уже установлен: {VOSK_DIR}")
        return
    archive = VOSK_DIR.parent / "vosk-model-small-ru-0.22.zip"
    _download(VOSK_URL, archive, min_bytes=10 * 1024 * 1024)
    try:
        _safe_extract_zip(archive, archive.parent)
        if not _check_vosk():
            raise RuntimeError("Архив Vosk распакован, но обязательные файлы модели отсутствуют.")
        _verify_locked_model_tree(VOSK_DIR, "vosk")
    finally:
        archive.unlink(missing_ok=True)
    _validate_vosk_model()
    print(f"Установлено: {VOSK_DIR}")


def install_basic() -> None:
    """Attempt each base engine independently so one failed download does not block fallbacks."""
    steps = (
        ("Whisper.cpp Small", install_whisper),
        ("faster-whisper Small", install_faster_whisper),
        ("Sherpa-ONNX T-one", install_sherpa),
        ("Vosk Russian Small", install_vosk),
    )
    failures: list[tuple[str, str]] = []
    for label, installer in steps:
        try:
            installer()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            failures.append((label, str(exc)))
            print(f"\n[ПРЕДУПРЕЖДЕНИЕ] {label}: {exc}")
            print("Продолжаем установку остальных компонентов и резервных движков…")

    ready = print_status()
    if failures:
        print("\nНе удалось установить отдельные компоненты:")
        for label, message in failures:
            print(f"  - {label}: {message}")
    if not ready:
        raise RuntimeError(
            "Не собрана минимально работоспособная конфигурация. Нужна хотя бы одна модель для файлов "
            "(Whisper.cpp или faster-whisper) и одна для диктовки (T-one или Vosk). "
            "Проверьте подключение к интернету, свободное место и повторите Install_Models.bat."
        )
    if failures:
        print("\nСПИКЕР готов к базовой работе; перечисленные выше дополнительные движки недоступны.")
    else:
        print("\nБазовые модели установлены. Доступны файловая транскрибация, потоковая диктовка и резервные движки.")


def print_diarization_status() -> bool:
    pyannote_runtime, runtime_detail = _pyannote_runtime_info()
    ready = pyannote_runtime and _check_diarization()
    print("\nАвтоматическое определение участников:")
    print(f"  [{'OK' if pyannote_runtime else '--'}] pyannote.audio runtime: {runtime_detail}")
    print(f"  [{'OK' if _check_diarization() else '--'}] Community-1 model: {PYANNOTE_DIR}")
    return ready


def install_diarization() -> None:
    print("\nУстановка автоматического определения участников (pyannote Community-1).")
    print("Эта модель требует принять условия доступа на Hugging Face и использовать персональный токен.")
    print(f"Откройте страницу модели и нажмите Accept/Agree: {PYANNOTE_URL}")
    try:
        webbrowser.open(PYANNOTE_URL)
    except Exception:
        pass
    input("После принятия условий нажмите Enter здесь…")
    token = getpass.getpass("Вставьте Hugging Face read token (ввод скрыт; токен не сохраняется): ").strip()
    if not token:
        raise RuntimeError("Токен не указан. Модель pyannote не установлена.")
    pyannote_installed, installed_version = _pyannote_runtime_info()
    # Pin the known current 4.0.x release rather than the original 4.0.0 baseline.
    # 4.0.2 corrected compatible torch/torchcodec/torchaudio pins; 4.0.7 adds
    # Pipeline.from_pretrained subfolder support and sequential batch inference.
    if not pyannote_installed or installed_version != PYANNOTE_AUDIO_VERSION:
        _run("-m", "pip", "install", "--upgrade", f"pyannote.audio=={PYANNOTE_AUDIO_VERSION}")
    pyannote_installed, installed_version = _pyannote_runtime_info()
    if not pyannote_installed:
        raise RuntimeError(f"pyannote.audio не импортируется после установки: {installed_version}")
    if importlib.util.find_spec("huggingface_hub") is None:
        _run("-m", "pip", "install", "huggingface_hub>=0.23")
    from huggingface_hub import snapshot_download
    PYANNOTE_DIR.mkdir(parents=True, exist_ok=True)
    print("Загрузка pyannote Community-1. Первый запуск может занять несколько минут и скачать несколько моделей…")
    try:
        snapshot_download(repo_id=PYANNOTE_REPO, local_dir=str(PYANNOTE_DIR), token=token)
    except Exception as exc:
        raise RuntimeError(
            "Не удалось получить модель. Проверьте, что условия доступа приняты именно для этого аккаунта, "
            "токен имеет права Read и модель доступна вашему аккаунту. Подробности: " + str(exc)
        ) from exc
    if not _check_diarization():
        raise RuntimeError(
            "Загрузка завершилась, но неполна: нужны config.yaml и каталоги segmentation, embedding, plda. "
            f"Проверьте локальную модель: {PYANNOTE_DIR}"
        )
    try:
        from pyannote.audio import Pipeline
        validated_pipeline = Pipeline.from_pretrained(str(PYANNOTE_DIR))
        if validated_pipeline is None:
            raise RuntimeError("Pipeline.from_pretrained вернул None")
        del validated_pipeline
    except Exception as exc:
        raise RuntimeError(
            "Файлы Community-1 скачаны, но локальный pipeline не загрузился. "
            "Проверьте установку ffmpeg, torchcodec и совместимость PyTorch. Подробности: " + str(exc)
        ) from exc
    print(f"Модель участников установлена и проверена локально: {PYANNOTE_DIR} (pyannote.audio {installed_version})")
    print("Токен не был сохранён в настройках или на диске.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Установка локальных моделей СПИКЕР")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="только проверить базовые модели и библиотеки")
    mode.add_argument("--check-diarization", action="store_true", help="проверить модель pyannote для участников")
    mode.add_argument("--faster-whisper", action="store_true", help="установить faster-whisper Small и проверить SHA-256")
    mode.add_argument("--vosk", action="store_true", help="установить и проверить резервную русскую модель Vosk")
    parser.add_argument("--target-root", type=Path, help="модельная папка назначения (для сборщика релизов)")
    mode.add_argument("--basic", action="store_true", help="установить Whisper, T-one и Vosk")
    mode.add_argument("--diarization", action="store_true", help="установить pyannote и локальную модель участников")
    mode.add_argument("--all", action="store_true", help="установить базовые модели и затем pyannote")
    args = parser.parse_args()
    try:
        if args.check:
            return 0 if print_status() else 1
        if args.check_diarization:
            return 0 if print_diarization_status() else 1
        if args.faster_whisper:
            install_faster_whisper()
            print_status()
            return 0
        if args.vosk:
            install_vosk(args.target_root)
            print_status()
            return 0
        if args.diarization:
            install_diarization()
        elif args.all:
            install_basic()
            install_diarization()
        else:
            install_basic()
        print_status()
        if args.diarization or args.all:
            print_diarization_status()
        return 0
    except KeyboardInterrupt:
        print("\nУстановка прервана пользователем.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\nОшибка установки моделей: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
