import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import local_ai
from assemble_windows_folder import assemble
from transcription.faster_whisper_backend import resolve_faster_model
from transcription.live_streaming import DEFAULT_MODEL_DIR, resolve_t_one_model


class UnifiedWindowsFolderTests(unittest.TestCase):
    def test_assembled_folder_still_resolves_models_after_move(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root / "stage"
            (stage / "res").mkdir(parents=True)
            (stage / "Spiker.exe").write_bytes(b"EXE")
            (stage / "data").mkdir()
            (stage / "data" / "queue.json").write_text("private", encoding="utf-8")
            archives = root / "archives"
            archives.mkdir()
            name = "Spiker-Models-test.zip"
            archive = archives / name
            with ZipFile(archive, "w") as bundle:
                for file in ("model.bin", "config.json", "tokenizer.json"):
                    bundle.writestr(f"models/faster-whisper/small/{file}", "test")
                bundle.writestr(f"models/llm/{local_ai.LIGHT_MODEL}", b"GGUF" + bytes(1024**2))
                for file in ("model.onnx", "tokens.txt"):
                    bundle.writestr(f"models/sherpa-onnx/{DEFAULT_MODEL_DIR}/{file}", "test")
            (stage / "res" / "model-bundles.json").write_text(
                json.dumps({name: hashlib.sha256(archive.read_bytes()).hexdigest()}), encoding="utf-8",
            )
            assembled = root / "output"
            assemble(stage, archives, assembled)
            moved = assembled.rename(root / "another drive").resolve()
            self.assertTrue((moved / "Spiker.exe").is_file())
            self.assertFalse((moved / "data").exists())
            self.assertFalse((moved / name).exists())
            with patch("model_paths.get_user_data_root", side_effect=AssertionError("legacy path read")), \
                 patch("local_ai.get_app_root", return_value=moved):
                self.assertEqual(resolve_faster_model(moved, "small", str(stage / "old.bin")),
                                 moved / "models/faster-whisper/small")
                self.assertEqual(resolve_t_one_model(moved), moved / "models/sherpa-onnx" / DEFAULT_MODEL_DIR)
                self.assertEqual(local_ai.model_path(local_ai.LIGHT_MODEL), moved / "models/llm" / local_ai.LIGHT_MODEL)

    def test_only_valid_local_gguf_candidates_are_discovered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "models/llm"
            folder.mkdir(parents=True)
            good = folder / "custom.Q4_K_M.gguf"
            good.write_bytes(b"GGUF" + bytes(1024**2))
            (folder / "incomplete.gguf").write_bytes(b"GGUF")
            (folder / "invalid.gguf").write_bytes(bytes(1024**2))
            with patch("local_ai.get_app_root", return_value=root), patch("local_ai.model_roots", return_value=(root / "models",)):
                self.assertEqual(local_ai.installed_models(), [good.name])
                with self.assertRaises(ValueError):
                    local_ai.model_path("../custom.Q4_K_M.gguf")

    def test_corrupt_bundle_does_not_install_models(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "res").mkdir()
            name = "Spiker-Models-test.zip"
            (root / name).write_bytes(b"tampered")
            (root / "res" / "model-bundles.json").write_text(json.dumps({name: "a" * 64}))
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                assemble(root, root, root / "destination", models_only=True)
            self.assertFalse((root / "destination" / "models").exists())
