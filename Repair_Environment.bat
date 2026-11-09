@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Spiker - Repair Python Environment
if exist ".venv311\Scripts\python.exe" (
  set "SPK_PYTHON=%CD%\.venv311\Scripts\python.exe"
  goto :repair
)
if exist ".venv\Scripts\python.exe" (
  set "SPK_PYTHON=%CD%\.venv\Scripts\python.exe"
  goto :repair
)
echo No existing Spiker virtual environment was found.
echo Run Launch_Spiker.bat to create one, or install Python 3.11 x64 first.
pause
exit /b 1
:repair
echo Repairing pip...
"%SPK_PYTHON%" "scripts\repair_pip.py"
if errorlevel 1 goto :failed
echo Installing runtime dependencies...
"%SPK_PYTHON%" -m pip install --disable-pip-version-check -r "res\requirements.txt"
if errorlevel 1 goto :failed
echo Environment repair completed.
pause
exit /b 0
:failed
echo Environment repair failed. Read the messages above.
pause
exit /b 1
