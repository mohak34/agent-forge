from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ChatMessage:
    role: str
    content: str
    tool_call_id: str = ""
    name: str = ""
    tool_calls: list[dict] | None = None


@dataclass
class ToolCall:
    id: str
    function_name: str
    arguments: str


@dataclass
class ChatResult:
    provider: str
    model: str
    output_text: str
    raw_response: dict
    tool_calls: list[ToolCall] | None = None


class ChatProvider(Protocol):
    name: str

    async def chat(self, messages: list[ChatMessage], tools: list[dict] | None = None) -> ChatResult: ...
