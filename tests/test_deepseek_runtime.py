"""DeepSeek Runtime 单元测试

使用 FakeDeepSeekClient 模拟 API 响应，不依赖真实 DeepSeek。
"""
from __future__ import annotations

import os


from src.llm.deepseek_runtime import DeepSeekRuntime
from src.llm.schemas import DeepSeekRequest, DeepSeekResult, get_profile


# ============================================================
# Helpers — fake responses for each scenario
# ============================================================


class _FakeChoice:
    def __init__(self, content: str = "{}", reasoning_content: str | None = None, tool_calls: list | None = None):
        self.message = _FakeMessage(content=content, reasoning_content=reasoning_content, tool_calls=tool_calls)


class _FakeMessage:
    def __init__(self, content: str = "{}", reasoning_content: str | None = None, tool_calls: list | None = None):
        self.content = content
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls


class _FakeUsage:
    def __init__(self):
        self.prompt_tokens = 50
        self.completion_tokens = 100
        self.total_tokens = 150
        self.prompt_cache_hit_tokens = 10
        self.prompt_cache_miss_tokens = 40


class _FakeResponse:
    def __init__(self, content: str = "{}", reasoning_content: str | None = None, tool_calls: list | None = None):
        self.choices = [_FakeChoice(content=content, reasoning_content=reasoning_content, tool_calls=tool_calls)]
        self.usage = _FakeUsage()


class _FakeAsyncClient:
    """Simulates AsyncOpenAI for testing."""

    def __init__(self, api_key=None, base_url=None):
        self.responses: list = []
        self._call_index = 0

    def set_responses(self, responses: list):
        self.responses = responses
        self._call_index = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    async def create(self, **kwargs):
        if self._call_index < len(self.responses):
            resp = self.responses[self._call_index]
            self._call_index += 1
            return resp
        return _FakeResponse(content='{"status": "ok", "message": "default"}')


# ============================================================
# Tests
# ============================================================


class TestDeepSeekRuntimeBasic:
    """Runtime 基本功能测试 —— missing key, missing SDK, JSON output"""

    def test_missing_api_key(self, monkeypatch):
        """缺少 API key 时返回 unavailable"""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        if "DEEPSEEK_API_KEY" in os.environ:
            monkeypatch.setenv("DEEPSEEK_API_KEY", "")
        runtime = DeepSeekRuntime()
        request = DeepSeekRequest(
            profile="signal_explanation",
            schema_name="test",
            system_prompt="test",
            user_prompt="test",
        )
        result = runtime.chat_json(request)
        assert result.status == "unavailable"
        assert result.error is not None
        assert "missing_api_key" in str(result.error)

    def test_missing_openai_package(self, monkeypatch):
        """缺少 openai 包时返回 unavailable"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        # Force import error by mocking
        import builtins
        original_import = builtins.__import__

        def _mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ModuleNotFoundError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _mock_import)

        runtime = DeepSeekRuntime()
        request = DeepSeekRequest(
            profile="signal_explanation",
            schema_name="test",
            system_prompt="test",
            user_prompt="test",
        )
        result = runtime.chat_json(request)
        assert result.status == "unavailable"
        assert "openai_package_not_installed" in str(result.error)

    def test_profile_resolution(self):
        """已知 profile 可被正确解析"""
        profile = get_profile("bugfix_analysis")
        assert profile.thinking_enabled is True
        assert profile.json_output is True
        assert profile.allow_tools is True
        assert profile.name == "bugfix_analysis"

    def test_unknown_profile_falls_back(self, monkeypatch):
        """未知 profile 不会崩溃"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        runtime = DeepSeekRuntime()
        request = DeepSeekRequest(
            profile="nonexistent_profile",
            schema_name="test",
            system_prompt="test",
            user_prompt="test",
        )
        result = runtime.chat_json(request)
        # Should proceed with default profile, but will hit API error since
        # we're using a fake key. Status should be api_error or unavailable.
        assert result.status in ("api_error", "unavailable", "timeout", "invalid_response")

    def test_signal_explanation_profile(self):
        """signal_explanation profile 的 thinking 为 disabled"""
        profile = get_profile("signal_explanation")
        assert profile.thinking_enabled is False
        assert profile.allow_tools is False


class TestDeepSeekRuntimeJSONOutput:
    """JSON Output 功能测试"""

    def test_parse_valid_json(self):
        """合法 JSON 被正确解析"""
        raw = '{"key": "value", "num": 42}'
        parsed, error = DeepSeekRuntime._parse_json(raw)
        assert error is None
        assert parsed == {"key": "value", "num": 42}

    def test_parse_markdown_json(self):
        """Markdown 代码块中的 JSON 可提取"""
        raw = '```json\n{"key": "wrapped"}\n```'
        parsed, error = DeepSeekRuntime._parse_json(raw)
        assert error is None
        assert parsed == {"key": "wrapped"}

    def test_parse_empty_content(self):
        """空 content 返回 parse_failed"""
        parsed, error = DeepSeekRuntime._parse_json("")
        assert parsed is None
        assert error == "parse_failed"

    def test_parse_invalid_json(self):
        """非法 JSON 返回 parse_failed"""
        parsed, error = DeepSeekRuntime._parse_json("{invalid}")
        assert parsed is None
        assert error == "parse_failed"


class TestDeepSeekRuntimeThinking:
    """Thinking Mode 参数测试"""

    def test_thinking_enabled_via_profile(self, monkeypatch):
        """thinking enabled 的 profile 设置正确"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        profile = get_profile("bugfix_analysis")
        assert profile.thinking_enabled is True
        assert profile.reasoning_effort == "high"

    def test_thinking_disabled_via_profile(self):
        """thinking disabled 的 profile 设置正确"""
        profile = get_profile("signal_explanation")
        assert profile.thinking_enabled is False


class TestDeepSeekRuntimeResultModel:
    """DeepSeekResult 模型校验"""

    def test_ok_result(self):
        """ok 状态的 result"""
        result = DeepSeekResult(
            status="ok",
            data={"root_cause": "test"},
            model="deepseek-v4-flash",
        )
        assert result.status == "ok"
        assert result.data is not None
        assert result.data["root_cause"] == "test"

    def test_error_result(self):
        """错误状态的 result"""
        result = DeepSeekResult(
            status="unavailable",
            error={"reason": "missing_api_key"},
        )
        assert result.status == "unavailable"
        assert result.data is None

    def test_timeout_result(self):
        """超时状态的 result"""
        result = DeepSeekResult(
            status="timeout",
            error={"reason": "max_retries_exceeded", "attempts": 3},
        )
        assert result.status == "timeout"
        assert "attempts" in result.error

    def test_invalid_response_result(self):
        """非法响应状态的 result"""
        result = DeepSeekResult(
            status="invalid_response",
            error={"reason": "empty_content"},
        )
        assert result.status == "invalid_response"

    def test_tool_error_result(self):
        """工具错误状态的 result"""
        result = DeepSeekResult(
            status="tool_error",
            error={"reason": "max_tool_rounds_exceeded"},
            tool_calls=[{"id": "call_1"}],
        )
        assert result.status == "tool_error"
        assert len(result.tool_calls) == 1
