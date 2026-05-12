from app.context_store import MeetingContextStore
from app.graph_engine import GraphCommandEngine
from app.tencent import TencentAsrPushEvent


def test_pronoun_command_resolves_to_recent_topic_and_splits_branches():
    store = MeetingContextStore()
    engine = GraphCommandEngine(store)

    store.add_transcript(
        meeting_id="demo",
        speaker_name="PM",
        text="我们当前讨论的是预算审批流程，先看客户是否批准预算。",
        timestamp_ms=1000,
        sentence_id="s1",
    )

    outcome = engine.handle_meeting_text(
        meeting_id="demo",
        text="这里拆成两个分支：如果客户批准预算，进入执行计划；如果客户拒绝，准备替代方案。",
    )

    assert outcome.kind == "diagram"
    assert outcome.diagram is not None
    assert outcome.diagram.nodes[0].label == "预算审批流程"
    assert [node.label for node in outcome.diagram.nodes[1:]] == ["客户批准预算", "客户拒绝"]


def test_pronoun_command_without_context_requests_clarification():
    store = MeetingContextStore()
    engine = GraphCommandEngine(store)

    outcome = engine.handle_meeting_text(meeting_id="demo", text="这里拆成两个分支")

    assert outcome.kind == "clarification"
    assert outcome.clarification is not None
    assert outcome.clarification.question == "你说的“这里”是指哪一块逻辑？"
    assert outcome.clarification.pendingCommandId


def test_clarification_confirmation_applies_pending_command():
    store = MeetingContextStore()
    engine = GraphCommandEngine(store)

    pending = engine.handle_meeting_text(meeting_id="demo", text="这里拆成两个分支")
    pending_id = pending.clarification.pendingCommandId

    outcome = engine.confirm_pending_command(
        meeting_id="demo",
        pending_command_id=pending_id,
        target_label="供应商评估流程",
    )

    assert outcome.kind == "diagram"
    assert outcome.diagram.nodes[0].label == "供应商评估流程"
    assert len(outcome.diagram.nodes) == 3


def test_language_controls_generated_default_labels_and_summary():
    store = MeetingContextStore()
    engine = GraphCommandEngine(store)
    store.set_selected_target("demo", "Budget approval")

    english = engine.handle_meeting_text(meeting_id="demo", text="split here into two branches", language="en")
    chinese = engine.handle_meeting_text(meeting_id="demo", text="这里拆成两个分支", language="zh")

    assert [node.label for node in english.diagram.nodes[1:]] == ["Branch 1", "Branch 2"]
    assert "has been split into 2 branches" in english.diagram.summaryScript
    assert [node.label for node in chinese.diagram.nodes[1:]] == ["分支 1", "分支 2"]
    assert "已拆分为 2 个分支" in chinese.diagram.summaryScript


def test_tencent_asr_push_event_normalizes_transcript_items():
    payload = {
        "event": "meeting.asr-push",
        "payload": {
            "operator": {"userid": "user-1", "ms_open_id": "open-1"},
            "meeting_info": {"meeting_id": "meeting-1", "meeting_code": "123456"},
            "speech_time": 1710000000123,
            "speaker": {"userid": "speaker-1", "name": "Alice"},
            "content": {"text": "这里拆成两个分支", "language": "zh-CN"},
            "sid": "sentence-1",
        },
    }

    event = TencentAsrPushEvent.model_validate(payload)
    transcript = event.to_transcript_item()

    assert transcript.meetingId == "meeting-1"
    assert transcript.speakerName == "Alice"
    assert transcript.text == "这里拆成两个分支"
    assert transcript.sentenceId == "sentence-1"
