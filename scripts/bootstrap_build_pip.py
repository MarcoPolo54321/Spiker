"""Robustly bootstrap/repair pip inside the active build virtual environment.

The helper uses only the Python standard library. It intentionally captures
child-process stderr so a failed ensurepip attempt can fall back to PyPA's
get-pip bootstrap without PowerShell treating that stderr as a terminating
NativeCommandError.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import urllib.request
from pathlib import Path

GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


def _pip_healthy() -> bool:
    # Check the exact entry point used by the build, but capture all output
    # inside Python so Windows PowerShell never sees expected missing-pip stderr.
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _show_result(label: str, result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        # Print captured stderr to stdout so PowerShell does not turn a
        # recoverable bootstrap failure into a terminating error record.
        print(result.stderr.rstrip())
    if result.returncode:
        print(f"{label} exited with code {result.returncode}.")


def _run(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
    print(f"Running: {label}")
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    _show_result(label, result)
    return result


def _remove_broken_pip() -> None:
    site_packages = Path(sysconfig.get_paths()["purelib"])
    if not site_packages.is_dir():
        return
    for pattern in ("pip", "pip-*.dist-info", "pip-*.data"):
        for path in site_packages.glob(pattern):
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
                print(f"Removed incomplete pip component: {path.name}")
            except OSError as exc:
                print(f"Could not remove {path}: {exc}")
                raise


def _download_get_pip(destination: Path) -> None:
    request = urllib.request.Request(
        GET_PIP_URL,
        headers={"User-Agent": "Spiker-Windows-Build/3.0.8"},
    )
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            print(f"Downloading official PyPA pip bootstrap (attempt {attempt}/3)...")
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            if len(data) < 100_000 or b"pip" not in data[:2_000_000].lower():
                raise RuntimeError("Downloaded get-pip.py looks incomplete.")
            destination.write_bytes(data)
            return
        except Exception as exc:  # network, TLS, proxy, interrupted download
            last_error = exc
            print(f"Download attempt {attempt} failed: {exc}")
            if attempt < 3:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Could not download the official PyPA bootstrap: {last_error}")


def main() -> int:
    if not sys.prefix or sys.prefix == sys.base_prefix:
        print("ERROR: bootstrap must run inside the isolated build venv.")
        return 2

    if _pip_healthy():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            text=True,
            capture_output=True,
            check=False,
        )
        print(f"pip is already available: {result.stdout.strip()}")
        return 0

    print("pip is missing or incomplete; repairing build environment...")
    try:
        _remove_broken_pip()
    except OSError:
        # ensurepip below may still repair an incomplete installation.
        pass

    ensurepip = _run(
        [sys.executable, "-m", "ensurepip", "--upgrade", "--default-pip"],
        "Python ensurepip",
    )
    if ensurepip.returncode == 0 and _pip_healthy():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            text=True,
            capture_output=True,
            check=False,
        )
        print(f"pip installed successfully by ensurepip: {result.stdout.strip()}")
        return 0

    print("ensurepip was unsuccessful; using the official PyPA get-pip fallback.")
    try:
        _remove_broken_pip()
        with tempfile.TemporaryDirectory(prefix="spiker-get-pip-") as temp_dir:
            bootstrap = Path(temp_dir) / "get-pip.py"
            _download_get_pip(bootstrap)
            result = _run(
                [sys.executable, str(bootstrap), "--disable-pip-version-check"],
                "PyPA get-pip bootstrap",
            )
            if result.returncode != 0:
                print("ERROR: PyPA get-pip bootstrap failed.")
                return result.returncode or 3
    except Exception as exc:
        print(f"ERROR: pip bootstrap failed: {exc}")
        return 4

    if not _pip_healthy():
        print("ERROR: `python -m pip` is still not working after bootstrap.")
        return 5
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    print(f"pip is ready: {result.stdout.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
