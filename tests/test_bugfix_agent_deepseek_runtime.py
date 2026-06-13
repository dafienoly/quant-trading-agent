"""BugFixAgent Runtime 迁移测试

验证 BugFixAgent 已切换到 DeepSeekRuntime 且现有行为不变。
使用 monkeypatch 模拟 Runtime 调用，不依赖真实 API。
"""
from __future__ import annotations



from src.llm.schemas import DeepSeekResult, BugFixAnalysis, BugFixProposal
from src.product_app.bug_fix_agent import BugFixAgent


# ============================================================
# Helper
# ============================================================


def _make_bug_report_dict(
    bug_id: str = "BUG_20260610_ABC123",
    status: str = "open",
    component: str = "data_gateway",
    title: str = "测试Bug",
    summary: str = "这是一个测试Bug",
    severity: str = "medium",
    **extra_fields,
) -> dict:
    """构造 Bug 报告字典"""
    data = {
        "bug_id": bug_id,
        "created_at": "2026-06-10 10:00:00",
        "updated_at": "2026-06-10 10:00:00",
        "status": status,
        "severity": severity,
        "component": component,
        "title": title,
        "summary": summary,
        "user_action": "",
        "endpoint_or_page": "",
        "exception_type": "ValueError",
        "exception_message": "invalid data",
        "sanitized_traceback": "",
        "runtime_context": {},
        "config_snapshot_masked": {},
        "reproduction_steps": [],
        "dedupe_hash": "abc123",
        "related_log_files": [],
        "occurrence_count": 1,
        "analysis_report": None,
        "fix_proposal": None,
        "approval_status": "pending",
        "approval_comment": "",
        "fix_result": None,
        "git_commit_hash": "",
    }
    data.update(extra_fields)
    return data


class _MockRuntime:
    """模拟 DeepSeekRuntime，不调用真实 API"""

    def __init__(self):
        self.last_request = None
        self.chat_json_calls = 0

    def chat_json(self, request):
        self.last_request = request
        self.chat_json_calls += 1

        if request.profile == "bugfix_analysis":
            return DeepSeekResult(
                status="ok",
                data={
                    "root_cause": "数据源返回空值未做校验",
                    "affected_files": ["src/data_gateway/akshare_provider.py"],
                    "fix_steps": ["添加空值校验", "添加重试逻辑"],
                    "risk_level": "medium",
                    "estimated_impact": "影响数据获取模块",
                    "needs_human_review": True,
                    "evidence": [],
                },
                model="mock-model",
            )
        elif request.profile == "bugfix_proposal":
            return DeepSeekResult(
                status="ok",
                data={
                    "fix_description": "添加空值校验和重试逻辑",
                    "code_changes": [
                        {
                            "file_path": "src/data_gateway/akshare_provider.py",
                            "change_type": "modify",
                            "diff": "--- a/src/data_gateway/akshare_provider.py\n+++ b/src/data_gateway/akshare_provider.py\n@@ -10,3 +10,3 @@\n-old_code\n+new_code\n",
                            "reason": "添加空值校验",
                        }
                    ],
                    "risk_level": "low",
                    "estimated_impact": "仅影响数据获取",
                    "test_suggestions": ["测试空值场景"],
                    "requires_approval": True,
                },
                model="mock-model",
            )
        return DeepSeekResult(status="invalid_response", error={"reason": "unknown_profile"})


# ============================================================
# Tests
# ============================================================


