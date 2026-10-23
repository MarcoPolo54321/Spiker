import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ai_provider
from app_config import load_settings, save_settings
from subtitle_export import format_timestamp, render_subtitles
from app_paths import get_app_root


class AppPathTests(unittest.TestCase):
    def test_source_mode_root_is_project_directory(self):
        self.assertEqual(get_app_root(), ROOT.resolve())

    def test_frozen_mode_root_is_executable_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp) / "InstalledSpiker"
            expected.mkdir()
            executable = expected / "Spiker.exe"
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(executable)):
                self.assertEqual(get_app_root(), expected.resolve())


class SplitTextTests(unittest.TestCase):
    def test_short_text_stays_one_chunk(self):
        self.assertEqual(ai_provider.split_text("Тест. Второе предложение."), ["Тест. Второе предложение."])

    def test_long_text_preserves_exact_content(self):
        text = ("Абзац один. Это длинная строка с русскими буквами и цифрами 123.\n\n" * 80).strip()
        chunks = ai_provider.split_text(text, 117)
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(chunks))

    def test_empty_text(self):
        self.assertEqual(ai_provider.split_text(""), [])


class SubtitleTests(unittest.TestCase):
    def test_timestamp_format(self):
        self.assertEqual(format_timestamp(3723.456), "01:02:03,456")
        self.assertEqual(format_timestamp(2.5, True), "00:00:02.500")

    def test_srt_uses_sorted_real_timestamps(self):
        text = render_subtitles([
            {"start": 2.0, "end": 3.25, "text": "Вторая фраза"},
            {"start": 0.0, "end": 1.2, "text": "Первая фраза"},
        ])
        self.assertIn("1\n00:00:00,000 --> 00:00:01,200", text)
        self.assertIn("2\n00:00:02,000 --> 00:00:03,250", text)
        self.assertLess(text.index("Первая фраза"), text.index("Вторая фраза"))

    def test_vtt_header(self):
        text = render_subtitles([{"start": 0, "end": 0.8, "text": "Привет"}], vtt=True)
        self.assertTrue(text.startswith("WEBVTT\n\n"))
        self.assertIn("00:00:00.000 --> 00:00:00.800", text)

    def test_no_segments_returns_empty(self):
        self.assertEqual(render_subtitles([]), "")


class SettingsTests(unittest.TestCase):
    def test_ai_settings_persist_but_api_secret_is_not_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_settings(root, {
                "threads": 3, "language": "ru", "ai_provider": "api",
                "ai_api_base_url": "https://api.example.test/v1", "ai_api_model": "example-model",
                "ai_api_key": "do-not-write-this",
            })
            loaded = load_settings(root)
            self.assertEqual(loaded["ai_provider"], "api")
            self.assertEqual(loaded["ai_api_base_url"], "https://api.example.test/v1")
            persisted = (root / "data" / "settings.json").read_text(encoding="utf-8")
            self.assertNotIn("do-not-write-this", persisted)
            self.assertNotIn('"ai_api_key"', persisted)


class AIPipelineTests(unittest.TestCase):
    @patch("ai_provider.chat_completion", return_value="Краткое содержание")
    def test_short_summary_uses_provider_and_returns_text(self, mock_chat):
        progress = []
        output = ai_provider.process_transcript(
            "local", "http://127.0.0.1:11434/v1", "qwen3.5:4b", "", "summary", "Текст исходной записи.",
            progress=lambda percent, msg: progress.append((percent, msg)),
        )
        self.assertEqual(output, "Краткое содержание")
        self.assertEqual(mock_chat.call_count, 1)
        self.assertEqual(progress[-1][0], 100)

    @patch("ai_provider.chat_completion", return_value="Фрагмент обработан")
    def test_long_text_summarizes_chunks_then_synthesizes(self, mock_chat):
        output = ai_provider.process_transcript(
            "local", "http://127.0.0.1:11434/v1", "qwen3.5:4b", "", "summary", ("Длинный текст. " * 1500),
        )
        self.assertEqual(output, "Фрагмент обработан")
        self.assertGreater(mock_chat.call_count, 2)

    @patch("ai_provider.chat_completion", return_value="Сводка фрагмента")
    def test_very_long_text_is_reduced_hierarchically(self, mock_chat):
        text = ("Очень длинный текст записи с несколькими фактами. " * 5000)
        output = ai_provider.process_transcript(
            "local", "http://127.0.0.1:11434/v1", "qwen3.5:4b", "", "summary", text,
        )
        self.assertEqual(output, "Сводка фрагмента")
        self.assertGreater(mock_chat.call_count, 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ModelPathMigrationTests(unittest.TestCase):
    def test_legacy_vosk_folder_moves_into_models_tree(self):
        from model_paths import resolve_vosk_model_path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "model" / "vosk-model-small-ru-0.22"
            legacy.mkdir(parents=True)
            marker = legacy / "am" / "final.mdl"
            marker.parent.mkdir(parents=True)
            marker.write_bytes(b"marker")
            resolved = resolve_vosk_model_path(root)
            self.assertEqual(resolved, root / "models" / "vosk" / "vosk-model-small-ru-0.22")
            self.assertTrue((resolved / "am" / "final.mdl").is_file())
            self.assertFalse(legacy.exists())
            self.assertFalse((root / "model").exists())

    def test_legacy_folder_keeps_other_content(self):
        from model_paths import resolve_vosk_model_path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_root = root / "model"
            legacy = legacy_root / "vosk-model-small-ru-0.22"
            legacy.mkdir(parents=True)
            (legacy / "model.marker").write_text("keep", encoding="utf-8")
            other = legacy_root / "unrelated.txt"
            other.write_text("keep", encoding="utf-8")
            resolved = resolve_vosk_model_path(root)
            self.assertTrue((resolved / "model.marker").is_file())
            self.assertTrue(other.is_file())
            self.assertTrue(legacy_root.exists())
