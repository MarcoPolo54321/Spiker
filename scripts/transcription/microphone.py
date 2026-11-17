"""Open a Windows microphone and adapt native input rates to PCM16/16 kHz."""
import audioop
import math


class ResampledCapture:
    def __init__(self, stream, rate, channels):
        self._stream = stream
        self._rate = rate
        self._channels = channels
        self._state = None
        self._pending = bytearray()

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def read(self, frames, exception_on_overflow=True):
        needed = frames * 2
        while len(self._pending) < needed:
            count = max(2, math.ceil((needed - len(self._pending)) / 2 * self._rate / 16000))
            raw = self._stream.read(count, exception_on_overflow=exception_on_overflow)
            if not raw:
                output = bytes(self._pending)
                self._pending.clear()
                return output
            if self._channels == 2:
                left = audioop.tomono(raw, 2, 1, 0)
                right = audioop.tomono(raw, 2, 0, 1)
                raw = left if audioop.rms(left, 2) >= audioop.rms(right, 2) else right
            elif self._channels > 2:
                import numpy as np
                samples = np.frombuffer(raw, dtype="<i2").reshape(-1, self._channels)
                channel = (samples.astype(np.float64) ** 2).mean(axis=0).argmax()
                raw = samples[:, channel].tobytes()
            audio, self._state = audioop.ratecv(raw, 2, 1, self._rate, 16000, self._state)
            self._pending.extend(audio)
        output = bytes(self._pending[:needed])
        del self._pending[:needed]
        return output


def default_input_device(audio):
    """Prefer the Windows WASAPI default without selecting a different endpoint."""
    import pyaudio
    if hasattr(audio, "get_host_api_info_by_type"):
        try:
            wasapi = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            wasapi = None
        if wasapi is not None:
            index = int(wasapi.get("defaultInputDevice", -1))
            if index < 0:
                raise OSError("В Windows нет микрофона по умолчанию. Выберите его в «Параметры → Система → Звук → Ввод».")
            return audio.get_device_info_by_index(index)
    return audio.get_default_input_device_info()


def input_devices(audio):
    """List the default route and physical Windows capture endpoints once."""
    import pyaudio
    try:
        default = default_input_device(audio)
    except OSError:
        default = None
    try:
        host = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
    except (AttributeError, OSError):
        host = None
    result = [("", f"По умолчанию Windows · {default['name']}" if default else "По умолчанию Windows", default)]
    if host is None:
        return result
    names = set()
    for index in range(int(host.get("deviceCount", 0))):
        device = audio.get_device_info_by_host_api_device_index(int(host["index"]), index)
        name = str(device.get("name", "")).strip()
        if not name or not int(device.get("maxInputChannels", 0)) or name.casefold() in names:
            continue
        names.add(name.casefold())
        result.append((name, name, device))
    return result


def open_capture(audio, device=None):
    import pyaudio
    device = default_input_device(audio) if device is None else device
    max_channels = int(device.get("maxInputChannels", 0))
    # Prefer the device's native rate; a successfully opened WASAPI conversion
    # at 16 kHz can still deliver poor or empty audio on some devices.
    for rate in dict.fromkeys((int(device["defaultSampleRate"]), 16000, 48000, 44100)):
        for channels in range(1, min(max_channels, 2) + 1):
            try:
                stream = audio.open(format=pyaudio.paInt16, channels=channels, rate=rate, input=True,
                                    input_device_index=int(device["index"]), frames_per_buffer=rate // 10,
                                    start=False)
                return stream if rate == 16000 and channels == 1 else ResampledCapture(stream, rate, channels)
            except (OSError, ValueError):
                continue
    raise OSError("Не удалось открыть выбранный микрофон. Проверьте вход и доступ к микрофону для классических приложений в параметрах Windows.")
