"""Tracked agent runner — wraps claude_agent_sdk.query() to log every action.

Intercepts the SDK message stream and records tool calls, assistant
messages, and results to the ActivityLogger.  Drop-in replacement for
calling query() directly in each agent file.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    query,
)
from claude_agent_sdk._errors import MessageParseError

from gtm.agents.activity_log import ActivityLogger

log = logging.getLogger(__name__)


def _has_sdk_mcp_servers(options: ClaudeAgentOptions) -> bool:
    """Check if options include SDK-type MCP servers.

    SDK MCP servers require the bidirectional control protocol (streaming
    mode) because the CLI needs to call back into the Python process for
    ``tools/list`` and ``tools/call``.  If we pass a plain string prompt
    the SDK uses ``--print`` mode which closes stdin immediately, making
    those callbacks impossible.
    """
    if not options.mcp_servers or not isinstance(options.mcp_servers, dict):
        return False
    return any(
        isinstance(cfg, dict) and cfg.get("type") == "sdk"
        for cfg in options.mcp_servers.values()
    )


async def _prompt_as_stream(
    prompt: str, done: asyncio.Event,
) -> AsyncIterator[dict[str, Any]]:
    """Wrap a string prompt into an async iterable for streaming mode.

    The SDK treats ``AsyncIterable`` prompts as streaming mode, which
    keeps stdin open and enables the bidirectional control protocol
    required for SDK MCP servers.

    IMPORTANT: After yielding the user message we must **block** until
    the caller signals *done*.  If this generator returns, the SDK's
    ``stream_input()`` calls ``end_input()`` which closes stdin — that
    kills the bidirectional control protocol and makes MCP tool callbacks
    impossible.
    """
    yield {
        "type": "user",
        "message": {"role": "user", "content": prompt},
    }
    # Keep the generator alive so stream_input() never calls end_input().
    # The task group will cancel this when the query finishes.
    await done.wait()


async def run_tracked_agent(
    agent_name: str,
    options: ClaudeAgentOptions,
    prompt: str,
    logger: ActivityLogger | None = None,
) -> str:
    """Run a Claude Code SDK agent with full activity tracking.

    This replaces direct ``query()`` calls in every agent file.
    It intercepts every message from the stream and logs it before
    extracting the final result text.

    Parameters
    ----------
    agent_name:
        Human-readable agent identifier (e.g. "scout", "builder").
    options:
        The ClaudeAgentOptions to pass to query().
    prompt:
        The user prompt to send to the agent.
    logger:
        Optional ActivityLogger — if None, runs without tracking
        (backwards-compatible).

    Returns
    -------
    str
        The final result/text from the agent.
    """
    if logger:
        logger.log_agent_start(
            agent_name,
            model=options.model,
            prompt_preview=prompt[:500],
            max_turns=options.max_turns,
        )

    result_text = ""
    agent_start = time.monotonic()
    message_index = 0
    tool_call_count = 0

    # SDK MCP servers need the bidirectional control protocol, which only
    # works in streaming mode.  When we pass a plain string prompt the SDK
    # uses ``--print`` mode and closes stdin immediately — the CLI can
    # never call back for tools/list or tools/call, so the MCP tools are
    # invisible to the agent.  Wrapping the prompt in an async generator
    # forces the SDK into ``--input-format stream-json`` mode.
    #
    # The generator must stay alive for the entire session — if it
    # returns, the SDK calls ``end_input()`` → closes stdin → kills the
    # control protocol.  We use an asyncio.Event to block the generator
    # until the query loop completes.
    stream_done = asyncio.Event()
    if _has_sdk_mcp_servers(options):
        log.debug(
            "[%s] SDK MCP servers detected — using streaming mode for control protocol",
            agent_name,
        )
        prompt_input: str | AsyncIterator[dict[str, Any]] = _prompt_as_stream(
            prompt, stream_done,
        )
    else:
        prompt_input = prompt

    _rate_limit_retries = 0
    _max_rate_limit_retries = 5

    # Hard timeout: scale with max_turns so the agent can't hang forever.
    # Each turn can take ~30s; add 5 min baseline for startup overhead.
    # If we hit this, it almost certainly means the SDK subprocess deadlocked.
    _max_turns = options.max_turns or 50
    _agent_timeout_secs = 300 + _max_turns * 30  # e.g. 40 turns → 25 min

    async def _run_query_once() -> None:
        """Run one query() iteration, updating outer-scope state."""
        nonlocal result_text, message_index, tool_call_count
        async for message in query(prompt=prompt_input, options=options):
            message_index += 1

            if isinstance(message, ResultMessage):
                result_text = message.result
                # Signal the stream generator to exit NOW so stream_input()
                # calls end_input() → closes stdin → CLI exits cleanly.
                # Must happen before the async for loop exits so that
                # query.close() → transport.close() → process.wait() doesn't
                # hang waiting for a subprocess that's still reading stdin.
                stream_done.set()
                if logger:
                    logger.log_decision(
                        agent_name,
                        decision="agent_result",
                        result_preview=result_text[:500] if result_text else "",
                    )
                log.info(
                    "[%s] Agent finished (%d tool calls)",
                    agent_name, tool_call_count,
                )

            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result_text = block.text
                        if logger:
                            logger.log_assistant_message(agent_name, block.text)
                        # Show a brief preview of assistant thinking
                        preview = block.text[:120].replace("\n", " ")
                        log.debug("[%s] 💬 %s", agent_name, preview)

                    elif isinstance(block, ToolUseBlock):
                        tool_call_count += 1
                        tool_name = getattr(block, "name", "unknown")
                        tool_input = getattr(block, "input", {})
                        if logger:
                            logger.log_tool_call(
                                agent_name,
                                tool_name=tool_name,
                                tool_input=tool_input,
                            )
                        # Print every tool call to the terminal (visible with -v)
                        input_preview = _safe_repr(tool_input, 50000)
                        log.info(
                            "[%s] tool #%d: %s(%s)",
                            agent_name, tool_call_count, tool_name, input_preview,
                        )

                    elif isinstance(block, ToolResultBlock):
                        tool_result_name = getattr(block, "tool_name", "unknown")
                        tool_output = getattr(block, "content", None)
                        if logger:
                            logger.log_tool_call(
                                agent_name,
                                tool_name=tool_result_name,
                                tool_input=None,
                                tool_output=tool_output,
                            )
                        is_error = getattr(block, "is_error", False)
                        if is_error:
                            log.warning(
                                "[%s] tool %s returned ERROR: %s",
                                agent_name, tool_result_name,
                                _safe_repr(tool_output, 300),
                            )
                        else:
                            output_preview = _safe_repr(tool_output, 120)
                            log.debug(
                                "[%s] tool %s result: %s",
                                agent_name, tool_result_name, output_preview,
                            )

                    else:
                        block_type = type(block).__name__
                        if logger and block_type not in ("TextBlock",):
                            logger.log_tool_call(
                                agent_name,
                                tool_name=f"__block:{block_type}",
                                tool_input=_safe_repr(block),
                            )

    try:
        while True:
            try:
                await asyncio.wait_for(_run_query_once(), timeout=_agent_timeout_secs)
                break  # query completed without rate limit interruption
            except asyncio.TimeoutError:
                log.error(
                    "[%s] Agent timed out after %ds (%d tool calls so far) — "
                    "likely SDK deadlock; aborting",
                    agent_name, _agent_timeout_secs, tool_call_count,
                )
                stream_done.set()
                raise RuntimeError(
                    f"Agent '{agent_name}' timed out after {_agent_timeout_secs}s "
                    f"(max_turns={_max_turns}). Possible SDK subprocess deadlock."
                )
            except MessageParseError as e:
                if "rate_limit_event" in str(e) and _rate_limit_retries < _max_rate_limit_retries:
                    _rate_limit_retries += 1
                    wait_secs = 60 * _rate_limit_retries
                    log.warning(
                        "[%s] Claude API rate limit hit — waiting %ds (attempt %d/%d)",
                        agent_name, wait_secs, _rate_limit_retries, _max_rate_limit_retries,
                    )
                    await asyncio.sleep(wait_secs)
                    # Re-wrap prompt for streaming mode if needed
                    if _has_sdk_mcp_servers(options):
                        stream_done2 = asyncio.Event()
                        prompt_input = _prompt_as_stream(prompt, stream_done2)
                        stream_done = stream_done2
                    continue
                raise
    finally:
        # Signal the stream generator to exit so stream_input() can finish
        # cleanly.  Without this, the generator blocks forever on done.wait()
        # and the task group never completes.
        stream_done.set()

    elapsed_ms = int((time.monotonic() - agent_start) * 1000)

    if logger:
        logger.log_agent_end(
            agent_name,
            total_messages=message_index,
            duration_ms=elapsed_ms,
            result_length=len(result_text) if result_text else 0,
        )

    return result_text


def _safe_repr(obj: Any, max_len: int = 500) -> str:
    """Safe string representation of an unknown object."""
    try:
        s = repr(obj)
    except Exception:
        s = f"<{type(obj).__name__}>"
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s
