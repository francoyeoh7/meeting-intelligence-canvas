from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    os.environ.setdefault("TTS_ENABLED", "true")
    os.environ.setdefault("TTS_DEVICE", "cpu")

    from app.contracts import VoicePersona
    from app.tts_service import TtsService

    result = TtsService().synthesize_base64(
        "The logic splits into approval and rejection branches.",
        VoicePersona.OBJECTIVE,
    )
    output_path = Path("smoke-output.wav")
    output_path.write_bytes(__import__("base64").b64decode(result.audio_base64))
    print(f"ok: generated {output_path} with engine={result.engine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
