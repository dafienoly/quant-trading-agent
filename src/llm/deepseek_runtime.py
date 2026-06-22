"""统一 DeepSeek async-first Runtime。"""

from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import inspect
import json
import threading
import time
import weakref
from dataclasses import dataclass, replace
from typing import Any, Awaitable, Callable

from loguru import logger
from pydantic import ValidationError

from src.llm.context_cache import ContextPrefixCache
from src.llm.conversation import AgentConversation, sanitize_text
from src.llm.model_router import ModelRouter
from src.llm.schemas import (
    DeepSeekRequest,
    DeepSeekResult,
    LLMTaskProfile,
    get_profile,
    schema_json,
    validate_schema,
)
from src.llm.tool_registry import ToolRegistry, get_tool_registry
from src.llm.usage import UsageTracker, get_usage_tracker


ClientFactory = Callable[..., Any]
SleepFunc = Callable[[float], Awaitable[None]]


@dataclass
class _CallOutcome:
    result: DeepSeekResult
    messages: list[dict[str, Any]]


class _InvalidResponseError(Exception):
    pass


class DeepSeekRuntime:
    """封装 DeepSeek JSON、Thinking、工具、重试和观测能力。"""

    def __init__(
        self,
        router: ModelRouter | None = None,
        *,
        client_factory: ClientFactory | None = None,
        tool_registry: ToolRegistry | None = None,
        context_cache: ContextPrefixCache | None = None,
        usage_tracker: UsageTracker | None = None,
        sleep_func: SleepFunc = asyncio.sleep,
    ) -> None:
        self.router = router or ModelRouter()
        self.config = self.router.get_config()
        self.client_factory = client_factory
        self.tool_registry = tool_registry or get_tool_registry()
        self.context_cache = context_cache or ContextPrefixCache()
        self.usage_tracker = usage_tracker or get_usage_tracker()
        self.sleep_func = sleep_func
        self._semaphores: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, asyncio.Semaphore
        ] = weakref.WeakKeyDictionary()
        self._semaphore_lock = threading.Lock()

    async def chat_json_async(self, request: DeepSeekRequest) -> DeepSeekResult:
        conversation: AgentConversation | None = None
        if request.conversation_id:
            conversation = AgentConversation.load(request.conversation_id)
            if conversation is None:
                conversation = AgentConversation(
                    profile=request.profile,
                    conversation_id=request.conversation_id,
                )
        return await self._chat_json_async(request, conversation)

    async def chat_json_async_with_conversation(
        self,
        request: DeepSeekRequest,
        conversation: AgentConversation,
    ) -> DeepSeekResult:
        return await self._chat_json_async(request, conversation)

    def chat_json(self, request: DeepSeekRequest) -> DeepSeekResult:
        """同步兼容入口；异步调用方应使用 ``chat_json_async``。"""

        return _run_sync(self.chat_json_async(request))

    async def _chat_json_async(
        self,
        request: DeepSeekRequest,
        conversation: AgentConversation | None,
    ) -> DeepSeekResult:
        if conversation is not None and request.conversation_id != conversation.conversation_id:
            request = request.model_copy(update={"conversation_id": conversation.conversation_id})
        started = time.monotonic()
        profile, preflight_error = self._preflight(request, conversation)
        if preflight_error is not None:
            self._record(preflight_error, request.profile, started, attempts=0, tool_rounds=0)
            return preflight_error
        assert profile is not None

        api_key = self._api_key()
        if not api_key:
            result = self._error_result(
                "unavailable",
                {"reason": "missing_api_key", "env_var": self.config.api_key_env},
                request,
            )
            self._record(result, profile.name, started, attempts=0, tool_rounds=0)
            return result

        try:
            base_messages = self._build_messages(request, profile, conversation)
        except Exception as exc:
            logger.warning("准备 LLM 上下文失败 error_type={}", type(exc).__name__)
            result = self._error_result(
                "api_error",
                {"reason": "context_preparation_failed", "error_type": type(exc).__name__},
                request,
            )
            self._record(result, profile.name, started, attempts=0, tool_rounds=0)
            return result

        client, client_error = self._create_client(api_key)
        if client_error is not None:
            self._record(client_error, profile.name, started, attempts=0, tool_rounds=0)
            return client_error
        assert client is not None

        attempts = 0
        last_error_type = ""
        try:
            async with self._semaphore():
                for attempt in range(1, self.config.max_retries + 1):
                    attempts = attempt
                    try:
                        outcome = await self._single_call(
                            client,
                            request,
                            profile,
                            copy.deepcopy(base_messages),
                        )
                        result = outcome.result
                        tool_rounds = int(result.usage.get("tool_round_count", 0))
                        if result.status == "ok" and conversation is not None:
                            conversation.messages = outcome.messages
                            conversation.save()
                        self._record(
                            result,
                            profile.name,
                            started,
                            attempts=attempts,
                            tool_rounds=tool_rounds,
                        )
                        return result
                    except asyncio.CancelledError:
                        self.usage_tracker.record(
                            profile=profile.name,
                            model=self.config.model,
                            provider=self.config.provider,
                            start_time=started,
                            end_time=time.monotonic(),
                            status="cancelled",
                            error_type="CancelledError",
                        )
                        raise
                    except _InvalidResponseError:
                        result = self._error_result(
                            "invalid_response",
                            {"reason": "malformed_response"},
                            request,
                        )
                        self._record(result, profile.name, started, attempts, 0)
                        return result
                    except Exception as exc:
                        last_error_type = type(exc).__name__
                        if self._is_timeout(exc):
                            if attempt < self.config.max_retries:
                                await self.sleep_func(2 ** (attempt - 1))
                                continue
                            result = self._error_result(
                                "timeout",
                                {
                                    "reason": "max_retries_exceeded",
                                    "attempts": attempt,
                                    "error_type": last_error_type,
                                },
                                request,
                            )
                            self._record(result, profile.name, started, attempts, 0)
                            return result
                        if self._is_transient(exc):
                            if attempt < self.config.max_retries:
                                await self.sleep_func(2 ** (attempt - 1))
                                continue
                            result = self._error_result(
                                "api_error",
                                {
                                    "reason": "max_retries_exceeded",
                                    "attempts": attempt,
                                    "error_type": last_error_type,
                                },
                                request,
                            )
                            self._record(result, profile.name, started, attempts, 0)
                            return result
                        result = self._error_result(
                            "api_error",
                            {
                                "reason": "non_transient_api_error",
                                "error_type": last_error_type,
                            },
                            request,
                        )
                        self._record(result, profile.name, started, attempts, 0)
                        return result
        finally:
            await self._close_client(client)

        result = self._error_result(
            "api_error",
            {"reason": "max_retries_exceeded", "error_type": last_error_type},
            request,
        )
        self._record(result, profile.name, started, attempts, 0)
        return result

    def _preflight(
        self,
        request: DeepSeekRequest,
        conversation: AgentConversation | None,
    ) -> tuple[LLMTaskProfile | None, DeepSeekResult | None]:
        try:
            profile = get_profile(request.profile)
        except KeyError:
            return None, self._error_result(
                "api_error",
                {"reason": "unknown_profile", "profile": request.profile},
                request,
            )
        profile = replace(
            profile,
            thinking_enabled=(
                profile.thinking_enabled
                or (profile.name == "compat" and self.config.thinking_default)
            ),
            reasoning_effort=self.config.thinking_effort,
        )
        try:
            schema_json(request.schema_name)
        except KeyError:
            return None, self._error_result(
                "invalid_response",
                {"reason": "unknown_schema", "schema": request.schema_name},
                request,
            )
        if conversation is not None and conversation.profile != request.profile:
            return None, self._error_result(
                "invalid_response",
                {"reason": "conversation_profile_mismatch"},
                request,
            )
        if request.tools and not profile.allow_tools:
            return None, self._error_result(
                "tool_error",
                {"reason": "tools_not_allowed_for_profile", "profile": profile.name},
                request,
            )
        for tool_name in request.tools:
            tool = self.tool_registry.get(tool_name)
            if tool is None:
                return None, self._error_result(
                    "tool_error",
                    {"reason": "unknown_tool", "tool": tool_name},
                    request,
                )
            if not tool.read_only:
                return None, self._error_result(
                    "tool_error",
                    {"reason": "write_tool_not_allowed", "tool": tool_name},
                    request,
                )
        return profile, None

    async def _single_call(
        self,
        client: Any,
        request: DeepSeekRequest,
        profile: LLMTaskProfile,
        messages: list[dict[str, Any]],
    ) -> _CallOutcome:
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
            "extra_body": {
                "thinking": {"type": "enabled" if profile.thinking_enabled else "disabled"}
            },
        }
        if profile.thinking_enabled:
            kwargs["reasoning_effort"] = profile.reasoning_effort
        if request.tools:
            kwargs["tools"] = self.tool_registry.to_openai_tools(request.tools)

        response = await self._invoke(client, kwargs)
        all_tool_calls: list[dict[str, Any]] = []
        tool_round_count = 0

        while self._message_tool_calls(response):
            if tool_round_count >= self.config.max_tool_rounds:
                result = self._error_result(
                    "tool_error",
                    {
                        "reason": "max_tool_rounds_exceeded",
                        "max_rounds": self.config.max_tool_rounds,
                    },
                    request,
                    tool_calls=all_tool_calls,
                )
                result.usage["tool_round_count"] = tool_round_count
                return _CallOutcome(result=result, messages=messages)
            tool_round_count += 1
            converted, conversion_error = self._convert_tool_calls(response)
            if conversion_error:
                result = self._error_result(
                    "tool_error",
                    {"reason": conversion_error},
                    request,
                    tool_calls=all_tool_calls,
                )
                result.usage["tool_round_count"] = tool_round_count
                return _CallOutcome(result=result, messages=messages)

            public_calls = [
                {"id": item["id"], "name": item["function"]["name"]} for item in converted
            ]
            all_tool_calls.extend(public_calls)
            assistant = {
                "role": "assistant",
                "content": self._message(response).content,
                "tool_calls": converted,
            }
            reasoning = getattr(self._message(response), "reasoning_content", None)
            if reasoning:
                assistant["reasoning_content"] = reasoning
            messages.append(assistant)

            for tool_call in converted:
                function = tool_call["function"]
                try:
                    arguments = json.loads(function["arguments"])
                except (TypeError, json.JSONDecodeError):
                    result = self._error_result(
                        "tool_error",
                        {
                            "reason": "invalid_tool_arguments",
                            "tool": function["name"],
                        },
                        request,
                        tool_calls=all_tool_calls,
                    )
                    result.usage["tool_round_count"] = tool_round_count
                    return _CallOutcome(result=result, messages=messages)
                execution = self.tool_registry.execute(function["name"], arguments)
                if execution.get("error"):
                    result = self._error_result(
                        "tool_error",
                        {
                            "reason": execution["error"],
                            "tool": function["name"],
                        },
                        request,
                        tool_calls=all_tool_calls,
                    )
                    result.usage["tool_round_count"] = tool_round_count
                    return _CallOutcome(result=result, messages=messages)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": execution["result"],
                    }
                )
            response = await self._invoke(client, kwargs)

        message = self._message(response)
        raw_content = message.content or ""
        if not raw_content.strip():
            result = self._error_result(
                "invalid_response",
                {"reason": "empty_content"},
                request,
                tool_calls=all_tool_calls,
            )
            result.usage["tool_round_count"] = tool_round_count
            return _CallOutcome(result=result, messages=messages)
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            result = self._error_result(
                "invalid_response",
                {
                    "reason": "invalid_json",
                    "raw_excerpt": sanitize_text(raw_content[:200]),
                },
                request,
                tool_calls=all_tool_calls,
            )
            result.usage["tool_round_count"] = tool_round_count
            return _CallOutcome(result=result, messages=messages)
        if not isinstance(parsed, dict):
            result = self._error_result(
                "invalid_response",
                {"reason": "json_root_must_be_object"},
                request,
                tool_calls=all_tool_calls,
            )
            result.usage["tool_round_count"] = tool_round_count
            return _CallOutcome(result=result, messages=messages)
        try:
            validated = validate_schema(request.schema_name, parsed)
        except ValidationError as exc:
            first_error = exc.errors(include_url=False, include_input=False)[0]
            location = ".".join(str(part) for part in first_error.get("loc", ()))
            result = self._error_result(
                "invalid_response",
                {
                    "reason": "schema_validation_failed",
                    "field": location,
                    "error_type": first_error.get("type", "validation_error"),
                },
                request,
                tool_calls=all_tool_calls,
            )
            result.usage["tool_round_count"] = tool_round_count
            return _CallOutcome(result=result, messages=messages)

        usage = self.usage_tracker.extract_usage(response)
        usage["tool_round_count"] = tool_round_count
        usage["tool_call_count"] = len(all_tool_calls)
        result = DeepSeekResult(
            status="ok",
            data=validated,
            provider=self.config.provider,
            model=self.config.model,
            conversation_id=request.conversation_id,
            usage=usage,
            tool_calls=all_tool_calls,
        )
        messages.append({"role": "assistant", "content": raw_content})
        return _CallOutcome(result=result, messages=messages)

    async def _invoke(self, client: Any, kwargs: dict[str, Any]) -> Any:
        call = client.chat.completions.create(**kwargs)
        return await asyncio.wait_for(call, timeout=self.config.timeout_seconds)

    def _build_messages(
        self,
        request: DeepSeekRequest,
        profile: LLMTaskProfile,
        conversation: AgentConversation | None,
    ) -> list[dict[str, Any]]:
        prefix = self.context_cache.build_prefix(
            profile.name,
            request.system_prompt,
            schema_json(request.schema_name),
        ).prefix
        if conversation is None:
            return [
                {"role": "system", "content": prefix},
                {"role": "user", "content": request.user_prompt},
            ]
        conversation.add_system(prefix)
        conversation.add_user(request.user_prompt)
        return copy.deepcopy(conversation.messages)

    def _create_client(self, api_key: str) -> tuple[Any | None, DeepSeekResult | None]:
        factory = self.client_factory
        if factory is None:
            try:
                from openai import AsyncOpenAI
            except ModuleNotFoundError:
                return None, DeepSeekResult(
                    status="unavailable",
                    error={"reason": "openai_package_not_installed"},
                    provider=self.config.provider,
                    model=self.config.model,
                )
            factory = AsyncOpenAI
        try:
            return factory(api_key=api_key, base_url=self.config.api_base), None
        except Exception as exc:
            logger.warning("初始化 LLM client 失败 error_type={}", type(exc).__name__)
            return None, DeepSeekResult(
                status="api_error",
                error={"reason": "client_initialization_failed", "error_type": type(exc).__name__},
                provider=self.config.provider,
                model=self.config.model,
            )

    async def _close_client(self, client: Any) -> None:
        close = getattr(client, "close", None)
        if close is None:
            return
        try:
            result = close()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.warning("关闭 LLM client 失败 error_type={}", type(exc).__name__)

    def _semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        with self._semaphore_lock:
            semaphore = self._semaphores.get(loop)
            if semaphore is None:
                semaphore = asyncio.Semaphore(self.config.max_concurrency)
                self._semaphores[loop] = semaphore
            return semaphore

    def _api_key(self) -> str:
        import os

        return os.getenv(self.config.api_key_env, "").strip()

    def _error_result(
        self,
        status: str,
        error: dict[str, Any],
        request: DeepSeekRequest,
        *,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> DeepSeekResult:
        return DeepSeekResult(
            status=status,
            error=error,
            provider=self.config.provider,
            model=self.config.model,
            conversation_id=request.conversation_id,
            tool_calls=tool_calls or [],
        )

    def _record(
        self,
        result: DeepSeekResult,
        profile: str,
        started: float,
        attempts: int,
        tool_rounds: int,
    ) -> None:
        result.usage.setdefault("attempts", attempts)
        record = self.usage_tracker.record(
            profile=profile,
            model=self.config.model,
            provider=self.config.provider,
            start_time=started,
            end_time=time.monotonic(),
            prompt_tokens=result.usage.get("prompt_tokens"),
            completion_tokens=result.usage.get("completion_tokens"),
            total_tokens=result.usage.get("total_tokens"),
            prompt_cache_hit_tokens=result.usage.get("prompt_cache_hit_tokens"),
            prompt_cache_miss_tokens=result.usage.get("prompt_cache_miss_tokens"),
            tool_call_count=len(result.tool_calls),
            tool_round_count=tool_rounds,
            status=result.status,
            error_type=(result.error or {}).get("reason"),
        )
        self.usage_tracker.log(record)

    @staticmethod
    def _message(response: Any) -> Any:
        choices = getattr(response, "choices", None)
        if not choices or not getattr(choices[0], "message", None):
            raise _InvalidResponseError
        return choices[0].message

    @classmethod
    def _message_tool_calls(cls, response: Any) -> Any:
        return getattr(cls._message(response), "tool_calls", None)

    @classmethod
    def _convert_tool_calls(
        cls, response: Any
    ) -> tuple[list[dict[str, Any]], str | None]:
        converted: list[dict[str, Any]] = []
        for item in cls._message_tool_calls(response) or []:
            function = getattr(item, "function", None)
            name = getattr(function, "name", "")
            arguments = getattr(function, "arguments", "")
            call_id = getattr(item, "id", "")
            if not call_id or not name or not isinstance(arguments, str):
                return [], "malformed_tool_call"
            converted.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }
            )
        return converted, None

    @staticmethod
    def _is_timeout(exc: Exception) -> bool:
        return isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or type(exc).__name__ == (
            "APITimeoutError"
        )

    @classmethod
    def _is_transient(cls, exc: Exception) -> bool:
        if cls._is_timeout(exc) or isinstance(exc, ConnectionError):
            return True
        return type(exc).__name__ in {
            "APIConnectionError",
            "RateLimitError",
            "InternalServerError",
        }


def _run_sync(coroutine: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()
