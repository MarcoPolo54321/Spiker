@echo off
setlocal
cd /d "%~dp0"
title СПИКЕР — сборка Windows-релиза
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" -Installer -Clean
if errorlevel 1 (
  echo.
  echo Сборка завершилась с ошибкой. Прочитайте сообщение выше.
  pause
  exit /b 1
)
echo.
echo Готово. Файлы находятся в папке dist.
pause
