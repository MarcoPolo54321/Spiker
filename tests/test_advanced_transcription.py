import os
import json
import sys
import types
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from app_config import load_settings, save_settings
from ai_provider import process_transcript
from subtitle_export import render_subtitles
from transcription.hardware_diagnostics import diagnose_hardware, resolve_compute_options
from transcription.faster_whisper_backend import resolve_faster_model, transcribe_with_faster_whisper
from transcription.speaker_diarization import (
    _run_external_diarization, assign_speakers_to_segments, apply_speaker_diarization,
    is_pyannote_available,
)
from transcription.transcript_render import render_transcript_segments, speaker_summary


class AdvancedSettingsTests(unittest.TestCase):
    def test_advanced_preferences_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            save_settings(root, {
                "transcription_engine": "faster-whisper",
                "performance_mode": "manual",
                "compute_device": "cpu",
                "compute_type": "int8",
                "faster_whisper_model": "medium",
                "batch_size": 7,
                "vad_filter": False,
                "word_timestamps": True,
                "audio_normalize": True,
                "diarization_enabled": True,
                "show_speakers": False,
                "speaker_min": 2,
                "speaker_max": 5,
                "context_terms": "CTranslate2, СПИКЕР",
                "audio_profile": "music", "audio_stream_index": 2,
            })
            loaded = load_settings(root)
            self.assertEqual(loaded["transcription_engine"], "faster-whisper")
            self.assertEqual(loaded["performance_mode"], "manual")
            self.assertEqual(loaded["compute_device"], "cpu")
            self.assertEqual(loaded["compute_type"], "int8")
            self.assertEqual(loaded["faster_whisper_model"], "medium")
            self.assertEqual(loaded["batch_size"], 7)
            self.assertFalse(loaded["vad_filter"])
            self.assertTrue(loaded["word_timestamps"])
            self.assertTrue(loaded["audio_normalize"])
            self.assertTrue(loaded["diarization_enabled"])
            self.assertFalse(loaded["show_speakers"])
            self.assertEqual((loaded["speaker_min"], loaded["speaker_max"]), (2, 5))
            self.assertEqual(loaded["context_terms"], "CTranslate2, СПИКЕР")
            self.assertEqual(loaded["audio_profile"], "music")
            self.assertEqual(loaded["audio_stream_index"], 2)

    def test_invalid_advanced_values_are_rejected_or_clamped(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            save_settings(root, {
                "transcription_engine": "unknown-engine",
                "faster_whisper_model": "not-a-model",
                "batch_size": 100,
                "speaker_min": -5,
                "speaker_max": 100,
            })
            loaded = load_settings(root)
            self.assertEqual(loaded["transcription_engine"], "auto")
            self.assertEqual(loaded["faster_whisper_model"], "medium")
            self.assertEqual(loaded["batch_size"], 32)
            self.assertEqual(loaded["speaker_min"], 0)
            self.assertEqual(loaded["speaker_max"], 20)


class TranscriptSpeakerTests(unittest.TestCase):
    def setUp(self):
        self.segments = [
            {"start": 2.0, "end": 4.0, "text": "Вторая реплика", "speaker_id": "SPEAKER_02"},
            {"start": 0.0, "end": 2.0, "text": "Первая реплика", "speaker_id": "SPEAKER_01"},
            {"start": 4.0, "end": 5.0, "text": "Общая фраза"},
        ]

    def test_show_hide_speakers_never_mutates_source_metadata(self):
        original = json.loads(json.dumps(self.segments, ensure_ascii=False))
        names = {"SPEAKER_01": "Анна", "SPEAKER_02": "Борис"}
        shown = render_transcript_segments(self.segments, show_speakers=True, speaker_names=names)
        hidden = render_transcript_segments(self.segments, show_speakers=False, speaker_names=names)
        self.assertTrue(shown.startswith("Анна: Первая реплика"))
        self.assertIn("Борис: Вторая реплика", shown)
        self.assertNotIn("Анна:", hidden)
        self.assertNotIn("Борис:", hidden)
        self.assertEqual(self.segments, original)
        self.assertEqual(self.segments[0]["speaker_id"], "SPEAKER_02")

    def test_speaker_summary_reports_duration_shares(self):
        summary = speaker_summary(self.segments, {"SPEAKER_01": "Анна", "SPEAKER_02": "Борис"})
        self.assertEqual(summary["SPEAKER_01"]["duration_seconds"], 2.0)
        self.assertEqual(summary["SPEAKER_02"]["duration_seconds"], 2.0)
        self.assertEqual(summary["SPEAKER_01"]["share"], 50.0)
        self.assertEqual(summary["SPEAKER_02"]["share"], 50.0)

    def test_speaker_summary_unions_overlapping_segments_per_speaker(self):
        segments = [
            {"start": 0.0, "end": 2.0, "speaker_id": "A"},
            {"start": 1.0, "end": 3.0, "speaker_id": "A"},
            {"start": 2.0, "end": 4.0, "speaker_id": "B"},
        ]
        summary = speaker_summary(segments, {"A": "Анна", "B": "Борис"})
        # A's overlapping intervals count as 3 seconds, not 4. Cross-speaker overlap
        # is retained, so B has 2 seconds and the total speaker-time is 5 seconds.
        self.assertEqual(summary["A"]["duration_seconds"], 3.0)
        self.assertEqual(summary["B"]["duration_seconds"], 2.0)
        self.assertEqual(summary["A"]["share"], 60.0)
        self.assertEqual(summary["B"]["share"], 40.0)

    def test_subtitle_export_includes_speaker_labels(self):
        output = render_subtitles(self.segments, speaker_names={"SPEAKER_01": "Анна", "SPEAKER_02": "Борис"})
        self.assertIn("Анна: Первая реплика", output)
        self.assertIn("Борис: Вторая реплика", output)

    def test_diarization_assigns_the_best_overlapping_speaker(self):
        source = [{"start": 0.5, "end": 2.5, "text": "Фраза"}]
        turns = [(0.0, 1.0, "A"), (1.0, 3.0, "B")]
        enriched, stats = assign_speakers_to_segments(source, turns)
        self.assertEqual(enriched[0]["speaker_id"], "Спикер 2")
        self.assertEqual(stats["Спикер 1"]["duration_seconds"], 1.0)
        self.assertEqual(stats["Спикер 2"]["duration_seconds"], 2.0)
        self.assertNotIn("speaker_id", source[0])

    def test_diarization_does_not_guess_nearest_speaker_when_there_is_no_overlap(self):
        enriched, stats = assign_speakers_to_segments(
            [{"start": 5.0, "end": 6.0, "text": "Без совпадения"}],
            [(0.0, 2.0, "A"), (8.0, 9.0, "B")],
        )
        self.assertEqual(enriched[0]["speaker_id"], "")
        self.assertEqual(stats["_meta"]["unassigned_segments"], 1)

    def test_diarization_preserves_overlap_candidates(self):
        enriched, stats = assign_speakers_to_segments(
            [{"start": 1.0, "end": 2.0, "text": "Перебивание"}],
            [(0.0, 3.0, "A")],
            regular_turns=[(0.0, 3.0, "A"), (1.2, 2.5, "B")],
        )
        self.assertIn("Спикер 2", enriched[0]["overlap_speaker_ids"])
        self.assertEqual(stats["_meta"]["overlapping_segments"], 1)

    def test_frozen_app_detects_its_optional_external_diarization_runtime(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            python = root / ".venv-diarization" / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"")
            helper = root / "scripts" / "diarization_worker.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("# runner", encoding="utf-8")
            self.assertTrue(is_pyannote_available(root))

    def test_external_diarization_helper_protocol_returns_turns(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            helper = root / "fake_runner.py"
            helper.write_text(
                "import argparse, json; from pathlib import Path; "
                "p=argparse.ArgumentParser(); p.add_argument('--output'); "
                "a=p.parse_known_args()[0]; Path(a.output).write_text(json.dumps({"
                "'regular_turns': [[0, 1, 'A']], 'exclusive_turns': [[0, 1, 'A']]}))",
                encoding="utf-8",
            )
            with patch("transcription.speaker_diarization._external_runtime", return_value=(Path(sys.executable), helper)):
                regular, exclusive = _run_external_diarization(
                    root / "audio.wav", root / "model", root,
                    min_speakers=None, max_speakers=None, device="cpu",
                    stage_callback=None, cancel_callback=None,
                )
            self.assertEqual(regular, [(0.0, 1.0, "A")])
            self.assertEqual(exclusive, regular)


class OptionalBackendTests(unittest.TestCase):
    def test_faster_whisper_model_must_be_local(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            model = root / "models" / "faster-whisper" / "small"
            model.mkdir(parents=True)
            self.assertIsNone(resolve_faster_model(root, "small"))
            (model / "config.json").write_text("{}", encoding="utf-8")
            self.assertEqual(resolve_faster_model(root, "small"), model.resolve())


    @patch("transcription.faster_whisper_backend.resolve_compute_options", return_value=("cpu", "int8"))
    def test_faster_whisper_batch_adapter_passes_context_vad_and_words(self, _compute):
        captured = {}

        class FakeWhisperModel:
            def __init__(self, *args, **kwargs):
                captured["model"] = (args, kwargs)

        class FakeBatchPipeline:
            def __init__(self, model):
                captured["pipeline_model"] = model

            def transcribe(self, source, **kwargs):
                captured["transcribe"] = kwargs
                word = SimpleNamespace(start=1.0, end=1.4, word=" Привет", probability=0.99)
                segment = SimpleNamespace(start=1.0, end=2.0, text="Привет", words=[word])
                return iter([segment]), SimpleNamespace(language="ru")

        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeWhisperModel
        fake_module.BatchedInferencePipeline = FakeBatchPipeline
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            model_path = root / "small"
            model_path.mkdir()
            (model_path / "config.json").write_text("{}", encoding="utf-8")
            audio = root / "audio.wav"
            audio.write_bytes(b"wav")
            from transcription import faster_whisper_backend
            faster_whisper_backend._MODEL_CACHE.clear()
            timestamps = []
            with patch.dict(sys.modules, {"faster_whisper": fake_module}):
                result = transcribe_with_faster_whisper(
                    audio, model_path, device="cpu", compute_type="int8", batch_size=4,
                    vad_filter=True, word_timestamps=True, initial_prompt="CTranslate2",
                    timestamp_callback=timestamps.append,
                )
        self.assertEqual(result, "Привет")
        self.assertEqual(captured["transcribe"]["batch_size"], 4)
        self.assertEqual(captured["transcribe"]["initial_prompt"], "CTranslate2")
        self.assertTrue(captured["transcribe"]["vad_filter"])
        self.assertTrue(captured["transcribe"]["word_timestamps"])
        self.assertFalse(captured["transcribe"]["condition_on_previous_text"])
        self.assertEqual(timestamps[0]["words"][0]["word"], "Привет")

    @patch("transcription.faster_whisper_backend.resolve_compute_options", return_value=("cpu", "int8"))
    def test_callback_errors_do_not_abort_faster_whisper_recognition(self, _compute):
        class FakeWhisperModel:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, source, **kwargs):
                word = SimpleNamespace(start=0.1, end=0.4, word=" Привет", probability=0.99)
                segment = SimpleNamespace(start=0.0, end=0.5, text="Привет", words=[word])
                return iter([segment]), SimpleNamespace(language="ru")

        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeWhisperModel
        fake_module.BatchedInferencePipeline = object

        def broken_callback(*args):
            raise NameError("simulated UI callback regression")

        from transcription import faster_whisper_backend
        faster_whisper_backend._MODEL_CACHE.clear()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            model_path = root / "small"
            model_path.mkdir()
            (model_path / "config.json").write_text("{}", encoding="utf-8")
            audio = root / "audio.wav"
            audio.write_bytes(b"placeholder")
            with patch.dict(sys.modules, {"faster_whisper": fake_module}):
                result = transcribe_with_faster_whisper(
                    audio, model_path, device="cpu", compute_type="int8", batch_size=1,
                    duration_seconds=1.0, stage_callback=broken_callback,
                    timestamp_callback=broken_callback, segment_callback=broken_callback,
                )
        self.assertEqual(result, "Привет")

    def test_faster_whisper_cache_can_be_released_before_diarization(self):
        from transcription import faster_whisper_backend
        faster_whisper_backend._MODEL_CACHE.clear()
        faster_whisper_backend._MODEL_CACHE[("model", "cuda", "float16")] = object()
        self.assertEqual(faster_whisper_backend.release_faster_whisper_cache("cuda"), 1)
        self.assertFalse(faster_whisper_backend._MODEL_CACHE)

    @patch("transcription.hardware_diagnostics.cuda_backend_ready", return_value=False)
    def test_compute_auto_uses_cpu_int8_when_cuda_is_unavailable(self, _cuda):
        self.assertEqual(resolve_compute_options("auto", "auto"), ("cpu", "int8"))
        self.assertEqual(resolve_compute_options("cpu", "float32"), ("cpu", "float32"))
        with self.assertRaisesRegex(RuntimeError, "предназначен для совместимой GPU-конфигурации"):
            resolve_compute_options("cpu", "float16")

    @patch("transcription.hardware_diagnostics.cuda_backend_ready", return_value=False)
    def test_forced_cuda_reports_unavailable_runtime(self, _cuda):
        with self.assertRaisesRegex(RuntimeError, "принудительный режим CUDA"):
            resolve_compute_options("cuda", "auto")


    def test_pyannote_adapter_uses_local_model_and_returns_speaker_ids(self):
        class Turn:
            def __init__(self, start, end):
                self.start = start
                self.end = end

        class Annotation:
            def itertracks(self, yield_label=False):
                yield Turn(0.0, 1.5), "track-a", "VOICE_A"
                yield Turn(1.5, 3.0), "track-b", "VOICE_B"

        class Pipeline:
            @classmethod
            def from_pretrained(cls, path, token=None):
                self = cls()
                self.path = path
                return self

            def __call__(self, path, **kwargs):
                return SimpleNamespace(speaker_diarization=Annotation())

        package = types.ModuleType("pyannote")
        package.__path__ = []
        audio = types.ModuleType("pyannote.audio")
        audio.Pipeline = Pipeline
        package.audio = audio
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SPIKER_DATA_DIR": tmp}):
            root = Path(tmp)
            model = root / "models" / "pyannote" / "speaker-diarization-community-1"
            model.mkdir(parents=True)
            (model / "config.yaml").write_text("pipeline: mock", encoding="utf-8")
            for component in ("segmentation", "embedding", "plda"):
                folder = model / component
                folder.mkdir()
                (folder / "model.bin").write_bytes(b"mock")
            wav = root / "audio.wav"
            wav.write_bytes(b"placeholder")
            with patch.dict(sys.modules, {"pyannote": package, "pyannote.audio": audio}):
                segments, stats = apply_speaker_diarization(
                    wav,
                    [{"start": 0.2, "end": 1.0, "text": "Первая"}, {"start": 1.6, "end": 2.6, "text": "Вторая"}],
                    root, device="cpu",
                )
        self.assertEqual([item["speaker_id"] for item in segments], ["Спикер 1", "Спикер 2"])
        self.assertEqual(set(stats) - {"_meta"}, {"Спикер 1", "Спикер 2"})

    @patch("transcription.hardware_diagnostics._memory_available_gb", return_value=8.0)
    @patch("transcription.hardware_diagnostics._memory_gb", return_value=16.0)
    @patch("transcription.hardware_diagnostics._nvidia_info", return_value=("NVIDIA Test", 8.0))
    @patch("transcription.hardware_diagnostics.cuda_backend_ready", return_value=True)
    def test_diagnostics_recommend_gpu_profile_from_hardware(self, _cuda, _gpu, _ram, _available_ram):
        report = diagnose_hardware()
        self.assertEqual(report.recommended_device, "cuda")
        self.assertEqual(report.recommended_compute_type, "float16")
        self.assertEqual(report.recommended_model, "large-v3-turbo")
        self.assertEqual(report.recommended_batch_size, 4)


    @patch("transcription.hardware_diagnostics._memory_gb", return_value=32.0)
    @patch("transcription.hardware_diagnostics._memory_available_gb", return_value=16.0)
    @patch("transcription.hardware_diagnostics._nvidia_info", return_value=("NVIDIA Test", 8.0))
    @patch("transcription.hardware_diagnostics._nvidia_usage_info", return_value=(2.0, 98.0))
    @patch("transcription.hardware_diagnostics.cuda_backend_ready", return_value=True)
    def test_diagnostics_uses_free_vram_not_total_vram(self, _cuda, _usage, _gpu, _available, _total):
        report = diagnose_hardware()
        self.assertEqual(report.gpu_vram_gb, 8.0)
        self.assertEqual(report.gpu_vram_free_gb, 2.0)
        self.assertEqual(report.gpu_utilization_percent, 98.0)
        self.assertEqual(report.recommended_device, "cpu")
        self.assertEqual(report.recommended_model, "small")

    @patch("transcription.hardware_diagnostics._memory_gb", return_value=16.0)
    @patch("transcription.hardware_diagnostics._nvidia_info", return_value=("NVIDIA Test", None))
    @patch("transcription.hardware_diagnostics.cuda_backend_ready", return_value=True)
    def test_diagnostics_uses_conservative_gpu_profile_when_vram_is_unknown(self, _cuda, _gpu, _ram):
        report = diagnose_hardware()
        self.assertEqual(report.recommended_device, "cuda")
        self.assertEqual(report.recommended_model, "small")
        self.assertEqual(report.recommended_batch_size, 1)


class SpeakerAwareAITests(unittest.TestCase):
    @patch("ai_provider.chat_completion", return_value="Сводка участников")
    def test_per_speaker_analysis_prompt_is_available(self, mock_chat):
        output = process_transcript(
            "local", "http://127.0.0.1:11434/v1", "test-model", "", "speaker_summary",
            "Анна: Предлагаю перенести запуск.\nБорис: Согласен.",
            speaker_context=[
                {"speaker_id": "SPEAKER_01", "name": "Анна"},
                {"speaker_id": "SPEAKER_02", "name": "Борис"},
            ],
        )
        self.assertEqual(output, "Сводка участников")
        prompt = mock_chat.call_args.args[3][1]["content"]
        self.assertIn("по каждому участнику", prompt)
        self.assertIn("SPEAKER_01", prompt)
        self.assertIn("Анна", prompt)
        self.assertIn("Борис", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)

class AdditionalRegressionTests(unittest.TestCase):
    def test_audio_profiles_disable_vad_for_music_and_preserve_original_audio(self):
        from transcription.faster_whisper_backend import resolve_audio_profile_options
        self.assertEqual(resolve_audio_profile_options("music", True, True), (False, True))
        self.assertEqual(resolve_audio_profile_options("preserve", True, True), (False, False))
        self.assertEqual(resolve_audio_profile_options("speech", True, False), (True, False))

    def test_diarization_rerun_preserves_existing_profile_ids_by_time_overlap(self):
        original = [
            {"start": 0.0, "end": 2.0, "text": "Реплика Анны", "speaker_id": "Анна"},
            {"start": 2.1, "end": 4.0, "text": "Реплика Бориса", "speaker_id": "Борис"},
        ]
        # Model labels are swapped relative to the previous run. Profile names remain tied to time.
        turns = [(0.0, 2.0, "SPEAKER_B"), (2.1, 4.0, "SPEAKER_A")]
        enriched, stats = assign_speakers_to_segments(original, turns)
        self.assertEqual([row["speaker_id"] for row in enriched], ["Анна", "Борис"])
        self.assertIn("Анна", stats)
        self.assertIn("Борис", stats)

    def test_meta_statistics_are_not_treated_as_speaker_profile(self):
        stats = {"Спикер 1": {"duration_seconds": 1.2}, "_meta": {"speakers_detected": 1}}
        profile_ids = [str(value) for value in stats if str(value) != "_meta"]
        self.assertEqual(profile_ids, ["Спикер 1"])
