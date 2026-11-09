from __future__ import annotations

import stat
import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from archive_utils import safe_extract_tar, safe_extract_zip


class SafeZipExtractionTests(unittest.TestCase):
    def make_zip(self, folder: Path, *, name: str, payload: bytes = b"ok", mode: int | None = None) -> Path:
        path = folder / "input.zip"
        with zipfile.ZipFile(path, "w") as archive:
            info = zipfile.ZipInfo(name)
            if mode is not None:
                info.external_attr = mode << 16
            archive.writestr(info, payload)
        return path

    def test_extracts_regular_file_under_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            archive_path = self.make_zip(folder, name="models/whisper/model.bin", payload=b"model")
            destination = folder / "output"
            with zipfile.ZipFile(archive_path) as archive:
                safe_extract_zip(archive, destination, allowed_top_level={"models"})
            self.assertEqual((destination / "models/whisper/model.bin").read_bytes(), b"model")

    def test_rejects_parent_traversal_and_windows_paths(self):
        for name in ("../escaped.txt", "models/../../escaped.txt", r"models\..\escaped.txt", "C:/outside.txt"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                archive_path = self.make_zip(folder, name=name)
                with zipfile.ZipFile(archive_path) as archive:
                    with self.assertRaises(ValueError):
                        safe_extract_zip(archive, folder / "output")
                self.assertFalse((folder / "escaped.txt").exists())

    def test_rejects_symlink_and_size_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            link_zip = self.make_zip(folder, name="models/link", payload=b"target", mode=stat.S_IFLNK | 0o777)
            with zipfile.ZipFile(link_zip) as archive:
                with self.assertRaises(ValueError):
                    safe_extract_zip(archive, folder / "output")

            size_zip = self.make_zip(folder, name="models/large.bin", payload=b"12345")
            with zipfile.ZipFile(size_zip) as archive:
                with self.assertRaises(ValueError):
                    safe_extract_zip(archive, folder / "output", max_total_bytes=4)

    def test_tar_extraction_rejects_parent_paths_and_links(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            archive_path = folder / "unsafe.tar"
            with tarfile.open(archive_path, "w") as archive:
                member = tarfile.TarInfo("../outside.txt")
                member.size = 2
                archive.addfile(member, io.BytesIO(b"no"))
            with tarfile.open(archive_path) as archive:
                with self.assertRaises(ValueError):
                    safe_extract_tar(archive, folder / "output")
            self.assertFalse((folder / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
