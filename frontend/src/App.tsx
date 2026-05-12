import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  MarkerType,
  MiniMap,
  Node,
  Position,
  useEdgesState,
  useNodesState,
} from "reactflow";
import { AudioLines, Check, Circle, Mic2, Play, Radio, Split, Target, Wifi, WifiOff } from "lucide-react";
import "reactflow/dist/style.css";

import { ClarificationRequest, DiagramResult, OutputLanguage, Persona, ServerEvent, TranscriptItem } from "./types";

const WS_URL = "ws://127.0.0.1:8000/ws/meeting";

const personaLabels: Record<OutputLanguage, Record<Persona, string>> = {
  zh: {
    objective: "客观总结",
    facilitator: "引导式脑暴",
    executive: "高管摘要",
  },
  en: {
    objective: "Objective",
    facilitator: "Facilitator",
    executive: "Executive",
  },
};

const copy = {
  zh: {
    title: "会议智能画布",
    subtitlePrefix: "腾讯会议就绪",
    waiting: "等待会议语音生成实时逻辑图。",
    target: "当前指向",
    changeTarget: "点击节点切换",
    voiceSource: "语音来源",
    sourceName: "腾讯会议实时转写",
    sourceHint: "Webhook 已就绪。下方按钮仅用于模拟传入的语音转写事件。",
    stream: "语音流",
    simulateTopic: "模拟主题",
    simulateCommand: "模拟指令",
    transcript: "实时转写",
    transcriptEmpty: "等待腾讯会议转写或模拟语音事件。",
    narration: "旁白脚本",
    connected: "在线",
    offline: "离线",
    connectedStatus: "已连接",
    disconnectedStatus: "未连接",
    connectionIssue: "连接异常",
    processing: "接收语音转写",
    clarificationNeeded: "需要确认指代对象",
    targetSelected: "已选择对象",
    diagramUpdated: "图表已更新",
    narrationStatus: "旁白",
  },
  en: {
    title: "Meeting Intelligence Canvas",
    subtitlePrefix: "Tencent Meeting-ready",
    waiting: "Waiting for meeting speech to generate the live logic map.",
    target: "Active Target",
    changeTarget: "Click a node to change",
    voiceSource: "Voice Source",
    sourceName: "Tencent Meeting ASR",
    sourceHint: "Webhook endpoint is listening. Local buttons only simulate incoming speech events.",
    stream: "Stream",
    simulateTopic: "Simulate topic",
    simulateCommand: "Simulate command",
    transcript: "Live Transcript",
    transcriptEmpty: "Waiting for Tencent Meeting ASR or simulated speech events.",
    narration: "Narration Script",
    connected: "Live",
    offline: "Offline",
    connectedStatus: "Connected",
    disconnectedStatus: "Disconnected",
    connectionIssue: "Connection issue",
    processing: "Receiving voice transcript",
    clarificationNeeded: "Clarification needed",
    targetSelected: "Target selected",
    diagramUpdated: "Diagram updated",
    narrationStatus: "Narration",
  },
};

