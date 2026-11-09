"""Integration checks on public/synthetic audio only. No user transcripts are read."""
import json
from pathlib import Path
import subprocess
import time
import wave
import imageio_ffmpeg
from speech_synthesis import synthesize
from transcription.onnx_diarization import diarize
from transcription.speaker_diarization import assign_speakers_to_segments
from transcription.live_streaming import create_t_one_recognizer, SherpaStreamingSession, resolve_t_one_model

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation_samples'
report = {}
def pcm(source, output):
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(source), '-ac', '1', '-ar', '16000', str(output)], check=True, capture_output=True)

def main():
    for voice in ('irina', 'ruslan'):
        path = OUT / (voice + '.wav')
        if not path.exists(): synthesize('Здравствуйте! Это проверка русской озвучки. Сегодня мы обсуждаем работу приложения Спикер.', ROOT, path, voice)
        pcm(path, OUT / (voice + '-16k.wav'))
    session = SherpaStreamingSession(create_t_one_recognizer(resolve_t_one_model(ROOT)))
    with wave.open(str(OUT / 'irina-16k.wav'), 'rb') as stream:
        while data := stream.readframes(1600): session.feed_pcm16(data)
    report['dictation_control_audio'] = session.finish()
    print('Dictation:', report['dictation_control_audio'], flush=True)
    turns = diarize(OUT / 'two-speakers.wav', ROOT)
    report['public_two_speakers'] = {'detected': len({t[2] for t in turns}), 'turns': turns}
    print('Public speakers:', report['public_two_speakers']['detected'], flush=True)
    timeline, offset = [], 0.0
    with wave.open(str(OUT / 'russian-dialogue.wav'), 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000)
        for voice in ('irina', 'ruslan', 'irina', 'ruslan'):
            with wave.open(str(OUT / (voice + '-16k.wav')), 'rb') as item:
                samples = item.readframes(item.getnframes())
            duration = len(samples) / 32000
            timeline.append((offset, offset + duration, voice))
            out.writeframes(samples); out.writeframes(b'\0' * 16000)
            offset += duration + 0.5
    turns = diarize(OUT / 'russian-dialogue.wav', ROOT)
    labels=[]
    for start,end,voice in timeline:
        counts={}
        for a,b,label in turns:
            counts[label]=counts.get(label,0)+max(0,min(end,b)-max(start,a))
        labels.append(max(counts,key=counts.get) if counts else '')
    report['synthetic_dialogue']={'detected':len({t[2] for t in turns}), 'voice_labels':labels, 'consistent':len(labels)==4 and labels[0]==labels[2] and labels[1]==labels[3] and labels[0]!=labels[1], 'turns':turns}
    print('Russian synthetic:', report['synthetic_dialogue'], flush=True)
    from faster_whisper import WhisperModel
    model=WhisperModel(str(ROOT/'models/faster-whisper/medium'),device='cpu',compute_type='int8',cpu_threads=4)
    start=time.monotonic()
    result,info=model.transcribe(str(OUT/'russian-dialogue.wav'),language='ru',word_timestamps=True,vad_filter=True)
    segments=[{'start':s.start,'end':s.end,'text':s.text,'words':[{'start':w.start,'end':w.end,'word':w.word} for w in s.words or []]} for s in result]
    enriched,stats=assign_speakers_to_segments(segments,turns)
    report['medium']={'seconds':round(time.monotonic()-start,2),'segments':enriched,'stats':stats}
    (OUT/'upgrade-integration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert report['dictation_control_audio'], 'Dictation did not produce text'
    assert report['public_two_speakers']['detected']==2, 'Public sample speaker count mismatch'
    assert report['synthetic_dialogue']['consistent'], 'Voice labels are inconsistent'
    assert len({s.get('speaker_id') for s in enriched if s.get('speaker_id')})==2, 'Text attribution mismatch'
    print('INTEGRATION PASS',flush=True)

if __name__=='__main__':main()
