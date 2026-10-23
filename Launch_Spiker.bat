@echo off
chcp 65001 >nul
setlocal EnableExtensions
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
title СПИКЕР — запуск

REM Reset Qt overrides sometimes inherited from another activated Python/Qt environment.
set "QT_PLUGIN_PATH="
set "QT_QPA_PLATFORM_PLUGIN_PATH="
set "QT_QPA_FONTDIR="
set "QT_QPA_PLATFORM="
set "QT_SCALE_FACTOR="
set "QT_SCREEN_SCALE_FACTORS="

REM Prefer the established Python 3.11 environment. Do not create a parallel .venv
REM if this project already uses .venv311.
if exist ".venv311\Scripts\python.exe" (
  set "SPK_PYTHON=%CD%\.venv311\Scripts\python.exe"
  goto :environment_ready
)
if exist ".venv\Scripts\python.exe" (
  set "SPK_PYTHON=%CD%\.venv\Scripts\python.exe"
  goto :environment_ready
)

echo Не найдено виртуальное окружение СПИКЕР. Создаю .venv311 на Python 3.11...
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
"%SPK_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 2)"
if errorlevel 1 (
  echo Ошибка: СПИКЕР требует Python 3.11 x64. Найденный интерпретатор: %SPK_PYTHON%
  echo Если у вас уже настроено окружение .venv311, проверьте его файл Scripts\python.exe.
  pause
  exit /b 2
)

REM Validate imports rather than relying on a stale marker file.
"%SPK_PYTHON%" -c "import PySide6, pyaudio, vosk, imageio_ffmpeg, pywhispercpp, docx" >nul 2>&1
if errorlevel 1 goto :install_dependencies
goto :launch

:install_dependencies
echo Не хватает зависимостей. Устанавливаю пакеты СПИКЕР...
"%SPK_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"%SPK_PYTHON%" -m pip install -r "res\requirements.txt"
if errorlevel 1 goto :failed

:launch
if not exist "logs" mkdir "logs"
echo Запускаю СПИКЕР через: %SPK_PYTHON%
echo [%date% %time%] Python: %SPK_PYTHON%>>"logs\launcher.log"
"%SPK_PYTHON%" "scripts\safe_main.py"
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
  echo Приложение завершилось с кодом %APP_EXIT%.
  echo Проверьте logs\errors.log, logs\application.log и logs\launcher.log.
  pause
)
endlocal & exit /b %APP_EXIT%

:python_missing
echo Python не найден. Установите Python 3.11 x64 или восстановите папку .venv311.
pause
exit /b 1

:failed
echo Не удалось подготовить окружение. Проверьте подключение к интернету и сообщение выше.
pause
exit /b 1
