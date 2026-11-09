@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
if exist "%~dp0Spiker.exe" goto :packaged
set "SPK_PYTHON=.venv311\Scripts\python.exe"
if not exist "%SPK_PYTHON%" if exist ".venv\Scripts\python.exe" set "SPK_PYTHON=.venv\Scripts\python.exe"
if not exist "%SPK_PYTHON%" (
  echo Окружение СПИКЕР не найдено. Создаём .venv311...
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3.11 -m venv .venv311
  ) else (
    where python >nul 2>&1
    if errorlevel 1 goto :python_missing
    python -m venv .venv311
  )
  if errorlevel 1 goto :failed
  set "SPK_PYTHON=.venv311\Scripts\python.exe"
)
"%SPK_PYTHON%" -c "import sys, platform; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and platform.machine().lower() in ('amd64','x86_64') else 2)"
if errorlevel 1 goto :wrong_python
if exist "res\wheels\PySocks-1.7.1-py3-none-any.whl" (
  "%SPK_PYTHON%" -m pip install --disable-pip-version-check --no-index --find-links "res\wheels" "PySocks==1.7.1"
  if errorlevel 1 goto :failed
)
"%SPK_PYTHON%" -m pip install --disable-pip-version-check -r res\requirements.txt
if errorlevel 1 goto :failed
"%SPK_PYTHON%" scripts\install_models.py --diarization
if errorlevel 1 goto :failed
echo.
echo Диаризация установлена. Перезапустите СПИКЕР и проверьте настройку «Автоматически определять спикеров».
pause
exit /b 0
:packaged
set "SPK_APP_ROOT=%~dp0"
if exist "%SPK_APP_ROOT%portable.flag" (
  set "SPK_DATA_ROOT=%SPK_APP_ROOT%user-data"
) else (
  set "SPK_DATA_ROOT=%LOCALAPPDATA%\Spiker"
)
if not exist "%SPK_DATA_ROOT%" mkdir "%SPK_DATA_ROOT%"
set "SPK_PYTHON=%SPK_DATA_ROOT%\.venv-diarization\Scripts\python.exe"
if not exist "%SPK_PYTHON%" (
  echo Создаём отдельное окружение для диаризации. Нужен Python 3.11 x64.
  where py >nul 2>&1
  if errorlevel 1 goto :python_missing
  py -3.11 -m venv "%SPK_DATA_ROOT%\.venv-diarization"
  if errorlevel 1 goto :failed
)
"%SPK_PYTHON%" -c "import sys, platform; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and platform.machine().lower() in ('amd64','x86_64') else 2)"
if errorlevel 1 goto :wrong_python
if exist "%~dp0res\wheels\PySocks-1.7.1-py3-none-any.whl" (
  "%SPK_PYTHON%" -m pip install --disable-pip-version-check --no-index --find-links "%~dp0res\wheels" "PySocks==1.7.1"
  if errorlevel 1 goto :failed
)
echo Устанавливаем отдельный runtime pyannote.audio 4.0.7. Загрузка может занять несколько минут.
"%SPK_PYTHON%" -m pip install --disable-pip-version-check --upgrade "pyannote.audio==4.0.7"
if errorlevel 1 goto :failed
if not exist "%~dp0scripts\diarization_worker.py" (
  echo Не найден scripts\diarization_worker.py. Переустановите СПИКЕР из полного установщика.
  goto :failed
)
"%SPK_PYTHON%" "%~dp0scripts\diarization_worker.py" --install-model "%SPK_DATA_ROOT%"
if errorlevel 1 goto :failed
echo.
echo Диаризация установлена. Перезапустите СПИКЕР и нажмите «Авто-спикеры».
pause
exit /b 0
:python_missing
echo Не найден Python 3.11 x64. Установите Python 3.11 x64 и повторите запуск.
pause
exit /b 2
:wrong_python
echo Для СПИКЕР требуется Python 3.11 x64.
pause
exit /b 2
:failed
echo Установка не завершена. Проверьте интернет, место на диске, токен Hugging Face и ошибки выше.
pause
exit /b 1
