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

    def test_launcher_does_not_upgrade_pip_on_every_launch(self):
        script = (ROOT / "Launch_Spiker.bat").read_text(encoding="ascii")
        self.assertNotIn("pip install --upgrade pip", script)
        self.assertIn("scripts\\repair_pip.py", script)
        self.assertIn("--disable-pip-version-check", script)

    def test_batch_launchers_are_ascii_only(self):
        for name in ("Launch_Spiker.bat", "Build_Windows_Release.bat", "Build_Spiker_Windows_Installer.bat", "Repair_Environment.bat"):
            content = (ROOT / name).read_bytes()
            self.assertTrue(all(byte < 128 for byte in content), f"{name} is not ASCII-only")

    def test_pip_repair_uses_ensurepip_without_importing_pip_first(self):
        repair = (ROOT / "scripts" / "repair_pip.py").read_text(encoding="utf-8")
        self.assertIn('"ensurepip"', repair)
        self.assertIn('"--default-pip"', repair)
        self.assertIn('site_packages.glob(pattern)', repair)


if __name__ == "__main__":
    unittest.main(verbosity=2)
