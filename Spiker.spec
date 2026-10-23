# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows onedir release of СПИКЕР."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve()
SCRIPTS = ROOT / "scripts"

binaries = []
datas = []
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
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
]

# The app's guarded launcher executes scripts/main.py from disk at runtime.
# Bundle project Python files as data as well as collecting their imports, so the
# source entry point and local UI modules remain available to runpy/path imports.
for source in SCRIPTS.rglob("*.py"):
    if "__pycache__" in source.parts:
        continue
    datas.append((str(source), str(source.relative_to(ROOT).parent)))

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

hiddenimports += collect_submodules("PySide6.QtMultimedia")
hiddenimports = sorted(set(hiddenimports))

analysis = Analysis(
    [str(SCRIPTS / "safe_main.py")],
    pathex=[str(ROOT), str(SCRIPTS)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "jupyter", "tkinter"],
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
