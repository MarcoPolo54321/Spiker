@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
if exist "%~dp0Spiker.exe" goto :packaged
set "SPK_PYTHON=.venv311\Scripts\python.exe"
if not exist "%SPK_PYTHON%" if exist ".venv\Scripts\python.exe" set "SPK_PYTHON=.venv\Scripts\python.exe"
if not exist "%SPK_PYTHON%" (
  echo Создаём окружение СПИКЕР на Python 3.11 x64...
  where py >nul 2>&1
  if errorlevel 1 goto :use_python
  py -3.11 -m venv .venv311
  if errorlevel 1 goto :failed
  goto :python_ready
)
:python_ready
if not exist "%SPK_PYTHON%" set "SPK_PYTHON=.venv311\Scripts\python.exe"
"%SPK_PYTHON%" -c "import sys, platform; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and platform.machine().lower() in ('amd64','x86_64') else 2)"
if errorlevel 1 goto :wrong_python
"%SPK_PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
  "%SPK_PYTHON%" scripts\repair_pip.py
  if errorlevel 1 goto :failed
)
"%SPK_PYTHON%" -m pip install --disable-pip-version-check -r res\requirements.txt
if errorlevel 1 goto :failed
echo.
echo Выберите установку базовых речевых моделей: Whisper (~466 MiB), T-one и Vosk.
echo Для диаризации будет отдельный шаг с принятием условий Hugging Face.
"%SPK_PYTHON%" scripts\install_models.py --basic
if errorlevel 1 goto :failed
echo.
choice /C YN /N /M "Установить также модель автоматического определения спикеров pyannote? [Y/N] "
if errorlevel 2 goto :done
"%SPK_PYTHON%" scripts\install_models.py --diarization
if errorlevel 1 goto :failed
:done
echo.
echo Установка завершена. Модели размещены в папке models.
pause
exit /b 0
:use_python
where python >nul 2>&1
if errorlevel 1 goto :python_missing
python -m venv .venv311
if errorlevel 1 goto :failed
goto :python_ready
:python_missing
echo Не найден Python 3.11 x64. Установите его и повторите запуск.
pause
exit /b 2
:wrong_python
echo Для СПИКЕР требуется Python 3.11 x64.
pause
exit /b 2
:failed
echo Ошибка установки. Проверьте интернет, свободное место и сообщение выше.
pause
exit /b 1

:packaged
set "SPK_APP_ROOT=%~dp0"
if exist "%SPK_APP_ROOT%portable.flag" (
  set "SPK_DATA_ROOT=%SPK_APP_ROOT%user-data"
) else (
  set "SPK_DATA_ROOT=%LOCALAPPDATA%\Spiker"
)
if not exist "%SPK_DATA_ROOT%" mkdir "%SPK_DATA_ROOT%"
set "SPIKER_DATA_DIR=%SPK_DATA_ROOT%"
set "SPK_PYTHON=%SPK_DATA_ROOT%\.venv-models\Scripts\python.exe"
if not exist "%SPK_PYTHON%" (
  echo Создаём дополнительное окружение в папке пользовательских данных...
  where py >nul 2>&1
  if errorlevel 1 goto :python_missing
  py -3.11 -m venv "%SPK_DATA_ROOT%\.venv-models"
  if errorlevel 1 goto :failed
)
"%SPK_PYTHON%" -m pip install --disable-pip-version-check -r "%SPK_APP_ROOT%res\requirements.txt"
if errorlevel 1 goto :failed
echo.
echo Выберите установку дополнительных моделей: faster-whisper, T-one и Vosk.
echo Файлы будут размещены в пользовательской папке данных СПИКЕР.
"%SPK_PYTHON%" "%SPK_APP_ROOT%scripts\install_models.py" --basic
if errorlevel 1 goto :failed
echo.
echo.
echo Дополнительные компоненты установлены в "%SPK_DATA_ROOT%\models".
echo Для автоматического разделения на спикеров запустите Install_Speaker_Diarization.bat.
pause
exit /b 0
