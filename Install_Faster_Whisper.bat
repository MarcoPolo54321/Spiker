@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "SPK_PYTHON=.venv311\Scripts\python.exe"
if not exist "%SPK_PYTHON%" if exist ".venv\Scripts\python.exe" set "SPK_PYTHON=.venv\Scripts\python.exe"

if not exist "%SPK_PYTHON%" (
  echo Окружение СПИКЕР не найдено. Создаём .venv311...
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3.11 -m venv ".venv311"
  ) else (
    where python >nul 2>&1
    if errorlevel 1 goto :python_missing
    python -m venv ".venv311"
  )
  if errorlevel 1 goto :venv_failed
  set "SPK_PYTHON=.venv311\Scripts\python.exe"
)

if not exist "%SPK_PYTHON%" goto :venv_failed
"%SPK_PYTHON%" -c "import sys, platform; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and platform.machine().lower() in ('amd64', 'x86_64') else 2)"
if errorlevel 1 (
  echo Ошибка: требуется Python 3.11 x64 в окружении СПИКЕР.
  pause
  exit /b 2
)

echo Установка дополнительного локального движка faster-whisper...
"%SPK_PYTHON%" -m pip install "faster-whisper>=1.1,<2"
if errorlevel 1 (
  echo Ошибка установки. Проверьте интернет и логи pip.
  pause
  exit /b 1
)
echo.
echo Установка завершена. Поместите модель CTranslate2 в models\faster-whisper\имя-модели.
echo Инструкция: docs\ADVANCED_TRANSCRIPTION.md
pause
exit /b 0

:python_missing
echo Не найден Python 3.11. Установите Python 3.11 x64 и повторите запуск.
pause
exit /b 2

:venv_failed
echo Не удалось создать окружение .venv311. Установите Python 3.11 x64.
pause
exit /b 1
