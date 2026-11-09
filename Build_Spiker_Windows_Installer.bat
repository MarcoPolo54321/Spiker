@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Spiker - Windows Installer Builder

for /f "usebackq delims=" %%V in ("%~dp0VERSION") do set "SPIKER_VERSION=%%V"
if not defined SPIKER_VERSION (
  echo ERROR: VERSION file is missing or empty.
  pause
  exit /b 2
)

echo ============================================================
echo                 SPIKER - WINDOWS BUILD
echo ============================================================
echo.
echo This script builds:
echo   dist\Spiker-Setup-%SPIKER_VERSION%.exe  - Windows installer
echo   dist\Spiker-Portable-%SPIKER_VERSION%.zip - portable package
echo   dist\SHA256SUMS.txt - checksums
echo.
echo Requirements: Windows 10/11 x64, Python 3.11 x64, internet.
echo Inno Setup 6 will be detected or installed using WinGet.
echo Whisper Small and Sherpa-ONNX T-one are downloaded. The faster-whisper/CTranslate2 runtime is bundled too.
echo Allow at least 8 GB of free disk space for dependencies and build artifacts.
echo.
where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo ERROR: Windows PowerShell was not found.
  pause
  exit /b 2
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" -Installer -Clean -WithFasterWhisper -WithFasterWhisperModel -WithVoskModel -WithLiveDictation
set "BUILD_EXIT=%ERRORLEVEL%"
if not "%BUILD_EXIT%"=="0" goto :failed

echo.
echo ============================================================
echo BUILD COMPLETED SUCCESSFULLY
echo ============================================================
echo Installer: %~dp0dist\Spiker-Setup-%SPIKER_VERSION%.exe
echo Portable:  %~dp0dist\Spiker-Portable-%SPIKER_VERSION%.zip
echo Checksums: %~dp0dist\SHA256SUMS.txt
echo.
if exist "%~dp0dist" explorer.exe "%~dp0dist"
pause
exit /b 0

:failed
echo.
echo BUILD FAILED. Exit code: %BUILD_EXIT%
echo Read the PowerShell error above. Source files have not been deleted.
pause
exit /b %BUILD_EXIT%
