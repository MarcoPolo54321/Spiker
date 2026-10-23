@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
echo [%date% %time%] Launcher started>>"logs\launcher.log"

where py >nul 2>nul
if errorlevel 1 goto no_python
py -3.11 --version >nul 2>nul
if errorlevel 1 goto no_python

if not exist ".venv311\Scripts\python.exe" goto create_env
goto check_pip

:create_env
echo First run: creating Python 3.11 environment...
py -3.11 -m venv ".venv311" >>"logs\install.log" 2>&1
if errorlevel 1 goto install_error

:check_pip
".venv311\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
  ".venv311\Scripts\python.exe" -m ensurepip --upgrade >>"logs\install.log" 2>&1
  if errorlevel 1 goto recreate_env
)

rem Check only distribution metadata on the fast path; never import Qt/Whisper at launch preflight.
if exist ".venv311\deps-installed.ok" (
  ".venv311\Scripts\python.exe" -c "import importlib.metadata as m; [m.version(x) for x in ['PySide6','vosk','pywhispercpp','PyAudio','imageio-ffmpeg','keyring','python-docx']]" >nul 2>nul
  if not errorlevel 1 goto launch_gui
  del ".venv311\deps-installed.ok" >nul 2>nul
)

echo Installing or repairing required packages. Details: logs\install.log
".venv311\Scripts\python.exe" -m pip install --disable-pip-version-check -r "res\requirements.txt" >>"logs\install.log" 2>&1
if errorlevel 1 goto install_error
".venv311\Scripts\python.exe" -c "import importlib.metadata as m; [m.version(x) for x in ['PySide6','vosk','pywhispercpp','PyAudio','imageio-ffmpeg','keyring','python-docx']]" >nul 2>nul
if errorlevel 1 goto install_error
echo installed>".venv311\deps-installed.ok"

:launch_gui
if not exist ".venv311\Scripts\pythonw.exe" goto no_pythonw
echo [%date% %time%] Starting GUI via pythonw + safe startup logger>>"logs\launcher.log"
start "" ".venv311\Scripts\pythonw.exe" "scripts\safe_main.py"
exit /b 0

:recreate_env
echo pip is not recoverable. Recreating Python environment; previous one is kept as .venv311.old.
if exist ".venv311.old" rmdir /s /q ".venv311.old"
if exist ".venv311" move ".venv311" ".venv311.old" >>"logs\install.log" 2>&1
py -3.11 -m venv ".venv311" >>"logs\install.log" 2>&1
if errorlevel 1 goto install_error
".venv311\Scripts\python.exe" -m ensurepip --upgrade >>"logs\install.log" 2>&1
if errorlevel 1 goto install_error
goto check_pip

:no_python
echo Python 3.11 x64 was not found. Install Python 3.11 and run this file again.
pause
exit /b 10

:no_pythonw
echo pythonw.exe was not found in .venv311. Check the virtual environment.
pause
exit /b 11

:install_error
echo Setup failed. Read logs\install.log for details.
pause
exit /b 1
