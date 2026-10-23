from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherSafetyTests(unittest.TestCase):
    def test_launcher_prefers_existing_python311_environment(self):
        script = (ROOT / "Launch_Spiker.bat").read_text(encoding="utf-8")
        self.assertLess(script.index('.venv311\\Scripts\\python.exe'), script.index('.venv\\Scripts\\python.exe'))
        self.assertIn('"scripts\\safe_main.py"', script)

    def test_launcher_clears_external_qt_overrides(self):
        script = (ROOT / "Launch_Spiker.bat").read_text(encoding="utf-8")
        for variable in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS"):
            self.assertIn(f'set "{variable}="', script)

    def test_main_window_adapts_to_available_screen(self):
        source = (ROOT / "scripts" / "main.py").read_text(encoding="utf-8")
        self.assertIn("def _fit_main_window_to_available_screen(app, window):", source)
        self.assertIn("screen.availableGeometry()", source)
        self.assertIn("_fit_main_window_to_available_screen(app, window)", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
