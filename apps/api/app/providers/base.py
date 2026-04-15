from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatResult:
    provider: str
    model: str
    output_text: str
    raw_response: dict


class ChatProvider(Protocol):
    name: str

    async def chat(self, messages: list[ChatMessage]) -> ChatResult: ...
