from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ai_transfer import available_annotations, transfer_payload
from app_paths import get_user_data_root, history_data_dir, history_results_dir
from document_storage import read_text, write_text
from queue_store import QueueStore


class OrdinaryHistoryTests(unittest.TestCase):
    def test_legacy_data_remains_untouched_when_new_history_is_saved(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SPIKER_DATA_DIR": directory}):
            get_user_data_root.cache_clear()
            try:
                root = Path(directory).resolve()
                self.assertEqual(history_data_dir(), root / "data")
                old = root / "data" / "queue.secure"
                old.parent.mkdir()
                old.write_bytes(b"simulated-old-encrypted-history")
                result = history_results_dir() / "новая.txt"
                write_text(result, "Проверка новой расшифровки")
                queue = QueueStore(history_data_dir() / "queue.sqlite")
                queue.save_tasks([{"id": "new", "path": "audio.wav", "model_choice": "faster:medium"}])
                self.assertEqual(queue.load_tasks()[0]["model_choice"], "faster:medium")
                self.assertEqual(result.parent, root / "results" / "current")
                self.assertEqual(read_text(result), "Проверка новой расшифровки")
                self.assertEqual(old.read_bytes(), b"simulated-old-encrypted-history")
            finally:
                get_user_data_root.cache_clear()


class TransferTests(unittest.TestCase):
    segments = [{"start": 3, "end": 7, "speaker_id": "Спикер 1", "text": "Встреча в 10:30."}]
    names = {"Спикер 1": "Иван"}

    def test_optional_metadata_is_independent_and_does_not_leak(self):
        self.assertEqual(transfer_payload("", self.segments, self.names), ("Встреча в 10:30.", []))
        timed, context = transfer_payload("", self.segments, self.names, timestamps=True)
        self.assertEqual((timed, context), ("[00:03–00:07] Встреча в 10:30.", []))
        spoken, context = transfer_payload("", self.segments, self.names, speakers=True)
        self.assertEqual(spoken, "Иван: Встреча в 10:30.")
        self.assertEqual(context[0]["name"], "Иван")
        structured, _ = transfer_payload("", self.segments, self.names, timestamps=True, speakers=True)
        self.assertIn("[SPEAKER_ID=Спикер 1]", structured)

    def test_edited_text_keeps_changed_words_and_literal_time(self):
        text = "[00:03–00:07] Иван: Встреча отменена.\nПричина: стало поздно.\nПроверьте в 10:30."
        self.assertEqual(available_annotations(text, self.segments, self.names, edited=True), (True, True))
        cleaned, context = transfer_payload(text, self.segments, self.names, edited=True)
        self.assertEqual(cleaned, "Встреча отменена.\nПричина: стало поздно.\nПроверьте в 10:30.")
        self.assertFalse(context)
