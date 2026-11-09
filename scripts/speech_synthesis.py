"""Russian offline speech, generated in bounded chunks with cancellation."""
from pathlib import Path
import re
import wave
from html import unescape
import numpy as np
from model_paths import native_model_path

VOICES = {'irina': 'Ирина · женский', 'ruslan': 'Руслан · мужской'}

def clean_markdown_for_speech(text):
    """Remove Markdown notation while keeping the words intended for narration."""
    source = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    source = re.sub(r"(?m)^\s*(```+|~~~+)[^\n]*\n?", "", source)
    source = re.sub(r"(?m)^\s*(?:[-*_]\s*){3,}$", "", source)
    output = []
    for raw_line in source.split("\n"):
        line = raw_line.strip()
        if not line:
            output.append("")
            continue
        if re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*", line):
            continue
        line = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", line)
        line = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", line)
        line = re.sub(r"^\s*>+\s?", "", line)
        line = re.sub(r"^\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?", "", line)
        line = re.sub(r"(?<!\\)(\*\*|__|~~)(.+?)(?<!\\)\1", r"\2", line)
        line = re.sub(r"(?<!\w)([*_])([^*_\n]+)(?<!\\)\1(?!\w)", r"\2", line)
        line = re.sub(r"(?<!\\)`{1,3}", "", line)
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>])", r"\1", line)
        line = re.sub(r"https?://\S+", "", line)
        line = unescape(line).replace("|", ", ")
        line = re.sub(r"\s+", " ", line).strip(" \t,;|")
        if line:
            output.append(line)
    return "\n".join(output).strip()

def synthesize(text, root, destination, voice='irina', speed=1.0, cancelled=None, progress=None, speaker_voices=None):
    import sherpa_onnx as sherpa
    if voice not in VOICES:
        raise ValueError('Неизвестный диктор.')
    text = clean_markdown_for_speech(text)
    if not text:
        raise ValueError('Введите текст для озвучки.')
    engines = {}
    def get_engine(engine_voice):
        if engine_voice in engines:
            return engines[engine_voice]
        folder = Path(root) / 'models/tts' / f'vits-piper-ru_RU-{engine_voice}-medium'
        model = folder / f'ru_RU-{engine_voice}-medium.onnx'
        if not model.is_file():
            raise FileNotFoundError(f'Не установлена модель {VOICES[engine_voice]}: {folder}')
        config = sherpa.OfflineTtsConfig(model=sherpa.OfflineTtsModelConfig(
            vits=sherpa.OfflineTtsVitsModelConfig(model=native_model_path(model), tokens=native_model_path(folder / 'tokens.txt'),
                                               data_dir=native_model_path(folder / 'espeak-ng-data')),
            num_threads=2), max_num_sentences=1)
        if not config.validate():
            raise RuntimeError(f'Модель {VOICES[engine_voice]} неполна.')
        engines[engine_voice] = sherpa.OfflineTts(config)
        return engines[engine_voice]
    # Preserve diarization labels and switch voice per speaker. Input may use
    # "Спикер 1: ..." / "Спикер 2: ..." on separate lines; unlabelled prose
    # continues with the currently selected/default voice.
    voice_map = {'1': voice, '2': ('ruslan' if voice == 'irina' else 'irina')}
    if speaker_voices:
        voice_map.update({str(key): value for key, value in speaker_voices.items() if value in VOICES})
    labeled = re.compile(r'^\s*(?:спикер|speaker)\s*(\d+)\s*:\s*(.*)$', re.IGNORECASE)
    units = []
    active_voice = voice
    for line in text.splitlines() or [text]:
        match = labeled.match(line)
        if match:
            active_voice = voice_map.get(match.group(1), voice)
            line = match.group(2)
        if line.strip():
            units.append((active_voice, line.strip()))
    chunks = []
    for unit_voice, sentence in units:
        # Prefer sentence boundaries for more natural pauses and prosody.
        pieces = re.split(r'(?<=[.!?…])\s+', sentence)
        for piece in pieces:
            words = re.findall(r'\S+\s*', piece)
            chunk = ''
            for word in words:
                if len(chunk) + len(word) > 240 and chunk:
                    chunks.append((unit_voice, chunk.strip())); chunk = ''
                chunk += word
            if chunk.strip():
                chunks.append((unit_voice, chunk.strip()))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.partial.wav')
    try:
        base_engine = get_engine(voice)
        with wave.open(str(temporary), 'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(base_engine.sample_rate)
            for index, (chunk_voice, chunk) in enumerate(chunks):
                if cancelled and cancelled():
                    raise InterruptedError('Озвучка отменена.')
                engine = get_engine(chunk_voice)
                audio = engine.generate(chunk, sid=0, speed=max(0.6, min(1.6, speed)))
                if cancelled and cancelled():
                    raise InterruptedError('Озвучка отменена.')
                out.writeframes((np.clip(audio.samples, -1, 1) * 32767).astype('<i2').tobytes())
                if progress:
                    progress((index + 1) * 100 // len(chunks))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
