"""Native Windows capture using the actual Qt audio endpoint and its mix format."""
from __future__ import annotations

import time
import audioop

from PySide6.QtCore import QEventLoop
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSource, QMediaDevices

from transcription.microphone import ResampledCapture, default_input_device, input_devices, open_capture


def capture_devices():
    """Use system endpoint IDs, including distinct devices with the same name."""
    default = QMediaDevices.defaultAudioInput()
    choices = [("", f"По умолчанию Windows · {default.description()}" if not default.isNull()
                else "По умолчанию Windows")]
    choices.extend((bytes(device.id()).hex(), device.description()) for device in QMediaDevices.audioInputs())
    return choices


def _as_pcm16(data, sample_format):
    if sample_format == QAudioFormat.SampleFormat.Float:
        import numpy as np
        amplitudes = np.frombuffer(data, dtype="<f4")
        amplitudes = np.nan_to_num(amplitudes, nan=0.0, posinf=1.0, neginf=-1.0)
        return np.rint(np.clip(amplitudes, -1.0, 32767 / 32768) * 32768).astype("<i2").tobytes()
    if sample_format == QAudioFormat.SampleFormat.UInt8:
        return audioop.lin2lin(audioop.bias(data, 1, -128), 1, 2)
    if sample_format == QAudioFormat.SampleFormat.Int32:
        return audioop.lin2lin(data, 4, 2)
    if sample_format == QAudioFormat.SampleFormat.Int16:
        return data
    raise OSError("Формат микрофона не поддерживается.")


class _QtNativeInput:
    def __init__(self, device, stopped):
        self.name = device.description()
        self._stopped = stopped
        self._format = fmt = device.preferredFormat()
        if not fmt.isValid():
            raise OSError("Windows не сообщил рабочий формат микрофона.")
        self._loop = QEventLoop()
        self._source = QAudioSource(device, fmt)
        self._source.setBufferSize(fmt.bytesForDuration(400_000))
        self._io = self._source.start()
        if self._io is None or self._source.error() != QAudio.Error.NoError:
            self.close()
            raise OSError("Windows не открыл выбранный аудиовход через Qt.")

    def read(self, frames, **_):
        size = self._format.bytesForFrames(frames)
        deadline = time.monotonic() + 1.8
        while not self._stopped():
            self._loop.processEvents()
            if self._source.error() != QAudio.Error.NoError:
                raise OSError(f"Захват звука прервался: {self._source.error().name}.")
            if self._io.bytesAvailable() >= size:
                data = bytes(self._io.read(size))
                if data:
                    return _as_pcm16(data, self._format.sampleFormat())
            if time.monotonic() >= deadline:
                raise OSError("Windows не передаёт аудиоданные выбранного входа.")
            time.sleep(0.008)
        return b""

    def close(self):
        self._source.stop()
        self._io = None


class _PortAudioInput:
    def __init__(self, endpoint_name, use_default):
        import pyaudio
        self._audio = pyaudio.PyAudio()
        try:
            device = default_input_device(self._audio) if use_default else next(
                (item for key, _, item in input_devices(self._audio)
                 if key and key.casefold() == endpoint_name.casefold()), None
            )
            if device is None:
                raise OSError("Выбранный микрофон не найден в резервном аудиодрайвере.")
            self._stream = open_capture(self._audio, device)
            self._stream.start_stream()
        except Exception:
            stream = getattr(self, "_stream", None)
            if stream is not None:
                stream.close()
            self._audio.terminate()
            raise
        self.name = device["name"]

    def read(self, frames, **kwargs):
        return self._stream.read(frames, **kwargs)

    def close(self):
        try:
            if self._stream.is_active():
                self._stream.stop_stream()
            self._stream.close()
        finally:
            self._audio.terminate()


class WindowsCapture:
    """Read normalized PCM16; only fall back to the same endpoint before first audio."""
    def __init__(self, endpoint_id, stopped, logger):
        self._stopped = stopped
        self._logger = logger
        self._default = not endpoint_id
        device = QMediaDevices.defaultAudioInput() if self._default else next(
            (item for item in QMediaDevices.audioInputs() if bytes(item.id()).hex() == endpoint_id), None
        )
        if device is None or device.isNull():
            raise OSError("Вход не найден. Обновите список микрофонов или назначьте вход в параметрах звука Windows.")
        self._name = device.description()
        self._delivered = False
        self._capture = None
        self.backend = "Windows / Qt"
        try:
            native = _QtNativeInput(device, stopped)
            fmt = device.preferredFormat()
            self._capture = ResampledCapture(native, fmt.sampleRate(), fmt.channelCount())
            logger.info("Input opened: implementation=%s, rate=%d, channels=%d, format=%s",
                        self.backend, fmt.sampleRate(), fmt.channelCount(), fmt.sampleFormat().name)
        except OSError:
            logger.warning("Could not open Qt capture, trying PortAudio", exc_info=True)
            self._use_portaudio()

    def _use_portaudio(self):
        if self._capture is not None:
            self._capture.close()
            self._capture = None
        self._capture = _PortAudioInput(self._name, self._default)
        self.backend = "Windows / PortAudio"
        self._logger.info("Input opened: implementation=%s", self.backend)

    def read(self, frames):
        try:
            data = self._capture.read(frames, exception_on_overflow=False)
        except OSError:
            if self._stopped() or self._delivered or self.backend.endswith("PortAudio"):
                raise
            self._logger.warning("Qt input gave no audio, trying PortAudio", exc_info=True)
            self._use_portaudio()
            data = self._capture.read(frames, exception_on_overflow=False)
        self._delivered = self._delivered or bool(data)
        return data

    def close(self):
        if self._capture is not None:
            self._capture.close()