class TestBugFixAgentRuntimeMigration:
    """BugFixAgent 使用 DeepSeekRuntime 后的行为验证"""

    def test_analyze_uses_runtime(self, monkeypatch):
        """analyze() 使用 DeepSeekRuntime 并获得正确结果"""
        mock_runtime = _MockRuntime()
        monkeypatch.setattr("src.product_app.bug_fix_agent.BugFixAgent.runtime",
                            property(lambda self: mock_runtime))

        agent = BugFixAgent()
        bug_report = _make_bug_report_dict()
        result = agent.analyze(bug_report)

        # Verify runtime was called
        assert mock_runtime.chat_json_calls >= 1
        assert mock_runtime.last_request is not None
        assert mock_runtime.last_request.profile == "bugfix_analysis"

        # Verify result
        assert "root_cause" in result
        assert result["root_cause"] == "数据源返回空值未做校验"
        assert "affected_files" in result
        assert "fix_steps" in result

    def test_analyze_has_correct_fields(self, monkeypatch):
        """analyze() 返回 schema 校验后的正确字段"""
        mock_runtime = _MockRuntime()
        monkeypatch.setattr("src.product_app.bug_fix_agent.BugFixAgent.runtime",
                            property(lambda self: mock_runtime))

        agent = BugFixAgent()
        result = agent.analyze(_make_bug_report_dict())

        assert "root_cause" in result
        assert "affected_files" in result
        assert "fix_steps" in result
        assert "risk_level" in result
        assert result["risk_level"] == "medium"
        assert "needs_human_review" in result
        assert result["needs_human_review"] is True

    def test_analyze_includes_tools_in_request(self, monkeypatch):
        """analyze() 向 runtime 传递正确的 tools 列表"""
        mock_runtime = _MockRuntime()
        monkeypatch.setattr("src.product_app.bug_fix_agent.BugFixAgent.runtime",
                            property(lambda self: mock_runtime))

        agent = BugFixAgent()
        agent.analyze(_make_bug_report_dict())

        assert mock_runtime.last_request is not None
        assert "read_feedback_bug" in mock_runtime.last_request.tools
        assert "search_project_text" in mock_runtime.last_request.tools
        assert "read_project_file" in mock_runtime.last_request.tools

    def test_propose_fix_uses_runtime(self, monkeypatch):
        """propose_fix() 使用 DeepSeekRuntime"""
        mock_runtime = _MockRuntime()
        monkeypatch.setattr("src.product_app.bug_fix_agent.BugFixAgent.runtime",
                            property(lambda self: mock_runtime))

        agent = BugFixAgent()
        bug_report = _make_bug_report_dict()
        analysis = {"root_cause": "test", "affected_files": [], "fix_steps": []}
        result = agent.propose_fix(bug_report, analysis)

        assert mock_runtime.chat_json_calls >= 1
        assert mock_runtime.last_request is not None
        assert mock_runtime.last_request.profile == "bugfix_proposal"

        assert "fix_description" in result
        assert result["fix_description"] == "添加空值校验和重试逻辑"
        assert "code_changes" in result
        assert len(result["code_changes"]) == 1

    def test_propose_fix_blocked_module(self, monkeypatch):
        """propose_fix() 检测到受限模块返回 blocked"""
        # Override the mock to return a blocked module proposal
        class _BlockedMockRuntime:
            def __init__(self):
                self.chat_json_calls = 0
                self.last_request = None

            def chat_json(self, request):
                self.chat_json_calls += 1
                self.last_request = request
                return DeepSeekResult(
                    status="ok",
                    data={
                        "fix_description": "修改风控引擎",
                        "code_changes": [
                            {
                                "file_path": "src/risk_engine/runtime.py",
                                "change_type": "modify",
                                "diff": "-old\n+new",
                                "reason": "Fix risk engine",
                            }
                        ],
                        "risk_level": "critical",
                        "estimated_impact": "风控模块",
                        "test_suggestions": [],
                        "requires_approval": True,
                    },
                    model="mock-model",
                )

        monkeypatch.setattr("src.product_app.bug_fix_agent.BugFixAgent.runtime",
                            property(lambda self: _BlockedMockRuntime()))

        agent = BugFixAgent()
        bug_report = _make_bug_report_dict()
        analysis = {"root_cause": "test", "affected_files": [], "fix_steps": []}
        result = agent.propose_fix(bug_report, analysis)

        assert result.get("blocked") is True
        assert "blocked_files" in result
        assert any("risk_engine" in f for f in result["blocked_files"])

    def test_execute_fix_still_rejects_blocked_module(self):
        """execute_fix() 仍然拒绝受限模块（不受 runtime 迁移影响）"""
        agent = BugFixAgent()
        proposal = {
            "code_changes": [
                {
                    "file_path": "src/execution_engine/live_broker.py",
                    "change_type": "modify",
                    "diff": "-old\n+new",
                }
            ]
        }
        result = agent.execute_fix(_make_bug_report_dict(), proposal)
        assert result["success"] is False
        assert result["blocked"] is True
        assert "execution_engine" in result["blocked_files"][0]

    def test_is_blocked_module_still_works(self):
        """_is_blocked_module() 行为不变"""
        agent = BugFixAgent()
        blocked, files = agent._is_blocked_module([{"file_path": "src/risk_engine/runtime.py"}])
        assert blocked is True
        assert len(files) == 1

        blocked, files = agent._is_blocked_module([{"file_path": "src/api/routes.py"}])
        assert blocked is False
        assert files == []

    def test_parse_json_response_still_works(self):
        """_parse_json_response() 行为不变"""
        valid = '{"key": "value"}'
        result = BugFixAgent._parse_json_response(valid)
        assert result == {"key": "value"}

        codeblock = '```json\n{"key": "wrapped"}\n```'
        result = BugFixAgent._parse_json_response(codeblock)
        assert result == {"key": "wrapped"}

        plain = "not json"
        result = BugFixAgent._parse_json_response(plain)
        assert "raw_analysis" in result
        assert plain in result["raw_analysis"]


