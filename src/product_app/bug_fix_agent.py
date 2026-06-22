"""Bug 自动分析与修复 Agent

基于统一 DeepSeek Runtime 的自动化 Bug 分析与修复方案生成。
提供 Bug 根因分析、修复方案提议和自动执行修复的能力。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import ValidationError

from src.llm.deepseek_runtime import DeepSeekRuntime
from src.llm.model_router import ModelRouter
from src.llm.schemas import BugFixAnalysis, BugFixProposal, DeepSeekRequest


# ============================================================
# 常量定义
# ============================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 组件 -> 源码目录映射
_COMPONENT_DIR_MAP: dict[str, str] = {
    "data_gateway": "src/data_gateway/",
    "risk_engine": "src/risk_engine/",
    "ui_report": "src/ui_report/",
    "api": "src/api/",
    "product_app": "src/product_app/",
}

# 受限模块模式（禁止自动修改）
_BLOCKED_PATTERNS = ("risk_engine", "execution_engine", "trading_log", "backtest_report")

# 上下文文件读取上限
_MAX_CONTEXT_FILES = 3
_MAX_LINES_PER_FILE = 200

_BUGFIX_TOOLS = [
    "read_feedback_bug",
    "search_project_text",
    "read_project_file",
    "read_test_report",
    "read_dev_report",
]


@dataclass
class BugFixExecutionContext:
    """Execution context for running a fix in an isolated worktree.

    When passed to ``execute_fix()``, all file operations and test
    commands run inside ``worktree_path`` instead of the active
    project root, protecting the active development workspace.
    """
    bug_id: str
    project_root: Path
    base_branch: str
    branch_name: str
    worktree_path: Path


# ============================================================
# BugFixAgent
# ============================================================

class BugFixAgent:
    """Bug 自动分析与修复 Agent

    通过 DeepSeek Runtime 对 Bug 报告进行根因分析、生成修复方案，
    并在审批后自动执行代码修改和测试验证。
    """

    def __init__(self, runtime: DeepSeekRuntime | None = None) -> None:
        self._router = ModelRouter()
        config = self._router.get_config()
        self.api_key = os.environ.get(config.api_key_env, "")
        self.api_base = config.api_base
        self.model = config.model
        self.project_root = _PROJECT_ROOT
        self._runtime = runtime

    @property
    def runtime(self) -> DeepSeekRuntime:
        if self._runtime is None:
            self._runtime = DeepSeekRuntime(router=self._router)
        return self._runtime

    # ----------------------------------------------------------
    # 公开方法
    # ----------------------------------------------------------

    def analyze(self, bug_report: dict) -> dict:
        """分析 Bug 报告，返回根因分析结果

        参数:
            bug_report: Bug 报告字典，包含 component、title、summary 等字段

        返回:
            分析结果字典，包含 root_cause、affected_files、fix_steps、
            risk_level、estimated_impact 等键。
            Runtime 或 schema 校验失败时返回结构化失败状态。
        """
        try:
            context = self._build_context(bug_report)

            system_prompt = (
                "你是一个专业的量化交易系统 Bug 分析专家。"
                "请根据提供的 Bug 报告和项目代码上下文，分析 Bug 的根本原因。"
                "只返回符合给定 schema 的 JSON，不得修改代码或执行命令。"
            )
            result = self.runtime.chat_json(
                DeepSeekRequest(
                    profile="bugfix_analysis",
                    schema_name="bugfix_analysis",
                    system_prompt=system_prompt,
                    user_prompt=self._build_analysis_prompt(bug_report, context),
                    tools=_BUGFIX_TOOLS,
                )
            )
            if result.status != "ok" or result.data is None:
                return self._runtime_failure(result.status, result.error)
            try:
                return BugFixAnalysis.model_validate(result.data).model_dump(mode="json")
            except ValidationError as exc:
                logger.warning("Bug 分析结果二次 schema 校验失败 error_count={}", exc.error_count())
                return {"status": "invalid_response", "error": "schema_validation_failed"}

        except Exception as e:
            logger.error("Bug 分析失败 error_type={}", type(e).__name__)
            return {"status": "api_error", "error": "agent_internal_error"}

    def propose_fix(self, bug_report: dict, analysis: dict) -> dict:
        """根据分析结果生成修复方案

        参数:
            bug_report: Bug 报告字典
            analysis: analyze() 返回的分析结果字典

        返回:
            修复方案字典，包含 fix_description、code_changes、risk_level、
            estimated_impact、test_suggestions 等键。
            如果涉及受限模块，返回 {"blocked": True, ...}。
        """
        try:
            system_prompt = (
                "你是一个专业的量化交易系统代码修复专家。"
                "请根据 Bug 报告和根因分析结果，生成具体的修复方案。"
                "只返回符合给定 schema 的 JSON。所有方案必须要求人工审批，"
                "不得修改受限交易、风控、执行、交易日志或回测报告模块。"
            )
            result = self.runtime.chat_json(
                DeepSeekRequest(
                    profile="bugfix_proposal",
                    schema_name="bugfix_proposal",
                    system_prompt=system_prompt,
                    user_prompt=self._build_proposal_prompt(bug_report, analysis),
                    tools=_BUGFIX_TOOLS,
                )
            )
            if result.status != "ok" or result.data is None:
                return self._runtime_failure(result.status, result.error)
            try:
                proposal = BugFixProposal.model_validate(result.data).model_dump(mode="json")
            except ValidationError as exc:
                logger.warning("Bug 修复提案二次 schema 校验失败 error_count={}", exc.error_count())
                return {"status": "invalid_response", "error": "schema_validation_failed"}

            # 检查是否涉及受限模块
            code_changes = proposal.get("code_changes", [])
            is_blocked, blocked_files = self._is_blocked_module(code_changes)
            if is_blocked:
                logger.warning(f"修复方案涉及受限模块: {blocked_files}")
                return {
                    "blocked": True,
                    "blocked_files": blocked_files,
                    "reason": "修复方案涉及受限模块，需要人工审核确认",
                }

            return proposal

        except Exception as e:
            logger.error("生成修复方案失败 error_type={}", type(e).__name__)
            return {"status": "api_error", "error": "agent_internal_error"}

    def execute_fix(
        self,
        bug_report: dict,
        proposal: dict,
        context: BugFixExecutionContext | None = None,
    ) -> dict:
        """执行修复方案，应用代码变更并运行测试

        参数:
            bug_report: Bug 报告字典
            proposal: propose_fix() 返回的修复方案字典
            context: 可选执行上下文。传入时文件操作和测试命令在
                ``context.worktree_path`` 内运行，避免修改活跃工作区。

        返回:
            执行结果字典。成功时包含 {"success": True, "test_output": ...}，
            测试失败时回滚变更并返回 {"success": False, "test_output": ..., "rolled_back": True}。
        """
        try:
            code_changes = proposal.get("code_changes", [])
            if not code_changes:
                return {"success": False, "error": "修复方案未包含 code_changes，拒绝执行自动修复"}

            is_blocked, blocked_files = self._is_blocked_module(code_changes)
            if is_blocked:
                return {
                    "success": False,
                    "blocked": True,
                    "blocked_files": blocked_files,
                    "error": "修复方案涉及受限模块，自动执行已拒绝",
                }

            # Use context root when available, otherwise fallback to project_root
            work_root = context.worktree_path.resolve() if context else self.project_root.resolve()
            # 保存原始文件内容，用于回滚
            originals: dict[str, str | None] = {}

            for change in code_changes:
                file_path = change.get("file_path", "")
                if not file_path:
                    continue

                full_path = (work_root / file_path).resolve()
                if not full_path.is_relative_to(work_root):
                    return {"success": False, "error": f"非法文件路径，已拒绝自动修复: {file_path}"}

                change_type = str(change.get("change_type", "modify")).lower()
                original_content = full_path.read_text(encoding="utf-8") if full_path.exists() else None
                originals[str(full_path)] = original_content

                if change_type == "add" and original_content is None:
                    diff = change.get("diff", "")
                    new_content = change.get("content") or self._extract_added_content(diff)
                    if not new_content:
                        return {"success": False, "error": f"新增文件缺少可应用内容: {file_path}"}
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(new_content, encoding="utf-8")
                    logger.info(f"已新增文件: {file_path}")
                    continue

                if change_type == "delete":
                    if full_path.exists():
                        full_path.unlink()
                        logger.info(f"已删除文件: {file_path}")
                    continue

                if original_content is None:
                    logger.warning(f"目标文件不存在，跳过: {full_path}")
                    continue

                # 解析 diff，执行简单字符串替换
                diff = change.get("diff", "")
                modified_content = self._apply_diff(original_content, diff)
                if modified_content is not None:
                    full_path.write_text(modified_content, encoding="utf-8")
                    logger.info(f"已应用变更: {file_path}")
                else:
                    logger.warning(f"无法应用 diff 到: {file_path}")

            # 运行测试
            test_workdir = str(context.worktree_path) if context else None
            test_result = self._run_tests(code_changes=code_changes, workdir=test_workdir)

            if test_result["passed"]:
                logger.info("测试通过，修复已应用")
                return {"success": True, "test_output": test_result["output"]}

            # 测试失败，回滚变更
            logger.warning("测试失败，开始回滚变更")
            for full_path_str, original_content in originals.items():
                full_path = Path(full_path_str)
                if original_content is None:
                    if full_path.exists():
                        full_path.unlink()
                else:
                    full_path.write_text(original_content, encoding="utf-8")
                logger.info(f"已回滚: {full_path_str}")

            return {
                "success": False,
                "test_output": test_result["output"],
                "rolled_back": True,
            }

        except Exception as e:
            logger.error(f"执行修复失败: {e}")
            return {"success": False, "error": str(e)}

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    @staticmethod
    def _runtime_failure(status: str, error: dict[str, Any] | None) -> dict[str, str]:
        reason = str((error or {}).get("reason", status))
        return {"status": status, "error": reason}

    @staticmethod
    def _build_analysis_prompt(bug_report: dict, context: str) -> str:
        prompt = (
            f"## Bug 报告\n\n"
            f"**Bug ID**: {bug_report.get('bug_id', '')}\n"
            f"**标题**: {bug_report.get('title', '')}\n"
            f"**组件**: {bug_report.get('component', '')}\n"
            f"**严重程度**: {bug_report.get('severity', '')}\n"
            f"**摘要**: {bug_report.get('summary', '')}\n"
            f"**异常类型**: {bug_report.get('exception_type', '')}\n"
            f"**异常消息**: {bug_report.get('exception_message', '')}\n"
            f"**脱敏堆栈**: {bug_report.get('sanitized_traceback', '')}\n"
            f"**用户操作**: {bug_report.get('user_action', '')}\n"
            f"**触发端点**: {bug_report.get('endpoint_or_page', '')}\n"
        )
        if context:
            prompt += f"\n## 相关项目代码\n\n{context}"
        return prompt

    @staticmethod
    def _build_proposal_prompt(bug_report: dict, analysis: dict) -> str:
        return (
            f"## Bug 报告\n\n"
            f"**Bug ID**: {bug_report.get('bug_id', '')}\n"
            f"**标题**: {bug_report.get('title', '')}\n"
            f"**组件**: {bug_report.get('component', '')}\n"
            f"**摘要**: {bug_report.get('summary', '')}\n"
            f"**异常消息**: {bug_report.get('exception_message', '')}\n"
            f"\n## 已校验根因分析\n\n{json.dumps(analysis, ensure_ascii=False, indent=2)}"
        )

    def _build_context(self, bug_report: dict) -> str:
        """根据 Bug 报告的组件信息，收集相关项目代码作为上下文

        参数:
            bug_report: Bug 报告字典

        返回:
            拼接后的代码上下文字符串，未找到时返回空字符串
        """
        component = bug_report.get("component", "")
        relative_dir = _COMPONENT_DIR_MAP.get(component, "src/")
        search_dir = self.project_root / relative_dir

        if not search_dir.exists():
            logger.warning(f"组件目录不存在: {search_dir}")
            return ""

        py_files = sorted(search_dir.glob("*.py"))[:_MAX_CONTEXT_FILES]
        if not py_files:
            return ""

        context_parts: list[str] = []
        for py_file in py_files:
            try:
                lines = py_file.read_text(encoding="utf-8").splitlines()
                truncated = "\n".join(lines[:_MAX_LINES_PER_FILE])
                if len(lines) > _MAX_LINES_PER_FILE:
                    truncated += f"\n... (已截断，共 {len(lines)} 行)"
                context_parts.append(f"### {py_file.relative_to(self.project_root)}\n\n```python\n{truncated}\n```")
            except OSError as e:
                logger.warning(f"读取文件失败 {py_file}: {e}")

        return "\n\n".join(context_parts)

    def _is_blocked_module(self, code_changes: list) -> tuple[bool, list[str]]:
        """检查代码变更是否涉及受限模块

        受限模块包括 risk_engine、trading_log、backtest_report，
        这些模块的修改需要人工审核。

        参数:
            code_changes: 代码变更列表

        返回:
            (是否受限, 受限文件路径列表)
        """
        blocked_files: list[str] = []
        for change in code_changes:
            file_path = change.get("file_path", "")
            for pattern in _BLOCKED_PATTERNS:
                if pattern in file_path:
                    blocked_files.append(file_path)
                    break

        return (len(blocked_files) > 0, blocked_files)

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------

    @staticmethod
    def _apply_diff(original_content: str, diff: str) -> str | None:
        """应用简单的 diff 变更

        解析 diff 中的 -/+ 行，执行字符串替换。

        参数:
            original_content: 原始文件内容
            diff: diff 格式的变更文本

        返回:
            修改后的内容，如果无法应用则返回 None
        """
        old_lines: list[str] = []
        new_lines: list[str] = []

        for line in diff.splitlines():
            if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                continue
            if line.startswith("-"):
                old_lines.append(line[1:])
            elif line.startswith("+"):
                new_lines.append(line[1:])

        if not old_lines:
            return original_content

        old_text = "\n".join(old_lines)
        new_text = "\n".join(new_lines)

        if old_text in original_content:
            return original_content.replace(old_text, new_text, 1)

        logger.warning("diff 中的旧代码未在原文件中找到匹配")
        return None

    @staticmethod
    def _extract_added_content(diff: str) -> str:
        """从新增文件 diff 中提取新增内容。"""
        new_lines: list[str] = []
        for line in diff.splitlines():
            if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                new_lines.append(line[1:])
        if not new_lines:
            return ""
        return "\n".join(new_lines) + "\n"

    def _run_tests(self, code_changes: list | None = None, workdir: str | None = None) -> dict[str, Any]:
        """运行 pytest 测试

        优先运行与修改文件相关的测试，若无匹配则运行全部测试。

        参数:
            code_changes: 代码变更列表，用于选择相关测试文件
            workdir: 可选工作目录，传入时在指定目录运行测试

        返回:
            {"passed": bool, "output": str}
        """
        test_args = [sys.executable, "-m", "pytest", "-x", "--tb=short"]

        # 根据修改文件选择相关测试
        if code_changes:
            test_paths = set()
            for change in code_changes:
                file_path = change.get("file_path", "")
                # 从文件路径推断测试文件名
                parts = file_path.replace("\\", "/").split("/")
                if len(parts) >= 2:
                    module = parts[-2]  # e.g. "product_app", "data_gateway"
                    test_file = self.project_root / "tests" / f"test_{module}.py"
                    if test_file.exists():
                        test_paths.add(str(test_file))
            if test_paths:
                test_args.extend(sorted(test_paths))

        try:
            result = subprocess.run(
                test_args,
                cwd=workdir or str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
            )
            return {
                "passed": result.returncode == 0,
                "output": result.stdout + result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"passed": False, "output": "测试执行超时（300秒）"}
        except FileNotFoundError:
            return {"passed": False, "output": "未找到 pytest，请确认已安装"}
        except Exception as e:
            return {"passed": False, "output": f"测试执行异常: {e}"}