function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [persona, setPersona] = useState<Persona>("objective");
  const [language, setLanguage] = useState<OutputLanguage>("zh");
  const [connected, setConnected] = useState(false);
  const [summary, setSummary] = useState("等待会议逻辑。");
  const [status, setStatus] = useState("未连接");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [meetingId] = useState("local-demo");
  const [selectedTarget, setSelectedTarget] = useState("预算审批流程");
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const t = copy[language];

  useEffect(() => {
    const socket = new WebSocket(WS_URL);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      setStatus(copy[language].connectedStatus);
    };

    socket.onclose = () => {
      setConnected(false);
      setStatus(copy[language].disconnectedStatus);
    };

    socket.onerror = () => {
      setConnected(false);
      setStatus(copy[language].connectionIssue);
    };

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as ServerEvent;
      if (message.type === "diagram_update") {
        applyDiagram(message.payload, setNodes, setEdges);
        setSummary(message.payload.summaryScript);
        setClarification(null);
        setStatus(`${copy[language].diagramUpdated} · ${Math.round(message.payload.confidence * 100)}%`);
      }
      if (message.type === "transcript_update") {
        setTranscripts((items) => [message.payload, ...items].slice(0, 12));
      }
      if (message.type === "clarification_required") {
        setClarification(message.payload);
        setStatus(copy[language].clarificationNeeded);
      }
      if (message.type === "target_selected") {
        setSelectedTarget(message.label);
        setStatus(`${copy[language].targetSelected} · ${message.label}`);
      }
      if (message.type === "tts_audio") {
        playAudio(message.audioBase64, setIsSpeaking, audioRef);
        setStatus(`${copy[language].narrationStatus} · ${message.engine}`);
      }
      if (message.type === "error") {
        setStatus(`${message.code}: ${message.message}`);
      }
    };

    return () => {
      socket.close();
    };
  }, [language, setEdges, setNodes]);

  const simulateAsr = useCallback(
    (utterance: string, speakerName = "Host") => {
      if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
        setStatus("WebSocket is not connected");
        return;
      }
      socketRef.current.send(JSON.stringify({ type: "meeting_text", text: utterance, persona, meetingId, speakerName, language }));
      setStatus(copy[language].processing);
    },
    [language, meetingId, persona],
  );

  const confirmTarget = useCallback(
    (targetLabel: string) => {
      if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN || !clarification) {
        return;
      }
      socketRef.current.send(
        JSON.stringify({
          type: "confirm_command",
          meetingId,
          pendingCommandId: clarification.pendingCommandId,
          targetLabel,
          language,
        }),
      );
      setSelectedTarget(targetLabel);
      setStatus(copy[language].processing);
    },
    [clarification, language, meetingId],
  );

  const selectTarget = useCallback(
    (node: Node) => {
      const label = String(node.data?.label ?? node.id);
      setSelectedTarget(label);
      socketRef.current?.send(JSON.stringify({ type: "select_target", meetingId, nodeId: node.id, label }));
    },
    [meetingId],
  );

  const emptyState = nodes.length === 0;

  return (
    <main className="h-screen overflow-hidden bg-canvas text-zinc-100">
      <div className="flex h-full flex-col">
        <header className="flex h-14 items-center justify-between border-b border-line/80 px-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-zinc-900 text-accent">
              <Split size={17} />
            </div>
            <div>
              <h1 className="text-sm font-medium tracking-normal">{t.title}</h1>
              <p className="text-xs text-muted">{t.subtitlePrefix} · {status}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ConnectionPill connected={connected} labels={{ connected: t.connected, offline: t.offline }} />
            <button
              onClick={() => {
                const nextLanguage = language === "zh" ? "en" : "zh";
                setLanguage(nextLanguage);
                setSummary(nextLanguage === "zh" ? "等待会议逻辑。" : "Waiting for meeting logic.");
                setStatus(copy[nextLanguage].connectedStatus);
              }}
              className="h-9 rounded-md border border-line bg-panel px-3 text-xs text-zinc-200 transition hover:border-accent/70"
            >
              {language === "zh" ? "中文" : "EN"}
            </button>
            <select
              value={persona}
              onChange={(event) => setPersona(event.target.value as Persona)}
              className="h-9 rounded-md border border-line bg-panel px-3 text-xs text-zinc-200 outline-none"
            >
              {Object.entries(personaLabels[language]).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </header>

        <section className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_340px] max-lg:grid-cols-1">
          <div className="relative min-h-0">
            {emptyState ? <EmptyCanvas text={t.waiting} /> : null}
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              fitView
              fitViewOptions={{ padding: 0.28 }}
              minZoom={0.3}
              maxZoom={1.6}
              onNodeClick={(_, node) => selectTarget(node)}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="#1f252b" gap={28} size={1} />
              <MiniMap
                className="!bg-zinc-950/70"
                nodeColor={(node) => String(node.data?.tone ?? "#63e6be")}
                maskColor="rgba(6, 7, 8, 0.72)"
              />
              <Controls className="!border-line !bg-zinc-950/70 !text-zinc-200" />
            </ReactFlow>
          </div>

          <aside className="flex min-h-0 flex-col border-l border-line/80 bg-panel max-lg:h-[52vh] max-lg:border-l-0 max-lg:border-t">
            <div className="border-b border-line/80 p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase text-muted">
                <Target size={14} />
                {t.target}
              </div>
              <div className="flex items-center justify-between rounded-md border border-line bg-canvas px-3 py-2">
                <span className="truncate text-sm text-zinc-200">{selectedTarget}</span>
                <span className="ml-3 text-xs text-muted">{t.changeTarget}</span>
              </div>
            </div>

            <div className="border-b border-line/80 p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase text-muted">
                <Radio size={14} />
                {t.voiceSource}
              </div>
              <div className="rounded-md border border-line bg-canvas px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm text-zinc-200">{t.sourceName}</div>
                    <div className="mt-1 text-xs leading-5 text-muted">{t.sourceHint}</div>
                  </div>
                  <div className="flex h-8 items-center gap-2 rounded-md bg-zinc-900 px-3 text-xs text-accent">
                    <Mic2 size={13} />
                    {t.stream}
                  </div>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button
                  onClick={() => simulateAsr(language === "zh" ? "我们当前讨论的是预算审批流程，先看客户是否批准预算。" : "We are discussing the budget approval process and whether the customer approves the budget.", "Alice")}
                  className="rounded-md border border-line bg-canvas px-3 py-2 text-left text-xs text-zinc-300 transition hover:border-accent/70"
                >
                  {t.simulateTopic}
                </button>
                <button
                  onClick={() => simulateAsr(language === "zh" ? "这里拆成两个分支：如果客户批准预算，进入执行计划；如果客户拒绝，准备替代方案。" : "Split this into two branches: if the customer approves the budget, move into execution; if the customer rejects it, prepare an alternative plan.", "Alice")}
                  className="rounded-md border border-line bg-canvas px-3 py-2 text-left text-xs text-zinc-300 transition hover:border-amber/70"
                >
                  {t.simulateCommand}
                </button>
              </div>
            </div>

            {clarification ? (
              <ClarificationPanel clarification={clarification} selectedTarget={selectedTarget} onConfirm={confirmTarget} language={language} />
            ) : null}

            <TranscriptPanel transcripts={transcripts} language={language} />

            <div className="min-h-0 flex-1 p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase text-muted">
                <AudioLines size={14} />
                {t.narration}
              </div>
              <p className="text-sm leading-6 text-zinc-300">{summary}</p>
            </div>

            <Waveform active={isSpeaking} />
          </aside>
        </section>
      </div>
    </main>
  );
}

