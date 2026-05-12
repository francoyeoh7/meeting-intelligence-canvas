# Meeting Intelligence Canvas

Tencent Meeting-ready assistant for turning realtime speech transcripts into live logic diagrams, context-aware command updates, and role-aware narration.

It is designed as a voice-first meeting canvas: the product listens to meeting transcription events, resolves contextual phrases such as "这里拆成两个分支", updates a live React Flow diagram, and generates a concise narration script with optional Coqui TTS.

## What It Does

- Receives local WebSocket commands and Tencent Meeting realtime transcription webhook events.
- Maintains rolling meeting context, active topic, selected graph target, and pending commands.
- Resolves pronouns such as "这里" from selected node or recent meeting topic.
- Asks for clarification when a command is ambiguous instead of guessing.
- Renders a dark React Flow canvas with voice source status, live transcript, active target, clarification controls, and narration waveform.
- Treats local demo buttons as simulated ASR events; the product surface is not a chatbot input.
- Plays fallback WAV narration by default and can enable Coqui TTS in a Python 3.10/3.11 environment.
- Supports Chinese / English output language switching that changes generated diagram labels and narration scripts.

## Architecture

```text
Tencent Meeting ASR / simulated voice event
          ↓
FastAPI webhook + WebSocket transport
          ↓
MeetingContextStore + GraphCommandEngine
          ↓
React Flow canvas + clarification UI + TTS waveform
```

Backend modules:

- `app/tencent.py` normalizes Tencent realtime transcription push events.
- `app/context_store.py` keeps rolling transcript, active topics, selected targets, and pending commands.
- `app/graph_engine.py` resolves contextual commands and applies graph updates.
- `app/parser.py` extracts branch logic into graph JSON.
- `app/tts_service.py` provides Coqui TTS with a safe fallback WAV provider.

Frontend modules:

- `src/App.tsx` renders the voice-first meeting canvas.
- `src/types.ts` mirrors backend event contracts.

## Backend

Use Python 3.10 or 3.11. Coqui `TTS==0.22.0` requires Python `<3.12`.

```powershell
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The default `.env.example` uses `TTS_ENABLED=false`, which returns a short fallback WAV tone so the full WebSocket flow works before Coqui models are installed.

To run a CPU Coqui smoke test after dependencies are installed:

```powershell
python -m pip install -r requirements-tts.txt
$env:TTS_ENABLED="true"
$env:TTS_DEVICE="cpu"
python smoke_tts.py
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The local buttons simulate incoming ASR events for demos. They are not a chatbot input surface.

## Test

Backend:

```bash
cd backend
python -m pytest tests/test_context_flow.py -q
```

Frontend:

```bash
cd frontend
npm audit --audit-level=moderate
npm run build
```

## Tencent Meeting Webhook Shape

Post Tencent realtime transcription events to:

```text
POST /webhooks/tencent/asr
```

If `TENCENT_WEBHOOK_SECRET` is set, include the same value in:

```text
X-Meeting-Diagram-Secret: <secret>
```

Expected event name: `meeting.asr-push`.

Minimal payload:

```json
{
  "event": "meeting.asr-push",
  "payload": {
    "meeting_info": { "meeting_id": "meeting-1", "meeting_code": "123456" },
    "speech_time": 1710000000123,
    "speaker": { "userid": "speaker-1", "name": "Alice" },
    "content": { "text": "这里拆成两个分支", "language": "zh-CN" },
    "sid": "sentence-1"
  }
}
```

## Commercial Boundaries

This MVP is ready for internal enterprise-app validation. For marketplace launch, add Tencent OAuth installation, tenant management, persistent storage, audit logs, webhook signature verification against Tencent's production signing rules, and legal review for transcript handling.