class TestBugFixAgentRuntimeErrorHandling:
    """Runtime 错误处理测试"""

    def test_analyze_runtime_unavailable(self, monkeypatch):
        """runtime 返回 unavailable 时 analyze 返回错误"""
        class _ErrorMockRuntime:
            def chat_json(self, request):
                return DeepSeekResult(
                    status="unavailable",
                    error={"reason": "missing_api_key"},
                    model="mock-model",
                )

        monkeypatch.setattr("src.product_app.bug_fix_agent.BugFixAgent.runtime",
                            property(lambda self: _ErrorMockRuntime()))

        agent = BugFixAgent()
        result = agent.analyze(_make_bug_report_dict())
        assert "error" in result
        assert result.get("status") == "unavailable"

    def test_analyze_runtime_invalid_response(self, monkeypatch):
        """runtime 返回 invalid_response 时 analyze 返回 error"""
        class _InvalidMockRuntime:
            def chat_json(self, request):
                return DeepSeekResult(
                    status="invalid_response",
                    error={"reason": "empty_content"},
                    model="mock-model",
                )

        monkeypatch.setattr("src.product_app.bug_fix_agent.BugFixAgent.runtime",
                            property(lambda self: _InvalidMockRuntime()))

        agent = BugFixAgent()
        result = agent.analyze(_make_bug_report_dict())
        assert "error" in result
        assert result.get("status") == "invalid_response"


class TestBugFixSchemaValidation:
    """BugFixAnalysis / BugFixProposal schema 测试"""

    def test_bugfix_analysis_schema_valid(self):
        """合法 analysis 通过 schema 校验"""
        data = BugFixAnalysis(
            root_cause="测试根因",
            affected_files=["src/api/routes.py"],
            fix_steps=["修复1"],
            risk_level="medium",
            estimated_impact="中",
            needs_human_review=True,
            evidence=[{"source": "test.log", "summary": "发现异常"}],
        )
        assert data.root_cause == "测试根因"
        assert len(data.evidence) == 1

    def test_bugfix_analysis_schema_minimal(self):
        """最小字段 analysis 通过 schema 校验"""
        data = BugFixAnalysis(root_cause="test")
        assert data.root_cause == "test"
        assert data.risk_level == "medium"  # default
        assert data.needs_human_review is True  # default

    def test_bugfix_proposal_schema_valid(self):
        """合法 proposal 通过 schema 校验"""
        data = BugFixProposal(
            fix_description="修复描述",
            code_changes=[
                {
                    "file_path": "src/api/routes.py",
                    "change_type": "modify",
                    "diff": "-old\n+new",
                    "reason": "修复",
                }
            ],
            risk_level="low",
            estimated_impact="低",
            test_suggestions=["测试1"],
            requires_approval=True,
        )
        assert data.fix_description == "修复描述"
        assert len(data.code_changes) == 1
        assert data.code_changes[0].file_path == "src/api/routes.py"

    def test_bugfix_proposal_add_change_type(self):
        """change_type 可以是 add/modify/delete"""
        add_proposal = BugFixProposal(
            fix_description="新增文件",
            code_changes=[{
                "file_path": "src/new_module/new.py",
                "change_type": "add",
                "diff": "",
                "reason": "新功能",
            }]
        )
        assert add_proposal.code_changes[0].change_type == "add"

        delete_proposal = BugFixProposal(
            fix_description="删除文件",
            code_changes=[{
                "file_path": "src/old.py",
                "change_type": "delete",
                "diff": "",
                "reason": "废弃",
            }]
        )
        assert delete_proposal.code_changes[0].change_type == "delete"
