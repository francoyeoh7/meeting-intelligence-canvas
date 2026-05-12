from __future__ import annotations

import re
from dataclasses import dataclass

from .contracts import DiagramEdge, DiagramNode, DiagramResult, OutputLanguage


BRANCH_PATTERNS = (
    r"split(?:\s+\w+){0,4}\s+into\s+(?P<count>two|three|four|\d+)\s+branches?",
    r"拆分为(?P<count>两个|三个|四个|\d+个?)分支",
    r"拆成(?P<count>两个|三个|四个|\d+个?)分支",
    r"分成(?P<count>两个|三个|四个|\d+个?)分支",
)

KEYWORD_KINDS = {
    "approve": "outcome",
    "approval": "outcome",
    "reject": "outcome",
    "rejection": "outcome",
    "risk": "risk",
    "blocker": "risk",
    "action": "action",
    "decision": "decision",
    "批准": "outcome",
    "拒绝": "outcome",
    "风险": "risk",
    "行动": "action",
    "决策": "decision",
}


@dataclass(frozen=True)
class ParsedPhrase:
    label: str
    kind: str


def parse_meeting_text(text: str, language: OutputLanguage = "zh") -> DiagramResult:
    normalized = normalize_text(text)
    phrases = extract_phrases(normalized)
    branch_count = detect_branch_count(normalized)

    if branch_count and len(phrases) < branch_count:
        phrases.extend(default_branch_phrases(branch_count - len(phrases), language))

    nodes = build_nodes(phrases, branch_count, language)
    edges = build_edges(nodes, branch_count)
    summary = build_summary(nodes, branch_count, language)
    confidence = 0.82 if branch_count or len(nodes) > 2 else 0.58
    warnings = [] if confidence >= 0.7 else [low_confidence_warning(language)]

    return DiagramResult(
        nodes=nodes,
        edges=edges,
        summaryScript=summary,
        confidence=confidence,
        warnings=warnings,
    )


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def detect_branch_count(text: str) -> int | None:
    for pattern in BRANCH_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return count_to_int(match.group("count"))
    return None


def count_to_int(value: str) -> int:
    mapping = {
        "two": 2,
        "three": 3,
        "four": 4,
        "两个": 2,
        "三个": 3,
        "四个": 4,
    }
    cleaned = value.replace("个", "")
    if cleaned in mapping:
        return mapping[cleaned]
    try:
        return max(1, min(6, int(cleaned)))
    except ValueError:
        return 2


def extract_phrases(text: str) -> list[ParsedPhrase]:
    branch_segments = extract_chinese_if_branches(text)
    if branch_segments:
        return [ParsedPhrase(label=label, kind=infer_kind(label)) for label in branch_segments[:8]]

    segments = re.split(r"[.;。；,，]|\band\b|\bthen\b|\bif\b|\bwhen\b", text, flags=re.IGNORECASE)
    phrases: list[ParsedPhrase] = []

    for raw in segments:
        label = clean_label(raw)
        if not label:
            continue
        phrases.append(ParsedPhrase(label=label, kind=infer_kind(label)))

    if not phrases:
        phrases.append(ParsedPhrase(label="Meeting logic", kind="topic"))

    return phrases[:8]


def extract_chinese_if_branches(text: str) -> list[str]:
    matches = re.findall(r"如果([^；。]+)", text)
    labels: list[str] = []
    for match in matches:
        label = re.split(r"，|,|则|那么", match, maxsplit=1)[0]
        cleaned = clean_label(label)
        if cleaned:
            labels.append(cleaned)
    return labels


def clean_label(value: str) -> str:
    label = value.strip(" -:：")
    label = re.sub(
        r"^(please|can you|could you|将|把|请|这里的|the|this)\s*",
        "",
        label,
        flags=re.IGNORECASE,
    )
    words = label.split()
    if len(words) > 9:
        label = " ".join(words[:9])
    if len(label) > 42:
        label = label[:39].rstrip() + "..."
    return label


def infer_kind(label: str) -> str:
    lowered = label.lower()
    for keyword, kind in KEYWORD_KINDS.items():
        if keyword in lowered:
            return kind
    if "?" in label or "是否" in label:
        return "decision"
    return "topic"


def default_branch_phrases(count: int, language: OutputLanguage) -> list[ParsedPhrase]:
    prefix = "分支" if language == "zh" else "Branch"
    return [ParsedPhrase(label=f"{prefix} {index + 1}", kind="outcome") for index in range(count)]


def build_nodes(phrases: list[ParsedPhrase], branch_count: int | None, language: OutputLanguage) -> list[DiagramNode]:
    root_label = "决策点" if branch_count and language == "zh" else "Decision point" if branch_count else "会议逻辑" if language == "zh" else "Meeting logic"
    root = DiagramNode(id="n0", label=root_label, kind="decision", x=0, y=0)
    nodes = [root]

    if branch_count:
        selected = phrases[:branch_count]
        start_x = -180 * (len(selected) - 1) / 2
        for index, phrase in enumerate(selected, start=1):
            nodes.append(
                DiagramNode(
                    id=f"n{index}",
                    label=phrase.label,
                    kind=phrase.kind,
                    x=start_x + (index - 1) * 180,
                    y=170,
                )
            )
        return nodes

    for index, phrase in enumerate(phrases, start=1):
        nodes.append(
            DiagramNode(
                id=f"n{index}",
                label=phrase.label,
                kind=phrase.kind,
                x=0,
                y=index * 140,
            )
        )
    return nodes


def build_edges(nodes: list[DiagramNode], branch_count: int | None) -> list[DiagramEdge]:
    edges: list[DiagramEdge] = []
    if len(nodes) <= 1:
        return edges

    if branch_count:
        for node in nodes[1:]:
            edges.append(DiagramEdge(id=f"e0-{node.id}", source="n0", target=node.id, label=node.label))
        return edges

    for source, target in zip(nodes, nodes[1:]):
        edges.append(DiagramEdge(id=f"e{source.id}-{target.id}", source=source.id, target=target.id, label="next"))
    return edges


def build_summary(nodes: list[DiagramNode], branch_count: int | None, language: OutputLanguage) -> str:
    labels = [node.label for node in nodes[1:]]
    if branch_count and labels:
        joined = ", ".join(labels)
        if language == "zh":
            return f"当前逻辑围绕一个决策点展开，包含 {len(labels)} 个分支：{joined}。"
        return f"The discussion centers on one decision point with {len(labels)} branches: {joined}."
    if labels:
        if language == "zh":
            return f"当前讨论包含 {len(labels)} 个步骤：{', '.join(labels[:4])}。"
        return f"The discussion flows through {len(labels)} steps: {', '.join(labels[:4])}."
    return "会议逻辑已记录为一个起点。" if language == "zh" else "The meeting logic has been captured as a single starting point."


def low_confidence_warning(language: OutputLanguage) -> str:
    if language == "zh":
        return "结构置信度较低；建议使用更明确的分支或依赖指令。"
    return "Low structure confidence; consider using an explicit branch or dependency instruction."
