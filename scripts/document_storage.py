"""Atomic, ordinary UTF-8 storage for app-owned documents."""
import json
import os
import tempfile
from pathlib import Path


def write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".spiker-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_text(path, *, encoding="utf-8"):
    return Path(path).read_text(encoding=encoding)


def write_text(path, text, *, encoding="utf-8", newline=None):
    write_bytes(path, text.encode(encoding))


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, separators=(",", ":")))
