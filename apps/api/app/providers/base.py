from dataclasses import dataclass
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
    input_tokens: int = 0
    output_tokens: int = 0


# Running token count for one agent run, summed across every LLM call it makes.
@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, result: ChatResult) -> None:
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self.calls += 1


class ChatProvider(Protocol):
    name: str
    model: str

    async def chat(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> ChatResult: ...
