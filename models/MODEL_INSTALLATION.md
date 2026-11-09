# Установка речевых моделей СПИКЕР 3.0.8

## Базовые речевые модели

Запустите `Install_Models.bat` из корня исходного проекта или используйте установщики отдельных компонентов. Все веса сохраняются в локальной папке `models/`; сами веса не коммитятся в Git.

| Компонент | Папка | Назначение | Поставка |
|---|---|---|---|
| Whisper.cpp Small | `models/whisper/ggml-small.bin` | Базовая транскрибация файлов | Входит в Windows Setup |
| faster-whisper Small | `models/faster-whisper/small/` | Ускоренная файловая транскрибация и словесные timestamp | Входит в полный Windows Setup; MIT, SHA-256 проверяется |
| Sherpa-ONNX T-one Russian | `models/sherpa-onnx/sherpa-onnx-streaming-t-one-russian-2025-09-08/` | Потоковая диктовка | Входит в GitHub Windows build |
| Vosk Russian Small | `models/vosk/vosk-model-small-ru-0.22/` | Альтернативный потоковый ASR | Входит в полный Windows Setup |
| pyannote Community-1 | `models/pyannote/speaker-diarization-community-1/` | Автоматическая диаризация | Гейтированная модель; требует Hugging Face acceptance и Read-токен |

## Автоматическое разделение участников

1. Войдите в Hugging Face и примите условия доступа модели `pyannote/speaker-diarization-community-1`.
2. Создайте Read-токен.
3. Закройте СПИКЕР и запустите `Install_Speaker_Diarization.bat`.
4. Скрипт устанавливает `pyannote.audio==4.0.7` в `.venv311`, скачивает модель и проверяет её локальный `Pipeline.from_pretrained`.

Токен вводится скрыто, не записывается в настройки и не должен отправляться в логах. Без принятия условий модель скачать нельзя. После загрузки диаризация выполняется локально. См. [карточку модели](https://huggingface.co/pyannote/speaker-diarization-community-1) и [pyannote.audio 4.0.7](https://pypi.org/project/pyannote-audio/4.0.7/).

## Языковая модель для ИИ

Ollama и Qwen — отдельные компоненты для анализа уже готового текста. Они не заменяют ASR и pyannote. Установите Ollama отдельно, загрузите совместимую по RAM/VRAM модель и выберите локального провайдера в настройках СПИКЕР.

## Проверка после установки

Запустите `Launch_Spiker.bat` и проверьте статусы компонентов в настройках. Не нужно запускать все BAT-файлы каждый раз: `Launch_Spiker.bat` — обычный запуск, установщики нужны только при первом добавлении или восстановлении соответствующего компонента.
