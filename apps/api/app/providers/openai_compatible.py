from app import cache
from app.providers.base import ChatMessage, ChatProvider, ChatResult, ToolCall
from app.providers.http import post_json


class OpenAICompatibleProvider(ChatProvider):
    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key: str = "",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.extra_headers = extra_headers or {}

    async def chat(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> ChatResult:
        payload_messages = []
        for m in messages:
            msg = {"role": m.role, "content": m.content}
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            payload_messages.append(msg)

        payload = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": 0.2,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            payload["parallel_tool_calls"] = False

        key = cache.make_key("chat", self.base_url, payload)
        data = cache.get(key)
        if not isinstance(data, dict):
            data = await self._post(payload)
            cache.put(key, data)

        output = ""
        tool_calls = None
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            output = message.get("content", "") or ""
            raw_tool_calls = message.get("tool_calls")
            if raw_tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.get("id", ""),
                        function_name=tc.get("function", {}).get("name", ""),
                        arguments=tc.get("function", {}).get("arguments", ""),
                    )
                    for tc in raw_tool_calls
                ]

        usage = data.get("usage") or {}
        return ChatResult(
            provider=self.name,
            model=self.model,
            output_text=output,
            raw_response=data,
            tool_calls=tool_calls,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )

    async def _post(self, payload: dict) -> dict:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return await post_json(f"{self.base_url}/chat/completions", payload, headers, self.name)
