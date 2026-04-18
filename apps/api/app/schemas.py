from datetime import datetime
from typing import Literal

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
    budget_limit_usd: float
    budget_used_usd: float
    budget_exceeded: bool
    thread_id: str | None
    user_message_id: str | None
    assistant_message_id: str | None
    turn_index: int
    provider: str
    model: str
    output_text: str
    token_estimate: int
    created_at: datetime
    updated_at: datetime | None


class RunHistoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal: str
    status: RunStatus
    memory_enabled: bool
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
    routed_provider: str
    routed_model: str
    token_estimate: int
    cost_estimate_usd: float
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


class AgentTemplateCreate(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0.0"
    config_json: str = "{}"


class AgentTemplateImport(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0.0"
    config_json: str


class AgentTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    version: str
    config_json: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime | None


class RunFromTemplateRequest(BaseModel):
    goal: str
    memory_enabled: bool = False


class ChatThreadCreate(BaseModel):
    title: str = "New chat"
    memory_enabled: bool = False
    template_id: str | None = None


class ChatThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    memory_enabled: bool
    template_id: str | None
    last_run_id: str | None
    created_at: datetime
    updated_at: datetime | None


class ChatMessageCreate(BaseModel):
    content: str
    route_mode: Literal["auto", "direct"] = "auto"


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    role: str
    content: str
    turn_index: int
    run_id: str | None
    created_at: datetime


class ChatThreadDetailResponse(BaseModel):
    thread: ChatThreadResponse
    messages: list[ChatMessageResponse]


class ChatTurnResponse(BaseModel):
    thread: ChatThreadResponse
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse | None = None
    run: RunResponse | None = None
