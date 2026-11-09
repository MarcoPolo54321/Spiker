# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows onedir release of СПИКЕР."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve()
SCRIPTS = ROOT / "scripts"

binaries = []
datas = []
# Optional speaker diarization is installed in a separate Python 3.11 environment.
# Keep the base app small while shipping its helper and one-click installer.
datas.append((str(ROOT / "Install_Speaker_Diarization.bat"), "."))
datas.append((str(ROOT / "INSTALL_WINDOWS_RU.txt"), "."))
pysocks_wheel = ROOT / "res" / "wheels" / "PySocks-1.7.1-py3-none-any.whl"
if not pysocks_wheel.is_file():
    raise RuntimeError("The offline SOCKS bootstrap wheel is missing: " + str(pysocks_wheel))
datas.append((str(pysocks_wheel), "res/wheels"))
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSvg",
    "shiboken6",
    "pyaudio",
    "pyaudio._portaudio",
    "vosk",
    "pywhispercpp",
    "pywhispercpp.model",
    "imageio_ffmpeg",
    "docx",
    "keyring",
    "keyring.backends.Windows",
    "app_config",
    "app_logging",
    "ai_provider",
    "app_paths",
    "model_paths",
    "subtitle_export",
    "Queue_page",
    "UI.Main_menu_script",
    "UI.theme",
    "UI.Settings_page",
    "UI.AI_page",
    "UI.Info_menu_script",
    "UI.Dictation_audio_menu_script",
    "transcription.audio_preparation",
    "transcription.wav_to_text",
    "transcription.hardware_diagnostics",
    "transcription.faster_whisper_backend",
    "transcription.speaker_diarization",
    "transcription.transcript_render",
    "transcription.live_streaming",
    "meeting_intelligence",
    "queue_store",
    "runtime_paths",
    "model_bundle",
    "download_t_one_model",
    "speech_synthesis", "UI.Speech_page", "transcription.onnx_diarization", "local_ai", "shutdown",
]

# The app's guarded launcher executes scripts/main.py from disk at runtime.
# Bundle project Python files as data as well as collecting their imports, so the
# source entry point and local UI modules remain available to runpy/path imports.
for source in SCRIPTS.rglob("*.py"):
    if "__pycache__" in source.parts:
        continue
    datas.append((str(source), str(source.relative_to(ROOT).parent)))

# Keep source/portable launch and model installation scripts next to the executable.
for filename in (
    "Launch_Spiker.bat", "Install_Models.bat", "Install_Live_Dictation.bat",
    "Install_Speaker_Diarization.bat", "Install_Faster_Whisper.bat",
):
    source = ROOT / filename
    if source.is_file():
        datas.append((str(source), "."))
docs_dir = ROOT / "docs"
if docs_dir.is_dir():
    datas.append((str(docs_dir), "docs"))

# llama.cpp is a small native CPU runtime; the multi-GB GigaChat weight remains
# a separately downloadable user model in Documents/Spiker/models/llm.
llama_runtime = ROOT / "runtime" / "llama"
if llama_runtime.is_dir():
    datas.append((str(llama_runtime), "runtime/llama"))
requirements_file = ROOT / "res" / "requirements.txt"
if requirements_file.is_file():
    datas.append((str(requirements_file), "res"))

# Include UI resources, but never bundle every model found on the build machine.
# A developer may have a private Whisper Medium or Vosk model in their local checkout.
icons_dir = ROOT / "icons"
if icons_dir.exists():
    datas.append((str(icons_dir), "icons"))

# Public release builds include exactly the pinned default model if the build script
# placed it in the source tree. Arbitrary local model weights are deliberately excluded.
whisper_default = ROOT / "models" / "whisper" / "ggml-small.bin"
if whisper_default.is_file():
    datas.append((str(whisper_default), "models/whisper"))
model_source = ROOT / "models" / "whisper" / "MODEL_SOURCE.md"
if model_source.is_file():
    datas.append((str(model_source), "models/whisper"))
asset_lock = ROOT / "models" / "verified-assets.json"
if asset_lock.is_file():
    datas.append((str(asset_lock), "models"))

icon_file = ROOT / "Spiker.ico"
version_file = ROOT / "build" / "version_info.txt"
if icon_file.exists():
    datas.append((str(icon_file), "."))

