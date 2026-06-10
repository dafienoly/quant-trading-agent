"""Bug 修复工作流状态机

编排完整的 Bug 修复流程：open→analyzing→proposed→approved→fixing→verified→fixed。
通过状态机约束流转，集成 BugFixAgent 和 FeedbackService 实现自动化修复。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from loguru import logger

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ANALYSIS_DIR = _PROJECT_ROOT / "feedback" / "bugs" / "analysis"

# Bug 报告所在的状态目录
_BUG_DIRS = [
    _PROJECT_ROOT / "feedback" / "bugs" / "open",
    _PROJECT_ROOT / "feedback" / "bugs" / "triaged",
    _PROJECT_ROOT / "feedback" / "bugs" / "fixed",
    _PROJECT_ROOT / "feedback" / "bugs" / "ignored",
]


class BugFixWorkflow:
    """Bug 修复工作流状态机

    管理从 Bug 发现到修复完成的完整生命周期，包括：
    - 状态流转校验
    - 自动分析 & 方案生成
    - 人工审批
    - 自动修复执行 & 验证
    - Git 操作（stash / commit）
    """

    VALID_TRANSITIONS: dict[str, list[str]] = {
        "open": ["analyzing"],
        "analyzing": ["proposed", "blocked", "open"],
        "proposed": ["approved", "rejected"],
        "approved": ["fixing"],
        "rejected": ["analyzing"],
        "fixing": ["verified", "fix_failed"],
        "fix_failed": ["fixing", "open"],
        "verified": ["fixed"],
        "blocked": [],
    }

    def __init__(self) -> None:
        self._bug_fix_agent = None
        self._feedback_service = None
        self._active_workflows: dict[str, str] = {}  # {bug_id: current_state}

    # ----------------------------------------------------------
    # 延迟加载依赖
    # ----------------------------------------------------------

    @property
    def bug_fix_agent(self):
        """延迟加载 BugFixAgent，避免循环导入"""
        if self._bug_fix_agent is None:
            from src.product_app.bug_fix_agent import BugFixAgent
            self._bug_fix_agent = BugFixAgent()
        return self._bug_fix_agent

    @property
    def feedback_service(self):
        """延迟加载 FeedbackService"""
        if self._feedback_service is None:
            from src.product_app.feedback import get_feedback_service
            self._feedback_service = get_feedback_service()
        return self._feedback_service

    # ----------------------------------------------------------
    # 公开方法
    # ----------------------------------------------------------

    def process_bug(self, bug_id: str) -> dict:
        """处理新检测到的 Bug

        执行分析和方案生成，将 Bug 从 open 推进到 proposed。

        参数:
            bug_id: Bug 唯一标识

        返回:
            包含 status、bug_id、analysis、proposal 的字典，
            或包含错误信息的字典。
        """
        # 读取 Bug 报告
        bug_report = self._read_bug_report(bug_id)
        if bug_report is None:
            return {"status": "error", "bug_id": bug_id, "error": f"Bug 报告未找到: {bug_id}"}

        # 检查状态
        if bug_report.get("status") != "open":
            logger.warning(f"Bug {bug_id} 状态不是 open（当前: {bug_report.get('status')}），跳过处理")
            return {"status": "skipped", "bug_id": bug_id, "reason": f"状态不是 open: {bug_report.get('status')}"}

        # 转换到 analyzing
        if not self._transition(bug_id, "analyzing"):
            return {"status": "error", "bug_id": bug_id, "error": "无法转换到 analyzing 状态"}

        # 执行分析
        try:
            analysis = self.bug_fix_agent.analyze(bug_report)
        except Exception as e:
            logger.error(f"Bug {bug_id} 分析失败: {e}")
            self._transition(bug_id, "open")
            return {"status": "error", "bug_id": bug_id, "error": f"分析失败: {e}"}

        # 保存分析报告
        self._update_bug_report(bug_id, analysis_report=analysis)
        self._save_analysis_file(bug_id, "analysis", analysis)

        # 检查分析是否包含错误
        if isinstance(analysis, dict) and analysis.get("error"):
            logger.error(f"Bug {bug_id} 分析结果包含错误: {analysis.get('error')}")
            self._transition(bug_id, "open")
            return {"status": "error", "bug_id": bug_id, "error": analysis.get("error")}

        # 生成修复方案
        try:
            proposal = self.bug_fix_agent.propose_fix(bug_report, analysis)
        except Exception as e:
            logger.error(f"Bug {bug_id} 方案生成失败: {e}")
            self._transition(bug_id, "open")
            return {"status": "error", "bug_id": bug_id, "error": f"方案生成失败: {e}"}

        # 检查方案是否被阻塞
        if isinstance(proposal, dict) and proposal.get("blocked"):
            self._transition(bug_id, "blocked")
            return {"status": "blocked", "bug_id": bug_id, "reason": proposal.get("reason", "方案被阻塞")}

        # 保存修复方案
        self._update_bug_report(bug_id, fix_proposal=proposal)
        self._save_analysis_file(bug_id, "proposal", proposal)

        # 转换到 proposed
        self._transition(bug_id, "proposed")

        return {
            "status": "proposed",
            "bug_id": bug_id,
            "analysis": analysis,
            "proposal": proposal,
        }

    def approve_fix(self, bug_id: str, comment: str = "") -> dict:
        """审批通过修复方案

        验证 Bug 状态为 proposed 后，更新审批信息并自动执行修复。

        参数:
            bug_id: Bug 唯一标识
            comment: 审批备注

        返回:
            修复执行结果字典
        """
        bug_report = self._read_bug_report(bug_id)
        if bug_report is None:
            return {"status": "error", "bug_id": bug_id, "error": f"Bug 报告未找到: {bug_id}"}

        if bug_report.get("status") != "proposed":
            return {"status": "error", "bug_id": bug_id, "error": f"Bug 状态不是 proposed（当前: {bug_report.get('status')}）"}

        # 更新审批信息
        self._update_bug_report(bug_id, approval_status="approved", approval_comment=comment)

        # 转换到 approved
        self._transition(bug_id, "approved")

        # 自动执行修复
        return self._execute_and_verify(bug_id)

    def reject_fix(self, bug_id: str, comment: str = "") -> dict:
        """拒绝修复方案

        验证 Bug 状态为 proposed 后，更新审批信息并转换到 rejected 状态。

        参数:
            bug_id: Bug 唯一标识
            comment: 拒绝备注

        返回:
            包含 status 和 bug_id 的字典
        """
        bug_report = self._read_bug_report(bug_id)
        if bug_report is None:
            return {"status": "error", "bug_id": bug_id, "error": f"Bug 报告未找到: {bug_id}"}

        if bug_report.get("status") != "proposed":
            return {"status": "error", "bug_id": bug_id, "error": f"Bug 状态不是 proposed（当前: {bug_report.get('status')}）"}

        # 更新审批信息
        self._update_bug_report(bug_id, approval_status="rejected", approval_comment=comment)

        # 转换到 rejected
        self._transition(bug_id, "rejected")

        return {"status": "rejected", "bug_id": bug_id}

    def get_bug_status(self, bug_id: str) -> Optional[dict]:
        """获取 Bug 当前状态信息

        参数:
            bug_id: Bug 唯一标识

        返回:
            包含 status、approval_status、has_analysis、has_proposal、has_fix_result
            的字典，未找到返回 None。
        """
        bug_report = self._read_bug_report(bug_id)
        if bug_report is None:
            return None

        return {
            "status": bug_report.get("status", ""),
            "approval_status": bug_report.get("approval_status", "pending"),
            "has_analysis": bug_report.get("analysis_report") is not None,
            "has_proposal": bug_report.get("fix_proposal") is not None,
            "has_fix_result": bug_report.get("fix_result") is not None,
        }

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    def _execute_and_verify(self, bug_id: str) -> dict:
        """执行修复并验证

        转换到 fixing 状态，执行修复，成功则提交，失败则回滚。

        参数:
            bug_id: Bug 唯一标识

        返回:
            修复结果字典
        """
        # 转换到 fixing
        if not self._transition(bug_id, "fixing"):
            return {"status": "error", "bug_id": bug_id, "error": "无法转换到 fixing 状态"}

        bug_report = self._read_bug_report(bug_id)
        proposal = bug_report.get("fix_proposal", {})

        try:
            # Git stash — record whether stash was actually created
            stash_result = subprocess.run(
                ["git", "stash"],
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            stashed = "No local changes to save" not in (stash_result.stdout or "")

            # 执行修复
            fix_result = self.bug_fix_agent.execute_fix(bug_report, proposal)

            if isinstance(fix_result, dict) and fix_result.get("success"):
                # 修复成功
                self._transition(bug_id, "verified")

                # Git commit — only stage files modified by the fix
                title = bug_report.get("title", "untitled")
                commit_msg = f"fix(auto): {bug_id} - {title}"
                code_changes = proposal.get("code_changes", [])
                for change in code_changes:
                    file_path = change.get("file_path", "")
                    if file_path:
                        subprocess.run(
                            ["git", "add", file_path],
                            cwd=str(_PROJECT_ROOT),
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=str(_PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                # 获取 commit hash
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(_PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                commit_hash = result.stdout.strip()

                # 更新 Bug 报告
                self._update_bug_report(
                    bug_id,
                    fix_result=fix_result,
                    git_commit_hash=commit_hash,
                )

                # 转换到 fixed
                self._transition(bug_id, "fixed")

                # 保存修复报告
                self._save_analysis_file(bug_id, "fix_report", fix_result)

                return {
                    "status": "fixed",
                    "bug_id": bug_id,
                    "commit_hash": commit_hash,
                }
            else:
                # 修复失败，回滚
                if stashed:
                    subprocess.run(
                        ["git", "stash", "pop"],
                        cwd=str(_PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                self._transition(bug_id, "fix_failed")

                error_msg = fix_result.get("error", "未知错误") if isinstance(fix_result, dict) else str(fix_result)
                self._update_bug_report(bug_id, fix_result=fix_result)

                return {
                    "status": "fix_failed",
                    "bug_id": bug_id,
                    "error": error_msg,
                }

        except Exception as e:
            # 异常回滚
            logger.error(f"Bug {bug_id} 修复执行异常: {e}")
            if stashed:
                try:
                    subprocess.run(
                        ["git", "stash", "pop"],
                        cwd=str(_PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except Exception:
                    logger.error(f"Bug {bug_id} git stash pop 回滚失败")

            self._transition(bug_id, "fix_failed")
            self._update_bug_report(bug_id, fix_result={"success": False, "error": str(e)})

            return {
                "status": "fix_failed",
                "bug_id": bug_id,
                "error": str(e),
            }

    def _transition(self, bug_id: str, new_status: str) -> bool:
        """执行状态转换

        校验转换合法性，调用 FeedbackService 更新状态，维护活跃工作流记录。

        参数:
            bug_id: Bug 唯一标识
            new_status: 目标状态

        返回:
            转换是否成功
        """
        current_state = self._active_workflows.get(bug_id)

        # 首次出现，从报告中读取当前状态
        if current_state is None:
            bug_report = self._read_bug_report(bug_id)
            if bug_report is not None:
                current_state = bug_report.get("status", "open")
            else:
                current_state = "open"

        # 校验转换合法性
        allowed = self.VALID_TRANSITIONS.get(current_state, [])
        if new_status not in allowed:
            logger.warning(f"Bug {bug_id} 非法状态转换: {current_state} -> {new_status}（允许: {allowed}）")
            return False

        # 调用 FeedbackService 更新状态
        success = self.feedback_service.update_bug_status(bug_id, new_status)
        if success:
            self._active_workflows[bug_id] = new_status
            logger.info(f"Bug {bug_id} 状态转换: {current_state} -> {new_status}")
        else:
            logger.error(f"Bug {bug_id} 状态转换失败: {current_state} -> {new_status}")

        return success

    def _update_bug_report(self, bug_id: str, **fields) -> bool:
        """更新 Bug 报告的指定字段

        通过 FeedbackService 公开方法更新字段并重新渲染 Markdown。

        参数:
            bug_id: Bug 唯一标识
            **fields: 需要更新的字段

        返回:
            更新是否成功
        """
        return self.feedback_service.update_bug_fields(bug_id, **fields)

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------

    def _read_bug_report(self, bug_id: str) -> Optional[dict]:
        """读取 Bug 报告数据

        在所有状态目录中查找并读取 Bug 的 JSON 文件。

        参数:
            bug_id: Bug 唯一标识

        返回:
            Bug 报告字典，未找到返回 None
        """
        bug_path = self._find_bug_json(bug_id)
        if bug_path is None:
            return None

        try:
            with open(bug_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取 Bug 报告失败 {bug_id}: {e}")
            return None

    def _find_bug_json(self, bug_id: str) -> Optional[Path]:
        """在所有状态目录中查找 Bug 的 JSON 文件

        参数:
            bug_id: Bug 唯一标识

        返回:
            JSON 文件路径，未找到返回 None
        """
        for status_dir in _BUG_DIRS:
            json_path = status_dir / f"{bug_id}.json"
            if json_path.exists():
                return json_path
        return None

    def _save_analysis_file(self, bug_id: str, suffix: str, data: Any) -> None:
        """保存分析相关文件到 analysis 目录

        参数:
            bug_id: Bug 唯一标识
            suffix: 文件后缀（analysis / proposal / fix_report）
            data: 要保存的数据
        """
        try:
            _ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
            file_path = _ANALYSIS_DIR / f"{bug_id}_{suffix}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"已保存分析文件: {file_path}")
        except OSError as e:
            logger.error(f"保存分析文件失败 {bug_id}_{suffix}: {e}")
