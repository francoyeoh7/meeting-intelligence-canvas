from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from .contracts import (
    ClarificationEvent,
    ConfirmCommandMessage,
    DiagramUpdateEvent,
    ErrorEvent,
    HealthResponse,
    MeetingTextMessage,
    SelectTargetMessage,
    TtsAudioEvent,
    TranscriptUpdateEvent,
)
from .context_store import MeetingContextStore
from .graph_engine import CommandOutcome, GraphCommandEngine
from .tencent import TencentAsrPushEvent
from .tts_service import TtsService

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("meeting-diagram-tts")

app = FastAPI(title="Meeting Diagram TTS", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tts_service = TtsService()
context_store = MeetingContextStore()
graph_engine = GraphCommandEngine(context_store)
connections: set[WebSocket] = set()


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    engine = "coqui" if tts_service.enabled else "fallback-tone"
    return HealthResponse(
        status="ok",
        ttsEnabled=tts_service.enabled,
        ttsEngine=engine,
        tencentWebhookConfigured=bool(os.getenv("TENCENT_WEBHOOK_SECRET")),
    )


@app.post("/parse")
async def parse(payload: MeetingTextMessage) -> DiagramUpdateEvent:
    outcome = graph_engine.handle_meeting_text(meeting_id=payload.meetingId, text=payload.text, language=payload.language)
    if outcome.diagram is None:
        raise HTTPException(status_code=409, detail="Clarification is required before applying this command.")
    return DiagramUpdateEvent(payload=outcome.diagram)


@app.post("/webhooks/tencent/asr")
async def tencent_asr_webhook(
    payload: TencentAsrPushEvent,
    x_meeting_diagram_secret: str | None = Header(default=None),
) -> dict[str, str]:
    expected_secret = os.getenv("TENCENT_WEBHOOK_SECRET")
    if expected_secret and x_meeting_diagram_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    transcript = payload.to_transcript_item()
    context_store.add_transcript(
        meeting_id=transcript.meetingId,
        speaker_name=transcript.speakerName,
        text=transcript.text,
        timestamp_ms=transcript.timestampMs,
        sentence_id=transcript.sentenceId,
    )
    await broadcast(TranscriptUpdateEvent(payload=transcript).model_dump())

    outcome = graph_engine.handle_meeting_text(meeting_id=transcript.meetingId, text=transcript.text, language="zh")
    await emit_outcome(outcome, persona=None)
    return {"status": "accepted"}


@app.websocket("/ws/meeting")
async def meeting_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    connections.add(websocket)
    logger.info("meeting websocket connected")

    try:
        while True:
            raw_message = await websocket.receive_json()
            try:
                message_type = raw_message.get("type")
                if message_type == "meeting_text":
                    message = MeetingTextMessage.model_validate(raw_message)
                    transcript = context_store.add_transcript(
                        meeting_id=message.meetingId,
                        speaker_name=message.speakerName,
                        text=message.text,
                        timestamp_ms=0,
                        sentence_id=f"local-{id(message)}",
                    )
                    await websocket.send_json(TranscriptUpdateEvent(payload=transcript).model_dump())
                    outcome = graph_engine.handle_meeting_text(meeting_id=message.meetingId, text=message.text, language=message.language)
                    await emit_outcome(outcome, persona=message.persona, websocket=websocket)
                elif message_type == "confirm_command":
                    message = ConfirmCommandMessage.model_validate(raw_message)
                    outcome = graph_engine.confirm_pending_command(
                        meeting_id=message.meetingId,
                        pending_command_id=message.pendingCommandId,
                        target_label=message.targetLabel,
                        language=message.language,
                    )
                    await emit_outcome(outcome, persona=None, websocket=websocket)
                elif message_type == "select_target":
                    message = SelectTargetMessage.model_validate(raw_message)
                    context_store.set_selected_target(meeting_id=message.meetingId, label=message.label)
                    await websocket.send_json({"type": "target_selected", "label": message.label, "nodeId": message.nodeId})
                else:
                    await websocket.send_json(ErrorEvent(code="unknown_message", message="Unsupported WebSocket message type.").model_dump())
            except ValidationError:
                await websocket.send_json(
                    ErrorEvent(code="invalid_message", message="The meeting message format is invalid.").model_dump()
                )
            except RuntimeError as exc:
                logger.warning("tts_error: %s", exc)
                await websocket.send_json(ErrorEvent(code="tts_error", message=str(exc)).model_dump())
            except Exception as exc:  # noqa: BLE001 - keep websocket alive with formatted errors
                logger.exception("unhandled_message_error")
                await websocket.send_json(
                    ErrorEvent(code="processing_error", message=f"Unable to process this meeting update: {exc.__class__.__name__}.").model_dump()
                )
    except WebSocketDisconnect:
        logger.info("meeting websocket disconnected")
    finally:
        connections.discard(websocket)


async def emit_outcome(
    outcome: CommandOutcome,
    persona,
    websocket: WebSocket | None = None,
) -> None:
    if outcome.kind == "ignored":
        return
    if outcome.kind == "clarification" and outcome.clarification:
        await send_or_broadcast(ClarificationEvent(payload=outcome.clarification).model_dump(), websocket)
        return
    if outcome.kind == "diagram" and outcome.diagram:
        await send_or_broadcast(DiagramUpdateEvent(payload=outcome.diagram).model_dump(), websocket)
        if persona:
            tts_result = await asyncio.to_thread(
                tts_service.synthesize_base64,
                outcome.diagram.summaryScript,
                persona,
            )
            await send_or_broadcast(
                TtsAudioEvent(audioBase64=tts_result.audio_base64, persona=persona, engine=tts_result.engine).model_dump(),
                websocket,
            )


async def send_or_broadcast(payload: dict, websocket: WebSocket | None) -> None:
    if websocket:
        await websocket.send_json(payload)
    else:
        await broadcast(payload)


async def broadcast(payload: dict) -> None:
    disconnected: list[WebSocket] = []
    for connection in list(connections):
        try:
            await connection.send_json(payload)
        except RuntimeError:
            disconnected.append(connection)
    for connection in disconnected:
        connections.discard(connection)
