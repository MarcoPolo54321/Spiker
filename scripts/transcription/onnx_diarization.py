"""Offline segmentation + voice embeddings; shared ONNX models also run on Android."""
from pathlib import Path
import wave
from model_paths import native_model_path


def model_files(root):
    base = Path(root) / 'models' / 'diarization'
    return (base / 'sherpa-onnx-pyannote-segmentation-3-0/model.onnx',
            base / 'wespeaker_en_voxceleb_resnet34.onnx')


def available(root):
    if not all(p.is_file() for p in model_files(root)):
        return False
    try:
        import sherpa_onnx
        return hasattr(sherpa_onnx, 'OfflineSpeakerDiarization')
    except ImportError:
        return False


def diarize(audio_path, root, minimum=0, maximum=0, progress=None, cancelled=None):
    import numpy as np
    import sherpa_onnx as sherpa
    minimum, maximum = int(minimum or 0), int(maximum or 0)
    if minimum and maximum and minimum > maximum:
        raise ValueError('Минимальное число участников больше максимального.')
    segmentation, embedding = model_files(root)
    with wave.open(str(audio_path), 'rb') as stream:
        if stream.getnchannels() != 1 or stream.getsampwidth() != 2 or stream.getframerate() != 16000:
            raise ValueError('Для разделения требуется WAV, mono, PCM16, 16000 Гц.')
        audio = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype(np.float32) / 32768
    config = sherpa.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa.OfflineSpeakerSegmentationPyannoteModelConfig(model=native_model_path(segmentation)),
            num_threads=2),
        embedding=sherpa.SpeakerEmbeddingExtractorConfig(model=native_model_path(embedding), num_threads=2),
        clustering=sherpa.FastClusteringConfig(num_clusters=minimum if minimum == maximum and minimum else -1, threshold=0.5),
        min_duration_on=0.2, min_duration_off=0.3)
    if not config.validate():
        raise RuntimeError('Не удалось проверить модели разделения голосов.')
    engine = sherpa.OfflineSpeakerDiarization(config)
    def callback(done, total):
        if cancelled and cancelled():
            return 1
        if progress:
            progress(f'Разделение голосов: {done * 100 // max(total, 1)}%')
        return 0
    if cancelled and cancelled():
        raise InterruptedError('Разделение отменено.')
    result = engine.process(audio, callback=callback).sort_by_start_time()
    if cancelled and cancelled():
        raise InterruptedError('Разделение отменено.')
    count = len({r.speaker for r in result})
    constrained = max(minimum or 1, min(maximum or max(count, 1), count))
    if result and count != constrained:
        config.clustering.num_clusters = constrained
        engine = sherpa.OfflineSpeakerDiarization(config)
        result = engine.process(audio, callback=callback).sort_by_start_time()
    if cancelled and cancelled():
        raise InterruptedError('Разделение отменено.')
    if not result:
        raise RuntimeError('В записи не обнаружена речь для разделения голосов.')
    return [(float(r.start), float(r.end), f'voice_{r.speaker}') for r in result]
