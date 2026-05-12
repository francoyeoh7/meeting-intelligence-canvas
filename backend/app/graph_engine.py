from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .context_store import MeetingContextStore
from .contracts import ClarificationRequest, DiagramNode, DiagramResult, OutputLanguage
from .parser import count_to_int, detect_branch_count, parse_meeting_text


PRONOUN_HINTS = ("这里", "这块", "这个", "刚才", "this", "here", "that")


@dataclass(frozen=True)
class CommandOutcome:
    kind: Literal["diagram", "clarification", "ignored"]
    diagram: DiagramResult | None = None
    clarification: ClarificationRequest | None = None


class GraphCommandEngine:
    def __init__(self, store: MeetingContextStore) -> None:
        self.store = store

    def handle_meeting_text(self, meeting_id: str, text: str, language: OutputLanguage = "zh") -> CommandOutcome:
        if not should_update_graph(text):
            return CommandOutcome(kind="ignored")

        target_label = None
        if uses_context_pronoun(text):
            target_label, candidates = self.store.resolve_target(meeting_id)
            if target_label is None:
                clarification = self.store.create_pending_command(meeting_id, text, candidates)
                return CommandOutcome(kind="clarification", clarification=clarification)

        diagram = self._build_diagram(text=text, target_label=target_label, language=language)
        self.store.set_graph(meeting_id, diagram)
        return CommandOutcome(kind="diagram", diagram=diagram)

    def confirm_pending_command(self, meeting_id: str, pending_command_id: str, target_label: str, language: OutputLanguage = "zh") -> CommandOutcome:
        pending = self.store.pop_pending_command(meeting_id, pending_command_id)
        self.store.set_selected_target(meeting_id, target_label)
        diagram = self._build_diagram(text=pending.text, target_label=target_label, language=language)
        self.store.set_graph(meeting_id, diagram)
        return CommandOutcome(kind="diagram", diagram=diagram)

    def _build_diagram(self, text: str, target_label: str | None, language: OutputLanguage) -> DiagramResult:
        diagram = parse_meeting_text(text, language=language)
        if target_label:
            diagram.nodes[0].label = target_label
        if has_only_command_label(text):
            diagram.nodes = rebuild_default_branch_nodes(diagram.nodes[0], detect_branch_count(text) or 2, language)
            diagram.edges = [
                edge.model_copy(update={"label": diagram.nodes[index].label})
                for index, edge in enumerate(diagram.edges[: len(diagram.nodes) - 1], start=1)
            ]
            if language == "zh":
                diagram.summaryScript = f"{diagram.nodes[0].label} 已拆分为 {len(diagram.nodes) - 1} 个分支，等待进一步确认。"
            else:
                diagram.summaryScript = f"{diagram.nodes[0].label} has been split into {len(diagram.nodes) - 1} branches for review."
        return diagram


def should_update_graph(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("拆成", "拆分", "分支", "split", "branch"))


def uses_context_pronoun(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in PRONOUN_HINTS)


def has_only_command_label(text: str) -> bool:
    if re.search(r"如果|if\s+", text, flags=re.IGNORECASE):
        return False
    return bool(detect_branch_count(text))


def rebuild_default_branch_nodes(root: DiagramNode, branch_count: int, language: OutputLanguage) -> list[DiagramNode]:
    count = max(2, min(6, count_to_int(str(branch_count))))
    start_x = -180 * (count - 1) / 2
    prefix = "分支" if language == "zh" else "Branch"
    nodes = [root]
    for index in range(1, count + 1):
        nodes.append(
            DiagramNode(
                id=f"n{index}",
                label=f"{prefix} {index}",
                kind="outcome",
                x=start_x + (index - 1) * 180,
                y=170,
            )
        )
    return nodes
