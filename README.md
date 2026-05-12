# Meeting Intelligence Canvas

Voice-first meeting canvas for turning real-time meeting transcripts into live logic diagrams and role-aware narration.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat-square)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?style=flat-square)](https://www.typescriptlang.org/)
[![Coqui TTS](https://img.shields.io/badge/Coqui_TTS-optional-7C3AED?style=flat-square)](https://github.com/coqui-ai/TTS)

Meeting Intelligence Canvas is a commercial MVP for a Tencent Meeting-ready assistant. It listens to meeting transcription events, understands contextual commands such as "这里拆成两个分支", updates a live React Flow diagram, asks for clarification when the target is ambiguous, and generates a concise narration script with optional Coqui TTS.

It is not a chatbot. The primary interface is a meeting voice stream, a live transcript, and an interactive canvas.

## Highlights

- **Voice-first workflow**: ingest Tencent Meeting real-time transcription webhooks or local simulated ASR events.
- **Context-aware commands**: resolve "here / 这里 / this" from selected nodes, recent meeting topics, and graph state.
- **Safe clarification**: ask the user to confirm the target instead of guessing when context is ambiguous.
- **Live diagramming**: render branch logic and decision flows with React Flow.
- **Narration layer**: generate concise narration scripts and play fallback WAV or Coqui TTS audio.
- **Bilingual output**: switch Chinese / English output and change generated graph labels plus narration language.
- **Commercial plugin shape**: backend webhook, WebSocket event bus, dark meeting-panel UI, and Tencent Meeting extension-ready surface.

## Demo Flow

1. Tencent Meeting ASR sends a transcript event, for example: "我们当前讨论的是预算审批流程。"
2. The context store records the active topic as "预算审批流程".
3. A later utterance says: "这里拆成两个分支。"
4. The graph engine resolves "这里" to the active topic.
5. The canvas generates a branch diagram.
6. The narration script is generated in the selected output language.

If the target cannot be resolved, the UI shows a clarification card instead of changing the graph.

## Architecture

```text
Tencent Meeting ASR webhook
or local simulated voice event
          |
          v
FastAPI transport layer
  - REST webhook
  - WebSocket event stream
          |
          v
Meeting intelligence layer
  - MeetingContextStore
  - GraphCommandEngine
  - deterministic parser
          |
          v
React meeting canvas
  - live transcript
  - active target
  - clarification flow
  - React Flow diagram
  - narration waveform
```

## Repository Structure

```text
backend/
  app/
    context_store.py     # rolling transcript, topics, selected target, pending commands
    contracts.py         # Pydantic event and graph contracts
    graph_engine.py      # context resolution and graph command application
    main.py              # FastAPI app, webhook, WebSocket session loop
    parser.py            # deterministic transcript-to-graph parser
    tencent.py           # Tencent Meeting ASR push normalization
    tts_service.py       # Coqui provider and fallback WAV provider
  tests/
    test_context_flow.py # context resolution, clarification, language behavior

frontend/
  src/
    App.tsx              # voice-first meeting canvas UI
    types.ts             # frontend event contracts
```

## Quick Start

### Backend

Use Python 3.10 or 3.11 for Coqui TTS compatibility. The base backend can also run without Coqui.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The local demo buttons simulate incoming ASR events. They exist for development only; the intended product surface is the meeting transcription stream.

## Tencent Meeting Integration

Configure Tencent Meeting real-time transcription push events to call:

```text
POST /webhooks/tencent/asr
```

If `TENCENT_WEBHOOK_SECRET` is set, include:

```text
X-Meeting-Diagram-Secret: <secret>
```

Expected event name:

```text
meeting.asr-push
```

Minimal payload:

```json
{
  "event": "meeting.asr-push",
  "payload": {
    "meeting_info": {
      "meeting_id": "meeting-1",
      "meeting_code": "123456"
    },
    "speech_time": 1710000000123,
    "speaker": {
      "userid": "speaker-1",
      "name": "Alice"
    },
    "content": {
      "text": "这里拆成两个分支",
      "language": "zh-CN"
    },
    "sid": "sentence-1"
  }
}
```

The backend normalizes this event into an internal transcript item, updates meeting context, and emits diagram or clarification events through WebSocket.

## Coqui TTS

The app starts with `TTS_ENABLED=false` and uses a short fallback WAV tone. This keeps the full meeting-to-canvas flow available even before model dependencies are installed.

To enable Coqui:

```bash
cd backend
python -m pip install -r requirements-tts.txt
export TTS_ENABLED=true
export TTS_DEVICE=cpu
python smoke_tts.py
```

Windows PowerShell:

```powershell
cd backend
python -m pip install -r requirements-tts.txt
$env:TTS_ENABLED="true"
$env:TTS_DEVICE="cpu"
python smoke_tts.py
```

`TTS==0.22.0` requires Python `>=3.9,<3.12`. Use Python 3.10 or 3.11 for the Coqui path.

## WebSocket Events

Client to server:

```json
{
  "type": "meeting_text",
  "meetingId": "local-demo",
  "speakerName": "Host",
  "text": "这里拆成两个分支",
  "persona": "objective",
  "language": "zh"
}
```

Server diagram event:

```json
{
  "type": "diagram_update",
  "payload": {
    "nodes": [],
    "edges": [],
    "summaryScript": "预算审批流程 已拆分为 2 个分支，等待进一步确认。",
    "confidence": 0.82,
    "warnings": []
  }
}
```

Server clarification event:

```json
{
  "type": "clarification_required",
  "payload": {
    "pendingCommandId": "pc_x",
    "question": "你说的“这里”是指哪一块逻辑？",
    "candidates": ["预算审批流程"],
    "originalText": "这里拆成两个分支"
  }
}
```

## Testing

Backend:

```bash
cd backend
python -m pytest tests/test_context_flow.py -q
python -m compileall app
```

Frontend:

```bash
cd frontend
npm audit --audit-level=moderate
npm run build
```

## Production Readiness

This repository is ready for internal product validation. Before marketplace or enterprise deployment, add:

- Tencent OAuth or enterprise app installation flow.
- Production webhook signature verification following Tencent's latest signing rules.
- Tenant isolation and persistent meeting state.
- Transcript retention controls and audit logs.
- Role-based access for hosts, co-hosts, and viewers.
- Real STT/TTS latency monitoring.
- Deployment manifests for Windows GPU hosts and CPU fallback hosts.

## Roadmap

- Persistent meeting workspaces and saved diagrams.
- Mermaid export and PNG/PDF export.
- LLM-backed parser behind the current graph contract.
- Multiple TTS providers: Coqui, Piper, OpenTTS, and cloud providers.
- True Tencent Meeting extension shell and OAuth install path.
- Fine-grained graph edits: add node, merge node, rename edge, explain path.

## License

No license has been declared yet. Treat this repository as all rights reserved until a license is added.
