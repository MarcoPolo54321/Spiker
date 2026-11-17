"""Assemble a ready-to-copy Windows folder from a release stage and model ZIPs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

from archive_utils import safe_extract_zip


def assemble(stage, archives, destination, *, reuse_models=None, models_only=False):
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Choose a new, empty path: {destination}")
    manifest = json.loads((stage / "res" / "model-bundles.json").read_text(encoding="utf-8-sig"))
    if not manifest or not isinstance(manifest, dict):
        raise ValueError("Release model manifest is missing or empty.")
    for name, digest in manifest.items():
        if Path(name).name != name or not name.startswith("Spiker-Models") or not name.endswith(".zip"):
            raise ValueError(f"Invalid model archive name: {name!r}")
        if not (archives / name).is_file() or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"Model archive or SHA-256 missing: {name}")

    def reuse(info, target):
        if reuse_models is None:
            return False
        candidate = reuse_models.joinpath(*Path(info.filename).parts[1:])
        if target.exists() or candidate.is_symlink() or not candidate.is_file() or candidate.stat().st_size != info.file_size:
            return False
        # For an explicit same-volume reuse, compare SHA-256 to the verified
        # ZIP member (CRC alone does not authenticate an existing source).
        with current_zip.open(info) as member, candidate.open("rb") as existing:
            if hashlib.file_digest(member, "sha256").digest() != hashlib.file_digest(existing, "sha256").digest():
                return False
        try:
            os.link(candidate, target)
        except OSError:
            return False
        return True

    if models_only:
        destination.mkdir(parents=True)
    else:
        if not (stage / "Spiker.exe").is_file():
            raise FileNotFoundError("Staged Spiker.exe is missing.")
        private = {"data", "logs", "results", "user-data", ".smoke-user-data"}

        def ignore(directory, names):
            if Path(directory) != stage:
                return []
            return [name for name in names if name.casefold() in private or name.lower().startswith("unins")]

        shutil.copytree(stage, destination, ignore=ignore)
    seen_files = set()
    for name, digest in manifest.items():
        print(f"Verifying {name}", flush=True)
        with (archives / name).open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != digest.lower():
                raise ValueError(f"Model archive SHA-256 mismatch: {name}")
            source.seek(0)
            with zipfile.ZipFile(source) as current_zip:
                files = {entry.filename.casefold() for entry in current_zip.infolist() if not entry.is_dir()}
                if seen_files.intersection(files):
                    raise ValueError(f"Model archives contain overlapping files: {name}")
                seen_files.update(files)
                safe_extract_zip(
                    current_zip, destination, allowed_top_level={"models"}, max_total_bytes=24 * 1024**3,
                    reuse_file=reuse if reuse_models is not None else None,
                )
    print(f"Ready: {destination}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=Path)
    parser.add_argument("archives", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--reuse-models", type=Path, help="Optional trusted same-drive files, verified before linking.")
    parser.add_argument("--models-only", action="store_true", help="Prepare a new install directory for Setup.")
    args = parser.parse_args()
    assemble(args.stage.resolve(), args.archives.resolve(), args.destination.absolute(),
             reuse_models=args.reuse_models, models_only=args.models_only)


if __name__ == "__main__":
    main()