# Include native dependencies, FFmpeg binary assets, Vosk resources and docx/keyring
# data that PyInstaller's static analysis cannot always infer from dynamic imports.
for package in ("pywhispercpp", "vosk", "imageio_ffmpeg", "pyaudio", "docx", "keyring"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

# Advanced ML dependencies remain optional to keep the normal installer manageable.
# Set SPIKER_PACKAGE_FASTER_WHISPER=1 to embed faster-whisper/CTranslate2.
import os
if os.environ.get("SPIKER_PACKAGE_FASTER_WHISPER") == "1":
    for package in ("faster_whisper", "ctranslate2"):
        package_datas, package_binaries, package_hiddenimports = collect_all(package)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hiddenimports

# The full Windows installer can include the pinned local Small CTranslate2 model.
# Only the canonical model directory is packaged; unrelated local model folders stay out.
if os.environ.get("SPIKER_PACKAGE_FASTER_WHISPER_MODEL") == "1":
    faster_model = ROOT / "models" / "faster-whisper" / "small"
    required_faster_files = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")
    missing_faster_files = [name for name in required_faster_files if not (faster_model / name).is_file()]
    if missing_faster_files:
        raise RuntimeError(
            "SPIKER_PACKAGE_FASTER_WHISPER_MODEL=1 requires the complete pinned Small model; "
            f"missing: {', '.join(missing_faster_files)}"
        )
    if (faster_model / "model.bin").stat().st_size < 100 * 1024 * 1024:
        raise RuntimeError("The faster-whisper Small model.bin looks incomplete.")
    datas.append((str(faster_model), "models/faster-whisper/small"))
    medium_model = ROOT / 'models/faster-whisper/medium'
    if not all((medium_model / name).is_file() for name in required_faster_files):
        raise RuntimeError('Full 3.1 release requires Whisper Medium.')
    datas.append((str(medium_model), 'models/faster-whisper/medium'))


# Package the small Russian Vosk fallback when requested by a full offline build.
if os.environ.get("SPIKER_PACKAGE_VOSK_MODEL") == "1":
    vosk_model = ROOT / "models" / "vosk" / "vosk-model-small-ru-0.22"
    required_vosk_files = (
        "am/final.mdl", "graph/HCLr.fst", "graph/Gr.fst", "graph/phones/word_boundary.int"
    )
    missing_vosk = [name for name in required_vosk_files if not (vosk_model / name).is_file()]
    if missing_vosk:
        raise RuntimeError("The Russian Vosk model is incomplete: " + ", ".join(missing_vosk))
    datas.append((str(vosk_model), "models/vosk/vosk-model-small-ru-0.22"))

# The true streaming dictation runtime is optional because it adds native ONNX Runtime
# binaries. When requested, bundle the sherpa package and only the official T-one model
# downloaded by the build script into the portable/installer artifact.
if os.environ.get("SPIKER_PACKAGE_SHERPA") == "1":
    for package in ("sherpa_onnx", "onnxruntime"):
        package_datas, package_binaries, package_hiddenimports = collect_all(package)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hiddenimports
    for feature in ('tts', 'diarization'):
        folder = ROOT / 'models' / feature
        if not folder.is_dir(): raise RuntimeError('Missing offline model folder: ' + feature)
        datas.append((str(folder), 'models/' + feature))
    live_model = ROOT / "models" / "sherpa-onnx" / "sherpa-onnx-streaming-t-one-russian-2025-09-08"
    if not (live_model / "model.onnx").is_file() or not (live_model / "tokens.txt").is_file():
        raise RuntimeError("SPIKER_PACKAGE_SHERPA=1 requires the downloaded T-one model in models/sherpa-onnx.")
    datas.append((str(live_model), "models/sherpa-onnx/sherpa-onnx-streaming-t-one-russian-2025-09-08"))

hiddenimports += collect_submodules("PySide6.QtMultimedia")
hiddenimports = sorted(set(hiddenimports))
optional_excludes = []
if os.environ.get("SPIKER_PACKAGE_FASTER_WHISPER") != "1":
    optional_excludes.extend(("faster_whisper", "ctranslate2"))
if os.environ.get("SPIKER_PACKAGE_SHERPA") != "1":
    optional_excludes.extend(("sherpa_onnx", "onnxruntime"))

analysis = Analysis(
    [str(SCRIPTS / "safe_main.py")],
    pathex=[str(ROOT), str(SCRIPTS)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "jupyter", "tkinter", *optional_excludes],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Spiker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_file) if icon_file.exists() else None,
    version=str(version_file) if version_file.is_file() else None,
    contents_directory=".",
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Spiker",
)

