"""Provider for the OpenAI Responses API (POST /responses), used by OpenCode Zen.

The rest of the app speaks chat-completions messages, so this module translates them to
Responses input items and back.
"""

from app import cache
from app.providers.base import ChatMessage, ChatProvider, ChatResult, ToolCall
from app.providers.http import post_json


def to_responses_request(model: str, messages: list[ChatMessage], tools: list[dict] | None) -> dict:
    instructions = "\n\n".join(m.content for m in messages if m.role == "system")
    items: list[dict] = []
    for m in messages:
        if m.role in {"user", "assistant"} and m.content:
            items.append({"role": m.role, "content": m.content})
        for tc in m.tool_calls or []:
            items.append(
                {
                    "type": "function_call",
                    "call_id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                }
            )
        if m.role == "tool":
            items.append(
                {"type": "function_call_output", "call_id": m.tool_call_id, "output": m.content}
            )

    payload: dict = {"model": model, "input": items}
    if instructions:
        payload["instructions"] = instructions
    if tools:
        payload["tools"] = [{"type": "function", **t["function"]} for t in tools]
        payload["parallel_tool_calls"] = False
    return payload


def parse_responses_output(data: dict) -> tuple[str, list[ToolCall] | None, int, int]:
    """Returns (text, tool_calls, input_tokens, output_tokens)."""
    texts: list[str] = []
    calls: list[ToolCall] = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            texts += [c["text"] for c in item.get("content", []) if c.get("type") == "output_text"]
        elif item.get("type") == "function_call":
            calls.append(ToolCall(item["call_id"], item["name"], item.get("arguments", "{}")))
    usage = data.get("usage") or {}
    return (
        "".join(texts),
        calls or None,
        int(usage.get("input_tokens", 0)),
        int(usage.get("output_tokens", 0)),
    )


class ResponsesProvider(ChatProvider):
    def __init__(self, name: str, base_url: str, model: str, api_key: str) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    async def chat(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> ChatResult:
        payload = to_responses_request(self.model, messages, tools)
        key = cache.make_key("responses", self.base_url, payload)
        data = cache.get(key)
        if not isinstance(data, dict):
            headers = {"Authorization": f"Bearer {self.api_key}"}
            data = await post_json(f"{self.base_url}/responses", payload, headers, self.name)
            cache.put(key, data)

        text, tool_calls, input_tokens, output_tokens = parse_responses_output(data)
        return ChatResult(
            provider=self.name,
            model=self.model,
            output_text=text,
            raw_response=data,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
