from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseAssetTests(unittest.TestCase):
    def test_github_readme_banner_and_screenshots_exist(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for relative in (
            "assets/readme-banner.jpg",
            "assets/screenshots/main-menu.png",
            "assets/screenshots/transcription-queue.png",
            "assets/screenshots/dictation.png",
            "assets/screenshots/ai-processing.png",
            "assets/screenshots/help.png",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
            self.assertIn(relative, readme)

    def test_release_version_is_consistent(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        installer = (ROOT / "installer" / "Spiker.iss").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertIn(f'#define AppVersion "{version}"', installer)
        self.assertIn("Spiker-Setup-<версия>.exe", readme)

    def test_build_bundles_model_and_checks_hash(self):
        build = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        spec = (ROOT / "Spiker.spec").read_text(encoding="utf-8")
        source = (ROOT / "models" / "whisper" / "MODEL_SOURCE.md").read_text(encoding="utf-8")
        self.assertIn("ggml-small.bin", build)
        self.assertIn("Get-FileHash", build)
        self.assertIn("ggml-small.bin", spec)
        self.assertIn("SHA-256", source)

    def test_spec_does_not_bundle_arbitrary_local_models(self):
        spec = (ROOT / "Spiker.spec").read_text(encoding="utf-8")
        self.assertIn('whisper_default = ROOT / "models" / "whisper" / "ggml-small.bin"', spec)
        self.assertNotIn('for folder in ("icons", "models")', spec)

    def test_github_about_has_copy_ready_description(self):
        about = (ROOT / "GITHUB_ABOUT.md").read_text(encoding="utf-8")
        self.assertIn("Description field", about)
        self.assertIn("Suggested topics", about)
        self.assertIn("assets/readme-banner.jpg", about)


if __name__ == "__main__":
    unittest.main()
