@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
if not exist ".venv311\Scripts\python.exe" (
  echo Python environment is not ready. Run the normal launcher first.
  pause
  exit /b 1
)
".venv311\Scripts\python.exe" "scripts\safe_main.py"
echo.
echo Diagnostic run ended. Review logs\errors.log and logs\application.log.
pause
