"""Build optional ZIP64 release packs from vetted local weights."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


DICTATION_MODELS = {
    "ggml-base-q5_1.bin": "422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898",
    "ggml-tiny-q5_1.bin": "818710568da3ca15689e31a743197b520007872ff9576237bda97bd1b469c3d7",
}


def build(root, dist, large_name="", ai_name="", dictation_name=""):
    asr = root / "models/faster-whisper/large-v3"
    llm = root / "models/llm"
    manifest = {}

    def pack(name, sources):
        result = dist / name
        if not sources:
            result.unlink(missing_ok=True)
            return
        part = result.with_suffix(".zip.part")
        try:
            with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
                for source in sources:
                    bundle.write(source, source.relative_to(root).as_posix())
            digest = sha(part)
            part.replace(result)
            manifest[name] = digest
        finally:
            part.unlink(missing_ok=True)

    if dictation_name:
        models = []
        for name, digest in DICTATION_MODELS.items():
            path = root / "models/whisper" / name
            if path.is_file():
                if sha(path) != digest:
                    raise ValueError(f"{name} checksum mismatch")
                models.append(path)
        pack(dictation_name, models if len(models) == len(DICTATION_MODELS) else [])
    if not large_name or not ai_name:
        return manifest

    large = []
    weight = asr / "model.bin"
    if weight.is_file():
        if sha(weight) != "69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1":
            raise ValueError("Whisper Large-v3 model.bin checksum mismatch")
        large = [asr / n for n in ("config.json", "model.bin", "tokenizer.json", "preprocessor_config.json", "vocabulary.json")]
        if not all(path.is_file() for path in large):
            raise FileNotFoundError("Whisper Large-v3 is incomplete")
    pack(large_name, large)
    light = llm / "Qwen3-4B-Q4_K_M.gguf"
    if light.is_file() and sha(light) != "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5":
        raise ValueError("Qwen3 4B checksum mismatch")
    models = [llm / name for name in ("GigaChat3.1-10B-A1.8B-q4_K_M.gguf", "Qwen3-4B-Q4_K_M.gguf")]
    if models[0].is_file() and sha(models[0]) != "68a8732fb5cee04f83ebffd7924e15c534d4442c5a43d2ba9e2041fe310b8deb":
        raise ValueError("GigaChat 10B checksum mismatch")
    available = [item for item in models if item.is_file()]
    if available and (llm / "MODEL_CARD.md").is_file():
        available.append(llm / "MODEL_CARD.md")
    pack(ai_name, available)
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1]), Path(sys.argv[2]), *sys.argv[3:])))
