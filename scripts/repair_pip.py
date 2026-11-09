"""Repair a damaged pip installation inside the active Windows virtual environment.

This helper deliberately uses Python's bundled ensurepip wheel instead of the
broken pip import. It removes only pip package files/metadata from this venv.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if os.name != "nt":
        print("This repair helper is intended for a Windows virtual environment.")
        return 2
    prefix = Path(sys.prefix)
    site_packages = prefix / "Lib" / "site-packages"
    if not site_packages.is_dir():
        print("The active environment does not contain Lib/site-packages.")
        return 3

    patterns = ("pip", "pip-*.dist-info", "pip-*.data")
    for pattern in patterns:
        for path in site_packages.glob(pattern):
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
            except OSError as exc:
                print(f"Unable to remove damaged pip component: {path.name}: {exc}")
                return 4

    print("Bootstrapping pip from the Python standard library...")
    result = subprocess.run(
        [sys.executable, "-m", "ensurepip", "--upgrade", "--default-pip"],
        check=False,
    )
    if result.returncode:
        print(f"ensurepip failed with exit code {result.returncode}.")
        return result.returncode or 5

    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        check=False,
    )
    if result.returncode:
        print("pip repair verification failed.")
        return result.returncode or 6
    print("pip was repaired successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
