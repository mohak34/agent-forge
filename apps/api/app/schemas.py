from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ApprovalStatus, RunStatus, TaskNodeStatus


class GoalCreate(BaseModel):
    goal: str
    memory_enabled: bool = False


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal: str
    memory_enabled: bool
    status: RunStatus
    provider: str
    model: str
    output_text: str
    token_estimate: int
    created_at: datetime
    updated_at: datetime | None


class TraceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    event_type: str
    actor: str
    status: str
    detail: str
    created_at: datetime


class TaskNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    title: str
    kind: str
    sequence: int
    depends_on: str
    status: TaskNodeStatus
    output_text: str
    created_at: datetime
    updated_at: datetime | None


class ToolResponse(BaseModel):
    name: str
    description: str
    risk_level: str


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    action_type: str
    reason: str
    payload: str
    status: ApprovalStatus
    decision_reason: str
    created_at: datetime
    updated_at: datetime | None


class ApprovalDecisionRequest(BaseModel):
    decision: str
    reason: str = ""


class MemoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scope_key: str
    run_id: str
    kind: str
    content: str
    created_at: datetime
