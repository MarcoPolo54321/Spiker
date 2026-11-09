"""Download public offline models; keep a provenance/hash manifest for release packs."""
from pathlib import Path
import argparse
import concurrent.futures
import hashlib
import json
import shutil
import tarfile
import urllib.request
import zipfile
import time
from archive_utils import safe_extract_zip

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/'
FASTER_SMALL_REVISION = '2ec96c5472da50d38d40c0cfe0602af2e94b4c8a'
FASTER_SMALL_SHA256 = '3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671'
ASSET_LOCK = json.loads((ROOT / 'models' / 'verified-assets.json').read_text(encoding='utf-8'))['sha256']

def download(url, target, expected_sha256=None):
    expected_sha256 = expected_sha256 or ASSET_LOCK.get(url)
    if not expected_sha256:
        raise RuntimeError(f'Нет закреплённой SHA-256 для загружаемого файла: {url}')
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        with target.open('rb') as stream:
            existing_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
        if existing_hash.lower() != expected_sha256.lower():
            print('Removing asset with a mismatched SHA-256:', target.name, flush=True)
            target.unlink()
    if not target.is_file():
        tmp = target.with_name(target.name + '.part')
        for attempt in range(4):
            try:
                fresh = url + ('&' if '?' in url else '?') + 'download=true&retry=' + str(int(time.time()))
                with urllib.request.urlopen(fresh, timeout=45) as response, tmp.open('wb') as out:
                    shutil.copyfileobj(response, out, 1024 * 1024)
                break
            except Exception:
                if attempt == 3: raise
                print('Retry:', target.name, attempt + 1, flush=True)
        tmp.replace(target)
    with target.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest.lower() != expected_sha256.lower():
        target.unlink(missing_ok=True)
        raise RuntimeError(f'SHA-256 mismatch for {target.name}: {digest}')
    print('Ready:', target.name, target.stat().st_size, flush=True)
    return {'url': url, 'path': str(target.relative_to(ROOT)), 'sha256': digest, 'bytes': target.stat().st_size}

def archive(tag, name, destination):
    target = ROOT / '.cache' / 'model-downloads' / name
    record = download(BASE + tag + '/' + name, target)
    destination.mkdir(parents=True, exist_ok=True)
    model_dir = destination / name.removesuffix('.tar.bz2')
    if 'pyannote-segmentation' in name:
        required = (model_dir / 'model.onnx', model_dir / 'model.int8.onnx')
    elif 'vits-piper-' in name:
        voice = 'irina' if 'irina' in name else 'ruslan'
        required = (
            model_dir / f'ru_RU-{voice}-medium.onnx',
            model_dir / 'tokens.txt',
            model_dir / 'espeak-ng-data' / 'phontab',
        )
    else:
        required = ()
    if required and all(item.is_file() for item in required):
        print('Already installed; keeping existing model files:', model_dir.name, flush=True)
        return record
    with tarfile.open(target) as tar:
        tar.extractall(destination, filter='data')
    return record

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release-assets', action='store_true', help='Download models included with a Windows installer; omit the 6.5 GB optional LLM.')
    parser.add_argument('--include-medium', action='store_true', help='Also download faster-whisper Medium for the Full Windows build.')
    parser.add_argument('--include-faster-whisper', action='store_true', help='Download the pinned faster-whisper Small files for the Full Windows build.')
    args = parser.parse_args()
    jobs = [
        lambda: archive('speaker-segmentation-models', 'sherpa-onnx-pyannote-segmentation-3-0.tar.bz2', ROOT / 'models/diarization'),
        lambda: download(BASE + 'speaker-recongition-models/wespeaker_en_voxceleb_resnet34.onnx', ROOT / 'models/diarization/wespeaker_en_voxceleb_resnet34.onnx'),
        lambda: archive('tts-models', 'vits-piper-ru_RU-irina-medium.tar.bz2', ROOT / 'models/tts'),
        lambda: archive('tts-models', 'vits-piper-ru_RU-ruslan-medium.tar.bz2', ROOT / 'models/tts'),
        lambda: download(BASE + 'speaker-segmentation-models/1-two-speakers-en.wav', ROOT / 'validation_samples/two-speakers.wav'),
    ]
    if not args.release_assets or args.include_medium:
        for name in ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']:
            jobs.append(lambda name=name: download('https://huggingface.co/Systran/faster-whisper-medium/resolve/main/' + name, ROOT / 'models/faster-whisper/medium' / name))
    if args.include_faster_whisper:
        for name in ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']:
            url = f'https://huggingface.co/Systran/faster-whisper-small/resolve/{FASTER_SMALL_REVISION}/{name}'
            expected = FASTER_SMALL_SHA256 if name == 'model.bin' else ''
            jobs.append(lambda name=name, url=url, expected=expected: download(url, ROOT / 'models/faster-whisper/small' / name, expected))
    if not args.release_assets:
        giga = 'GigaChat3.1-10B-A1.8B-q4_K_M.gguf'
        jobs.append(lambda: download('https://huggingface.co/ai-sage/GigaChat3.1-10B-A1.8B-GGUF/resolve/main/' + giga, ROOT / 'models/llm' / giga))
        jobs.append(lambda: download('https://huggingface.co/ai-sage/GigaChat3.1-10B-A1.8B-GGUF/raw/main/README.md', ROOT / 'models/llm/MODEL_CARD.md'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(lambda fn: fn(), jobs))
    name = 'llama-b12211-bin-win-cpu-x64.zip'
    target = ROOT / '.cache/model-downloads' / name
    if not args.release_assets:
        records.append(download('https://github.com/ggml-org/llama.cpp/releases/download/b12211/' + name, target))
    if not (ROOT / 'runtime/llama/llama-server.exe').is_file():
        if not target.is_file():
            records.append(download('https://github.com/ggml-org/llama.cpp/releases/download/b12211/' + name, target))
        with zipfile.ZipFile(target) as z:
            safe_extract_zip(z, ROOT / 'runtime/llama', max_total_bytes=8 * 1024**3)
    manifest = json.dumps(records, ensure_ascii=False, indent=2)
    manifest_path = ROOT / 'models/download-manifest.json'
    try:
        manifest_path.write_text(manifest, encoding='utf-8')
    except PermissionError:
        # Some Windows checkouts mark model assets read-only or deny replacement.
        # Keep the provenance record in the writable release folder in that case.
        fallback = ROOT / 'dist' / 'model-download-manifest.json'
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(manifest, encoding='utf-8')
        print('Model directory is read-only; wrote manifest to:', fallback, flush=True)

if __name__ == '__main__':
    main()
