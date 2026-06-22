from __future__ import annotations

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from src.llm.context_cache import ContextPrefixCache
from src.llm.conversation import AgentConversation
from src.llm.deepseek_runtime import DeepSeekRuntime
from src.llm.schemas import DeepSeekRequest
from src.llm.tool_registry import ToolDef, ToolRegistry
from src.llm.usage import UsageTracker


def _analysis_json() -> str:
    return json.dumps(
        {
            "status": "ok",
            "root_cause": "输入数据缺少校验",
            "affected_files": ["src/product_app/example.py"],
            "fix_steps": ["增加校验"],
            "risk_level": "medium",
            "estimated_impact": "仅影响分析流程",
            "needs_human_review": True,
            "evidence": [],
        },
        ensure_ascii=False,
    )


class FakeToolCall:
    def __init__(self, name: str, arguments: str, call_id: str = "call-1") -> None:
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)


class FakeResponse:
    def __init__(
        self,
        content: str | None,
        *,
        tool_calls: list[FakeToolCall] | None = None,
        reasoning_content: str | None = None,
    ) -> None:
        message = SimpleNamespace(
            content=content,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
        )
        self.choices = [SimpleNamespace(message=message)]
        self.usage = SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            prompt_cache_hit_tokens=4,
            prompt_cache_miss_tokens=6,
        )


class FakeCompletions:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return await outcome()
        return outcome


class FakeClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.completions = FakeCompletions(outcomes)
        self.chat = SimpleNamespace(completions=self.completions)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _request(**overrides) -> DeepSeekRequest:
    values = {
        "profile": "bugfix_analysis",
        "schema_name": "bugfix_analysis",
        "system_prompt": "分析缺陷并返回 json。",
        "user_prompt": "请分析这个缺陷。",
    }
    values.update(overrides)
    return DeepSeekRequest(**values)


def _runtime(monkeypatch, tmp_path, client: FakeClient, **kwargs) -> DeepSeekRuntime:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    return DeepSeekRuntime(
        client_factory=lambda **_client_kwargs: client,
        context_cache=ContextPrefixCache(cache_dir=tmp_path / "cache"),
        usage_tracker=kwargs.pop("usage_tracker", UsageTracker()),
        **kwargs,
    )


def test_missing_key_fails_closed(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = FakeClient([FakeResponse(_analysis_json())])
    runtime = DeepSeekRuntime(
        client_factory=lambda **_kwargs: client,
        context_cache=ContextPrefixCache(cache_dir=tmp_path / "cache"),
    )

    result = runtime.chat_json(_request())

    assert result.status == "unavailable"
    assert result.error == {"reason": "missing_api_key", "env_var": "DEEPSEEK_API_KEY"}
    assert client.completions.calls == []


def test_json_output_thinking_schema_and_cache_prefix(monkeypatch, tmp_path):
    client = FakeClient([FakeResponse(_analysis_json(), reasoning_content="private")])
    runtime = _runtime(monkeypatch, tmp_path, client)

    result = runtime.chat_json(_request())

    assert result.status == "ok"
    assert result.data is not None
    assert result.data["needs_human_review"] is True
    call = client.completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}
    assert call["reasoning_effort"] == "high"
    assert "Safety Invariants" in call["messages"][0]["content"]
    assert "分析缺陷并返回 json" in call["messages"][0]["content"]
    assert "root_cause" in call["messages"][0]["content"]
    assert "private" not in json.dumps(result.model_dump(), ensure_ascii=False)
    assert client.closed is True


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("", "empty_content"),
        ("not-json", "invalid_json"),
        (json.dumps({"status": "ok"}), "schema_validation_failed"),
    ],
)
def test_invalid_content_fails_closed(monkeypatch, tmp_path, content, reason):
    client = FakeClient([FakeResponse(content)])
    runtime = _runtime(monkeypatch, tmp_path, client)

    result = runtime.chat_json(_request())

    assert result.status == "invalid_response"
    assert result.error is not None
    assert result.error["reason"] == reason
    assert result.data is None


