from __future__ import annotations

from .contracts import VoicePersona


GRAPH_EXTRACTION_SYSTEM_PROMPT = """You convert messy meeting transcript fragments into a compact graph JSON object.
Return only valid JSON. Do not include markdown.
The JSON shape is:
{
  "nodes": [{"id": "n1", "label": "Short label", "kind": "topic|decision|action|risk|outcome", "x": 0, "y": 0}],
  "edges": [{"id": "e1", "source": "n1", "target": "n2", "label": "condition"}],
  "summaryScript": "One or two spoken sentences.",
  "confidence": 0.0,
  "warnings": []
}
Use stable ids, short labels, and condition labels for branches."""


PERSONA_GUIDANCE = {
    VoicePersona.OBJECTIVE: "Neutral, concise, factual. Avoid persuasive language.",
    VoicePersona.FACILITATOR: "Encouraging and workshop-oriented. Highlight the next useful question.",
    VoicePersona.EXECUTIVE: "Brief, outcome-focused, and suitable for a senior stakeholder.",
}


def build_graph_extraction_prompt(transcript: str) -> str:
    return f"{GRAPH_EXTRACTION_SYSTEM_PROMPT}\n\nTranscript:\n{transcript.strip()}"


def build_narration_prompt(summary: str, persona: VoicePersona) -> str:
    guidance = PERSONA_GUIDANCE.get(persona, PERSONA_GUIDANCE[VoicePersona.OBJECTIVE])
    return f"Rewrite this as a short spoken narration.\nVoice persona: {guidance}\nSummary: {summary.strip()}"