function ConnectionPill({ connected, labels }: { connected: boolean; labels: { connected: string; offline: string } }) {
  const Icon = connected ? Wifi : WifiOff;
  return (
    <div className="flex h-9 items-center gap-2 rounded-md border border-line bg-panel px-3 text-xs text-zinc-300">
      <Icon size={14} className={connected ? "text-accent" : "text-amber"} />
      {connected ? labels.connected : labels.offline}
    </div>
  );
}

function EmptyCanvas({ text }: { text: string }) {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
      <div className="flex items-center gap-3 text-muted">
        <Circle size={10} />
        <span className="text-sm">{text}</span>
      </div>
    </div>
  );
}

function ClarificationPanel({
  clarification,
  selectedTarget,
  onConfirm,
  language,
}: {
  clarification: ClarificationRequest;
  selectedTarget: string;
  onConfirm: (targetLabel: string) => void;
  language: OutputLanguage;
}) {
  const choices = clarification.candidates.length > 0 ? clarification.candidates : [selectedTarget];
  return (
    <div className="border-b border-line/80 p-4">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase text-amber">
        <Mic2 size={14} />
        {language === "zh" ? "澄清确认" : "Clarification"}
      </div>
      <p className="mb-3 text-sm leading-5 text-zinc-300">{clarification.question}</p>
      <div className="grid gap-2">
        {choices.map((choice) => (
          <button
            key={choice}
            onClick={() => onConfirm(choice)}
            className="flex items-center justify-between rounded-md border border-line bg-canvas px-3 py-2 text-left text-xs text-zinc-200 transition hover:border-accent/70"
          >
            <span>{choice}</span>
            <Check size={13} className="text-accent" />
          </button>
        ))}
      </div>
    </div>
  );
}

