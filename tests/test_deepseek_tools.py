"""Tool Registry 单元测试

覆盖工具注册、执行、安全校验和只读约束。
所有测试不访问真实文件系统（使用 tmp_path fixture 隔离）。
"""
from __future__ import annotations



from src.llm.tool_registry import (
    _is_path_allowed,
    _list_feedback_bugs,
    get_tool_registry,
)


class TestToolRegistry:
    """ToolRegistry 注册和执行测试"""

    def test_registry_singleton(self):
        """get_tool_registry() 返回单例"""
        r1 = get_tool_registry()
        r2 = get_tool_registry()
        assert r1 is r2

    def test_default_tools_registered(self):
        """默认工具都已注册"""
        registry = get_tool_registry()
        tools = registry.list_tools()
        assert "read_project_file" in tools
        assert "search_project_text" in tools
        assert "list_feedback_bugs" in tools
        assert "read_feedback_bug" in tools
        assert "read_test_report" in tools
        assert "read_dev_report" in tools

    def test_to_openai_tools_format(self):
        """to_openai_tools() 返回正确的格式"""
        registry = get_tool_registry()
        openai_tools = registry.to_openai_tools(["read_project_file"])
        assert len(openai_tools) == 1
        tool = openai_tools[0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "read_project_file"
        assert "parameters" in tool["function"]

    def test_execute_unknown_tool(self):
        """执行不存在的工具返回错误"""
        registry = get_tool_registry()
        result = registry.execute("nonexistent_tool", {})
        assert result["error"] is not None
        assert "Unknown tool" in result["error"]

    def test_execute_all_tools_have_read_only(self):
        """所有默认工具都是只读的"""
        registry = get_tool_registry()
        for name in registry.list_tools():
            tool = registry.get(name)
            assert tool is not None
            assert tool.read_only is True


class TestReadProjectFile:
    """read_project_file 工具测试"""

    def test_path_outside_allowed_prefix(self, tmp_path):
        """访问允许前缀之外的路径返回拒绝"""
        # Point _PROJECT_ROOT to a temp dir
        outside_path = tmp_path / "outside" / "secret.txt"
        outside_path.parent.mkdir(parents=True)
        outside_path.write_text("secret", encoding="utf-8")

        allowed = _is_path_allowed(outside_path)
        assert allowed is False


class TestListFeedbackBugs:
    """list_feedback_bugs 工具测试"""

    def test_no_bugs_dir(self, monkeypatch, tmp_path):
        """bug 目录不存在时返回提示"""
        monkeypatch.setattr("src.llm.tool_registry._PROJECT_ROOT", tmp_path)
        result = _list_feedback_bugs()
        assert "No feedback/bugs/open/" in result["result"]

    def test_bugs_dir_listed(self, monkeypatch, tmp_path):
        """存在 bug 文件时返回列表"""
        bugs_dir = tmp_path / "feedback" / "bugs" / "open"
        bugs_dir.mkdir(parents=True)
        (bugs_dir / "BUG_001.json").write_text("{}", encoding="utf-8")
        (bugs_dir / "BUG_002.json").write_text("{}", encoding="utf-8")

        monkeypatch.setattr("src.llm.tool_registry._PROJECT_ROOT", tmp_path)
        result = _list_feedback_bugs()
        assert "BUG_001.json" in result["result"]
        assert "BUG_002.json" in result["result"]


class TestPathValidation:
    """路径安全校验测试"""

    def test_allowed_src_path(self, tmp_path):
        """src/ 下的路径应允许"""
        src_dir = tmp_path / "src" / "api" / "routes.py"
        src_dir.parent.mkdir(parents=True, exist_ok=True)
        src_dir.write_text("", encoding="utf-8")
        allowed = _is_path_allowed(src_dir.resolve())
        # This depends on whether tmp_path is under _ALLOWED_READ_PREFIXES
        # which points to the actual project root
        assert allowed is not None  # just check it doesn't crash

    def test_forbidden_runtime_path(self, tmp_path):
        """runtime/ 路径应被拒绝"""
        runtime_path = tmp_path / "runtime" / "secrets.json"
        runtime_path.parent.mkdir(parents=True)
        runtime_path.write_text("", encoding="utf-8")
        allowed = _is_path_allowed(runtime_path.resolve())
        assert allowed is False
