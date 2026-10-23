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
echo Pulling qwen3.5:4b. This may take several GB of download.
ollama pull qwen3.5:4b
if errorlevel 1 (
  echo Model download failed. Check connection, disk space, and Ollama status.
  pause
  exit /b 3
)
echo.
echo Installed models:
ollama list
echo.
echo Open Spiker, select AI - Local Ollama, then click Check Connection / Refresh Models.
pause
