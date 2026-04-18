from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    goal: Mapped[str] = mapped_column(Text)
    memory_enabled: Mapped[bool] = mapped_column(default=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.QUEUED)
    budget_limit_usd: Mapped[float] = mapped_column(Float, default=0.05)
    budget_used_usd: Mapped[float] = mapped_column(Float, default=0.0)
    budget_exceeded: Mapped[bool] = mapped_column(Boolean, default=False)
    thread_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="SET NULL"), index=True, nullable=True
    )
    user_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assistant_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    turn_index: Mapped[int] = mapped_column(Integer, default=0)
    provider: Mapped[str] = mapped_column(String(50), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    output_text: Mapped[str] = mapped_column(Text, default="")
    token_estimate: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    events: Mapped[list["TraceEvent"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="TraceEvent.created_at",
    )
    thread: Mapped["ChatThread | None"] = relationship(back_populates="runs")


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    actor: Mapped[str] = mapped_column(String(100), default="system")
    status: Mapped[str] = mapped_column(String(50), default="ok")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[Run] = relationship(back_populates="events")


class TaskNodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class TaskNode(Base):
    __tablename__ = "task_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(80), default="generic")
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    depends_on: Mapped[str] = mapped_column(Text, default="")
    routed_provider: Mapped[str] = mapped_column(String(50), default="")
    routed_model: Mapped[str] = mapped_column(String(120), default="")
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[TaskNodeStatus] = mapped_column(
        Enum(TaskNodeStatus), default=TaskNodeStatus.PENDING
    )
    output_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.PENDING
    )
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scope_key: Mapped[str] = mapped_column(String(120), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(80), default="summary")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentTemplate(Base):
    __tablename__ = "agent_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(40), default="1.0.0")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(180), default="New chat")
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    template_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    last_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    runs: Mapped[list[Run]] = relationship(back_populates="thread", foreign_keys=[Run.thread_id])
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    summary: Mapped["ThreadSummary | None"] = relationship(
        back_populates="thread",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    turn_index: Mapped[int] = mapped_column(Integer, default=0)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    thread: Mapped[ChatThread] = relationship(back_populates="messages")


class ThreadSummary(Base):
    __tablename__ = "thread_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), unique=True, index=True
    )
    summary_text: Mapped[str] = mapped_column(Text, default="")
    summarized_until_turn: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    thread: Mapped[ChatThread] = relationship(back_populates="summary")
