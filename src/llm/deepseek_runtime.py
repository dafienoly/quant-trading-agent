"""DeepSeek Agent Runtime — unified async-first calling framework.

Wraps OpenAI-compatible SDK calls with:
- thinking mode
- JSON Output
- multi-round conversation
- tool call loop
- usage tracking
- structured error handling

All Agent code must go through this runtime instead of calling
``chat.completions.create()`` directly.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

from loguru import logger

from src.llm.conversation import AgentConversation
from src.llm.model_router import ModelRouter
from src.llm.schemas import DeepSeekRequest, DeepSeekResult, get_profile
from src.llm.tool_registry import get_tool_registry
from src.llm.usage import get_usage_tracker


class DeepSeekRuntime:
    """Unified calling framework for DeepSeek / OpenAI-compatible APIs.

    Usage::

        runtime = DeepSeekRuntime()
        result = await runtime.chat_json_async(
            DeepSeekRequest(
                profile="bugfix_analysis",
                schema_name="bugfix_analysis",
                system_prompt="...",
                user_prompt="...",
                tools=["read_feedback_bug", "search_project_text"],
            )
        )
        if result.status == "ok":
            data = result.data
    """

    def __init__(
        self,
        router: ModelRouter | None = None,
    ) -> None:
        self._router = router or ModelRouter()
        self._config = self._router.get_config()
        self._semaphore: asyncio.Semaphore | None = None

    # ------------------------------------------------------------------
    # Public API — async
    # ------------------------------------------------------------------

    async def chat_json_async(self, request: DeepSeekRequest) -> DeepSeekResult:
        """Call DeepSeek with JSON Output enabled. Returns validated result."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrency())

        async with self._semaphore:
            return await self._call_with_retry(request)

    async def chat_json_async_with_conversation(
        self,
        request: DeepSeekRequest,
        conversation: AgentConversation,
    ) -> DeepSeekResult:
        """Call DeepSeek with a managed conversation for multi-round flow."""
        conversation.add_system(request.system_prompt)
        conversation.add_user(request.user_prompt)
        request.conversation_id = conversation.conversation_id

        result = await self.chat_json_async(request)

        if result.status == "ok" and result.data:
            conversation.add_assistant(
                json.dumps(result.data, ensure_ascii=False),
            )
            conversation.save()
        return result

    # ------------------------------------------------------------------
    # Public API — sync wrapper
    # ------------------------------------------------------------------

    def chat_json(self, request: DeepSeekRequest) -> DeepSeekResult:
        """Synchronous convenience wrapper around ``chat_json_async``.

        Uses ``asyncio.run()``. Prefer the async version in async contexts.
        """
        return _run_async(self.chat_json_async(request))

    # ------------------------------------------------------------------
    # Internal: core call logic
    # ------------------------------------------------------------------

    async def _call_with_retry(self, request: DeepSeekRequest) -> DeepSeekResult:
        """Call DeepSeek with retry logic for transient errors."""
        profile = self._resolve_profile(request)
        api_key = os.getenv(self._config.api_key_env, "").strip()
        start_time = time.time()

        # --- Pre-flight checks ---
        if not api_key:
            return DeepSeekResult(
                status="unavailable",
                model=self._config.model,
                error={"reason": "missing_api_key", "env_var": self._config.api_key_env},
            )

        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError:
            return DeepSeekResult(
                status="unavailable",
                model=self._config.model,
                error={
                    "reason": "openai_package_not_installed",
                    "message": "pip install openai>=1.0",
                },
            )

        client = AsyncOpenAI(api_key=api_key, base_url=self._config.api_base)
        last_error: str | None = None

        for attempt in range(profile.max_retries):
            try:
                result = await self._single_call(client, request, profile)
                if result.status == "ok":
                    self._track_usage(result, profile, start_time)
                return result

            except asyncio.TimeoutError:
                last_error = "timeout"
                logger.warning("DeepSeek call timeout (attempt {}/{}): {}",
                               attempt + 1, profile.max_retries, request.profile)
                if attempt < profile.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue

            except Exception as exc:
                last_error = str(exc)
                logger.warning("DeepSeek call failed (attempt {}/{}): {}",
                               attempt + 1, profile.max_retries, exc)
                if attempt < profile.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue

        # All retries exhausted
        error_detail = {
            "reason": "max_retries_exceeded",
            "last_error": last_error,
            "attempts": profile.max_retries,
        }
        status = "timeout" if last_error == "timeout" else "api_error"
        result = DeepSeekResult(
            status=status,
            model=self._config.model,
            error=error_detail,
        )
        self._track_usage(result, profile, start_time)
        return result

    async def _single_call(
        self,
        client: Any,
        request: DeepSeekRequest,
        profile: Any,
    ) -> DeepSeekResult:
        """Execute a single API call (may include tool rounds)."""
        from openai import APIError, APITimeoutError

        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": self._build_messages(request),
            "max_tokens": 4096,
        }

        # JSON Output (always on for this runtime)
        kwargs["response_format"] = {"type": "json_object"}

        # Thinking mode
        kwargs["extra_body"] = {
            "thinking": {
                "type": "enabled" if profile.thinking_enabled else "disabled",
            },
        }
        if profile.thinking_enabled:
            kwargs["reasoning_effort"] = profile.reasoning_effort

        # Tools
        tool_names = request.tools
        if tool_names and profile.allow_tools:
            registry = get_tool_registry()
            kwargs["tools"] = registry.to_openai_tools(tool_names)

        # Execute with timeout
        coro = client.chat.completions.create(**kwargs)
        response = await asyncio.wait_for(coro, timeout=profile.timeout_seconds)

        # Extract reasoning content if present (for internal use only)
        reasoning_content = getattr(response.choices[0].message, "reasoning_content", None)
        if reasoning_content and profile.thinking_enabled:
            logger.debug("Thinking mode output available for profile={}", profile.name)

        # Tool call loop
        raw_data = response.choices[0].message.content or ""
        tool_calls_raw = getattr(response.choices[0].message, "tool_calls", None)

        round_count = 0
        all_tool_calls: list[dict[str, Any]] = []

        while tool_calls_raw and round_count < profile.max_tool_rounds:
            if not profile.allow_tools:
                return DeepSeekResult(
                    status="tool_error",
                    model=self._config.model,
                    error={"reason": "tools_not_allowed_for_profile", "profile": profile.name},
                )

            round_count += 1
            # Append assistant message with tool_calls
            call_list = _convert_tool_calls(tool_calls_raw)
            all_tool_calls.extend(call_list)

            # Prepare tool result messages for next round
            tool_messages = self._execute_tools(call_list)
            kwargs["messages"].append({"role": "assistant", "content": None, "tool_calls": call_list})
            kwargs["messages"].extend(tool_messages)

            # Next API call
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(**kwargs),
                    timeout=profile.timeout_seconds,
                )
            except (APITimeoutError, asyncio.TimeoutError):
                return DeepSeekResult(
                    status="tool_error",
                    model=self._config.model,
                    error={"reason": "tool_round_timeout", "round": round_count},
                    tool_calls=all_tool_calls,
                )
            except APIError as exc:
                return DeepSeekResult(
                    status="api_error",
                    model=self._config.model,
                    error={"reason": "tool_round_api_error", "detail": str(exc)},
                    tool_calls=all_tool_calls,
                )

            raw_data = response.choices[0].message.content or ""
            tool_calls_raw = getattr(response.choices[0].message, "tool_calls", None)

        if tool_calls_raw and round_count >= profile.max_tool_rounds:
            return DeepSeekResult(
                status="tool_error",
                model=self._config.model,
                error={
                    "reason": "max_tool_rounds_exceeded",
                    "max_rounds": profile.max_tool_rounds,
                },
                tool_calls=all_tool_calls,
            )

        # Parse JSON
        if not raw_data or not raw_data.strip():
            return DeepSeekResult(
                status="invalid_response",
                model=self._config.model,
                error={"reason": "empty_content"},
                tool_calls=all_tool_calls,
            )

        parsed, parse_error = self._parse_json(raw_data)
        if parse_error:
            return DeepSeekResult(
                status="invalid_response",
                model=self._config.model,
                error={"reason": parse_error, "raw_excerpt": raw_data[:300]},
                tool_calls=all_tool_calls,
            )

        # Wrap result
        usage = get_usage_tracker().extract_usage_from_response(response)
        return DeepSeekResult(
            status="ok",
            data=parsed,
            provider=self._config.provider,
            model=self._config.model,
            conversation_id=request.conversation_id,
            usage=usage,
            tool_calls=all_tool_calls,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_profile(self, request: DeepSeekRequest) -> Any:
        """Resolve and validate the task profile."""
        try:
            return get_profile(request.profile)
        except KeyError:
            logger.warning("Unknown profile {!r}, using default", request.profile)
            from src.llm.schemas import LLMTaskProfile
            return LLMTaskProfile(name=request.profile)

    def _build_messages(self, request: DeepSeekRequest) -> list[dict[str, Any]]:
        """Build the messages list for the API call.

        If a conversation_id is given, try to load existing conversation.
        """
        if request.conversation_id:
            conv = AgentConversation.load(request.conversation_id)
            if conv and conv.messages:
                return conv.messages

        return [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

    def _execute_tools(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Execute a list of tool calls and return tool result messages.

        Only read-only tools are allowed.
        """
        registry = get_tool_registry()
        messages: list[dict[str, Any]] = []

        for tc in tool_calls:
            name = tc.get("function", {}).get("name", "")
            raw_args = tc.get("function", {}).get("arguments", "{}")
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                arguments = {}

            tool_id = tc.get("id", "")
            result = registry.execute(name, arguments)

            if result.get("error"):
                content = f"Error: {result['error']}"
            else:
                content = result.get("result", "")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": content[:4000],
            })

        return messages

    @staticmethod
    def _parse_json(raw: str) -> tuple[dict[str, Any] | None, str | None]:
        """Parse JSON, with fallback for markdown-wrapped JSON."""
        raw = raw.strip()
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data, None
        except json.JSONDecodeError:
            pass

        # Try markdown code block extraction
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict):
                    return data, None
            except json.JSONDecodeError:
                pass

        return None, "parse_failed"

    @staticmethod
    def _max_concurrency() -> int:
        """Read max concurrency from env or default to 2."""
        raw = os.getenv("LLM_MAX_CONCURRENCY", "2")
        try:
            return max(1, int(raw))
        except (ValueError, TypeError):
            return 2

    def _track_usage(self, result: DeepSeekResult, profile: Any, start_time: float) -> None:
        """Record usage metrics."""
        tracker = get_usage_tracker()
        record = tracker.record(
            profile=profile.name,
            model=result.model,
            start_time=start_time,
            end_time=time.time(),
            prompt_tokens=result.usage.get("prompt_tokens"),
            completion_tokens=result.usage.get("completion_tokens"),
            total_tokens=result.usage.get("total_tokens"),
            prompt_cache_hit_tokens=result.usage.get("prompt_cache_hit_tokens"),
            prompt_cache_miss_tokens=result.usage.get("prompt_cache_miss_tokens"),
            tool_call_count=len(result.tool_calls),
            tool_round_count=0,
            status=result.status,
        )
        if result.status == "ok":
            tracker.log_usage(record)


def _convert_tool_calls(tool_calls_raw: Any) -> list[dict[str, Any]]:
    """Convert OpenAI SDK tool call objects to plain dicts."""
    results: list[dict[str, Any]] = []
    for tc in tool_calls_raw:
        results.append({
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        })
    return results


def _run_async(coro: Any) -> Any:
    """Run an async coroutine synchronously."""
    try:
        _ = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Running in an existing event loop — create a new one in a thread
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()
