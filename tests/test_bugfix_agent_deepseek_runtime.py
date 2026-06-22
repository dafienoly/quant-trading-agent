from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.llm.schemas import BugFixAnalysis, BugFixProposal, DeepSeekResult
from src.product_app.bug_fix_agent import BugFixAgent


def _bug_report(**overrides) -> dict:
    report = {
        "bug_id": "BUG_TEST_001",
        "title": "数据校验失败",
        "component": "product_app",
        "severity": "medium",
        "summary": "输入为空",
        "exception_type": "ValueError",
        "exception_message": "empty input",
        "sanitized_traceback": "traceback",
        "user_action": "运行分析",
        "endpoint_or_page": "/product/bugs",
    }
    report.update(overrides)
    return report


def _analysis_data() -> dict:
    return {
        "status": "ok",
        "root_cause": "输入未校验",
        "affected_files": ["src/product_app/service.py"],
        "fix_steps": ["增加输入校验"],
        "risk_level": "medium",
        "estimated_impact": "仅影响缺陷分析",
        "needs_human_review": True,
        "evidence": [],
    }


def _proposal_data(path: str = "src/product_app/service.py") -> dict:
    return {
        "status": "ok",
        "fix_description": "增加输入校验",
        "code_changes": [
            {
                "file_path": path,
                "change_type": "modify",
                "diff": "-old\n+new",
                "reason": "拒绝空输入",
            }
        ],
        "risk_level": "low",
        "estimated_impact": "局部",
        "test_suggestions": ["增加空输入测试"],
        "requires_approval": True,
    }


class FakeRuntime:
    def __init__(self, results: list[DeepSeekResult]) -> None:
        self.results = results
        self.requests = []

    def chat_json(self, request):
        self.requests.append(request)
        return self.results.pop(0)


def test_analyze_delegates_to_runtime_and_returns_validated_data(tmp_path):
    runtime = FakeRuntime([DeepSeekResult(status="ok", data=_analysis_data(), model="fake")])
    agent = BugFixAgent(runtime=runtime)
    agent.project_root = tmp_path

    result = agent.analyze(_bug_report())

    assert result["root_cause"] == "输入未校验"
    assert result["needs_human_review"] is True
    request = runtime.requests[0]
    assert request.profile == "bugfix_analysis"
    assert request.schema_name == "bugfix_analysis"
    assert "read_project_file" in request.tools
    assert "search_project_text" in request.tools


def test_analyze_runtime_failure_is_not_treated_as_success(tmp_path):
    runtime = FakeRuntime(
        [
            DeepSeekResult(
                status="invalid_response",
                error={"reason": "empty_content"},
                model="fake",
            )
        ]
    )
    agent = BugFixAgent(runtime=runtime)
    agent.project_root = tmp_path

    result = agent.analyze(_bug_report())

    assert result == {"status": "invalid_response", "error": "empty_content"}
    assert "root_cause" not in result


def test_analyze_defensively_rejects_unvalidated_fake_runtime_data(tmp_path):
    runtime = FakeRuntime(
        [DeepSeekResult(status="ok", data={"status": "ok", "root_cause": "x"}, model="fake")]
    )
    agent = BugFixAgent(runtime=runtime)
    agent.project_root = tmp_path

    result = agent.analyze(_bug_report())

    assert result["status"] == "invalid_response"
    assert result["error"] == "schema_validation_failed"


def test_propose_fix_delegates_and_preserves_approval(tmp_path):
    runtime = FakeRuntime([DeepSeekResult(status="ok", data=_proposal_data(), model="fake")])
    agent = BugFixAgent(runtime=runtime)
    agent.project_root = tmp_path

    result = agent.propose_fix(_bug_report(), _analysis_data())

    assert result["fix_description"] == "增加输入校验"
    assert result["requires_approval"] is True
    assert runtime.requests[0].profile == "bugfix_proposal"


def test_propose_fix_still_blocks_restricted_module(tmp_path):
    runtime = FakeRuntime(
        [
            DeepSeekResult(
                status="ok",
                data=_proposal_data("src/risk_engine/runtime.py"),
                model="fake",
            )
        ]
    )
    agent = BugFixAgent(runtime=runtime)
    agent.project_root = tmp_path

    result = agent.propose_fix(_bug_report(), _analysis_data())

    assert result["blocked"] is True
    assert result["blocked_files"] == ["src/risk_engine/runtime.py"]


def test_bugfix_agent_source_has_no_direct_openai_client():
    source = Path("src/product_app/bug_fix_agent.py").read_text(encoding="utf-8")

    assert "from openai import" not in source
    assert "chat.completions.create" not in source
    assert "_call_deepseek" not in source
    assert "raw_analysis" not in source


def test_bugfix_schemas_force_human_review_and_approval():
    invalid_analysis = _analysis_data()
    invalid_analysis["needs_human_review"] = False
    invalid_proposal = _proposal_data()
    invalid_proposal["requires_approval"] = False

    with pytest.raises(ValidationError):
        BugFixAnalysis.model_validate(invalid_analysis)
    with pytest.raises(ValidationError):
        BugFixProposal.model_validate(invalid_proposal)


def test_llm_runtime_has_no_trading_execution_imports():
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(Path("src/llm").glob("*.py"))
    )

    for forbidden in (
        "src.broker",
        "src.execution_engine",
        "src.order",
        "submit_order",
        "place_order",
        "send_order",
    ):
        assert forbidden not in source
