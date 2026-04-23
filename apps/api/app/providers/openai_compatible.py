import httpx

from app.providers.base import ChatMessage, ChatProvider, ChatResult, ToolCall


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

    async def chat(self, messages: list[ChatMessage], tools: list[dict] | None = None) -> ChatResult:
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

        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()

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

        return ChatResult(
            provider=self.name,
            model=self.model,
            output_text=output,
            raw_response=data,
            tool_calls=tool_calls,
        )
