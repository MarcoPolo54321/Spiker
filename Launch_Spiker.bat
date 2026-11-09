@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title Spiker - Launch

REM In installed/portable releases start the bundled executable directly.
REM The Python bootstrap below is intended for the source checkout only.
if exist "%~dp0Spiker.exe" (
  start "" "%~dp0Spiker.exe"
  exit /b 0
)

REM Clear external Qt settings that may point to a different Python installation.
set "QT_PLUGIN_PATH="
set "QT_QPA_PLATFORM_PLUGIN_PATH="
set "QT_QPA_FONTDIR="
set "QT_QPA_PLATFORM="
set "QT_SCALE_FACTOR="
set "QT_SCREEN_SCALE_FACTORS="

REM Prefer the established Python 3.11 environment.
if exist ".venv311\Scripts\python.exe" (
  set "SPK_PYTHON=%CD%\.venv311\Scripts\python.exe"
  goto :environment_ready
)
if exist ".venv\Scripts\python.exe" (
  set "SPK_PYTHON=%CD%\.venv\Scripts\python.exe"
  goto :environment_ready
)

echo No Spiker virtual environment was found. Creating .venv311 with Python 3.11...
where py >nul 2>&1
if not errorlevel 1 (
  py -3.11 -m venv ".venv311"
) else (
  where python >nul 2>&1
  if errorlevel 1 goto :python_missing
  python -m venv ".venv311"
)
if errorlevel 1 goto :failed
if not exist ".venv311\Scripts\python.exe" goto :failed
set "SPK_PYTHON=%CD%\.venv311\Scripts\python.exe"

:environment_ready
"%SPK_PYTHON%" -c "import sys, platform; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and platform.machine().lower() in ('amd64','x86_64') else 2)"
if errorlevel 1 (
  echo ERROR: Spiker requires Python 3.11 x64. Current interpreter: %SPK_PYTHON%
  pause
  exit /b 2
)

REM Check required runtime imports. Repair the bundled pip if its files are damaged.
"%SPK_PYTHON%" -c "import PySide6, pyaudio, vosk, imageio_ffmpeg, pywhispercpp, docx" >nul 2>&1
if errorlevel 1 goto :install_dependencies
goto :models_check

:install_dependencies
echo Required packages are missing. Checking pip...
"%SPK_PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo pip is damaged. Repairing it from Python's bundled installer...
  "%SPK_PYTHON%" "scripts\repair_pip.py"
  if errorlevel 1 goto :failed
)
echo Installing Spiker runtime packages. An internet connection is required if packages are not cached.
"%SPK_PYTHON%" -m pip install --disable-pip-version-check -r "res\requirements.txt"
if errorlevel 1 goto :failed
"%SPK_PYTHON%" -c "import PySide6, pyaudio, vosk, imageio_ffmpeg, pywhispercpp, docx" >nul 2>&1
if errorlevel 1 goto :failed
goto :models_check

:models_check
if not exist "scripts\install_models.py" goto :launch
"%SPK_PYTHON%" "scripts\install_models.py" --check >nul 2>&1
if not errorlevel 1 goto :diarization_check
echo.
echo One or more local speech models are missing.
echo The complete base set may download about 1.2 GB and will be stored in the local models folder.
choice /C YN /N /M "Install or repair the speech models now? [Y/N] "
if errorlevel 2 goto :launch
"%SPK_PYTHON%" "scripts\install_models.py" --basic
if errorlevel 1 (
  echo Model setup did not finish. Spiker will open, but missing engines will remain unavailable.
  pause
  goto :launch
)

:diarization_check
"%SPK_PYTHON%" "scripts\install_models.py" --check-diarization >nul 2>&1
if not errorlevel 1 goto :launch
echo.
echo Automatic speaker recognition is not installed.
echo It requires accepting the model conditions and entering a Hugging Face Read token.
choice /C YN /N /M "Install automatic speaker diarization now? [Y/N] "
if errorlevel 2 goto :launch
"%SPK_PYTHON%" "scripts\install_models.py" --diarization
if errorlevel 1 (
  echo Speaker diarization was not installed. File transcription will still work.
  pause
)

:launch
if not exist "logs" mkdir "logs"
echo Starting Spiker with: %SPK_PYTHON%
echo [%date% %time%] Python: %SPK_PYTHON%>>"logs\launcher.log"
"%SPK_PYTHON%" "scripts\safe_main.py"
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
  echo Spiker exited with code %APP_EXIT%.
  echo Check logs\errors.log and logs\application.log for details.
  pause
)
endlocal & exit /b %APP_EXIT%

:python_missing
echo Python 3.11 x64 was not found. Install it or restore the .venv311 folder.
pause
exit /b 1

:failed
echo Environment setup failed. Check the errors above. No application files were deleted.
pause
exit /b 1
