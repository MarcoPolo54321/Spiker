"""Guarded GUI entry point with persistent stdout/stderr for pythonw."""
from __future__ import annotations
import logging
import hashlib
import runpy
import sys
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from app_paths import get_user_data_root

USER_DATA_ROOT = get_user_data_root(ROOT)
LOGS = USER_DATA_ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

# pythonw.exe sets sys.stderr/sys.stdout to None. pywhispercpp uses
# sys.stderr.flush() during native model initialization, so keep real streams.
try:
    _native_log = open(LOGS / "pythonw_streams.log", "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _native_log
    if sys.stderr is None:
        sys.stderr = _native_log
except Exception:
    # Last-resort stream for libraries expecting a file-like stderr.
    import io
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()

try:
    from runtime_paths import extend_optional_runtime_paths
    extend_optional_runtime_paths(ROOT)
except Exception:
    logging.getLogger("startup").exception("Could not extend optional ML runtime paths")
try:
    from app_logging import configure_logging
    configure_logging(ROOT)
except Exception:
    pass

logger = logging.getLogger("startup")
logger.info("Guarded application entry point started")


def _packaging_smoke_test() -> None:
    """Verify imports and packaged UI/resources without starting a long-running GUI."""
    # Initialize Qt before other native audio libraries. Some of those ship
    # Microsoft runtime DLLs of their own; loading them first can make Windows
    # bind Qt to an older already-loaded runtime in the frozen process.
    from PySide6.QtWidgets import QApplication, QDialog, QMainWindow
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    import imageio_ffmpeg
    import pyaudio
    import vosk
    import pywhispercpp.model
    from Queue_page import QueuePage  # noqa: F401 — explicit frozen-import check
    from UI.AI_page import AIProcessingPage  # noqa: F401 — explicit frozen-import check
    from UI.Dictation_audio_menu_script import Ui_Dialog_dict_audio  # noqa: F401
    from UI.Info_menu_script import Ui_Dialog_info
    from UI.Main_menu_script import Ui_MainWindow
    from UI.Settings_page import SettingsPage  # noqa: F401
    from transcription.audio_preparation import prepare_media_audio  # noqa: F401
    from transcription.wav_to_text import find_whisper_model  # noqa: F401

    required_assets = (
        ROOT / "Spiker.ico",
        ROOT / "scripts" / "main.py",
        ROOT / "icons" / "spiker_app.png",
        ROOT / "icons" / "ai_processing.png",
        ROOT / "icons" / "training_button.png",
    )
    if "--require-whisper-model" in sys.argv:
        required_assets += (ROOT / "models" / "whisper" / "ggml-small.bin",)
    if "--require-faster-whisper" in sys.argv:
        try:
            import faster_whisper  # noqa: F401
            import ctranslate2  # noqa: F401
        except Exception as exc:
            raise RuntimeError(f"faster-whisper/CTranslate2 runtime is missing or incompatible: {exc}") from exc
    if "--require-faster-whisper-model" in sys.argv:
        faster_model = ROOT / "models" / "faster-whisper" / "small"
        required_faster_files = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")
        missing_faster_files = [name for name in required_faster_files if not (faster_model / name).is_file()]
        model_path = faster_model / "model.bin"
        if missing_faster_files or model_path.stat().st_size < 100 * 1024 * 1024:
            raise FileNotFoundError(
                "Bundled faster-whisper Small model is incomplete: "
                + (", ".join(missing_faster_files) if missing_faster_files else str(faster_model / "model.bin"))
            )
        digest = hashlib.sha256()
        with model_path.open("rb") as model_file:
            for block in iter(lambda: model_file.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671":
            raise RuntimeError("Bundled faster-whisper Small model failed its pinned SHA-256 check.")
    if "--require-vosk-model" in sys.argv:
        vosk_model = ROOT / "models" / "vosk" / "vosk-model-small-ru-0.22"
        required_vosk_files = (
            "am/final.mdl", "graph/HCLr.fst", "graph/Gr.fst", "graph/phones/word_boundary.int"
        )
        missing_vosk = [name for name in required_vosk_files if not (vosk_model / name).is_file()]
        if missing_vosk:
            raise FileNotFoundError("Bundled Vosk model is incomplete: " + ", ".join(missing_vosk))
        try:
            import vosk
            from model_paths import native_model_path
            validated_vosk_model = vosk.Model(native_model_path(vosk_model))
            del validated_vosk_model
        except Exception as exc:
            raise RuntimeError(f"Bundled Vosk model cannot be loaded: {exc}") from exc
    require_live_dictation = "--require-live-dictation" in sys.argv
    live_model = ROOT / "models" / "sherpa-onnx" / "sherpa-onnx-streaming-t-one-russian-2025-09-08"
    if require_live_dictation:
        required_assets += (live_model / "model.onnx", live_model / "tokens.txt")
        try:
            import sherpa_onnx
            if not hasattr(getattr(sherpa_onnx, "OnlineRecognizer", None), "from_t_one_ctc"):
                raise RuntimeError("sherpa-onnx does not expose OnlineRecognizer.from_t_one_ctc")
        except Exception as exc:
            raise RuntimeError(f"Optional live-dictation runtime is missing or incompatible: {exc}") from exc
    missing = [str(path) for path in required_assets if not path.is_file()]
    if "--require-whisper-model" in sys.argv and not missing:
        bundled_model = ROOT / "models" / "whisper" / "ggml-small.bin"
        if bundled_model.stat().st_size < 100 * 1024 * 1024:
            raise FileNotFoundError(f"Bundled Whisper Small model looks incomplete: {bundled_model}")
    if missing:
        raise FileNotFoundError("Missing packaged resources: " + ", ".join(missing))
    ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not ffmpeg_path.is_file():
        raise FileNotFoundError(f"FFmpeg binary missing: {ffmpeg_path}")
    # Native audio modules should load successfully even when no model or microphone is installed.
    _ = (pyaudio, vosk, pywhispercpp.model)
    app = QApplication.instance() or QApplication([])
    media_player = QMediaPlayer()
    audio_output = QAudioOutput()
    media_player.setAudioOutput(audio_output)
    media_player.deleteLater()
    audio_output.deleteLater()
    main_window = QMainWindow()
    Ui_MainWindow().setupUi(main_window)
    help_dialog = QDialog()
    Ui_Dialog_info().setupUi(help_dialog)
    main_window.close()
    help_dialog.close()
    app.quit()


if "--smoke-test" in sys.argv:
    try:
        _packaging_smoke_test()
    except Exception as exc:
        logger.exception("Packaged smoke test failed")
        raise SystemExit(17) from exc
    logger.info("Packaged smoke test passed")
    raise SystemExit(0)

try:
    runpy.run_path(str(SCRIPTS / "main.py"), run_name="__main__")
except Exception as exc:
    logger.exception("Fatal error while importing or starting Spiker")
    message = (
        "СПИКЕР не удалось запустить.\n\n"
        f"Причина: {type(exc).__name__}: {exc}\n\n"
        f"Подробный журнал: {LOGS}\\errors.log и {LOGS}\\application.log.\n"
        "Проверьте application.log и errors.log; перед отправкой журналов удалите личные данные."
    )
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "Ошибка запуска СПИКЕР", message)
    except Exception:
        pass
    raise
