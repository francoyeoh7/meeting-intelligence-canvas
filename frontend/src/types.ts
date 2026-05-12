export type Persona = "objective" | "facilitator" | "executive";
export type OutputLanguage = "zh" | "en";

export type DiagramNodeDto = {
  id: string;
  label: string;
  kind: "topic" | "decision" | "action" | "risk" | "outcome";
  x: number;
  y: number;
};

export type DiagramEdgeDto = {
  id: string;
  source: string;
  target: string;
  label: string;
};

export type DiagramResult = {
  nodes: DiagramNodeDto[];
  edges: DiagramEdgeDto[];
  summaryScript: string;
  confidence: number;
  warnings: string[];
};

export type TranscriptItem = {
  meetingId: string;
  speakerName: string;
  text: string;
  timestampMs: number;
  sentenceId: string;
};

export type ClarificationRequest = {
  pendingCommandId: string;
  question: string;
  candidates: string[];
  originalText: string;
};

export type ServerEvent =
  | { type: "diagram_update"; payload: DiagramResult }
  | { type: "transcript_update"; payload: TranscriptItem }
  | { type: "clarification_required"; payload: ClarificationRequest }
  | { type: "target_selected"; label: string; nodeId?: string }
  | { type: "tts_audio"; mimeType: "audio/wav"; audioBase64: string; persona: Persona; engine: string }
  | { type: "error"; code: string; message: string };
