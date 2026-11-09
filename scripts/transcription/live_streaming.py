"""Optional real-time Russian speech recognition using sherpa-onnx T-one CTC.

The live path is intentionally independent from Whisper file transcription. It consumes
small PCM16 microphone frames, keeps one online decoder state per recording, publishes
interim hypotheses, and commits utterances when endpoint detection fires.
"""
from __future__ import annotations

import logging
from pathlib import Path

from model_paths import native_model_path
from app_paths import get_user_data_root

LOGGER = logging.getLogger("processing.live_dictation")
DEFAULT_MODEL_DIR = "sherpa-onnx-streaming-t-one-russian-2025-09-08"
MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-streaming-t-one-russian-2025-09-08.tar.bz2"
)


def resolve_t_one_model(project_root: Path, configured_path: str = "") -> Path | None:
    """Find a previously downloaded T-one model without performing network access."""
    root = Path(project_root)
    user_models = get_user_data_root(root) / "models"
    candidates: list[Path] = []
    if configured_path:
        configured = Path(configured_path).expanduser()
        candidates.append(configured)
    candidates.extend([
        root / "models" / "sherpa-onnx" / DEFAULT_MODEL_DIR,
        root / "models" / "live" / DEFAULT_MODEL_DIR,
        root / "models" / DEFAULT_MODEL_DIR,
        user_models / "sherpa-onnx" / DEFAULT_MODEL_DIR,
        user_models / "live" / DEFAULT_MODEL_DIR,
        user_models / DEFAULT_MODEL_DIR,
    ])
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
            if candidate.is_file():
                candidate = candidate.parent
            if (candidate / "model.onnx").is_file() and (candidate / "tokens.txt").is_file():
                return candidate
        except OSError:
            continue
    for search_root in (user_models, root / "models"):
        if not search_root.is_dir():
            continue
        try:
            for model_file in search_root.rglob("model.onnx"):
                parent = model_file.parent
                if (parent / "tokens.txt").is_file() and "t-one" in parent.name.lower():
                    return parent.resolve()
        except OSError:
            pass
    return None


def is_sherpa_available() -> bool:
    try:
        import sherpa_onnx  # noqa: F401
        return hasattr(sherpa_onnx, "OnlineRecognizer")
    except Exception:
        return False


def create_t_one_recognizer(model_dir: Path, num_threads: int = 2):
    """Load the locally installed streaming recognizer. No model is downloaded here."""
    model_dir = Path(model_dir).expanduser().resolve()
    model = model_dir / "model.onnx"
    tokens = model_dir / "tokens.txt"
    if not model.is_file() or not tokens.is_file():
        raise FileNotFoundError(
            f"Модель T-one не найдена в {model_dir}. Запустите Install_Live_Dictation.bat."
        )
    try:
        import sherpa_onnx
    except Exception as exc:
        raise RuntimeError(
            "sherpa-onnx не установлен. Запустите Install_Live_Dictation.bat из папки СПИКЕР."
        ) from exc
    recognizer_type = getattr(sherpa_onnx, "OnlineRecognizer", None)
    if recognizer_type is None or not hasattr(recognizer_type, "from_t_one_ctc"):
        raise RuntimeError(
            "Установленная версия sherpa-onnx не содержит потоковый T-one CTC API. "
            "Переустановите компонент командой Install_Live_Dictation.bat."
        )
    try:
        # T-one was trained for an 8 kHz feature rate. sherpa-onnx accepts 16 kHz
        # microphone samples and performs the required internal resampling.
        return recognizer_type.from_t_one_ctc(
            model=native_model_path(model),
            tokens=native_model_path(tokens),
            num_threads=max(1, min(8, int(num_threads or 2))),
            sample_rate=8000,
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=1.6,
            rule2_min_trailing_silence=0.75,
            rule3_min_utterance_length=20.0,
            decoding_method="greedy_search",
            provider="cpu",
        )
    except Exception as exc:
        raise RuntimeError(f"Не удалось загрузить потоковую модель T-one: {exc}") from exc


class SherpaStreamingSession:
    """Stateful adapter around sherpa-onnx's OnlineRecognizer API."""

    def __init__(self, recognizer, sample_rate: int = 16000):
        try:
            import numpy as np
        except Exception as exc:
            raise RuntimeError("Для потоковой диктовки требуется NumPy (устанавливается вместе с sherpa-onnx).") from exc
        self.np = np
        self.recognizer = recognizer
        self.sample_rate = int(sample_rate)
        self.stream = recognizer.create_stream()
        self.committed: list[str] = []
        self.last_partial = ""
        # T-one examples use a short left pad so the first phoneme is not clipped
        # when microphone capture starts immediately after the model is ready.
        self.stream.accept_waveform(
            self.sample_rate,
            self.np.zeros(int(0.3 * self.sample_rate), dtype=self.np.float32),
        )

    @property
    def committed_text(self) -> str:
        return self._join(self.committed)

    @property
    def partial_text(self) -> str:
        return self.last_partial

    def _decode(self) -> None:
        while self.recognizer.is_ready(self.stream):
            self.recognizer.decode_stream(self.stream)

    def _result_text(self) -> str:
        getter = getattr(self.recognizer, "get_result_all", None) or getattr(self.recognizer, "get_result", None)
        if getter is None:
            raise RuntimeError("В sherpa-onnx отсутствует метод получения результата распознавания.")
        result = getter(self.stream)
        return str(getattr(result, "text", "") or "").strip()

    @staticmethod
    def _join(parts: list[str], partial: str = "") -> str:
        return " ".join(part.strip() for part in [*parts, partial] if part and part.strip()).strip()

    def feed_pcm16(self, pcm: bytes) -> tuple[str, bool]:
        """Feed one PCM16 mono frame. Return (full_preview, endpoint_committed)."""
        if not pcm:
            return self._join(self.committed, self.last_partial), False
        usable = len(pcm) - (len(pcm) % 2)
        if usable <= 0:
            return self._join(self.committed, self.last_partial), False
        samples = self.np.frombuffer(pcm[:usable], dtype=self.np.int16).astype(self.np.float32) / 32768.0
        self.stream.accept_waveform(self.sample_rate, samples)
        self._decode()
        partial = self._result_text()
        endpoint = bool(self.recognizer.is_endpoint(self.stream))
        if endpoint:
            if partial:
                self.committed.append(partial)
            self.last_partial = ""
            self.recognizer.reset(self.stream)
            return self._join(self.committed), True
        self.last_partial = partial
        return self._join(self.committed, partial), False

    def finish(self) -> str:
        """Flush the last utterance at stop without waiting for the long silence endpoint."""
        # T-one's reference examples use about 0.6 s of tail padding before
        # input_finished(); this helps the final syllable flush at manual stop.
        tail = self.np.zeros(int(0.66 * self.sample_rate), dtype=self.np.float32)
        self.stream.accept_waveform(self.sample_rate, tail)
        self.stream.input_finished()
        self._decode()
        final_text = self._result_text()
        if final_text:
            # On most sherpa models get_result_all returns the full current utterance.
            # If it equals the latest interim hypothesis, append it once; otherwise it
            # is still the authoritative result for this current stream.
            self.last_partial = final_text
        if self.last_partial:
            self.committed.append(self.last_partial)
        self.last_partial = ""
        return self._join(self.committed)


def merge_live_text(committed: str, partial: str) -> str:
    """Render stable and mutable text without modifying either source value."""
    return "\n".join(part for part in (str(committed or "").strip(), str(partial or "").strip()) if part)
