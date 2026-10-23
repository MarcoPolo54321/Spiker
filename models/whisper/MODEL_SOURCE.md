# Bundled Whisper model

The Windows release build downloads the multilingual `ggml-small.bin` model from the `ggerganov/whisper.cpp` Hugging Face repository at a pinned revision.

- Model file: `ggml-small.bin`
- Source: https://huggingface.co/ggerganov/whisper.cpp
- Pinned revision: `90a64d80ea254cf67575b41a5971f972c79f7b45`
- SHA-256: `1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b`
- Model repository license indicated by the source: MIT

The model is downloaded during Windows release builds, integrity-checked, bundled into `Spiker.exe` distribution, and included in the Inno Setup installer. Model weights are not committed to this Git repository.

The application can use a different user-selected Whisper model after installation. Model performance and transcription quality depend on the chosen model and computer hardware.
