from app.providers.base import ChatMessage
from app.providers.responses import parse_responses_output, to_responses_request

TOOLS = [
    {
        "type": "function",
        "function": {"name": "search_web", "description": "d", "parameters": {"type": "object"}},
    }
]


def test_request_maps_system_tool_calls_and_outputs() -> None:
    messages = [
        ChatMessage("system", "be brief"),
        ChatMessage("user", "q"),
        ChatMessage(
            "assistant",
            "",
            tool_calls=[
                {"id": "c1", "type": "function", "function": {"name": "search_web", "arguments": "{}"}}
            ],
        ),
        ChatMessage("tool", "result", tool_call_id="c1", name="search_web"),
    ]
    payload = to_responses_request("m", messages, TOOLS)
    assert payload["instructions"] == "be brief"
    assert payload["input"] == [
        {"role": "user", "content": "q"},
        {"type": "function_call", "call_id": "c1", "name": "search_web", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "c1", "output": "result"},
    ]
    assert payload["tools"] == [
        {"type": "function", "name": "search_web", "description": "d", "parameters": {"type": "object"}}
    ]


def test_parse_reads_text_calls_and_usage() -> None:
    data = {
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "function_call", "id": "fc", "call_id": "c2", "name": "calculator", "arguments": "{}"},
            {"type": "message", "content": [{"type": "output_text", "text": "hi"}]},
        ],
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }
    text, calls, tokens_in, tokens_out = parse_responses_output(data)
    assert (text, tokens_in, tokens_out) == ("hi", 12, 3)
    assert calls is not None and calls[0].id == "c2" and calls[0].function_name == "calculator"
