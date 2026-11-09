# Публикация СПИКЕР 3.1.3 на GitHub

## 1. Подготовка репозитория

1. Создайте пустой GitHub repository (например, `Spiker`).
2. Распакуйте исходный ZIP так, чтобы `.github`, `.gitignore`, `README.md`, `VERSION` и `Spiker.spec` находились в корне.
3. Проверьте `.gitignore`: пользовательские записи, `data/`, `results/`, журналы, настройки и тяжёлые веса моделей не должны попадать в Git.
4. Вставьте текст и topics из `GITHUB_ABOUT.md` в раздел About репозитория.

```powershell
git init
git add .
git status
git commit -m "Prepare Spiker 3.1.0"
git branch -M main
git remote add origin https://github.com/OWNER/Spiker.git
git push -u origin main
```

Перед commit проверьте `git status` и убедитесь, что не добавлены аудиозаписи, API-ключи, пользовательские данные, модели или `.venv`.

## 2. Автоматическая сборка Windows

Workflow `.github/workflows/windows-release.yml` работает на GitHub-hosted Windows runner. Для ручной проверки откройте **Actions → Windows build and release → Run workflow**. После выполнения скачайте артефакт `Spiker-Windows-...` и проверьте Setup/Portable на чистом компьютере.

Workflow собирает два профиля:

```powershell
.\build_windows.ps1 -Installer -Clean -WithFasterWhisper -WithFasterWhisperModel -WithVoskModel -WithLiveDictation
.\build_windows.ps1 -Installer -Profile Basic
```

Полный профиль включает Whisper.cpp, faster-whisper Small/Medium, Sherpa-ONNX с T-one, офлайн-разделение участников и два русских голоса озвучки. Basic включает Whisper.cpp Small, потоковую диктовку, разделение участников и те же голоса, без faster-whisper и Vosk. Для обоих профилей запускаются тесты, PyInstaller smoke-test и Inno Setup. Большая модель GigaChat скачивается отдельно в Documents/Spiker/models/llm; CPU runtime входит в приложение.

Перед публикацией убедитесь, что Windows build проходит тест `test_training_utility_button_uses_same_transparent_style_as_settings_and_help`. Его зависимость Pillow устанавливается из `res/requirements-test.txt`; она не является runtime-моделью и не требует добавления в основной список зависимостей приложения.

## 3. Опубликовать релиз 3.1.3

Убедитесь, что `VERSION` содержит `3.1.3`, затем создайте и отправьте тег:

```powershell
git tag v3.1.3
git push origin v3.1.3
```

Workflow соберёт и приложит к GitHub Release:

- `Spiker-Setup-3.1.3.exe` и `Spiker-Models-3.1.3.zip` — стандартная установка; оба файла нужны рядом, установщик автоматически раскладывает модели;
- `Spiker-Portable-3.1.3.zip` и `Spiker-Models-3.1.3.zip` — переносная версия; приложение раскладывает соседний архив при первом запуске;
- соответствующие `Spiker-Setup-3.1.3-Basic.exe`, `Spiker-Portable-3.1.3-Basic.zip` и `Spiker-Models-3.1.3-Basic.zip` — компактная сборка;
- `SHA256SUMS.txt` — контрольные суммы.

Не обещайте размер/скорость/точность, которые не измерялись. После CI всё равно протестируйте установщик на чистой Windows 10/11 x64.

## 4. Модели и лицензии

- Whisper Small (`ggml-small.bin`) загружается сборщиком с закреплённой ревизии и проверяется по SHA-256.
- Sherpa T-one загружается build script из источника, указанного в `scripts/download_t_one_model.py`.
- faster-whisper runtime/CTranslate2 и Small-модель включены в полный публичный Windows build.
- pyannote Community-1 требует принять условия Hugging Face и персональный Read-токен. Установщик просит токен скрытым вводом и не сохраняет его; сама модель не коммитится и не встраивается в публичный Setup.
- Локальный GigaChat 3.1 размещён в Hugging Face model pack; модель весит около 6.5 ГБ и не включается в единый GitHub asset. Пользователь может скачать файл на странице модели и положить в `Documents/Spiker/models/llm`.
- Русские Piper-модели Ирина/Руслан поставляются в отдельном model ZIP. До публичного распространения проверьте права: лицензия Ирины не указана, Руслан помечен CC-BY-NC-SA 4.0.
- Локальные WeSpeaker/Pyannote segmentation веса скачиваются workflow для сборок и входят в Full/Basic. Проверьте upstream условия распространения и сохраните атрибуцию перед публикацией артефактов.

См. [MODELS.md](MODELS.md) и [PRIVACY.md](PRIVACY.md).

## 5. Локальный Windows build

Для локального создания Setup требуется Windows 10/11 x64, Python 3.11 x64, интернет и Inno Setup 6. Запустите `Build_Spiker_Windows_Installer.bat` для полного набора или `Build_Spiker_Windows_Basic.bat` для компактного. Файлы обоих профилей и контрольные суммы появятся в `dist/`. APK строится отдельной инструкцией [Android](ANDROID_BUILD_RU.md).

## 6. Финальная проверка

Используйте [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) и [TEST_PLAN_3.1.0.md](TEST_PLAN_3.1.0.md). GitHub Actions подтверждает успешную сборку и базовый smoke-test, но не заменяет реальную проверку микрофона, CUDA, длинных файлов, pyannote и русского качества диаризации.
