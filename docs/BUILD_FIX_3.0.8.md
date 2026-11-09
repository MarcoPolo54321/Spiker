# Исправление сборки Windows для СПИКЕР 3.0.8

## Симптом

На компьютерах, где `.build-venv` был создан через `python -m venv --without-pip`, сборка завершалась на команде `python -m pip --version` с сообщением `No module named pip`. При `$ErrorActionPreference = 'Stop'` Windows PowerShell мог преобразовать stderr Python в завершающий `NativeCommandError`. Из-за этого выполнение прекращалось до вызова `ensurepip` и резервного bootstrap.

## Исправление

`build_windows.ps1` теперь сначала запускает `scripts/bootstrap_build_pip.py`. Helper:

1. Проверяет реальный вызов `python -m pip --version` внутри дочернего Python-процесса и захватывает stdout/stderr.
2. При отсутствующем или повреждённом pip удаляет только компоненты pip внутри активного `.build-venv`.
3. Пытается восстановить pip через стандартный `ensurepip`.
4. Если ensurepip не сработал, скачивает официальный `https://bootstrap.pypa.io/get-pip.py` и запускает его тем же интерпретатором виртуального окружения.
5. Проверяет, что `python -m pip --version` теперь работает.

PowerShell больше не выполняет заведомо неуспешную команду `python -m pip --version` до bootstrap. В результате отсутствующий pip не должен обрывать сборку раньше резервного восстановления.

## Что сделать пользователю

1. Распаковать исправленный исходный ZIP 3.0.8 в отдельную папку.
2. Запустить `Build_Spiker_Windows_Installer.bat`.
3. Если в папке уже остался неполный `.build-venv`, его можно оставить: helper попытается восстановить pip. При повреждённом `python.exe` сборщик попросит пересоздать окружение; тогда удалите только `.build-venv` и повторите запуск.
4. Не удалять `models/`, исходники или пользовательские записи.

## Проверки в среде разработки

- Создано чистое виртуальное окружение с `--without-pip`.
- `bootstrap_build_pip.py` успешно установил pip через ensurepip и проверил `python -m pip --version`.
- 107 unittest пройдены.
- 107 pytest пройдены (5 subtests).
- `compileall` завершился без ошибок.

Финальную сборку `Setup.exe` необходимо выполнить на Windows 10/11 x64 с Python 3.11 x64 и Inno Setup 6.
