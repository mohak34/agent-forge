from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_db
from app.memory import get_recent_memory, store_memory
from app.orchestrator import execute_task_graph
from app.models import (
    AgentTemplate,
    ApprovalRequest,
    ApprovalStatus,
    MemoryItem,
    Run,
    RunStatus,
    TaskNode,
    TraceEvent,
)
from app.planner import build_task_plan
from app.schemas import (
    AgentTemplateCreate,
    AgentTemplateImport,
    AgentTemplateResponse,
    ApprovalDecisionRequest,
    ApprovalRequestResponse,
    GoalCreate,
    MemoryItemResponse,
    RunFromTemplateRequest,
    RunResponse,
    TaskNodeResponse,
    ToolResponse,
    TraceEventResponse,
)
from app.tools import list_tools

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


@app.post(f"{settings.api_prefix}/goals", response_model=RunResponse)
async def create_goal(payload: GoalCreate, db: Session = Depends(get_db)) -> Run:
    run = Run(goal=payload.goal, memory_enabled=payload.memory_enabled, status=RunStatus.QUEUED)
    db.add(run)
    db.flush()

    create_event(db, run.id, "run.created", "Goal accepted")

    nodes = build_task_plan(run)
    for node in nodes:
        db.add(node)
    db.flush()
    emit_plan_events(db, run.id, nodes)

    try:
        needs_approval, approval_reason = goal_requires_approval(payload.goal)
        if needs_approval:
            run.status = RunStatus.WAITING_APPROVAL
            request = ApprovalRequest(
                run_id=run.id,
                action_type="external_action",
                reason=approval_reason,
                payload=payload.goal,
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
        run.status = RunStatus.FAILED
        create_event(db, run.id, "run.failed", str(exc), actor="executor")

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


@app.get(f"{settings.api_prefix}/runs/{{run_id}}", response_model=RunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get(f"{settings.api_prefix}/runs/{{run_id}}/timeline", response_model=list[TraceEventResponse])
def get_timeline(run_id: str, db: Session = Depends(get_db)) -> list[TraceEvent]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.events


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
    except Exception as exc:
        run.status = RunStatus.FAILED
        create_event(db, run.id, "run.failed", str(exc), actor="executor")

    db.commit()
    db.refresh(approval)
    return approval


@app.get(f"{settings.api_prefix}/memory", response_model=list[MemoryItemResponse])
def list_memory(db: Session = Depends(get_db)) -> list[MemoryItem]:
    return db.query(MemoryItem).order_by(MemoryItem.created_at.desc()).limit(20).all()
