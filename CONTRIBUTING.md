# Участие в разработке

Перед изменениями прочитайте [CLAUDE.md](CLAUDE.md), [правила управления изменениями](docs/CHANGE_MANAGEMENT.md) и [рабочий процесс](docs/workflow.md). Карта компонентов находится в [docs/architecture.md](docs/architecture.md), принятые решения — в [docs/decisions.md](docs/decisions.md).

1. Создайте ветку от актуальной основной ветки и кратко опишите цель изменения.
2. Используйте Python 3.11 x64 на Windows для проверки пользовательского интерфейса и упаковки.
3. Перед pull request выполните:

   ```powershell
   python -m unittest discover -s tests -v
   python -m compileall -q scripts tests
   ```

4. Не добавляйте пользовательские записи, настройки, API-ключи, журналы или веса моделей.
5. Изменения упаковки проверяйте через `docs/BUILD_WINDOWS.md`; UI, микрофон и нативный whisper.cpp дополнительно проверяйте на Windows.
6. В pull request укажите проверенные сценарии, окружение, результаты команд и известные ограничения.
