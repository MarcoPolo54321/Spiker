# Сборка СПИКЕР для Windows

## Что создаёт сборка

- `dist/Spiker/Spiker.exe` и каталоги DLL/ресурсов — Windows onedir-приложение.
- `dist/Spiker-Portable-3.0.8.zip` — переносной пакет приложения без весов моделей.
- `dist/Spiker-Setup-3.0.8.exe` — пользовательский установщик Inno Setup без встроенных весов моделей.
- `dist/Spiker-Models-3.0.8.zip` — соответствующий архив моделей. Для установки Setup.exe и ZIP должны лежать рядом; установщик сам разложит модели.
- `dist/Spiker-Portable-3.0.8-Basic.zip` и `dist/Spiker-Setup-3.0.8-Basic.exe` — компактная версия с Whisper Small и без дополнительных движков, вместе с `Spiker-Models-3.0.8-Basic.zip`.
- `dist/SHA256SUMS.txt` — контрольные суммы релизных файлов.
- Установщик и portable ZIP также содержат `INSTALL_WINDOWS_RU.txt` и один необязательный `Install_Speaker_Diarization.bat`.

Полный профиль, создаваемый `Build_Spiker_Windows_Installer.bat`, включает:

- приложение, PySide6/Qt, FFmpeg и базовые зависимости;
- модель Whisper.cpp Small (`ggml-small.bin`, около 488 МБ), загружаемую с закреплённой ревизии и проверяемую по SHA-256;
- в отдельном ZIP — модели Whisper, а в полном профиле также выбранные faster-whisper, Vosk, T-one и TTS веса;
- Setup извлекает ZIP в папку программы. Portable сборка при первом запуске автоматически раскладывает соседний архив `Spiker-Models-*.zip`.

Компактный профиль (суффикс `-Basic`) включает приложение, FFmpeg и Whisper.cpp Small.
Он уменьшает состав пакета; faster-whisper, потоковая диктовка и Vosk доступны как
дополнительные компоненты. Сборка Basic сохраняет готовые файлы полного профиля в `dist/`.

