"""Fetch Android build dependencies into the work disk, never the C: SDK cache."""
from pathlib import Path
import json
import zipfile
import concurrent.futures
from download_release_models import download, ROOT
from archive_utils import safe_extract_zip

TOOLCHAIN = json.loads((ROOT / 'android' / 'toolchain-lock.json').read_text(encoding='utf-8'))

def unpack(url, destination):
    target = ROOT / '.cache/android' / url.split('/')[-1]
    download(url, target)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target) as archive:
        safe_extract_zip(archive, destination, max_total_bytes=16 * 1024**3)

def main():
    tools = ROOT / '.android-tools'
    jobs = [lambda:unpack(TOOLCHAIN['jdk']['url'], tools / 'java'),
        lambda:unpack(TOOLCHAIN['gradle']['url'], tools),
        lambda:unpack(TOOLCHAIN['android_commandline_tools']['url'], tools / 'sdk'),
        lambda:unpack(TOOLCHAIN['android_platform']['url'], tools / 'sdk'),
        lambda:unpack(TOOLCHAIN['android_build_tools']['url'], tools / 'sdk'),
        lambda:unpack(TOOLCHAIN['android_platform_tools']['url'], tools / 'sdk'),
        lambda:download('https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/sherpa-onnx-1.13.8.aar', ROOT / 'android/app/libs/sherpa-onnx-1.13.8.aar')]
    with concurrent.futures.ThreadPoolExecutor(4) as pool:list(pool.map(lambda f:f(), jobs))
    base = 'https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.13.8/sherpa-onnx/kotlin-api/'
    names = ['FeatureConfig.kt', 'HomophoneReplacerConfig.kt', 'OfflineRecognizer.kt', 'OfflineStream.kt', 'OfflineSpeakerDiarization.kt', 'SpeakerEmbeddingExtractorConfig.kt', 'OnlineRecognizer.kt', 'OnlineStream.kt', 'QnnConfig.kt', 'Tts.kt']
    for name in names:
        download(base + name, ROOT / 'android/app/src/main/java/com/k2fsa/sherpa/onnx' / name)
    # Explicitly mirror the same inference assets into the Android app pack.
    import shutil
    assets = ROOT / 'android/app/src/main/assets/models'
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT/'models/sherpa-onnx/sherpa-onnx-streaming-t-one-russian-2025-09-08', assets/'t-one', dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.wav','README*','LICENSE'))
    shutil.copy2(ROOT/'models/diarization/sherpa-onnx-pyannote-segmentation-3-0/model.int8.onnx', assets/'diarization/model.onnx')
    shutil.copy2(ROOT/'models/diarization/wespeaker_en_voxceleb_resnet34.onnx', assets/'diarization/embedding.onnx')
    for voice in ('irina','ruslan'):
        shutil.copytree(ROOT/f'models/tts/vits-piper-ru_RU-{voice}-medium', assets/f'tts/{voice}', dirs_exist_ok=True, ignore=shutil.ignore_patterns('MODEL_CARD','*.json'))
    print('ANDROID_TOOLS_READY', flush=True)

if __name__ == '__main__': main()
