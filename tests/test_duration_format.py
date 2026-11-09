"""Regression tests for duration labels in live transcription callbacks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from time_utils import format_duration


class DurationFormatTests(unittest.TestCase):
    def test_minutes_and_seconds(self):
        self.assertEqual(format_duration(0), "00:00")
        self.assertEqual(format_duration(65.9), "01:05")
        self.assertEqual(format_duration(3599), "59:59")

    def test_hours_are_included_when_needed(self):
        self.assertEqual(format_duration(3600), "01:00:00")
        self.assertEqual(format_duration(3661.8), "01:01:01")

    def test_invalid_values_are_safe(self):
        for value in (None, "bad", float("nan"), float("inf"), -10):
            with self.subTest(value=value):
                self.assertEqual(format_duration(value), "00:00")

    def test_main_worker_imports_the_formatter_used_in_progress_callback(self):
        source = (ROOT / "scripts" / "main.py").read_text(encoding="utf-8")
        self.assertIn("from time_utils import format_duration as _format_duration", source)
        self.assertIn('label = f"Распознавание {_format_duration(global_seconds)} / {_format_duration(full_duration)} · {self.backend_used}"', source)


if __name__ == "__main__":
    unittest.main()
