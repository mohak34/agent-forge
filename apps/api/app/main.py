import asyncio
import logging
import traceback

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.bootstrap_migrations import run_bootstrap_migrations
from app.chat_context import (
    assemble_thread_goal,
    build_summary_snapshot,
)
from app.config import settings
from app.database import Base, engine, get_db
from app.memory import get_recent_memory, store_memory
from app.orchestrator import execute_task_graph
from app.models import (
    AgentTemplate,
    ApprovalRequest,
    ApprovalStatus,
    ChatMessage,
    ChatThread,
    MemoryItem,
    Run,
    RunStatus,
    TaskNode,
    ThreadSummary,
    TraceEvent,
)
from app.planner import build_task_plan
from app.route_classifier import classify_route
from app.schemas import (
    AgentTemplateCreate,
    AgentTemplateImport,
    AgentTemplateResponse,
    ApprovalDecisionRequest,
    ApprovalRequestResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatThreadCreate,
    ChatThreadDetailResponse,
    ChatThreadResponse,
    ChatTurnResponse,
    GoalCreate,
    MemoryItemResponse,
    RunFromTemplateRequest,
    RunHistoryItemResponse,
    RunResponse,
    TaskNodeResponse,
    ToolResponse,
    TraceEventResponse,
)
from app.executor import run_agent_with_tools
from app.tools import get_tool_schemas, list_tools

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    run_bootstrap_migrations(engine)


def create_event(
    db: Session, run_id: str, event_type: str, detail: str, actor: str = "system"
) -> None:
    db.add(
        TraceEvent(
            run_id=run_id,
            event_type=event_type,
            detail=detail,
            actor=actor,
            status="ok",
        )
    )


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def emit_plan_events(db: Session, run_id: str, task_nodes: list[TaskNode]) -> None:
    create_event(db, run_id, "plan.generated", f"Generated task graph with {len(task_nodes)} nodes")
    for node in task_nodes:
        create_event(
            db,
            run_id,
            "task.planned",
            f"seq={node.sequence} kind={node.kind} title={node.title} depends_on={node.depends_on or 'none'}",
            actor="planner",
        )


def goal_requires_approval(goal: str) -> tuple[bool, str]:
    risky_keywords = ["email", "slack", "send", "write", "execute", "delete", "notify"]
    lowered = goal.lower()
    for keyword in risky_keywords:
        if keyword in lowered:
            return True, f"Goal includes risky action keyword: {keyword}"
    return False, ""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def parse_template_json(config_json: str) -> dict:
    import json

    try:
        parsed = json.loads(config_json or "{}")
        if isinstance(parsed, dict):
            return parsed
        return {}
    except Exception:
        return {}


def _recent_thread_messages(db: Session, thread_id: str, limit: int = 8) -> list[ChatMessage]:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    messages.reverse()
    return messages


