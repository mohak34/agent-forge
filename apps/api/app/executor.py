import json
import logging
import traceback

from app.config import settings
from app.providers.base import ChatMessage, ChatResult, Usage
from app.providers.registry import build_provider_registry
from app.tools import invoke_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5
DEFAULT_SYSTEM = "You are the baseline agent in agent-forge. Answer clearly and concisely."
TOOL_ARG = {"search_web": "query", "fetch_url": "url", "calculator": "expression"}


async def run_single_agent(
    goal: str,
    provider_override: str | None = None,
    model_override: str | None = None,
    tools: list[dict] | None = None,
) -> dict:
    if settings.mock_mode:
        return {
            "provider": provider_override or "mock",
            "model": model_override or "mock-baseline",
            "text": f"Mock execution complete for goal: {goal}",
            "tool_calls": None,
        }

    providers = build_provider_registry()
    provider_name = provider_override or settings.default_model_provider
    provider = providers.get(provider_name)

    if provider is None:
        raise ValueError(f"Unknown provider: {provider_name}")

    messages = [
        ChatMessage(role="system", content=DEFAULT_SYSTEM),
        ChatMessage(role="user", content=goal),
    ]

    if model_override is not None:
        provider.model = model_override

    try:
        result = await provider.chat(messages, tools=tools)
    except Exception as exc:
        logger.error(f"Provider chat failed: {exc}")
        logger.error(traceback.format_exc())
        raise

    return {
        "provider": result.provider,
        "model": result.model,
        "text": result.output_text,
        "tool_calls": result.tool_calls,
    }


async def run_agent_with_tools(
    goal: str,
    provider_override: str | None = None,
    model_override: str | None = None,
    tools: list[dict] | None = None,
    max_iterations: int = MAX_TOOL_ITERATIONS,
    on_tool_call=None,
    system: str = DEFAULT_SYSTEM,
    usage: Usage | None = None,
) -> dict:
    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=goal),
    ]

    providers = build_provider_registry()
    provider_name = provider_override or settings.default_model_provider
    provider = providers.get(provider_name)

    if provider is None:
        raise ValueError(f"Unknown provider: {provider_name}")

    if model_override is not None:
        provider.model = model_override

    async def call(active_tools: list[dict] | None) -> ChatResult:
        result = await provider.chat(messages, tools=active_tools)
        if usage is not None:
            usage.add(result)
        return result

    for iteration in range(max_iterations):
        try:
            result = await call(tools)
        except Exception as exc:
            logger.error(f"Provider chat failed in tool loop iteration {iteration}: {exc}")
            if not (tools and iteration == 0):
                raise
            logger.warning("Tool call failed, falling back to plain text generation")
            result = await call(None)

        if not result.tool_calls:
            return {
                "provider": result.provider,
                "model": result.model,
                "text": result.output_text,
                "tool_calls": None,
            }

        messages.append(
            ChatMessage(
                role="assistant",
                content=result.output_text or "",
                tool_calls=[
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function_name, "arguments": tc.arguments},
                    }
                    for tc in result.tool_calls
                ],
            )
        )

        for tc in result.tool_calls:
            try:
                args = json.loads(tc.arguments)
            except Exception:
                args = {}
            payload = str(args.get(TOOL_ARG.get(tc.function_name, ""), ""))

            if on_tool_call:
                await on_tool_call(tc.function_name, payload)

            try:
                tool_output = invoke_tool(tc.function_name, payload)
            except Exception as exc:
                tool_output = f"Error: {exc}"

            messages.append(
                ChatMessage(
                    role="tool",
                    content=tool_output,
                    tool_call_id=tc.id,
                    name=tc.function_name,
                )
            )

    # Out of tool rounds: force a plain answer from what was gathered so far.
    messages.append(
        ChatMessage(role="user", content="Answer now using the tool results above. No more tools.")
    )
    result = await call(None)
    return {
        "provider": result.provider,
        "model": result.model,
        "text": result.output_text or "No response generated.",
        "tool_calls": None,
    }
