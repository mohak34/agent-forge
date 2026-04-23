import json
import logging
import traceback

from app.config import settings
from app.providers.base import ChatMessage
from app.providers.registry import build_provider_registry
from app.tools import invoke_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5


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

    system_message = "You are the baseline agent in agent-forge. Answer clearly and concisely."
    messages = [
        ChatMessage(role="system", content=system_message),
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
) -> dict:
    system_message = "You are the baseline agent in agent-forge. Answer clearly and concisely."
    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=system_message),
        ChatMessage(role="user", content=goal),
    ]

    providers = build_provider_registry()
    provider_name = provider_override or settings.default_model_provider
    provider = providers.get(provider_name)

    if provider is None:
        raise ValueError(f"Unknown provider: {provider_name}")

    if model_override is not None:
        provider.model = model_override

    iteration = 0
    final_result = None

    while iteration < max_iterations:
        try:
            result = await provider.chat(messages, tools=tools)
        except Exception as exc:
            logger.error(f"Provider chat failed in tool loop iteration {iteration}: {exc}")
            logger.error(traceback.format_exc())
            if tools and iteration == 0:
                logger.warning("Tool call failed, falling back to plain text generation")
                try:
                    result = await provider.chat(messages, tools=None)
                except Exception as fallback_exc:
                    logger.error(f"Fallback plain text generation also failed: {fallback_exc}")
                    logger.error(traceback.format_exc())
                    raise fallback_exc
            else:
                raise exc

        if not result.tool_calls:
            final_result = {
                "provider": result.provider,
                "model": result.model,
                "text": result.output_text,
                "tool_calls": None,
            }
            break

        assistant_tool_calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function_name,
                    "arguments": tc.arguments,
                },
            }
            for tc in result.tool_calls
        ]
        messages.append(
            ChatMessage(
                role="assistant",
                content=result.output_text or "",
                tool_calls=assistant_tool_calls,
            )
        )

        tool_outputs: list[str] = []
        for tc in result.tool_calls:
            tool_name = tc.function_name
            tool_call_id = tc.id
            try:
                args = json.loads(tc.arguments)
            except Exception:
                args = {}

            if tool_name == "search_web":
                payload = args.get("query", "")
            elif tool_name == "fetch_url":
                payload = args.get("url", "")
            elif tool_name == "calculator":
                payload = args.get("expression", "")
            else:
                payload = ""

            if on_tool_call:
                await on_tool_call(tool_name, payload)

            try:
                tool_output = invoke_tool(tool_name, payload)
            except Exception as exc:
                tool_output = f"Error: {exc}"

            tool_outputs.append(f"Tool {tool_name} result: {tool_output}")
            messages.append(
                ChatMessage(
                    role="tool",
                    content=tool_output,
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )

        messages.append(
            ChatMessage(
                role="user",
                content="Please answer the user's original question using the tool results above.",
            )
        )
        iteration += 1
        final_result = {
            "provider": result.provider,
            "model": result.model,
            "text": result.output_text,
            "tool_calls": result.tool_calls,
        }

    if final_result is None:
        final_result = {
            "provider": provider_override or settings.default_model_provider,
            "model": model_override or "unknown",
            "text": "No response generated.",
            "tool_calls": None,
        }

    return final_result
