from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from time import time
from uuid import uuid4

from .contracts import ClarificationRequest, DiagramResult, TranscriptItem


COMMAND_HINTS = ("拆成", "拆分", "分支", "画", "生成", "新增", "删除", "调整", "split", "branch")
TOPIC_PATTERNS = (
    r"讨论的是(?P<topic>[^，。；;,.]+)",
    r"当前讨论(?P<topic>[^，。；;,.]+)",
    r"关于(?P<topic>[^，。；;,.]+)",
    r"围绕(?P<topic>[^，。；;,.]+)",
)


@dataclass
class PendingCommand:
    id: str
    text: str
    candidates: list[str]
    created_at: float = field(default_factory=time)


@dataclass
class MeetingSession:
    meeting_id: str
    transcript: deque[TranscriptItem] = field(default_factory=lambda: deque(maxlen=80))
    topics: deque[str] = field(default_factory=lambda: deque(maxlen=12))
    selected_label: str | None = None
    graph: DiagramResult | None = None
    pending: dict[str, PendingCommand] = field(default_factory=dict)


class MeetingContextStore:
    def __init__(self) -> None:
        self._sessions: dict[str, MeetingSession] = {}

    def session(self, meeting_id: str) -> MeetingSession:
        if meeting_id not in self._sessions:
            self._sessions[meeting_id] = MeetingSession(meeting_id=meeting_id)
        return self._sessions[meeting_id]

    def add_transcript(
        self,
        meeting_id: str,
        speaker_name: str,
        text: str,
        timestamp_ms: int,
        sentence_id: str,
    ) -> TranscriptItem:
        item = TranscriptItem(
            meetingId=meeting_id,
            speakerName=speaker_name,
            text=text.strip(),
            timestampMs=timestamp_ms,
            sentenceId=sentence_id,
        )
        session = self.session(meeting_id)
        session.transcript.append(item)

        topic = extract_topic(item.text)
        if topic and not is_graph_command(item.text):
            session.topics.append(topic)

        return item

    def set_selected_target(self, meeting_id: str, label: str) -> None:
        self.session(meeting_id).selected_label = label.strip()

    def set_graph(self, meeting_id: str, graph: DiagramResult) -> None:
        self.session(meeting_id).graph = graph

    def resolve_target(self, meeting_id: str) -> tuple[str | None, list[str]]:
        session = self.session(meeting_id)
        candidates: list[str] = []
        if session.selected_label:
            return session.selected_label, [session.selected_label]
        candidates.extend(reversed(session.topics))
        if session.graph:
            candidates.extend(node.label for node in session.graph.nodes if node.kind in {"decision", "topic"})

        deduped = dedupe(candidates)
        if len(deduped) == 1:
            return deduped[0], deduped
        if len(deduped) > 1:
            return None, deduped[:4]
        return None, []

    def create_pending_command(self, meeting_id: str, text: str, candidates: list[str]) -> ClarificationRequest:
        pending = PendingCommand(id=f"pc_{uuid4().hex[:10]}", text=text, candidates=candidates)
        self.session(meeting_id).pending[pending.id] = pending
        return ClarificationRequest(
            pendingCommandId=pending.id,
            question="你说的“这里”是指哪一块逻辑？",
            candidates=candidates,
            originalText=text,
        )

    def pop_pending_command(self, meeting_id: str, pending_command_id: str) -> PendingCommand:
        session = self.session(meeting_id)
        if pending_command_id not in session.pending:
            raise KeyError(f"Unknown pending command: {pending_command_id}")
        return session.pending.pop(pending_command_id)


def is_graph_command(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in COMMAND_HINTS)


def extract_topic(text: str) -> str | None:
    for pattern in TOPIC_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_topic(match.group("topic"))
    return None


def clean_topic(value: str) -> str:
    topic = value.strip(" ：:，,。.;； ")
    topic = re.sub(r"^(这个|这块|这条|the|this)\s*", "", topic, flags=re.IGNORECASE)
    return topic[:40]


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result