function TranscriptPanel({ transcripts, language }: { transcripts: TranscriptItem[]; language: OutputLanguage }) {
  return (
    <div className="max-h-44 overflow-auto border-b border-line/80 p-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase text-muted">
        <Mic2 size={14} />
        {language === "zh" ? "实时转写" : "Live Transcript"}
      </div>
      {transcripts.length === 0 ? (
        <p className="text-xs leading-5 text-muted">{copy[language].transcriptEmpty}</p>
      ) : (
        <div className="space-y-2">
          {transcripts.map((item) => (
            <div key={item.sentenceId} className="rounded-md bg-canvas px-3 py-2">
              <div className="mb-1 text-[11px] text-muted">{item.speakerName}</div>
              <div className="text-xs leading-5 text-zinc-300">{item.text}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Waveform({ active }: { active: boolean }) {
  const bars = useMemo(() => Array.from({ length: 48 }, (_, index) => index), []);
  return (
    <div className="flex h-16 items-center gap-1 border-t border-line/80 px-4">
      <Play size={14} className={active ? "text-accent" : "text-muted"} />
      <div className="flex flex-1 items-center gap-1">
        {bars.map((bar) => (
          <span
            key={bar}
            className={`block w-1 rounded-full ${active ? "animate-wave bg-accent" : "bg-zinc-700"}`}
            style={{
              height: `${8 + ((bar * 7) % 24)}px`,
              animationDelay: `${bar * 35}ms`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

function applyDiagram(
  diagram: DiagramResult,
  setNodes: Dispatch<SetStateAction<Node[]>>,
  setEdges: Dispatch<SetStateAction<Edge[]>>,
) {
  setNodes(
    diagram.nodes.map((node) => ({
      id: node.id,
      type: "default",
      position: { x: node.x, y: node.y },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      data: { label: node.label, tone: toneForKind(node.kind) },
      className: `diagram-node diagram-node-${node.kind}`,
    })),
  );

  setEdges(
    diagram.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      animated: true,
      markerEnd: { type: MarkerType.ArrowClosed, color: "#56616b" },
      style: { stroke: "#56616b", strokeWidth: 1.4 },
      labelStyle: { fill: "#aeb7bf", fontSize: 11 },
    })),
  );
}

function toneForKind(kind: string) {
  if (kind === "decision") return "#63e6be";
  if (kind === "risk") return "#f0b95e";
  if (kind === "action") return "#7aa2ff";
  if (kind === "outcome") return "#d4f7e9";
  return "#aeb7bf";
}

function playAudio(
  audioBase64: string,
  setIsSpeaking: (value: boolean) => void,
  audioRef: React.MutableRefObject<HTMLAudioElement | null>,
) {
  const audioUrl = `data:audio/wav;base64,${audioBase64}`;
  audioRef.current?.pause();
  const audio = new Audio(audioUrl);
  audioRef.current = audio;
  audio.onplay = () => setIsSpeaking(true);
  audio.onended = () => setIsSpeaking(false);
  audio.onerror = () => setIsSpeaking(false);
  void audio.play().catch(() => setIsSpeaking(false));
}

export default App;
