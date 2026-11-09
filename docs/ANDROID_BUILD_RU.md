# Сборка Android версии СПИКЕР 3.1.2 Mobile Preview

## Комплект

- Проект Kotlin: `android/`
- Потоковая русская диктовка T-one sherpa-onnx; import аудио и видеофайлов через MediaCodec
- Локальная диаризация sherpa-onnx + WeSpeaker с переименованием двух профилей
- Офлайн синтез русскими голосами Ирина/Руслан
- Экспорт TXT/WAV в публичную папку Android `Документы/Spiker`
- Синяя тема интерфейса в стиле Windows-приложения

## Подготовка на Windows

1. Запустите из корня репозитория `python scripts/prepare_android_tools.py`. Скрипт скачает Temurin JDK 17, Gradle 8.9, Android SDK API 35/build tools и AAR sherpa-onnx, после чего разложит модели из `models/` в Android assets.
2. Откройте PowerShell в `android/` и задайте окружение:

```powershell
$env:JAVA_HOME = (Get-ChildItem ..\.android-tools\java -Directory | Select-Object -First 1).FullName
$env:GRADLE_USER_HOME = (Resolve-Path ..\.android-tools\gradle-user).Path
```

3. Запустите `..\.android-tools\gradle-8.9\bin\gradle.bat assembleDebug`.
4. Debug APK появится в `android/app/build/outputs/apk/debug/app-debug.apk`. Его можно передать на ARM64 Android телефон и разрешить установку приложения из этого источника.

## Границы текущей версии

Телефонный APK рассчитан на ручную установку и модельную офлайн-работу; его общие модели занимают более 300 МБ плюс Android framework. Это мобильный preview, а не полный перенос Windows-версии: Android ещё не содержит компьютерный Queue/SQLite workspace, CTranslate2 Whisper Medium и локальный GigaChat. Это ограничение теперь показано в самом приложении. Перед выпуском APK проверьте скорость и память на физическом телефоне.

Модель Руслан помечена upstream лицензией CC BY-NC-SA 4.0; для распространения только для личного использования нужно сохранить указание авторства/условия. Для коммерческой публикации потребуется отдельное разрешение. У Ирины upstream карточка отмечает лицензию неизвестной: проверьте её до публичного APK.
