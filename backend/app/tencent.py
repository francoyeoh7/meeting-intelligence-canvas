from __future__ import annotations

from pydantic import BaseModel, Field

from .contracts import TranscriptItem


class TencentOperator(BaseModel):
    userid: str | None = None
    ms_open_id: str | None = None


class TencentMeetingInfo(BaseModel):
    meeting_id: str
    meeting_code: str | None = None


class TencentSpeaker(BaseModel):
    userid: str | None = None
    name: str = "Unknown speaker"


class TencentContent(BaseModel):
    text: str = Field(min_length=1)
    language: str | None = None
    translate_text: str | None = None


class TencentAsrPushPayload(BaseModel):
    operator: TencentOperator | None = None
    meeting_info: TencentMeetingInfo
    speech_time: int
    speaker: TencentSpeaker
    content: TencentContent
    sid: str


class TencentAsrPushEvent(BaseModel):
    event: str
    payload: TencentAsrPushPayload

    def to_transcript_item(self) -> TranscriptItem:
        return TranscriptItem(
            meetingId=self.payload.meeting_info.meeting_id,
            speakerName=self.payload.speaker.name,
            text=self.payload.content.text,
            timestampMs=self.payload.speech_time,
            sentenceId=self.payload.sid,
        )
