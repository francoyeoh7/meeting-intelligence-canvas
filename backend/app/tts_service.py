from __future__ import annotations

import base64
import io
import math
import os
import wave
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol

from .contracts import VoicePersona


PERSONA_PREFIX = {
    VoicePersona.OBJECTIVE: "Objective summary.",
    VoicePersona.FACILITATOR: "Facilitator prompt.",
    VoicePersona.EXECUTIVE: "Executive brief.",
}


@dataclass(frozen=True)
class TtsResult:
    audio_base64: str
    engine: str


class SpeechProvider(Protocol):
    def synthesize_base64(self, text: str, persona: VoicePersona) -> TtsResult:
        ...


class CoquiSpeechProvider:
    def __init__(self) -> None:
        self.model_name = os.getenv("TTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC")
        self.device_preference = os.getenv("TTS_DEVICE", "auto").lower()

    @cached_property
    def _coqui(self):  # noqa: ANN202 - optional dependency object
        from TTS.api import TTS

        tts = TTS(self.model_name)
        device = self._resolve_device()
        if hasattr(tts, "to"):
            tts.to(device)
        return tts

    def synthesize_base64(self, text: str, persona: VoicePersona) -> TtsResult:
        spoken_text = self._apply_persona(text, persona)

        try:
            wav_bytes = self._synthesize_with_coqui(spoken_text)
            return TtsResult(audio_base64=base64.b64encode(wav_bytes).decode("ascii"), engine="coqui")
        except Exception as exc:  # noqa: BLE001 - convert optional engine failures to clean app errors
            message = f"TTS synthesis failed: {exc.__class__.__name__}: {exc}"
            raise RuntimeError(message) from exc

    def _apply_persona(self, text: str, persona: VoicePersona) -> str:
        prefix = PERSONA_PREFIX.get(persona, PERSONA_PREFIX[VoicePersona.OBJECTIVE])
        return f"{prefix} {text}"

    def _resolve_device(self) -> str:
        if self.device_preference in {"cpu", "cuda"}:
            if self.device_preference == "cuda" and not cuda_available():
                raise RuntimeError("CUDA was requested but is not available. Set TTS_DEVICE=cpu or install a matching PyTorch CUDA wheel.")
            return self.device_preference
        return "cuda" if cuda_available() else "cpu"

    def _synthesize_with_coqui(self, text: str) -> bytes:
        buffer = io.BytesIO()
        wav = self._coqui.tts(text=text)
        write_wav(buffer, wav)
        return buffer.getvalue()


class FallbackToneProvider:
    def synthesize_base64(self, text: str, persona: VoicePersona) -> TtsResult:
        return TtsResult(audio_base64=base64.b64encode(generate_tone_wav()).decode("ascii"), engine="fallback-tone")


class TtsService:
    def __init__(self) -> None:
        self.enabled = os.getenv("TTS_ENABLED", "false").lower() == "true"
        self.provider: SpeechProvider = CoquiSpeechProvider() if self.enabled else FallbackToneProvider()

    def synthesize_base64(self, text: str, persona: VoicePersona) -> TtsResult:
        return self.provider.synthesize_base64(text, persona)


def cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - torch may be absent or partially installed
        return False


def write_wav(buffer: io.BytesIO, samples: list[float], sample_rate: int = 22050) -> None:
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            clipped = max(-1.0, min(1.0, float(sample)))
            frames.extend(int(clipped * 32767).to_bytes(2, byteorder="little", signed=True))
        wav_file.writeframes(bytes(frames))


def generate_tone_wav(duration_seconds: float = 0.6, sample_rate: int = 22050) -> bytes:
    buffer = io.BytesIO()
    samples: list[float] = []
    total = int(duration_seconds * sample_rate)
    for index in range(total):
        envelope = min(1.0, index / 1200, (total - index) / 1200)
        samples.append(math.sin(2 * math.pi * 220 * index / sample_rate) * 0.18 * envelope)
    write_wav(buffer, samples, sample_rate)
    return buffer.getvalue()