Не включаются в обычный публичный установщик: модель pyannote Community-1, Ollama и языковая модель Qwen. pyannote Community-1 требует пользовательского принятия условий Hugging Face и персонального Read-токена. Для frozen/portable версии `Install_Speaker_Diarization.bat` создаёт отдельную `.venv-diarization`, загружает модель в `models/pyannote/speaker-diarization-community-1/` и проверяет локальный Pipeline; основное приложение запускает helper-процесс в этом окружении. Условия доступа и процедура описаны на [странице модели](https://huggingface.co/pyannote/speaker-diarization-community-1).

## Требования для локальной сборки

- Windows 10/11 x64.
- Python 3.11 x64 и Windows Python Launcher (`py.exe`).
- Интернет для Python packages и загрузки моделей.
- Свободное место для build environment, PyInstaller artifacts и моделей; для полного профиля требуется больше места, чем для Basic.
- Inno Setup 6 для Setup.exe. Для portable ZIP Inno Setup не обязателен.

## Сборка двойным щелчком

1. Распакуйте исходный архив полностью в рабочую папку.
2. Установите Python 3.11 x64.
3. Дважды щёлкните `Build_Spiker_Windows_Installer.bat`.
4. Сборщик проверит Python, обнаружит или предложит установить Inno Setup 6, создаст `.build-venv`, установит build dependencies, скачает/проверит модели, запустит проверки, соберёт PyInstaller onedir, выполнит smoke-test, затем вынесет веса в отдельный `Spiker-Models-<версия>.zip` и создаст Setup/Portable без них.
5. После сообщения об успешной сборке откроется `dist/`.

Для компактного Setup и portable ZIP запустите `Build_Spiker_Windows_Basic.bat`.
Если уже создано `.build-venv` полной сборки, Basic повторно использует его в
офлайн-режиме и не ставит второй комплект зависимостей. На чистом checkout без
этого окружения сборщик создаёт отдельное `.build-venv-basic`. Для Basic
используется отдельный staging-каталог, поэтому файлы полной сборки сохраняются
рядом в `dist/`.

Сборщик не запускает pyannote install и не скачивает гейтированную модель в процессе публичной сборки. Пользователь устанавливает её отдельно после установки программы.

## Восстановление build venv и тестовые зависимости

Сборщик создаёт `.build-venv` с `python -m venv --without-pip`, чтобы обойти сбой встроенного `ensurepip` на некоторых установках Python. Затем запускает `scripts/bootstrap_build_pip.py`. Helper проверяет именно `python -m pip --version` внутри дочернего Python-процесса и захватывает его stderr; это важно, потому что Windows PowerShell с `$ErrorActionPreference = 'Stop'` может превратить ожидаемое `No module named pip` в завершающий `NativeCommandError` ещё до резервного восстановления. Если pip отсутствует или повреждён, helper очищает только его файлы в `.build-venv`, пробует стандартный `ensurepip`, а затем официальный `https://bootstrap.pypa.io/get-pip.py`. Если осталась неполная папка `.build-venv` без `python.exe`, она пересоздаётся. Повторный запуск сборщика безопасен: уже рабочее окружение не пересоздаётся.

Тестовая зависимость Pillow задаётся отдельно в `res/requirements-test.txt`: она нужна тесту прозрачности PNG и не является обязательной runtime-зависимостью СПИКЕР. Этот файл устанавливается и локальным Windows build, и GitHub CI.

## PowerShell-команды

Полный офлайн-релизный набор (приложение и отдельный ZIP с Whisper.cpp + faster-whisper + T-one + Vosk + Setup.exe):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_windows.ps1 -Installer -Clean -WithFasterWhisper -WithFasterWhisperModel -WithVoskModel -WithLiveDictation
```

Только portable package (без компилятора Inno Setup):

```powershell
.\build_windows.ps1 -Clean -WithFasterWhisper -WithFasterWhisperModel -WithVoskModel -WithLiveDictation
```

Компактный вариант (отдельное build-окружение, только Whisper Small):

```powershell
.\build_windows.ps1 -Installer -Profile Basic
```

Если полный build уже создан на этом компьютере, а сеть недоступна, компактный
вариант можно собрать из проверенного полного build-окружения:

```powershell
.\build_windows.ps1 -Installer -Profile Basic -ReuseFullBuildEnvironment
```

В этом режиме используются отдельные рабочая папка PyInstaller и staging-каталог.
PyInstaller исключает faster-whisper/CTranslate2 и sherpa-onnx/ONNX Runtime, чтобы
они не попали в Basic из общего окружения. GitHub Actions использует отдельную
`.build-venv-basic`, как и обычная локальная сборка Basic.

Developer-only сборка без встроенной Whisper Small (не для обычных пользователей):

```powershell
.\build_windows.ps1 -WithoutWhisperModel
```

Полный профиль использует `.build-venv`, компактный — `.build-venv-basic`. Каждый профиль устанавливает собственные зависимости, запускает unittest и compileall, собирает приложение через PyInstaller, выполняет `Spiker.exe --smoke-test` и создаёт отдельные portable ZIP/Setup. Полный профиль включает Whisper, faster-whisper, T-one и Vosk; компактный включает Whisper Small.

## GitHub Actions

`.github/workflows/windows-release.yml` запускается вручную через Actions или автоматически при push-теге `v*`. Workflow выполняется на Windows runner и собирает оба профиля: полный офлайн-набор и компактный Basic. В Actions загружаются оба Setup, оба Portable ZIP и SHA-256; при version tag те же файлы прикладываются к GitHub Release.

Для `VERSION=3.0.8` используйте тег:

```powershell
git tag v3.0.8
git push origin v3.0.8
```

## Дополнительные компоненты после установки

- `Install_Models.bat` — модели Whisper/faster-whisper, T-one и Vosk в папки `models/`.
- `Install_Faster_Whisper.bat` — отдельная установка движка/модели faster-whisper в Python 3.11 runtime.
- `Install_Speaker_Diarization.bat` — необязательный pyannote.audio 4.0.7 и Community-1. В собранной версии он создаёт отдельное `.venv-diarization`, поэтому PyTorch/pyannote не увеличивают базовый исполняемый файл; нужны Python 3.11 x64, доступ к модели на Hugging Face и Read-токен. Маленький PySocks wheel включён для установки за SOCKS/VPN.
- `Prepare_Local_AI.bat` — подготовка Ollama/локального AI пути; саму Ollama и LLM следует устанавливать отдельно по её инструкциям.
- `Repair_Environment.bat` — восстановление исходного `.venv311`, не является обычным способом запуска.

Установщики моделей не требуется запускать все подряд. Для штатного использования запускайте `Launch_Spiker.bat` (или установленный `Spiker.exe`); остальные BAT запускайте только для отсутствующих дополнительных компонентов/ремонта.

Короткая инструкция конечному пользователю включена в установщик и portable пакет как `INSTALL_WINDOWS_RU.txt`.

## Что обязательно проверить вручную на Windows

- Чистая установка и удаление Setup; запуск без установленного Python.
- Whisper.cpp Small офлайн-транскрибация WAV/MP3/MP4.
- faster-whisper Small CPU/INT8; при совместимом CUDA — отдельный GPU тест.
- Sherpa/T-one с настоящим микрофоном, задержка partial и фиксация фразы после паузы.
- Установка pyannote 4.0.7, HF token, загрузка Community-1, `Pipeline.from_pretrained` и автоматическая разбивка на 2–5 участников.
- Перебивания/перекрывающиеся интервалы; отсутствие ложного назначения на «ближайшего» спикера.
- Музыкальный профиль не удаляет вокальные участки VAD.
- Длинная запись 60–90 минут, SQLite recovery, остановка, продолжение и смена исходного файла по прежнему пути.
- Экспорт TXT/DOCX/SRT/VTT/JSON и Structured Meeting Minutes с исходными SEGMENT_ID/таймкодами.
- Работа на компьютере без интернета после предварительной установки всех требуемых компонентов.

Pytest/unittest и packaged smoke-test проверяют программную логику и базовые импорты. Они не подтверждают акустическое качество русской речи, реальную задержку диктовки, корректность GPU-драйвера или точность DER на конкретном микрофоне.