async def execute_run_for_goal(
    db: Session,
    goal: str,
    memory_enabled: bool,
    thread_id: str | None = None,
    user_message_id: str | None = None,
    turn_index: int = 0,
) -> Run:
    run = Run(
        goal=goal,
        memory_enabled=memory_enabled,
        status=RunStatus.QUEUED,
        thread_id=thread_id,
        user_message_id=user_message_id,
        turn_index=turn_index,
    )
    db.add(run)
    db.flush()

    create_event(db, run.id, "run.created", "Goal accepted")

    nodes = build_task_plan(run)
    for node in nodes:
        db.add(node)
    db.flush()
    emit_plan_events(db, run.id, nodes)

    try:
        needs_approval, approval_reason = goal_requires_approval(goal)
        if needs_approval:
            run.status = RunStatus.WAITING_APPROVAL
            request = ApprovalRequest(
                run_id=run.id,
                action_type="external_action",
                reason=approval_reason,
                payload=goal,
                status=ApprovalStatus.PENDING,
            )
            db.add(request)
            create_event(
                db,
                run.id,
                "approval.requested",
                f"Approval required: {approval_reason}",
                actor="policy",
            )
        else:
            run.status = RunStatus.RUNNING
            create_event(db, run.id, "run.started", "Run entered running state")
            if run.memory_enabled:
                memory_items = get_recent_memory(db, run)
                if memory_items:
                    memory_preview = " | ".join(item.content[:120] for item in memory_items[:3])
                    create_event(
                        db,
                        run.id,
                        "memory.retrieved",
                        f"Loaded {len(memory_items)} memory item(s): {memory_preview}",
                        actor="memory",
                    )
                    run.goal = f"{run.goal}\n\nRelevant memory:\n{memory_preview}"
            create_event(
                db, run.id, "model.routed", f"Selected provider={settings.default_model_provider}"
            )
            task_nodes = (
                db.query(TaskNode)
                .filter(TaskNode.run_id == run.id)
                .order_by(TaskNode.sequence.asc())
                .all()
            )
            result, task_nodes = await execute_task_graph(
                db=db,
                run=run,
                task_nodes=task_nodes,
                create_event=create_event,
            )

            run.provider = result["provider"]
            run.model = result["model"]
            run.output_text = result["text"]
            run.token_estimate = estimate_tokens(result["text"])

            preview = result["text"][:400].strip()
            create_event(
                db, run.id, "run.output", f"Final output preview: {preview}", actor="executor"
            )
            if run.memory_enabled:
                store_memory(db, run, content=run.output_text[:600], kind="run_summary")
                create_event(
                    db,
                    run.id,
                    "memory.stored",
                    "Stored run output in persistent memory",
                    actor="memory",
                )

            run.status = RunStatus.COMPLETED
            if run.budget_exceeded and run.output_text.strip() == "":
                run.status = RunStatus.FAILED
            create_event(db, run.id, "run.completed", "Run finished")
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.error(f"execute_run_for_goal failed: {exc}")
        logger.error(traceback.format_exc())
        run.status = RunStatus.FAILED
        create_event(db, run.id, "run.failed", str(exc), actor="executor")

    return run


async def execute_direct_turn(
    db: Session,
    goal: str,
    raw_message: str,
    memory_enabled: bool,
    thread_id: str,
    user_message_id: str,
    turn_index: int,
) -> Run:
    run = Run(
        goal=goal,
        memory_enabled=memory_enabled,
        status=RunStatus.RUNNING,
        thread_id=thread_id,
        user_message_id=user_message_id,
        turn_index=turn_index,
    )
    db.add(run)
    db.flush()

    create_event(db, run.id, "run.created", "Direct chat turn accepted")
    create_event(db, run.id, "run.started", "Direct turn entered running state")
    create_event(
        db, run.id, "chat.context.assembled", "Used thread summary + recent message window"
    )

    try:
        available_tools = get_tool_schemas()

        async def on_tool_call(tool_name: str, payload: str) -> None:
            create_event(
                db,
                run.id,
                "tool.invoked",
                f"tool={tool_name} input={payload[:140]}",
                actor="direct-agent",
            )
            db.commit()

        result = await run_agent_with_tools(
            goal,
            provider_override="groq",
            tools=available_tools,
            on_tool_call=on_tool_call,
        )
        run.provider = result["provider"]
        run.model = result["model"]
        run.output_text = result["text"]
        run.token_estimate = estimate_tokens(result["text"])
        create_event(
            db,
            run.id,
            "run.output",
            f"Final output preview: {run.output_text[:400]}",
            actor="executor",
        )
        run.status = RunStatus.COMPLETED
        create_event(db, run.id, "run.completed", "Direct run finished")
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.error(f"execute_direct_turn failed: {exc}")
        logger.error(traceback.format_exc())
        run.status = RunStatus.FAILED
        create_event(db, run.id, "run.failed", str(exc), actor="executor")

    return run


@app.post(f"{settings.api_prefix}/goals", response_model=RunResponse)
async def create_goal(payload: GoalCreate, db: Session = Depends(get_db)) -> Run:
    run = await execute_run_for_goal(
        db=db,
        goal=payload.goal,
        memory_enabled=payload.memory_enabled,
    )

    db.commit()
    db.refresh(run)
    return run


