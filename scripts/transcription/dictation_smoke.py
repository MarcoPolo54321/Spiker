"""Verify a short reference WAV through the actual dictation page and local decoders."""
from __future__ import annotations

import logging
import time
import wave


def verify_dictation_fixture(app, page, fixture, expected):
    """Exercise the GUI delivery and stop lifecycle, replacing only the audio source."""
    from transcription import qt_microphone

    with wave.open(str(fixture), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError("Dictation fixture must be mono PCM16 at 16 kHz.")
        if not 16000 <= audio.getnframes() <= 16000 * 60:
            raise ValueError("Dictation fixture must be between one and sixty seconds.")
        pcm = audio.readframes(audio.getnframes())
    if not expected.strip():
        raise ValueError("A known word from the dictation fixture is required.")

    class ReferenceCapture:
        def __init__(self, endpoint, stopped, logger):
            self.stopped = stopped
            self.offset = 0

        def read(self, frames):
            time.sleep(0.04)  # Leave time for the GUI to display a streaming hypothesis.
            if self.stopped():
                return b""
            end = self.offset + frames * 2
            block = pcm[self.offset:end]
            self.offset = end
            return block.ljust(frames * 2, b"\x00")

        def close(self):
            pass

    def until(condition, timeout=45):
        deadline = time.monotonic() + timeout
        while not condition():
            app.processEvents()
            if time.monotonic() > deadline:
                raise RuntimeError(f"{page.live_engine}: {page.ui.lineEdit_words_to_dict_info.text()}")
            time.sleep(0.01)
        app.processEvents()

    loader = page.load_model.__func__.__globals__
    original_loader = loader["load_settings"]
    original_capture = qt_microphone.WindowsCapture
    try:
        qt_microphone.WindowsCapture = ReferenceCapture
        for engine in ("vosk", "sherpa", "whisper"):
            loader["load_settings"] = lambda root, engine=engine: {
                **original_loader(root), "dictation_engine": engine
            }
            editor = page.ui.textEdit_field_to_text_from_audio
            button = page.ui.pushButton_record_start
            button.click()
            until(lambda: page.is_recording and expected.casefold() in editor.toPlainText().casefold())
            button.click()
            until(lambda: not page.is_recording and button.isEnabled())
            if expected.casefold() not in editor.toPlainText().casefold():
                raise RuntimeError(f"{engine} dropped already displayed words when stopped.")
            logging.getLogger("startup").info("Dictation fixture appeared in editor live and after stop: %s", engine)
    finally:
        if page.is_recording or page.whisper_worker is not None:
            page.abort_live_dictation()
            until(lambda: page.whisper_worker is None, 12)
        loader["load_settings"] = original_loader
        qt_microphone.WindowsCapture = original_capture
