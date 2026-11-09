@echo off
setlocal
cd /d "%~dp0"
echo ==================================================
echo SPIKER 3.0 - Local AI model preparation
echo ==================================================
echo This script intentionally downloads one local model once.
echo It requires internet for the initial model download.
echo After preparation, local text processing can run offline.
echo.
where ollama >nul 2>nul
if errorlevel 1 (
  echo Ollama was not found.
  echo Install Ollama for Windows first, then run this script again.
  echo Official page: https://ollama.com/download
  pause
  exit /b 2
)
echo The recommended compact model is qwen2.5:0.5b (about 400 MB).
ollama show qwen2.5:0.5b >nul 2>nul
if not errorlevel 1 goto :model_ready
echo Downloading the compact model. It is downloaded only if it is missing.
ollama pull qwen2.5:0.5b
if errorlevel 1 (
  echo Model download failed. Check connection, disk space, and Ollama status.
  pause
  exit /b 3
)
:model_ready
echo.
echo Installed models:
ollama list
echo.
echo Open Spiker, select AI - Local Ollama, then click Check Connection / Refresh Models.
pause