def test_unknown_schema_is_rejected_before_api_call(monkeypatch, tmp_path):
    client = FakeClient([FakeResponse('{"value": 1}')])
    runtime = _runtime(monkeypatch, tmp_path, client)

    result = runtime.chat_json(_request(schema_name="unknown_schema"))

    assert result.status == "invalid_response"
    assert result.error == {"reason": "unknown_schema", "schema": "unknown_schema"}
    assert client.completions.calls == []


def test_context_cache_failure_fails_before_client_creation(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    factory_calls = []

    class BrokenCache:
        def build_prefix(self, *_args, **_kwargs):
            raise OSError("read-only filesystem")

    runtime = DeepSeekRuntime(
        client_factory=lambda **kwargs: factory_calls.append(kwargs),
        context_cache=BrokenCache(),
        usage_tracker=UsageTracker(),
    )

    result = runtime.chat_json(_request())

    assert result.status == "api_error"
    assert result.error == {
        "reason": "context_preparation_failed",
        "error_type": "OSError",
    }
    assert factory_calls == []


def test_malformed_sdk_response_is_invalid_response(monkeypatch, tmp_path):
    client = FakeClient([SimpleNamespace(choices=[])])
    runtime = _runtime(monkeypatch, tmp_path, client)

    result = runtime.chat_json(_request())

    assert result.status == "invalid_response"
    assert result.error == {"reason": "malformed_response"}
    assert len(client.completions.calls) == 1


def test_thinking_effort_can_be_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_THINKING_EFFORT", "max")
    client = FakeClient([FakeResponse(_analysis_json())])
    runtime = _runtime(monkeypatch, tmp_path, client)

    result = runtime.chat_json(_request())

    assert result.status == "ok"
    assert client.completions.calls[0]["reasoning_effort"] == "max"


def test_timeout_retries_then_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")

    async def slow_response():
        await asyncio.sleep(1)
        return FakeResponse(_analysis_json())

    client = FakeClient([slow_response, slow_response])
    runtime = _runtime(monkeypatch, tmp_path, client, sleep_func=lambda _delay: asyncio.sleep(0))

    result = runtime.chat_json(_request())

    assert result.status == "timeout"
    assert result.error is not None
    assert result.error["reason"] == "max_retries_exceeded"
    assert result.error["attempts"] == 2
    assert len(client.completions.calls) == 2


def test_transient_error_retries_until_success(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_MAX_RETRIES", "3")
    client = FakeClient(
        [ConnectionError("temporary-1"), ConnectionError("temporary-2"), FakeResponse(_analysis_json())]
    )
    runtime = _runtime(monkeypatch, tmp_path, client, sleep_func=lambda _delay: asyncio.sleep(0))

    result = runtime.chat_json(_request())

    assert result.status == "ok"
    assert len(client.completions.calls) == 3


def test_non_transient_error_does_not_retry(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_MAX_RETRIES", "3")
    client = FakeClient([ValueError("bad request"), FakeResponse(_analysis_json())])
    runtime = _runtime(monkeypatch, tmp_path, client, sleep_func=lambda _delay: asyncio.sleep(0))

    result = runtime.chat_json(_request())

    assert result.status == "api_error"
    assert result.error is not None
    assert result.error["reason"] == "non_transient_api_error"
    assert len(client.completions.calls) == 1


def test_cancellation_propagates(monkeypatch, tmp_path):
    async def scenario() -> None:
        started = asyncio.Event()

        async def never_finishes():
            started.set()
            await asyncio.Event().wait()

        client = FakeClient([never_finishes])
        runtime = _runtime(monkeypatch, tmp_path, client)
        task = asyncio.create_task(runtime.chat_json_async(_request()))
        await started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_concurrency_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    active = 0
    max_active = 0

    async def measured_response():
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return FakeResponse(_analysis_json())

    client = FakeClient([measured_response, measured_response])
    runtime = _runtime(monkeypatch, tmp_path, client)

    async def scenario():
        return await asyncio.gather(
            runtime.chat_json_async(_request(user_prompt="one")),
            runtime.chat_json_async(_request(user_prompt="two")),
        )

    results = asyncio.run(scenario())

    assert [result.status for result in results] == ["ok", "ok"]
    assert max_active == 1


def test_tool_loop_and_reasoning_are_supported(monkeypatch, tmp_path):
    registry = ToolRegistry(register_defaults=False)
    registry.register(
        ToolDef(
            name="read_note",
            description="读取测试内容",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            func=lambda name: {"result": f"note:{name}", "truncated": False},
        )
    )
    first = FakeResponse(
        None,
        tool_calls=[FakeToolCall("read_note", '{"name":"alpha"}')],
        reasoning_content="private reasoning",
    )
    client = FakeClient([first, FakeResponse(_analysis_json())])
    runtime = _runtime(monkeypatch, tmp_path, client, tool_registry=registry)

    result = runtime.chat_json(_request(tools=["read_note"]))

    assert result.status == "ok"
    assert len(result.tool_calls) == 1
    second_messages = client.completions.calls[1]["messages"]
    assert second_messages[-2]["reasoning_content"] == "private reasoning"
    assert second_messages[-1]["role"] == "tool"
    assert second_messages[-1]["content"] == "note:alpha"
    assert "private reasoning" not in json.dumps(result.model_dump(), ensure_ascii=False)


def test_unknown_requested_tool_fails_before_api_call(monkeypatch, tmp_path):
    client = FakeClient([FakeResponse(_analysis_json())])
    runtime = _runtime(monkeypatch, tmp_path, client, tool_registry=ToolRegistry(register_defaults=False))

    result = runtime.chat_json(_request(tools=["write_file"]))

    assert result.status == "tool_error"
    assert result.error == {"reason": "unknown_tool", "tool": "write_file"}
    assert client.completions.calls == []


def test_tool_execution_error_stops_loop(monkeypatch, tmp_path):
    registry = ToolRegistry(register_defaults=False)
    registry.register(
        ToolDef(
            name="read_note",
            description="读取测试内容",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            func=lambda name: (_ for _ in ()).throw(OSError("secret token=abc")),
        )
    )
    client = FakeClient(
        [
            FakeResponse(None, tool_calls=[FakeToolCall("read_note", '{"name":"alpha"}')]),
            FakeResponse(_analysis_json()),
        ]
    )
    runtime = _runtime(monkeypatch, tmp_path, client, tool_registry=registry)

    result = runtime.chat_json(_request(tools=["read_note"]))

    assert result.status == "tool_error"
    assert result.error is not None
    assert result.error["reason"] == "tool_execution_failed"
    assert "abc" not in json.dumps(result.error)
    assert len(client.completions.calls) == 1


def test_usage_is_recorded(monkeypatch, tmp_path):
    tracker = UsageTracker()
    client = FakeClient([FakeResponse(_analysis_json())])
    runtime = _runtime(monkeypatch, tmp_path, client, usage_tracker=tracker)

    result = runtime.chat_json(_request())

    assert result.usage["prompt_cache_hit_tokens"] == 4
    summary = tracker.summary()
    assert summary["total_calls"] == 1
    assert summary["ok_calls"] == 1
    assert summary["total_tokens"] == 30


def test_managed_conversation_is_used_and_persisted(monkeypatch, tmp_path):
    client = FakeClient([FakeResponse(_analysis_json(), reasoning_content="private")])
    runtime = _runtime(monkeypatch, tmp_path, client)
    conversation = AgentConversation(
        profile="bugfix_analysis",
        storage_dir=tmp_path / "conversations",
    )

    result = asyncio.run(
        runtime.chat_json_async_with_conversation(_request(), conversation)
    )

    assert result.status == "ok"
    assert result.conversation_id == conversation.conversation_id
    persisted = conversation.save().read_text(encoding="utf-8")
    assert "请分析这个缺陷" in persisted
    assert "输入数据缺少校验" in persisted
    assert "private" not in persisted
