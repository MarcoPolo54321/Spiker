@echo off
setlocal
cd /d "%~dp0"
if not exist "scripts\transcription\wav_to_text.py" (
  echo ERROR: New transcription code was not found. Nothing was deleted.
  pause
  exit /b 1
)
if not exist "scripts\transcription\audio_preparation.py" (
  echo ERROR: New audio-preparation code was not found. Nothing was deleted.
  pause
  exit /b 1
)
if exist "scripts\model" (
  echo This will remove only the obsolete Python code folder scripts\model.
  echo It does NOT touch the root models folder or any model weights.
  choice /M "Remove scripts\model now?"
  if errorlevel 2 exit /b 0
  rmdir /s /q "scripts\model"
  if exist "scripts\model" (
    echo Could not completely remove scripts\model. Close any editor or program using it and retry.
    pause
    exit /b 1
  )
  echo Old code folder removed.
) else (
  echo No old scripts\model folder found. Nothing to clean.
)
echo Done.
pause
