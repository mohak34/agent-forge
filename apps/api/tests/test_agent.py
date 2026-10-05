import asyncio

from app import agent, executor
from app.planner import parse_plan
from app.providers.base import ChatMessage, ChatResult, ToolCall, Usage


def test_parse_plan_reads_json_and_appends_writing_step() -> None:
    text = 'Sure: {"steps": [{"title": "Find X", "kind": "research"}, {"title": "Compare", "kind": "analysis"}]}'
    steps = parse_plan(text)
    assert [s.kind for s in steps] == ["research", "analysis", "writing"]


def test_parse_plan_falls_back_on_garbage() -> None:
    assert [s.kind for s in parse_plan("no json here")] == ["research", "analysis", "writing"]


# Scripted provider: plans two steps, makes one tool call in the research step, then answers.
class FakeProvider:
    name = "groq"
    model = "openai/gpt-oss-20b"

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages: list[ChatMessage], tools: list[dict] | None = None) -> ChatResult:
        self.calls += 1
        system = messages[0].content
        tool_calls = None
        if "plan work" in system:
            text = '{"steps": [{"title": "Look it up", "kind": "research"}, {"title": "Answer", "kind": "writing"}]}'
        elif tools and messages[-1].role == "user":
            text, tool_calls = "", [ToolCall("t1", "calculator", '{"expression": "6*7"}')]
        else:
            text = f"answer from: {messages[-1].content[:40]}"
        return ChatResult("groq", self.model, text, {}, tool_calls, input_tokens=10, output_tokens=5)


def test_run_orchestrated_plans_runs_tools_and_counts_usage(monkeypatch) -> None:
    fake = FakeProvider()
    monkeypatch.setattr(executor, "build_provider_registry", lambda: {"groq": fake})
    usage = Usage()
    answer = asyncio.run(agent.run_orchestrated("What is 6*7?", "openai/gpt-oss-20b", usage))
    # plan (1) + research step tool call and follow-up (2) + writing step (1)
    assert fake.calls == 4
    assert usage == Usage(input_tokens=40, output_tokens=20, calls=4)
    assert answer.startswith("answer from:")
