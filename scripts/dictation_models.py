"""Find compatible local Whisper.cpp reserves for Russian dictation."""
from pathlib import Path
import re


def is_whisper_model(path):
    """GGML Whisper.cpp is not interchangeable with CTranslate2 or GGUF."""
    file = Path(path)
    try:
        if file.suffix.lower() != ".bin" or file.stat().st_size < 10 * 1024**2:
            return False
        with file.open("rb") as source:
            return source.read(4) == b"lmgg"
    except OSError:
        return False


def available_whisper_models(*roots):
    seen = set()
    for root in roots:
        root = Path(root)
        for path in sorted((*root.glob("ggml-*.bin"), *(root / "whisper").glob("*.bin"))):
            try:
                if is_whisper_model(path):
                    resolved = path.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        yield resolved
            except OSError:
                continue


def is_multilingual(path):
    return not re.search(r"\.en(?:[.-])", Path(path).name, re.IGNORECASE)


def pick_dictation_model(models):
    """Prefer balanced Small; fall back to Base, Tiny or another multilingual model."""
    models = [path for path in models if is_multilingual(path)]
    if not models:
        return None
    priority = {"small": 0, "base": 1, "tiny": 2}
    return min(models, key=lambda path: (
        priority.get((path.stem.lower().split("-", 2) + [""])[1], 3),
        bool(re.search(r"-q\d", path.stem)),
    ))
