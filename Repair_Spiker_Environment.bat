@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
if not exist ".venv311\Scripts\python.exe" py -3.11 -m venv .venv311
".venv311\Scripts\python.exe" -m pip install --disable-pip-version-check -r "res\requirements.txt" >"logs\install.log" 2>&1
if errorlevel 1 (echo Installation failed. See logs\install.log & pause & exit /b 1)
echo installed>".venv311\deps-installed.ok"
echo Dependencies repaired. Future launches will not reinstall them.
pause
