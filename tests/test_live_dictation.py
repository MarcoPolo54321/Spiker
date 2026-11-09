"""Unit tests for the optional streaming live-dictation backend."""
from __future__ import annotations
import os

import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from app_config import load_settings, save_settings
from transcription.live_streaming import (
    DEFAULT_MODEL_DIR,
    SherpaStreamingSession,
    create_t_one_recognizer,
    merge_live_text,
    resolve_t_one_model,
)


class LiveDictationSettingsTests(unittest.TestCase):
    def test_engine_preference_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            save_settings(root, {"dictation_engine": "sherpa", "sherpa_model_path": "C:/Spiker/models/live"})
            loaded = load_settings(root)
            self.assertEqual(loaded["dictation_engine"], "sherpa")
            self.assertEqual(loaded["sherpa_model_path"], "C:/Spiker/models/live")

    def test_invalid_live_engine_falls_back_to_auto(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            save_settings(root, {"dictation_engine": "made-up"})
            self.assertEqual(load_settings(root)["dictation_engine"], "auto")


class LiveModelDiscoveryTests(unittest.TestCase):
    def test_resolves_installed_t_one_model_without_network(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            model = root / "models" / "sherpa-onnx" / DEFAULT_MODEL_DIR
            model.mkdir(parents=True)
            (model / "model.onnx").write_bytes(b"model")
            (model / "tokens.txt").write_text("<blk>\n", encoding="utf-8")
            self.assertEqual(resolve_t_one_model(root), model.resolve())

    def test_configured_model_path_accepts_model_file_or_directory(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            model = Path(tmp) / "my-model"
            model.mkdir()
            (model / "model.onnx").write_bytes(b"model")
            (model / "tokens.txt").write_text("<blk>\n", encoding="utf-8")
            self.assertEqual(resolve_t_one_model(Path(tmp), str(model / "model.onnx")), model.resolve())

    def test_missing_model_is_not_downloaded_automatically(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            self.assertIsNone(resolve_t_one_model(Path(tmp)))

    def test_recognizer_factory_uses_local_files_and_expected_options(self):
        captured = {}

        class FakeRecognizer:
            @classmethod
            def from_t_one_ctc(cls, **kwargs):
                captured.update(kwargs)
                return "fake-recognizer"

        fake_module = types.ModuleType("sherpa_onnx")
        fake_module.OnlineRecognizer = FakeRecognizer
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            model = Path(tmp)
            (model / "model.onnx").write_bytes(b"model")
            (model / "tokens.txt").write_text("<blk>\n", encoding="utf-8")
            with patch.dict(sys.modules, {"sherpa_onnx": fake_module}):
                recognizer = create_t_one_recognizer(model, num_threads=16)
        self.assertEqual(recognizer, "fake-recognizer")
        self.assertEqual(captured["sample_rate"], 8000)
        self.assertEqual(captured["num_threads"], 8)
        self.assertEqual(captured["provider"], "cpu")
        self.assertTrue(captured["enable_endpoint_detection"])
        self.assertTrue(str(captured["model"]).endswith("model.onnx"))


class FakeStream:
    def __init__(self):
        self.sample_rates = []
        self.frames = 0

    def accept_waveform(self, sample_rate, samples):
        self.sample_rates.append(sample_rate)
        self.frames += len(samples)

    def input_finished(self):
        return None


class FakeOnlineRecognizer:
    def __init__(self):
        self.text = ""
        self.endpoint = False
        self.reset_count = 0
        self.stream = FakeStream()

    def create_stream(self):
        return self.stream

    def is_ready(self, _stream):
        return False

    def decode_stream(self, _stream):
        raise AssertionError("decode_stream should not be called when stream is not ready")

    def get_result_all(self, _stream):
        return SimpleNamespace(text=self.text)

    def is_endpoint(self, _stream):
        return self.endpoint

    def reset(self, _stream):
        self.reset_count += 1
        self.text = ""
        self.endpoint = False


class LiveStreamingSessionTests(unittest.TestCase):
    @staticmethod
    def pcm_frame():
        return struct.pack("<160h", *([100] * 160))

    def test_partial_text_is_updated_and_endpoint_commits_phrase(self):
        recognizer = FakeOnlineRecognizer()
        session = SherpaStreamingSession(recognizer, sample_rate=16000)

        recognizer.text = "привет"
        preview, committed = session.feed_pcm16(self.pcm_frame())
        self.assertEqual(preview, "привет")
        self.assertFalse(committed)

        recognizer.text = "привет мир"
        recognizer.endpoint = True
        preview, committed = session.feed_pcm16(self.pcm_frame())
        self.assertEqual(preview, "привет мир")
        self.assertTrue(committed)
        self.assertEqual(recognizer.reset_count, 1)

        recognizer.text = "следующая фраза"
        preview, committed = session.feed_pcm16(self.pcm_frame())
        self.assertEqual(preview, "привет мир следующая фраза")
        self.assertFalse(committed)

        final_text = session.finish()
        self.assertEqual(final_text, "привет мир следующая фраза")

    def test_empty_and_odd_length_pcm_are_safe(self):
        recognizer = FakeOnlineRecognizer()
        session = SherpaStreamingSession(recognizer)
        self.assertEqual(session.feed_pcm16(b""), ("", False))
        self.assertEqual(session.feed_pcm16(b"\x01"), ("", False))

    def test_t_one_stream_uses_reference_padding_at_start_and_stop(self):
        recognizer = FakeOnlineRecognizer()
        session = SherpaStreamingSession(recognizer, sample_rate=16000)
        # 300 ms left padding plus 660 ms tail padding from the T-one examples.
        self.assertEqual(recognizer.stream.frames, 4800)
        session.finish()
        self.assertEqual(recognizer.stream.frames, 4800 + 10560)
        self.assertEqual(recognizer.stream.sample_rates, [16000, 16000])

    def test_merge_helper_keeps_committed_and_partial_separate(self):
        self.assertEqual(merge_live_text("Уже готово.", "Новая фраза"), "Уже готово.\nНовая фраза")
        self.assertEqual(merge_live_text("Уже готово.", ""), "Уже готово.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
