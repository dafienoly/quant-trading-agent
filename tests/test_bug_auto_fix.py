"""BUG Auto-Fix System 集成测试

覆盖 BugFixAgent、BugWatchdog、BugFixWorkflow 和 API 端点，
使用 monkeypatch 模拟 DeepSeek API 响应和外部依赖。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.product_app.bug_fix_agent import BugFixAgent
from src.product_app.bug_fix_workflow import BugFixWorkflow
from src.product_app.bug_watchdog import BugWatchdog
from src.product_app.service_manager import JobState, ServiceManager


# ============================================================
# 辅助工具
# ============================================================


class _MockChoice:
    """模拟 OpenAI response.choices[0]"""

    def __init__(self, content: str):
        self.message = _MockMessage(content)


class _MockMessage:
    """模拟 OpenAI response.choices[0].message"""

    def __init__(self, content: str):
        self.content = content


class _MockResponse:
    """模拟 OpenAI chat.completions.create() 返回值"""

    def __init__(self, content: str):
        self.choices = [_MockChoice(content)]


class _MockCompletions:
    """模拟 OpenAI chat.completions"""

    def __init__(self, side_effects: list):
        """side_effects: 每次调用返回的内容或异常列表"""
        self._side_effects = list(side_effects)
        self._call_count = 0

    def create(self, **kwargs):
        idx = self._call_count
        self._call_count += 1
        if idx < len(self._side_effects):
            effect = self._side_effects[idx]
            if isinstance(effect, Exception):
                raise effect
            return _MockResponse(effect)
        return _MockResponse("")


class _MockChat:
    """模拟 OpenAI chat"""

    def __init__(self, completions: _MockCompletions):
        self.completions = completions


class _MockOpenAIClient:
    """模拟 OpenAI 客户端"""

    def __init__(self, side_effects: list, **kwargs):
        self.chat = _MockChat(_MockCompletions(side_effects))


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


def _write_bug_json(bug_dir: Path, bug_id: str, **extra_fields) -> Path:
    """在指定目录下写入 Bug JSON 文件"""
    data = _make_bug_report_dict(bug_id=bug_id, **extra_fields)
    bug_dir.mkdir(parents=True, exist_ok=True)
    json_path = bug_dir / f"{bug_id}.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


# ============================================================
# TestBugFixAgent
# ============================================================


class TestBugFixAgent:
    """BugFixAgent 单元测试：使用 monkeypatch 模拟 DeepSeek API"""

    def test_analyze_success(self, monkeypatch, tmp_path):
        """测试 analyze() 正常返回根因分析结果"""
        analysis_json = json.dumps({
            "root_cause": "数据源返回空值未做校验",
            "affected_files": ["src/data_gateway/akshare_provider.py"],
            "fix_steps": ["添加空值校验", "添加重试逻辑"],
            "risk_level": "medium",
            "estimated_impact": "影响数据获取模块",
        })

        monkeypatch.setattr(
            "src.product_app.bug_fix_agent.OpenAI",
            lambda **kwargs: _MockOpenAIClient(side_effects=[analysis_json]),
        )

        agent = BugFixAgent()
        agent.project_root = tmp_path

        bug_report = _make_bug_report_dict()
        result = agent.analyze(bug_report)

        assert "root_cause" in result
        assert result["root_cause"] == "数据源返回空值未做校验"
        assert "affected_files" in result
        assert len(result["affected_files"]) == 1
        assert "fix_steps" in result
        assert result["risk_level"] == "medium"
        assert "estimated_impact" in result

    def test_analyze_json_in_markdown_codeblock(self, monkeypatch):
        """测试 analyze() 能解析 markdown 代码块中的 JSON"""
        analysis_data = {
            "root_cause": "缺少空值检查",
            "affected_files": [],
            "fix_steps": [],
            "risk_level": "low",
            "estimated_impact": "无",
        }
        wrapped = "```json\n" + json.dumps(analysis_data, ensure_ascii=False) + "\n```"

        monkeypatch.setattr(
            "src.product_app.bug_fix_agent.OpenAI",
            lambda **kwargs: _MockOpenAIClient(side_effects=[wrapped]),
        )

        agent = BugFixAgent()
        result = agent.analyze(_make_bug_report_dict())

        assert "root_cause" in result
        assert result["root_cause"] == "缺少空值检查"

    def test_analyze_non_json_response(self, monkeypatch):
        """测试 analyze() 对非 JSON 响应返回 raw_analysis"""
        plain_text = "这个 Bug 是因为数据源返回了空值，建议添加校验逻辑。"

        monkeypatch.setattr(
            "src.product_app.bug_fix_agent.OpenAI",
            lambda **kwargs: _MockOpenAIClient(side_effects=[plain_text]),
        )

        agent = BugFixAgent()
        result = agent.analyze(_make_bug_report_dict())

        assert "raw_analysis" in result
        assert plain_text in result["raw_analysis"]

    def test_propose_fix_success(self, monkeypatch):
        """测试 propose_fix() 正常返回修复方案"""
        proposal_json = json.dumps({
            "fix_description": "添加空值校验和重试逻辑",
            "code_changes": [
                {
                    "file_path": "src/data_gateway/akshare_provider.py",
                    "change_type": "modify",
                    "diff": "--- a/src/data_gateway/akshare_provider.py\n+++ b/src/data_gateway/akshare_provider.py\n@@ -10,3 +10,3 @@\n-old_code\n+new_code\n",
                }
            ],
            "risk_level": "low",
            "estimated_impact": "仅影响数据获取",
            "test_suggestions": ["测试空值场景"],
        })

        monkeypatch.setattr(
            "src.product_app.bug_fix_agent.OpenAI",
            lambda **kwargs: _MockOpenAIClient(side_effects=[proposal_json]),
        )

        agent = BugFixAgent()
        bug_report = _make_bug_report_dict()
        analysis = {"root_cause": "test", "affected_files": [], "fix_steps": []}
        result = agent.propose_fix(bug_report, analysis)

        assert "fix_description" in result
        assert result["fix_description"] == "添加空值校验和重试逻辑"
        assert "code_changes" in result
        assert len(result["code_changes"]) == 1
        assert result["risk_level"] == "low"

    def test_propose_fix_blocked_module(self, monkeypatch):
        """测试 propose_fix() 检测到受限模块时返回 blocked"""
        proposal_json = json.dumps({
            "fix_description": "修改风控引擎",
            "code_changes": [
                {
                    "file_path": "src/risk_engine/runtime.py",
                    "change_type": "modify",
                    "diff": "--- a/src/risk_engine/runtime.py\n+++ b/src/risk_engine/runtime.py\n@@ -1,1 +1,1 @@\n-old\n+new\n",
                }
            ],
            "risk_level": "critical",
            "estimated_impact": "风控模块",
            "test_suggestions": [],
        })

        monkeypatch.setattr(
            "src.product_app.bug_fix_agent.OpenAI",
            lambda **kwargs: _MockOpenAIClient(side_effects=[proposal_json]),
        )

        agent = BugFixAgent()
        bug_report = _make_bug_report_dict()
        analysis = {"root_cause": "test", "affected_files": [], "fix_steps": []}
        result = agent.propose_fix(bug_report, analysis)

        assert result.get("blocked") is True
        assert "blocked_files" in result
        assert any("risk_engine" in f for f in result["blocked_files"])

    def test_execute_fix_rejects_blocked_module(self):
        """测试 execute_fix() 二次阻断受限模块，防止手工篡改 proposal 绕过审批"""
        agent = BugFixAgent()
        proposal = {
            "code_changes": [
                {
                    "file_path": "src/execution_engine/live_broker.py",
                    "change_type": "modify",
                    "diff": "--- a/src/execution_engine/live_broker.py\n+++ b/src/execution_engine/live_broker.py\n@@ -1,1 +1,1 @@\n-old\n+new\n",
                }
            ]
        }

        result = agent.execute_fix(_make_bug_report_dict(), proposal)

        assert result["success"] is False
        assert result["blocked"] is True
        assert "execution_engine" in result["blocked_files"][0]

    def test_is_blocked_module(self):
        """测试 _is_blocked_module() 对各种文件路径的判断"""
        agent = BugFixAgent()

        # 受限模块
        blocked, files = agent._is_blocked_module([{"file_path": "src/risk_engine/runtime.py"}])
        assert blocked is True
        assert len(files) == 1

        blocked, files = agent._is_blocked_module([{"file_path": "src/trading_log/recorder.py"}])
        assert blocked is True

        blocked, files = agent._is_blocked_module([{"file_path": "src/backtest_report/generator.py"}])
        assert blocked is True

        # 非受限模块
        blocked, files = agent._is_blocked_module([{"file_path": "src/api/routes.py"}])
        assert blocked is False
        assert files == []

        # 空列表
        blocked, files = agent._is_blocked_module([])
        assert blocked is False

        # 混合：受限 + 非受限
        blocked, files = agent._is_blocked_module([
            {"file_path": "src/api/routes.py"},
            {"file_path": "src/risk_engine/models.py"},
        ])
        assert blocked is True
        assert len(files) == 1

    def test_call_deepseek_retry(self, monkeypatch):
        """测试 _call_deepseek() 的重试机制：前两次失败，第三次成功"""
        call_count = 0

        class _FlakyOpenAI:
            def __init__(self, **kwargs):
                pass

            @property
            def chat(self):
                return self

            @property
            def completions(self):
                return self

            def create(self, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise ConnectionError("API 连接失败")
                return _MockResponse("重试成功")

        # 跳过 time.sleep 以加速测试
        monkeypatch.setattr("src.product_app.bug_fix_agent.time.sleep", lambda s: None)
        monkeypatch.setattr("src.product_app.bug_fix_agent.OpenAI", _FlakyOpenAI)

        agent = BugFixAgent()
        result = agent._call_deepseek("system", "user")

        assert result == "重试成功"
        assert call_count == 3

    def test_parse_json_response(self):
        """测试 _parse_json_response() 对各种输入的处理"""
        # 1. 合法 JSON 字符串
        valid_json = '{"key": "value", "num": 42}'
        result = BugFixAgent._parse_json_response(valid_json)
        assert result == {"key": "value", "num": 42}

        # 2. markdown 代码块中的 JSON
        codeblock = '```json\n{"key": "wrapped"}\n```'
        result = BugFixAgent._parse_json_response(codeblock)
        assert result == {"key": "wrapped"}

        # 3. 无语言标注的代码块
        codeblock_no_lang = '```\n{"key": "no_lang"}\n```'
        result = BugFixAgent._parse_json_response(codeblock_no_lang)
        assert result == {"key": "no_lang"}

        # 4. 非 JSON 文本
        plain = "This is just plain text, not JSON at all."
        result = BugFixAgent._parse_json_response(plain)
        assert "raw_analysis" in result
        assert plain in result["raw_analysis"]


# ============================================================
# TestBugWatchdog
# ============================================================


class TestBugWatchdog:
    """BugWatchdog 单元测试：使用 tmp_path 和回调验证"""

    def test_process_existing_bugs(self, tmp_path):
        """测试 process_existing_bugs() 能发现并回调已有 Bug 文件"""
        watch_dir = tmp_path / "open"
        watch_dir.mkdir()

        callback_data = []

        def on_bug(bug_id: str, data: dict):
            callback_data.append((bug_id, data))

        _write_bug_json(watch_dir, "BUG_20260610_XYZ789", component="api")

        watchdog = BugWatchdog(on_new_bug_callback=on_bug)
        watchdog._watch_path = watch_dir
        watchdog.process_existing_bugs()

        assert len(callback_data) == 1
        assert callback_data[0][0] == "BUG_20260610_XYZ789"
        assert callback_data[0][1]["component"] == "api"

    def test_deduplication(self, tmp_path):
        """测试重复 Bug 只触发一次回调"""
        watch_dir = tmp_path / "open"
        watch_dir.mkdir()

        callback_count = []

        def on_bug(bug_id: str, data: dict):
            callback_count.append(bug_id)

        _write_bug_json(watch_dir, "BUG_20260610_DUP001")

        watchdog = BugWatchdog(on_new_bug_callback=on_bug)
        watchdog._watch_path = watch_dir

        # 第一次处理
        watchdog.process_existing_bugs()
        assert len(callback_count) == 1

        # 第二次处理同一 Bug，应去重
        watchdog.process_existing_bugs()
        assert len(callback_count) == 1

    def test_process_existing_bugs_skips_non_open_status(self, tmp_path):
        """测试 watchdog 只自动分析 open 状态 Bug"""
        watch_dir = tmp_path / "open"
        watch_dir.mkdir()

        callback_count = []

        def on_bug(bug_id: str, data: dict):
            callback_count.append(bug_id)

        _write_bug_json(watch_dir, "BUG_20260610_PROP01", status="proposed")

        watchdog = BugWatchdog(on_new_bug_callback=on_bug)
        watchdog._watch_path = watch_dir
        watchdog.process_existing_bugs()

        assert callback_count == []

    def test_stop(self, tmp_path):
        """测试 start/stop 后 is_running() 返回 False"""
        watch_dir = tmp_path / "open"
        watch_dir.mkdir()

        watchdog = BugWatchdog()
        watchdog._watch_path = watch_dir

        # 使用轮询模式（不依赖 watchdog 库）
        # 直接启动轮询
        watchdog._start_polling()
        assert watchdog.is_running() is True

        watchdog.stop()
        # 等待线程退出
        time.sleep(0.5)
        assert watchdog.is_running() is False


# ============================================================
# TestBugFixWorkflow
# ============================================================


class TestBugFixWorkflow:
    """BugFixWorkflow 单元测试：模拟 BugFixAgent 和 FeedbackService"""

    def test_valid_transitions(self):
        """测试 VALID_TRANSITIONS 字典定义正确"""
        vt = BugFixWorkflow.VALID_TRANSITIONS

        assert "analyzing" in vt["open"]
        assert "proposed" in vt["analyzing"]
        assert "blocked" in vt["analyzing"]
        assert "approved" in vt["proposed"]
        assert "rejected" in vt["proposed"]
        assert "fixing" in vt["approved"]
        assert "analyzing" in vt["rejected"]
        assert "verified" in vt["fixing"]
        assert "fix_failed" in vt["fixing"]
        assert "fixing" in vt["fix_failed"]
        assert "open" in vt["fix_failed"]
        assert "fixed" in vt["verified"]
        assert vt["blocked"] == []

    def test_invalid_transition(self, tmp_path, monkeypatch):
        """测试非法状态转换返回 False"""
        open_dir = tmp_path / "open"
        _write_bug_json(open_dir, "BUG_20260610_INV001", status="open")

        # 重定向 _BUG_DIRS 和 _PROJECT_ROOT
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path
        )

        # 模拟 FeedbackService
        class _MockFeedbackService:
            def update_bug_status(self, bug_id, new_status):
                return True

            def update_bug_fields(self, bug_id, **fields):
                return True

        workflow = BugFixWorkflow()
        workflow._feedback_service = _MockFeedbackService()

        # open -> fixed 是非法转换
        result = workflow._transition("BUG_20260610_INV001", "fixed")
        assert result is False

    def test_process_bug_full_flow(self, tmp_path, monkeypatch):
        """测试 process_bug() 完整流程：open -> analyzing -> proposed"""
        open_dir = tmp_path / "open"
        analysis_dir = tmp_path / "analysis"
        _write_bug_json(open_dir, "BUG_20260610_FLOW01", status="open")

        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._ANALYSIS_DIR", analysis_dir
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path
        )

        # 模拟 FeedbackService
        class _MockFeedbackService:
            def __init__(self):
                self.status_updates = []

            def update_bug_status(self, bug_id, new_status):
                self.status_updates.append(new_status)
                # 同步更新文件中的状态
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["status"] = new_status
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def update_bug_fields(self, bug_id, **fields):
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data.update(fields)
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def _render_markdown(self, report):
                return f"# {report.title}"

        mock_fs = _MockFeedbackService()
        workflow = BugFixWorkflow()
        workflow._feedback_service = mock_fs

        # 模拟 BugFixAgent
        class _MockAgent:
            def analyze(self, bug_report):
                return {
                    "root_cause": "测试根因",
                    "affected_files": [],
                    "fix_steps": ["步骤1"],
                    "risk_level": "low",
                    "estimated_impact": "低",
                }

            def propose_fix(self, bug_report, analysis):
                return {
                    "fix_description": "测试修复",
                    "code_changes": [],
                    "risk_level": "low",
                    "estimated_impact": "低",
                    "test_suggestions": [],
                }

        workflow._bug_fix_agent = _MockAgent()

        result = workflow.process_bug("BUG_20260610_FLOW01")

        assert result["status"] == "proposed"
        assert result["bug_id"] == "BUG_20260610_FLOW01"
        assert "analysis" in result
        assert "proposal" in result
        # 验证状态流转：open -> analyzing -> proposed
        assert "analyzing" in mock_fs.status_updates
        assert "proposed" in mock_fs.status_updates

    def test_approve_fix(self, tmp_path, monkeypatch):
        """测试 approve_fix() 流程：proposed -> approved -> fixing -> verified -> fixed"""
        open_dir = tmp_path / "open"
        analysis_dir = tmp_path / "analysis"
        _write_bug_json(
            open_dir,
            "BUG_20260610_APRV01",
            status="proposed",
            fix_proposal={
                "fix_description": "测试修复",
                "code_changes": [],
                "risk_level": "low",
            },
        )

        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._ANALYSIS_DIR", analysis_dir
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path
        )

        # 模拟 FeedbackService
        class _MockFeedbackService:
            def __init__(self):
                self.status_updates = []

            def update_bug_status(self, bug_id, new_status):
                self.status_updates.append(new_status)
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["status"] = new_status
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def update_bug_fields(self, bug_id, **fields):
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data.update(fields)
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def _render_markdown(self, report):
                return f"# {report.title}"

        mock_fs = _MockFeedbackService()
        workflow = BugFixWorkflow()
        workflow._feedback_service = mock_fs

        # 模拟 BugFixAgent.execute_fix 返回成功
        class _MockAgent:
            def execute_fix(self, bug_report, proposal):
                return {"success": True, "test_output": "All tests passed"}

        workflow._bug_fix_agent = _MockAgent()

        # 模拟 git 命令
        def mock_run(cmd, **kwargs):
            class _Result:
                stdout = "abc123def"
                stderr = ""
                returncode = 0
            return _Result()

        monkeypatch.setattr("subprocess.run", mock_run)

        result = workflow.approve_fix("BUG_20260610_APRV01", comment="LGTM")

        assert result["status"] == "fixed"
        assert result["bug_id"] == "BUG_20260610_APRV01"
        # 验证状态流转
        assert "approved" in mock_fs.status_updates
        assert "fixing" in mock_fs.status_updates
        assert "verified" in mock_fs.status_updates
        assert "fixed" in mock_fs.status_updates

    def test_approve_fix_marks_failed_when_git_commit_fails(self, tmp_path, monkeypatch):
        """测试 git commit 失败时不得把 Bug 误标为 fixed"""
        open_dir = tmp_path / "open"
        _write_bug_json(
            open_dir,
            "BUG_20260610_COMMIT",
            status="proposed",
            fix_proposal={
                "fix_description": "测试修复",
                "code_changes": [{"file_path": "src/product_app/example.py"}],
                "risk_level": "low",
            },
        )

        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr("src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path)

        class _MockFeedbackService:
            def __init__(self):
                self.status_updates = []
                self.last_fields = {}

            def update_bug_status(self, bug_id, new_status):
                self.status_updates.append(new_status)
                json_path = open_dir / f"{bug_id}.json"
                data = json.loads(json_path.read_text(encoding="utf-8"))
                data["status"] = new_status
                json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                return True

            def update_bug_fields(self, bug_id, **fields):
                self.last_fields.update(fields)
                json_path = open_dir / f"{bug_id}.json"
                data = json.loads(json_path.read_text(encoding="utf-8"))
                data.update(fields)
                json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                return True

        class _MockAgent:
            def execute_fix(self, bug_report, proposal):
                return {"success": True, "test_output": "All tests passed"}

        def mock_run(cmd, **kwargs):
            class _Result:
                stdout = ""
                stderr = ""
                returncode = 0

            result = _Result()
            if cmd[:2] == ["git", "commit"]:
                result.returncode = 1
                result.stderr = "nothing to commit"
            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        workflow = BugFixWorkflow()
        workflow._feedback_service = _MockFeedbackService()
        workflow._bug_fix_agent = _MockAgent()

        result = workflow.approve_fix("BUG_20260610_COMMIT", comment="LGTM")

        assert result["status"] == "fix_failed"
        assert result["error"] == "nothing to commit"
        assert "fixed" not in workflow._feedback_service.status_updates
        assert workflow._feedback_service.last_fields["fix_result"]["commit_failed"] is True

    def test_reject_fix(self, tmp_path, monkeypatch):
        """测试 reject_fix() 流程：proposed -> rejected"""
        open_dir = tmp_path / "open"
        _write_bug_json(
            open_dir,
            "BUG_20260610_REJ001",
            status="proposed",
            fix_proposal={"fix_description": "测试修复"},
        )

        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path
        )

        class _MockFeedbackService:
            def __init__(self):
                self.status_updates = []

            def update_bug_status(self, bug_id, new_status):
                self.status_updates.append(new_status)
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["status"] = new_status
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def update_bug_fields(self, bug_id, **fields):
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data.update(fields)
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def _render_markdown(self, report):
                return f"# {report.title}"

        mock_fs = _MockFeedbackService()
        workflow = BugFixWorkflow()
        workflow._feedback_service = mock_fs

        result = workflow.reject_fix("BUG_20260610_REJ001", comment="风险过高")

        assert result["status"] == "rejected"
        assert result["bug_id"] == "BUG_20260610_REJ001"
        assert "rejected" in mock_fs.status_updates

    def test_get_bug_status(self, tmp_path, monkeypatch):
        """测试 get_bug_status() 返回正确的状态标志"""
        open_dir = tmp_path / "open"
        _write_bug_json(
            open_dir,
            "BUG_20260610_STS001",
            status="proposed",
            analysis_report={"root_cause": "test"},
            fix_proposal={"fix_description": "test"},
            fix_result=None,
        )

        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path
        )

        workflow = BugFixWorkflow()
        result = workflow.get_bug_status("BUG_20260610_STS001")

        assert result is not None
        assert result["status"] == "proposed"
        assert result["has_analysis"] is True
        assert result["has_proposal"] is True
        assert result["has_fix_result"] is False
        assert result["approval_status"] == "pending"


# ============================================================
# TestBugFixAPIEndpoints
# ============================================================


class TestBugFixAPIEndpoints:
    """API 端点测试：使用 FastAPI TestClient"""

    @pytest.fixture
    def client(self):
        """创建 TestClient"""
        return TestClient(create_app())

    def test_get_bug_analysis(self, client, tmp_path, monkeypatch):
        """测试 GET /product/feedback/{bug_id}/analysis"""
        open_dir = tmp_path / "open"
        _write_bug_json(
            open_dir,
            "BUG_20260610_API001",
            status="proposed",
            analysis_report={"root_cause": "test"},
            fix_proposal={"fix_description": "test"},
        )

        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path
        )

        response = client.get("/product/feedback/BUG_20260610_API001/analysis")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["bug_id"] == "BUG_20260610_API001"
        assert "workflow_status" in body
        assert body["workflow_status"]["status"] == "proposed"
        assert body["analysis_report"] == {"root_cause": "test"}
        assert body["fix_proposal"] == {"fix_description": "test"}

    def test_approve_bug_fix(self, client, tmp_path, monkeypatch):
        """测试 POST /product/feedback/{bug_id}/approve"""
        open_dir = tmp_path / "open"
        analysis_dir = tmp_path / "analysis"
        _write_bug_json(
            open_dir,
            "BUG_20260610_API002",
            status="proposed",
            fix_proposal={"fix_description": "test", "code_changes": []},
        )

        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._ANALYSIS_DIR", analysis_dir
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path
        )

        # 模拟 FeedbackService
        class _MockFeedbackService:
            def update_bug_status(self, bug_id, new_status):
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["status"] = new_status
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def update_bug_fields(self, bug_id, **fields):
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data.update(fields)
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def _render_markdown(self, report):
                return f"# {report.title}"

        # 模拟 BugFixAgent.execute_fix
        class _MockAgent:
            def execute_fix(self, bug_report, proposal):
                return {"success": True, "test_output": "All tests passed"}

        # 模拟 git 命令
        def mock_run(cmd, **kwargs):
            class _Result:
                stdout = "abc123def"
                stderr = ""
                returncode = 0
            return _Result()

        monkeypatch.setattr("subprocess.run", mock_run)

        # 清除 BugFixWorkflow 单例缓存
        from src.api.product_routes import _get_bug_fix_workflow
        if hasattr(_get_bug_fix_workflow, "_instance"):
            delattr(_get_bug_fix_workflow, "_instance")

        # 通过 monkeypatch BugFixWorkflow 的延迟加载属性注入 mock
        original_init = BugFixWorkflow.__init__

        def patched_init(self_wf):
            original_init(self_wf)
            self_wf._feedback_service = _MockFeedbackService()
            self_wf._bug_fix_agent = _MockAgent()

        monkeypatch.setattr(BugFixWorkflow, "__init__", patched_init)

        response = client.post("/product/feedback/BUG_20260610_API002/approve")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "fixed"
        assert body["bug_id"] == "BUG_20260610_API002"

    def test_reject_bug_fix(self, client, tmp_path, monkeypatch):
        """测试 POST /product/feedback/{bug_id}/reject"""
        open_dir = tmp_path / "open"
        _write_bug_json(
            open_dir,
            "BUG_20260610_API003",
            status="proposed",
            fix_proposal={"fix_description": "test"},
        )

        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path
        )

        class _MockFeedbackService:
            def update_bug_status(self, bug_id, new_status):
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["status"] = new_status
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def update_bug_fields(self, bug_id, **fields):
                json_path = open_dir / f"{bug_id}.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data.update(fields)
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                return True

            def _render_markdown(self, report):
                return f"# {report.title}"

        original_init = BugFixWorkflow.__init__

        def patched_init(self_wf):
            original_init(self_wf)
            self_wf._feedback_service = _MockFeedbackService()

        monkeypatch.setattr(BugFixWorkflow, "__init__", patched_init)

        response = client.post("/product/feedback/BUG_20260610_API003/reject")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "rejected"
        assert body["bug_id"] == "BUG_20260610_API003"

    def test_get_bug_fix_status(self, client, tmp_path, monkeypatch):
        """测试 GET /product/feedback/{bug_id}/fix-status"""
        open_dir = tmp_path / "open"
        _write_bug_json(
            open_dir,
            "BUG_20260610_API004",
            status="fixing",
            analysis_report={"root_cause": "test"},
            fix_proposal={"fix_description": "test"},
            fix_result=None,
        )

        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._BUG_DIRS",
            [open_dir, tmp_path / "triaged", tmp_path / "fixed", tmp_path / "ignored"],
        )
        monkeypatch.setattr(
            "src.product_app.bug_fix_workflow._PROJECT_ROOT", tmp_path
        )

        response = client.get("/product/feedback/BUG_20260610_API004/fix-status")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["bug_id"] == "BUG_20260610_API004"
        assert "fix_status" in body
        assert body["fix_status"]["status"] == "fixing"
        assert body["fix_status"]["has_analysis"] is True
        assert body["fix_status"]["has_proposal"] is True
        assert body["fix_status"]["has_fix_result"] is False


class TestServiceManagerBugFixAgent:
    """ServiceManager 对 bug_fix_agent 常驻作业的生命周期测试"""

    def test_bug_fix_agent_job_stays_running_until_stopped(self, tmp_path, monkeypatch):
        """测试 bug_fix_agent 启动后保持 RUNNING，并可正常停止 watchdog"""
        instances = []
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        class _FakeWatchdog:
            def __init__(self, on_new_bug_callback=None):
                self._running = False
                instances.append(self)

            def start(self):
                self._running = True

            def stop(self):
                self._running = False

            def is_running(self):
                return self._running

        monkeypatch.setattr("src.product_app.bug_watchdog.BugWatchdog", _FakeWatchdog)

        manager = ServiceManager(state_dir=str(tmp_path / "state"))
        result = manager.start_job("bug_fix_agent")

        assert result["status"] == "ok"

        deadline = time.time() + 2
        while (
            (
                manager.get_job_status("bug_fix_agent")["state"] != JobState.RUNNING.value
                or not instances
            )
            and time.time() < deadline
        ):
            time.sleep(0.05)

        assert manager.get_job_status("bug_fix_agent")["state"] == JobState.RUNNING.value
        assert instances and instances[0].is_running() is True

        stop_result = manager.stop_job("bug_fix_agent")

        assert stop_result["status"] == "ok"
        assert manager.get_job_status("bug_fix_agent")["state"] == JobState.CANCELLED.value
        assert instances[0].is_running() is False

    def test_bug_fix_agent_requires_deepseek_key(self, tmp_path, monkeypatch):
        """缺少 DeepSeek Key 时同步拒绝启动，避免用户误判 Agent 正在处理。"""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        manager = ServiceManager(state_dir=str(tmp_path / "state"))
        result = manager.start_job("bug_fix_agent")

        status = manager.get_job_status("bug_fix_agent")
        assert result["status"] == "error"
        assert "DEEPSEEK_API_KEY" in result["message"]
        assert status["state"] == JobState.FAILED.value
        assert "DEEPSEEK_API_KEY" in status["error_message"]
