"""Bug 自动分析与修复 Agent

基于 DeepSeek API 的自动化 Bug 分析与修复方案生成。
提供 Bug 根因分析、修复方案提议和自动执行修复的能力。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from loguru import logger

try:
    from openai import OpenAI
except ModuleNotFoundError:
    OpenAI = None  # type: ignore[assignment]


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


# ============================================================
# BugFixAgent
# ============================================================

class BugFixAgent:
    """Bug 自动分析与修复 Agent

    通过 DeepSeek API 对 Bug 报告进行根因分析、生成修复方案，
    并在审批后自动执行代码修改和测试验证。
    """

    def __init__(self) -> None:
        from src.llm.model_router import ModelRouter

        config = ModelRouter().get_config()
        self.api_key = os.environ.get(config.api_key_env, "")
        self.api_base = config.api_base
        self.model = config.model
        self.project_root = _PROJECT_ROOT

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
            如果 JSON 解析失败，返回包含 raw_analysis 的字典。
            如果发生异常，返回 {"error": str(e)}。
        """
        try:
            context = self._build_context(bug_report)

            system_prompt = (
                "你是一个专业的量化交易系统 Bug 分析专家。"
                "请根据提供的 Bug 报告和项目代码上下文，分析 Bug 的根本原因。"
                "请以 JSON 格式返回分析结果，包含以下字段：\n"
                "- root_cause: 根本原因分析\n"
                "- affected_files: 受影响的文件列表\n"
                "- fix_steps: 修复步骤列表\n"
                "- risk_level: 风险等级 (low/medium/high/critical)\n"
                "- estimated_impact: 预估影响范围\n"
                "只返回 JSON，不要包含其他内容。"
            )

            user_prompt = (
                f"## Bug 报告\n\n"
                f"**标题**: {bug_report.get('title', '')}\n"
                f"**组件**: {bug_report.get('component', '')}\n"
                f"**严重程度**: {bug_report.get('severity', '')}\n"
                f"**摘要**: {bug_report.get('summary', '')}\n"
                f"**异常类型**: {bug_report.get('exception_type', '')}\n"
                f"**异常消息**: {bug_report.get('exception_message', '')}\n"
                f"**堆栈跟踪**: {bug_report.get('sanitized_traceback', '')}\n"
                f"**用户操作**: {bug_report.get('user_action', '')}\n"
                f"**触发端点**: {bug_report.get('endpoint_or_page', '')}\n"
            )

            if context:
                user_prompt += f"\n## 相关项目代码\n\n{context}"

            response_text = self._call_deepseek(system_prompt, user_prompt)
            return self._parse_json_response(response_text)

        except Exception as e:
            logger.error(f"Bug 分析失败: {e}")
            return {"error": str(e)}

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
                "请以 JSON 格式返回修复方案，包含以下字段：\n"
                "- fix_description: 修复方案描述\n"
                "- code_changes: 代码变更列表，每项包含 file_path、change_type (add/modify/delete)、diff\n"
                "- risk_level: 风险等级 (low/medium/high/critical)\n"
                "- estimated_impact: 预估影响范围\n"
                "- test_suggestions: 测试建议列表\n"
                "diff 格式示例：\n"
                "```diff\n"
                "--- a/file.py\n"
                "+++ b/file.py\n"
                "@@ -10,3 +10,3 @@\n"
                "-old_code\n"
                "+new_code\n"
                "```\n"
                "只返回 JSON，不要包含其他内容。"
            )

            user_prompt = (
                f"## Bug 报告\n\n"
                f"**标题**: {bug_report.get('title', '')}\n"
                f"**组件**: {bug_report.get('component', '')}\n"
                f"**摘要**: {bug_report.get('summary', '')}\n"
                f"**异常消息**: {bug_report.get('exception_message', '')}\n"
                f"\n## 根因分析\n\n{json.dumps(analysis, ensure_ascii=False, indent=2)}"
            )

            response_text = self._call_deepseek(system_prompt, user_prompt)
            proposal = self._parse_json_response(response_text)

            # 检查是否涉及受限模块
            code_changes = proposal.get("code_changes", [])
            is_blocked, blocked_files = self._is_blocked_module(code_changes)
            if is_blocked:
                logger.warning(f"修复方案涉及受限模块: {blocked_files}")
                return {
                    "blocked": True,
                    "blocked_files": blocked_files,
                    "reason": "修复方案涉及受限模块（risk_engine/trading_log/backtest_report），需要人工审核确认",
                }

            return proposal

        except Exception as e:
            logger.error(f"生成修复方案失败: {e}")
            return {"error": str(e)}

    def execute_fix(self, bug_report: dict, proposal: dict) -> dict:
        """执行修复方案，应用代码变更并运行测试

        参数:
            bug_report: Bug 报告字典
            proposal: propose_fix() 返回的修复方案字典

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

            project_root = self.project_root.resolve()
            # 保存原始文件内容，用于回滚
            originals: dict[str, str | None] = {}

            for change in code_changes:
                file_path = change.get("file_path", "")
                if not file_path:
                    continue

                full_path = (self.project_root / file_path).resolve()
                if not full_path.is_relative_to(project_root):
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
            test_result = self._run_tests(code_changes=code_changes)

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

    def _call_deepseek(self, system_prompt: str, user_prompt: str) -> str:
        """调用 DeepSeek API

        使用 OpenAI 兼容 SDK 调用 DeepSeek，支持 3 次重试和指数退避。

        参数:
            system_prompt: 系统提示词
            user_prompt: 用户提示词

        返回:
            模型生成的文本内容

        异常:
            所有重试耗尽后抛出最后一次异常
        """
        max_retries = 3
        last_exception: Exception | None = None

        for attempt in range(max_retries):
            try:
                if OpenAI is None:
                    raise RuntimeError("openai package is not installed; cannot call DeepSeek API")
                client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.api_base,
                )
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return response.choices[0].message.content or ""

            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = 2 ** (attempt + 1)
                    logger.warning(f"DeepSeek API 调用失败 (第{attempt + 1}次)，{delay}秒后重试: {e}")
                    time.sleep(delay)

        raise last_exception  # type: ignore[misc]

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
    def _parse_json_response(text: str) -> dict:
        """解析 LLM 返回的 JSON 文本

        优先直接解析，失败后尝试从 markdown 代码块中提取 JSON。

        参数:
            text: LLM 返回的原始文本

        返回:
            解析后的字典，解析失败时返回包含 raw_analysis 的字典
        """
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取
        pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning("无法解析 LLM 返回的 JSON，返回原始文本")
        return {"raw_analysis": text}

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

    def _run_tests(self, code_changes: list | None = None) -> dict[str, Any]:
        """运行 pytest 测试

        优先运行与修改文件相关的测试，若无匹配则运行全部测试。

        参数:
            code_changes: 代码变更列表，用于选择相关测试文件

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
                cwd=str(self.project_root),
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
