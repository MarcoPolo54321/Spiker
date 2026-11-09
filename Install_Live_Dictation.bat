@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
if exist "%~dp0Spiker.exe" goto :packaged
set "PYTHON=.venv311\Scripts\python.exe"

if not exist "%PYTHON%" if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
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
  set "PYTHON=.venv311\Scripts\python.exe"
)

if not exist "%PYTHON%" goto :venv_failed
"%PYTHON%" -c "import sys, platform; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and platform.machine().lower() in ('amd64', 'x86_64') else 2)"
if errorlevel 1 (
  echo Ошибка: для потоковой диктовки требуется Python 3.11 x64.
  pause
  exit /b 2
)

echo Установка дополнительного движка потоковой диктовки sherpa-onnx...
"%PYTHON%" -m pip install "sherpa-onnx>=1.12,<2"
if errorlevel 1 (
  echo Ошибка установки sherpa-onnx. Проверьте Python 3.11 x64 и подключение к интернету.
  pause
  exit /b 1
)
echo.
echo Загрузка модели T-one для русского языка. Размер модели около 138 МБ.
"%PYTHON%" scripts\download_t_one_model.py
if errorlevel 1 (
  echo Не удалось установить модель. Повторите запуск после проверки подключения.
  pause
  exit /b 1
)
echo.
echo Потоковая диктовка установлена.
echo В настройках СПИКЕР выберите «Авто» или «Потоковый Sherpa-ONNX / T-one».
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

:packaged
set "SPK_APP_ROOT=%~dp0"
if exist "%SPK_APP_ROOT%portable.flag" (
  set "SPK_DATA_ROOT=%SPK_APP_ROOT%user-data"
) else (
  set "SPK_DATA_ROOT=%LOCALAPPDATA%\Spiker"
)
if not exist "%SPK_DATA_ROOT%" mkdir "%SPK_DATA_ROOT%"
set "SPIKER_DATA_DIR=%SPK_DATA_ROOT%"
set "PYTHON=%SPK_DATA_ROOT%\.venv-models\Scripts\python.exe"
if not exist "%PYTHON%" (
  where py >nul 2>&1
  if errorlevel 1 goto :python_missing
  py -3.11 -m venv "%SPK_DATA_ROOT%\.venv-models"
  if errorlevel 1 goto :venv_failed
)
"%PYTHON%" -m pip install --disable-pip-version-check -r "%SPK_APP_ROOT%res\requirements.txt"
if errorlevel 1 goto :venv_failed
echo Устанавливаем дополнительный движок sherpa-onnx для потоковой диктовки...
"%PYTHON%" -m pip install "sherpa-onnx>=1.12,<2"
if errorlevel 1 goto :venv_failed
echo Загрузка модели T-one для русского языка. Размер модели около 138 МБ.
"%PYTHON%" "%SPK_APP_ROOT%scripts\download_t_one_model.py"
if errorlevel 1 goto :venv_failed
echo Потоковая диктовка установлена в пользовательскую папку данных.
pause
exit /b 0
