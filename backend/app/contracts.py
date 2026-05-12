from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

OutputLanguage = Literal["zh", "en"]


class VoicePersona(str, Enum):
    OBJECTIVE = "objective"
    FACILITATOR = "facilitator"
    EXECUTIVE = "executive"


class DiagramNode(BaseModel):
    id: str
    label: str
    kind: Literal["topic", "decision", "action", "risk", "outcome"] = "topic"
    x: float = 0
    y: float = 0


class DiagramEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str = ""


class DiagramResult(BaseModel):
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]
    summaryScript: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class MeetingTextMessage(BaseModel):
    type: Literal["meeting_text"]
    meetingId: str = "local-demo"
    text: str = Field(min_length=1, max_length=8000)
    persona: VoicePersona = VoicePersona.OBJECTIVE
    speakerName: str = "Local user"
    language: OutputLanguage = "zh"


class ConfirmCommandMessage(BaseModel):
    type: Literal["confirm_command"]
    meetingId: str = "local-demo"
    pendingCommandId: str
    targetLabel: str = Field(min_length=1, max_length=120)
    language: OutputLanguage = "zh"


class SelectTargetMessage(BaseModel):
    type: Literal["select_target"]
    meetingId: str = "local-demo"
    nodeId: str | None = None
    label: str = Field(min_length=1, max_length=120)


class TranscriptItem(BaseModel):
    meetingId: str
    speakerName: str
    text: str
    timestampMs: int
    sentenceId: str


class ClarificationRequest(BaseModel):
    pendingCommandId: str
    question: str
    candidates: list[str] = Field(default_factory=list)
    originalText: str


class DiagramUpdateEvent(BaseModel):
    type: Literal["diagram_update"] = "diagram_update"
    payload: DiagramResult


class TranscriptUpdateEvent(BaseModel):
    type: Literal["transcript_update"] = "transcript_update"
    payload: TranscriptItem


class ClarificationEvent(BaseModel):
    type: Literal["clarification_required"] = "clarification_required"
    payload: ClarificationRequest


class TtsAudioEvent(BaseModel):
    type: Literal["tts_audio"] = "tts_audio"
    mimeType: Literal["audio/wav"] = "audio/wav"
    audioBase64: str
    persona: VoicePersona
    engine: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    ttsEnabled: bool
    ttsEngine: str
    tencentWebhookConfigured: bool = False
