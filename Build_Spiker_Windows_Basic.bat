@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Spiker - Compact Windows Build
for /f "usebackq delims=" %%V in ("%~dp0VERSION") do set "SPIKER_VERSION=%%V"

echo ============================================================
echo             SPIKER - COMPACT WINDOWS BUILD
echo ============================================================
echo.
echo Builds a smaller installer and portable ZIP with the standard
echo Whisper Small engine and model. Optional advanced engines stay
echo available as separate installs from the app's Settings page.
echo.
set "BUILD_REUSE="
if exist "%~dp0.build-venv\Scripts\python.exe" (
  echo Reusing the existing Full build environment in offline mode.
  set "BUILD_REUSE=-ReuseFullBuildEnvironment"
) else (
  echo Preparing a separate Basic build environment.
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" -Installer -Profile Basic %BUILD_REUSE%
set "BUILD_EXIT=%ERRORLEVEL%"
if not "%BUILD_EXIT%"=="0" goto :failed

echo.
echo Build completed:
echo   dist\Spiker-Setup-%SPIKER_VERSION%-Basic.exe
echo   dist\Spiker-Portable-%SPIKER_VERSION%-Basic.zip
echo.
pause
exit /b 0

:failed
echo.
echo BUILD FAILED. Exit code: %BUILD_EXIT%
pause
exit /b %BUILD_EXIT%