@app.get(f"{settings.api_prefix}/agents", response_model=list[AgentTemplateResponse])
def list_templates(db: Session = Depends(get_db)) -> list[AgentTemplate]:
    return db.query(AgentTemplate).order_by(AgentTemplate.created_at.desc()).all()


@app.post(f"{settings.api_prefix}/agents", response_model=AgentTemplateResponse)
def create_template(payload: AgentTemplateCreate, db: Session = Depends(get_db)) -> AgentTemplate:
    existing = db.query(AgentTemplate).filter(AgentTemplate.name == payload.name).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Template with this name already exists")
    template = AgentTemplate(
        name=payload.name,
        description=payload.description,
        version=payload.version,
        config_json=payload.config_json,
        is_builtin=False,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@app.post(f"{settings.api_prefix}/agents/import", response_model=AgentTemplateResponse)
def import_template(payload: AgentTemplateImport, db: Session = Depends(get_db)) -> AgentTemplate:
    existing = db.query(AgentTemplate).filter(AgentTemplate.name == payload.name).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Template with this name already exists")
    template = AgentTemplate(
        name=payload.name,
        description=payload.description,
        version=payload.version,
        config_json=payload.config_json,
        is_builtin=False,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@app.get(f"{settings.api_prefix}/agents/{{template_id}}", response_model=AgentTemplateResponse)
def get_template(template_id: str, db: Session = Depends(get_db)) -> AgentTemplate:
    template = db.get(AgentTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@app.get(f"{settings.api_prefix}/agents/{{template_id}}/export")
def export_template(template_id: str, db: Session = Depends(get_db)) -> dict:
    template = db.get(AgentTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "name": template.name,
        "description": template.description,
        "version": template.version,
        "config_json": template.config_json,
    }


@app.post(f"{settings.api_prefix}/agents/{{template_id}}/run", response_model=RunResponse)
async def run_with_template(
    template_id: str,
    payload: RunFromTemplateRequest,
    db: Session = Depends(get_db),
) -> Run:
    template = db.get(AgentTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    config = parse_template_json(template.config_json)
    goal_prefix = config.get("goal_prefix", "")
    final_goal = f"{goal_prefix}\n{payload.goal}".strip() if goal_prefix else payload.goal
    return await create_goal(
        GoalCreate(goal=final_goal, memory_enabled=payload.memory_enabled),
        db,
    )


@app.post(f"{settings.api_prefix}/chat/threads", response_model=ChatThreadResponse)
def create_chat_thread(payload: ChatThreadCreate, db: Session = Depends(get_db)) -> ChatThread:
    template_id = payload.template_id
    if template_id:
        template = db.get(AgentTemplate, template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Template not found")
    thread = ChatThread(
        title=payload.title.strip() or "New chat",
        memory_enabled=payload.memory_enabled,
        template_id=template_id,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@app.get(f"{settings.api_prefix}/chat/threads", response_model=list[ChatThreadResponse])
def list_chat_threads(limit: int = 50, db: Session = Depends(get_db)) -> list[ChatThread]:
    bounded_limit = max(1, min(limit, 200))
    return db.query(ChatThread).order_by(ChatThread.updated_at.desc()).limit(bounded_limit).all()


@app.get(
    f"{settings.api_prefix}/chat/threads/{{thread_id}}", response_model=ChatThreadDetailResponse
)
def get_chat_thread(thread_id: str, db: Session = Depends(get_db)) -> ChatThreadDetailResponse:
    thread = db.get(ChatThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return ChatThreadDetailResponse(thread=thread, messages=messages)


@app.get(
    f"{settings.api_prefix}/chat/threads/{{thread_id}}/messages",
    response_model=list[ChatMessageResponse],
)
def list_thread_messages(thread_id: str, db: Session = Depends(get_db)) -> list[ChatMessage]:
    thread = db.get(ChatThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


@app.post(
    f"{settings.api_prefix}/chat/threads/{{thread_id}}/messages",
    response_model=ChatTurnResponse,
)
async def send_thread_message(
    thread_id: str,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
) -> ChatTurnResponse:
    thread = db.get(ChatThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content is required")

    previous_message = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.turn_index.desc())
        .first()
    )
    next_turn = (previous_message.turn_index + 1) if previous_message else 1

    user_message = ChatMessage(
        thread_id=thread_id,
        role="user",
        content=content,
        turn_index=next_turn,
    )
    db.add(user_message)
    db.flush()

    summary = db.query(ThreadSummary).filter(ThreadSummary.thread_id == thread_id).first()
    recent = _recent_thread_messages(db, thread_id, limit=8)
    assembled_goal = assemble_thread_goal(content, summary.summary_text if summary else "", recent)

    selected_route = payload.route_mode
    route_reason = "manual route mode"

    if payload.route_mode == "auto":
        classifier_decision = await classify_route(content)
        selected_route = classifier_decision["route"]
        route_reason = classifier_decision["reason"]
    elif payload.route_mode == "orchestrated":
        selected_route = "orchestrated"

    direct_mode = selected_route == "direct"

    run: Run
    if direct_mode:
        run = await execute_direct_turn(
            db=db,
            goal=assembled_goal,
            raw_message=content,
            memory_enabled=thread.memory_enabled,
            thread_id=thread_id,
            user_message_id=user_message.id,
            turn_index=next_turn,
        )
    else:
        run = await execute_run_for_goal(
            db=db,
            goal=assembled_goal,
            memory_enabled=thread.memory_enabled,
            thread_id=thread_id,
            user_message_id=user_message.id,
            turn_index=next_turn,
        )
        create_event(
            db,
            run.id,
            "chat.context.assembled",
            "Used thread summary + recent message window",
            actor="orchestrator",
        )

    create_event(
        db,
        run.id,
        "route.classified",
        f"route={selected_route} reason={route_reason}",
        actor="router",
    )

    assistant_message = ChatMessage(
        thread_id=thread_id,
        role="assistant",
        content=run.output_text or "",
        turn_index=next_turn,
        run_id=run.id,
    )
    db.add(assistant_message)
    db.flush()

    run.assistant_message_id = assistant_message.id
    thread.last_run_id = run.id
    if next_turn == 1:
        thread.title = content[:80]

    all_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    snapshot = build_summary_snapshot(all_messages)
    if summary is None:
        summary = ThreadSummary(thread_id=thread_id)
        db.add(summary)
    summary.summary_text = snapshot
    summary.summarized_until_turn = next_turn
    create_event(
        db, run.id, "chat.summary.updated", "Updated thread rolling summary", actor="memory"
    )

    db.commit()
    db.refresh(thread)
    db.refresh(user_message)
    db.refresh(assistant_message)
    db.refresh(run)
    return ChatTurnResponse(
        thread=thread,
        user_message=user_message,
        assistant_message=assistant_message,
        run=run,
    )


@app.get(f"{settings.api_prefix}/runs/{{run_id}}", response_model=RunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get(f"{settings.api_prefix}/runs", response_model=list[RunHistoryItemResponse])
def list_runs(limit: int = 50, db: Session = Depends(get_db)) -> list[Run]:
    bounded_limit = max(1, min(limit, 200))
    return db.query(Run).order_by(Run.created_at.desc()).limit(bounded_limit).all()


@app.get(f"{settings.api_prefix}/runs/{{run_id}}/timeline", response_model=list[TraceEventResponse])
def get_timeline(run_id: str, db: Session = Depends(get_db)) -> list[TraceEvent]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.events


@app.get(f"{settings.api_prefix}/runs/{{run_id}}/stream")
def stream_run_events(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        seen_count = 0
        max_wait = 300  # 5 minutes max
        waited = 0
        while waited < max_wait:
            db.expire_all()
            events = (
                db.query(TraceEvent)
                .filter(TraceEvent.run_id == run_id)
                .order_by(TraceEvent.created_at.asc())
                .all()
            )
            new_events = events[seen_count:]
            for event in new_events:
                payload = {
                    "event_type": event.event_type,
                    "detail": event.detail,
                    "actor": event.actor,
                    "status": event.status,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
                yield f"data: {__import__('json').dumps(payload)}\n\n"
            seen_count = len(events)

            # Check if run is finished
            db.expire_all()
            current_run = db.get(Run, run_id)
            if current_run and current_run.status.value in {"completed", "failed", "waiting_approval"}:
                final = {"event_type": "run.final", "detail": current_run.status.value, "actor": "system", "status": current_run.status.value}
                yield f"data: {__import__('json').dumps(final)}\n\n"
                break

            await asyncio.sleep(1)
            waited += 1

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get(f"{settings.api_prefix}/runs/{{run_id}}/tasks", response_model=list[TaskNodeResponse])
def get_tasks(run_id: str, db: Session = Depends(get_db)) -> list[TaskNode]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return (
        db.query(TaskNode).filter(TaskNode.run_id == run_id).order_by(TaskNode.sequence.asc()).all()
    )


@app.get(f"{settings.api_prefix}/tools", response_model=list[ToolResponse])
def get_tools() -> list[ToolResponse]:
    return [
        ToolResponse(name=tool.name, description=tool.description, risk_level=tool.risk_level)
        for tool in list_tools()
    ]


@app.get(f"{settings.api_prefix}/approvals", response_model=list[ApprovalRequestResponse])
def list_approvals(db: Session = Depends(get_db)) -> list[ApprovalRequest]:
    return (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.status == ApprovalStatus.PENDING)
        .order_by(ApprovalRequest.created_at.asc())
        .all()
    )


@app.post(
    f"{settings.api_prefix}/approvals/{{approval_id}}/decision",
    response_model=ApprovalRequestResponse,
)
async def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
) -> ApprovalRequest:
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail="Approval request is already resolved")

    decision = payload.decision.strip().lower()
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")

    run = db.get(Run, approval.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Related run not found")

    approval.status = ApprovalStatus.APPROVED if decision == "approve" else ApprovalStatus.REJECTED
    approval.decision_reason = payload.reason or ""
    create_event(
        db,
        run.id,
        "approval.decided",
        f"decision={decision} reason={approval.decision_reason or 'none'}",
        actor="human",
    )

    if decision == "reject":
        run.status = RunStatus.FAILED
        create_event(db, run.id, "run.failed", "Run rejected by approval decision", actor="human")
        db.commit()
        db.refresh(approval)
        return approval

    try:
        task_nodes = (
            db.query(TaskNode)
            .filter(TaskNode.run_id == run.id)
            .order_by(TaskNode.sequence.asc())
            .all()
        )
        run.status = RunStatus.RUNNING
        create_event(db, run.id, "run.resumed", "Run resumed after approval", actor="orchestrator")
        result, task_nodes = await execute_task_graph(
            db=db,
            run=run,
            task_nodes=task_nodes,
            create_event=create_event,
        )
        run.provider = result["provider"]
        run.model = result["model"]
        run.output_text = result["text"]
        run.token_estimate = estimate_tokens(result["text"])
        preview = result["text"][:400].strip()
        create_event(db, run.id, "run.output", f"Final output preview: {preview}", actor="executor")
        if run.memory_enabled:
            store_memory(db, run, content=run.output_text[:600], kind="run_summary")
            create_event(
                db,
                run.id,
                "memory.stored",
                "Stored run output in persistent memory after approval",
                actor="memory",
            )
        run.status = RunStatus.COMPLETED
        if run.budget_exceeded and run.output_text.strip() == "":
            run.status = RunStatus.FAILED
        create_event(db, run.id, "run.completed", "Run finished after approval")

        if run.assistant_message_id:
            assistant_message = db.get(ChatMessage, run.assistant_message_id)
            if assistant_message is not None:
                assistant_message.content = run.output_text or assistant_message.content
    except Exception as exc:
        run.status = RunStatus.FAILED
        create_event(db, run.id, "run.failed", str(exc), actor="executor")

    db.commit()
    db.refresh(approval)
    return approval


@app.get(f"{settings.api_prefix}/memory", response_model=list[MemoryItemResponse])
def list_memory(db: Session = Depends(get_db)) -> list[MemoryItem]:
    return db.query(MemoryItem).order_by(MemoryItem.created_at.desc()).limit(20).all()
