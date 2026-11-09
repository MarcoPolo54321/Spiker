"""Russian translations for standard Qt controls and platform dialogs."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator


def install_russian_qt_translations(app):
    """Translate standard Qt buttons such as Yes/No, Save/Cancel, and OK."""
    QLocale.setDefault(QLocale(QLocale.Language.Russian, QLocale.Country.Russia))
    translator = QTranslator(app)
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        bundled_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.append(bundled_root / "translations" / "qtbase_ru.qm")

    qt_translations = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    candidates.append(qt_translations / "qtbase_ru.qm")

    for path in candidates:
        if path.is_file() and translator.load(str(path)):
            app.installTranslator(translator)
            return translator
    return None
