"""结构化 Bug 报告系统

提供 Bug 报告的创建、去重、状态管理和索引功能。
报告写入 feedback/bugs/open/ 目录，同时维护 feedback/index.json 索引。
反馈写入失败时不会影响产品主流程。
"""
from __future__ import annotations

import hashlib
import json
import re
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field

# ============================================================
# 常量定义
# ============================================================

# 需要脱敏的关键字
SENSITIVE_KEYWORDS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "COOKIE", "ACCOUNT", "BROKER")

# Bug 状态
BUG_STATUS_OPEN = "open"
BUG_STATUS_TRIAGED = "triaged"
BUG_STATUS_FIXED = "fixed"
BUG_STATUS_IGNORED = "ignored"

VALID_BUG_STATUSES = {BUG_STATUS_OPEN, BUG_STATUS_TRIAGED, BUG_STATUS_FIXED, BUG_STATUS_IGNORED}

# 严重程度
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

VALID_SEVERITIES = {SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW}

# 去重时间窗口（小时）
DEDUPE_WINDOW_HOURS = 24

# 目录结构
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_FEEDBACK_DIR = _PROJECT_ROOT / "feedback"
_BUGS_DIR = _FEEDBACK_DIR / "bugs"
_OPEN_DIR = _BUGS_DIR / "open"
_TRIAGED_DIR = _BUGS_DIR / "triaged"
_FIXED_DIR = _BUGS_DIR / "fixed"
_IGNORED_DIR = _BUGS_DIR / "ignored"
_INDEX_PATH = _FEEDBACK_DIR / "index.json"


# ============================================================
# Pydantic 数据模型
# ============================================================

class BugReport(BaseModel):
    """Bug 报告数据模型"""
    bug_id: str = Field(description="Bug 唯一标识，格式 BUG_{YYYYMMDD}_{6位随机码}")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")
    status: str = Field(default=BUG_STATUS_OPEN, description="Bug 状态")
    severity: str = Field(default=SEVERITY_MEDIUM, description="严重程度")
    component: str = Field(description="所属组件")
    title: str = Field(description="Bug 标题")
    summary: str = Field(description="Bug 摘要")
    user_action: str = Field(default="", description="用户操作描述")
    endpoint_or_page: str = Field(default="", description="触发端点或页面")
    exception_type: str = Field(default="", description="异常类型")
    exception_message: str = Field(default="", description="异常消息")
    sanitized_traceback: str = Field(default="", description="脱敏后的堆栈跟踪")
    runtime_context: dict[str, Any] = Field(default_factory=dict, description="运行时上下文")
    config_snapshot_masked: dict[str, Any] = Field(default_factory=dict, description="脱敏后的配置快照")
    reproduction_steps: list[str] = Field(default_factory=list, description="复现步骤")
    dedupe_hash: str = Field(default="", description="去重哈希")
    related_log_files: list[str] = Field(default_factory=list, description="相关日志文件")
    occurrence_count: int = Field(default=1, description="出现次数")


class BugIndexEntry(BaseModel):
    """Bug 索引条目"""
    bug_id: str
    title: str
    component: str
    severity: str
    status: str
    created_at: str
    updated_at: str
    dedupe_hash: str
    occurrence_count: int = 1


# ============================================================
# 脱敏工具
# ============================================================

def mask_value(key: str, value: Any) -> Any:
    """对敏感键值进行脱敏处理"""
    if not isinstance(value, str) or not value:
        return value

    key_upper = key.upper()
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in key_upper:
            if len(value) <= 4:
                return "****"
            return f"{value[:2]}****{value[-2:]}"

    return value


def mask_dict(data: dict[str, Any]) -> dict[str, Any]:
    """对字典中所有敏感值进行脱敏"""
    return {k: mask_value(k, v) for k, v in data.items()}


def sanitize_traceback(tb_str: str) -> str:
    """脱敏堆栈跟踪中的敏感信息

    移除可能包含的 token、密钥等敏感值。
    """
    if not tb_str:
        return ""

    # 替换常见的敏感模式：key=value, key: value
    result = tb_str
    for keyword in SENSITIVE_KEYWORDS:
        # 匹配 keyword=xxx 或 keyword:xxx 模式
        pattern = rf'({keyword}\s*[=:]\s*)\S+'
        result = re.sub(pattern, r'\1****', result, flags=re.IGNORECASE)

    return result


# ============================================================
# 去重工具
# ============================================================

def compute_dedupe_hash(
    component: str,
    exception_type: str,
    exception_message: str,
    endpoint_or_page: str,
) -> str:
    """计算去重哈希

    基于 component + exception_type + normalized_message + endpoint 生成哈希。
    """
    # 归一化异常消息：移除具体数值、路径等可变部分
    normalized_msg = re.sub(r'\d+', 'N', exception_message)
    normalized_msg = re.sub(r'/[\w/.]+', '/PATH', normalized_msg)
    normalized_msg = re.sub(r'0x[0-9a-fA-F]+', '0xADDR', normalized_msg)

    raw = f"{component}|{exception_type}|{normalized_msg}|{endpoint_or_page}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ============================================================
# Bug 报告服务
# ============================================================

class FeedbackService:
    """结构化 Bug 报告服务

    职责：
    - 创建 Bug 报告（.md + .json 双格式）
    - 自动去重（24小时窗口内相同特征视为重复）
    - 管理 Bug 状态流转
    - 维护 Bug 索引

    重要：反馈写入失败时不会影响产品主流程，仅记录本地日志。
    """

    def __init__(self) -> None:
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """确保目录结构存在"""
        for d in (_OPEN_DIR, _TRIAGED_DIR, _FIXED_DIR, _IGNORED_DIR):
            d.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------
    # 写入 Bug 报告
    # ----------------------------------------------------------

    def write_bug_report(
        self,
        component: str,
        title: str,
        summary: str,
        *,
        severity: str = SEVERITY_MEDIUM,
        user_action: str = "",
        endpoint_or_page: str = "",
        exception_type: str = "",
        exception_message: str = "",
        sanitized_traceback: str = "",
        runtime_context: Optional[dict[str, Any]] = None,
        config_snapshot_masked: Optional[dict[str, Any]] = None,
        reproduction_steps: Optional[list[str]] = None,
        related_log_files: Optional[list[str]] = None,
    ) -> Optional[str]:
        """写入 Bug 报告

        参数:
            component: 所属组件（如 data_gateway, risk_engine 等）
            title: Bug 标题
            summary: Bug 摘要
            severity: 严重程度 (critical/high/medium/low)
            user_action: 用户操作描述
            endpoint_or_page: 触发端点或页面
            exception_type: 异常类型
            exception_message: 异常消息
            sanitized_traceback: 已脱敏的堆栈跟踪
            runtime_context: 运行时上下文
            config_snapshot_masked: 已脱敏的配置快照
            reproduction_steps: 复现步骤
            related_log_files: 相关日志文件

        返回:
            bug_id，如果写入失败返回 None。
            重复 Bug 会增加 occurrence_count 并返回已有 bug_id。
        """
        try:
            now = datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")

            # 验证严重程度
            if severity not in VALID_SEVERITIES:
                severity = SEVERITY_MEDIUM

            # 计算去重哈希
            dedupe_hash = compute_dedupe_hash(component, exception_type, exception_message, endpoint_or_page)

            # 检查去重
            existing_bug_id = self._check_dedupe(dedupe_hash, now)
            if existing_bug_id:
                # 重复 Bug：增加计数
                self._increment_occurrence(existing_bug_id)
                logger.info(f"Bug 去重命中: {existing_bug_id}，已增加出现次数")
                return existing_bug_id

            # 生成 bug_id
            import random
            import string
            rand_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            bug_id = f"BUG_{now.strftime('%Y%m%d')}_{rand_code}"

            # 脱敏处理
            if runtime_context:
                runtime_context = mask_dict(runtime_context)
            if config_snapshot_masked:
                config_snapshot_masked = mask_dict(config_snapshot_masked)
            sanitized_traceback = sanitize_traceback(sanitized_traceback)

            # 构建 Bug 报告
            report = BugReport(
                bug_id=bug_id,
                created_at=now_str,
                updated_at=now_str,
                status=BUG_STATUS_OPEN,
                severity=severity,
                component=component,
                title=title,
                summary=summary,
                user_action=user_action,
                endpoint_or_page=endpoint_or_page,
                exception_type=exception_type,
                exception_message=exception_message,
                sanitized_traceback=sanitized_traceback,
                runtime_context=runtime_context or {},
                config_snapshot_masked=config_snapshot_masked or {},
                reproduction_steps=reproduction_steps or [],
                dedupe_hash=dedupe_hash,
                related_log_files=related_log_files or [],
                occurrence_count=1,
            )

            # 写入 .json 文件
            json_path = _OPEN_DIR / f"{bug_id}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2, ensure_ascii=False))

            # 写入 .md 文件
            md_path = _OPEN_DIR / f"{bug_id}.md"
            md_content = self._render_markdown(report)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            # 更新索引
            self._add_to_index(report)

            logger.info(f"Bug 报告已创建: {bug_id} [{severity}] {title}")
            return bug_id

        except Exception as e:
            # 反馈写入失败不影响产品主流程
            logger.error(f"Bug 报告写入失败: {e}")
            logger.debug(f"原始错误详情: {traceback.format_exc()}")
            return None

    # ----------------------------------------------------------
    # 查询 Bug
    # ----------------------------------------------------------

    def get_open_bugs(self) -> list[BugReport]:
        """获取所有 open 状态的 Bug 报告"""
        bugs: list[BugReport] = []
        if not _OPEN_DIR.exists():
            return bugs

        for json_file in _OPEN_DIR.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                bugs.append(BugReport(**data))
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"读取 Bug 报告失败 {json_file.name}: {e}")

        return sorted(bugs, key=lambda b: b.created_at, reverse=True)

    def get_bug_index(self) -> list[BugIndexEntry]:
        """获取 Bug 索引"""
        index = self._load_index()
        return [BugIndexEntry(**entry) for entry in index.get("bugs", [])]

    # ----------------------------------------------------------
    # 状态管理
    # ----------------------------------------------------------

    def update_bug_status(self, bug_id: str, new_status: str) -> bool:
        """更新 Bug 状态

        状态流转：open -> triaged -> fixed/ignored
        """
        if new_status not in VALID_BUG_STATUSES:
            logger.warning(f"无效的 Bug 状态: {new_status}")
            return False

        try:
            # 在所有状态目录中查找 Bug
            source_dir, report = self._find_bug(bug_id)
            if report is None:
                logger.warning(f"未找到 Bug: {bug_id}")
                return False

            if report.status == new_status:
                logger.info(f"Bug {bug_id} 状态未变: {new_status}")
                return True

            # 更新状态和时间
            old_status = report.status
            report.status = new_status
            report.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 如果状态目录变化，移动文件
            target_dir = self._status_to_dir(new_status)
            if target_dir and source_dir != target_dir:
                # 写入新位置
                target_json = target_dir / f"{bug_id}.json"
                target_md = target_dir / f"{bug_id}.md"
                with open(target_json, "w", encoding="utf-8") as f:
                    f.write(report.model_dump_json(indent=2, ensure_ascii=False))
                with open(target_md, "w", encoding="utf-8") as f:
                    f.write(self._render_markdown(report))

                # 删除旧位置
                if source_dir:
                    old_json = source_dir / f"{bug_id}.json"
                    old_md = source_dir / f"{bug_id}.md"
                    for old_file in (old_json, old_md):
                        if old_file.exists():
                            old_file.unlink()
            else:
                # 同目录更新
                if source_dir:
                    json_path = source_dir / f"{bug_id}.json"
                    md_path = source_dir / f"{bug_id}.md"
                    with open(json_path, "w", encoding="utf-8") as f:
                        f.write(report.model_dump_json(indent=2, ensure_ascii=False))
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(self._render_markdown(report))

            # 更新索引
            self._update_index_entry(bug_id, new_status, report.updated_at)

            logger.info(f"Bug {bug_id} 状态变更: {old_status} -> {new_status}")
            return True

        except Exception as e:
            logger.error(f"更新 Bug 状态失败: {e}")
            return False

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    def _check_dedupe(self, dedupe_hash: str, now: datetime) -> Optional[str]:
        """检查是否存在24小时窗口内的重复 Bug

        返回已存在的 bug_id，或 None 表示新 Bug。
        """
        index = self._load_index()
        cutoff = (now - timedelta(hours=DEDUPE_WINDOW_HOURS)).strftime("%Y-%m-%d %H:%M:%S")

        for entry in index.get("bugs", []):
            if entry.get("dedupe_hash") == dedupe_hash:
                # 检查是否在时间窗口内
                if entry.get("updated_at", "") >= cutoff:
                    return entry.get("bug_id")

        # 也检查 open 目录中的实际文件
        if _OPEN_DIR.exists():
            for json_file in _OPEN_DIR.glob("*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("dedupe_hash") == dedupe_hash:
                        if data.get("updated_at", "") >= cutoff:
                            return data.get("bug_id")
                except (json.JSONDecodeError, Exception):
                    continue

        return None

    def _increment_occurrence(self, bug_id: str) -> None:
        """增加 Bug 出现次数"""
        source_dir, report = self._find_bug(bug_id)
        if report is None or source_dir is None:
            return

        report.occurrence_count += 1
        report.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 更新文件
        json_path = source_dir / f"{bug_id}.json"
        md_path = source_dir / f"{bug_id}.md"
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2, ensure_ascii=False))
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._render_markdown(report))

        # 更新索引
        self._update_index_entry(bug_id, report.status, report.updated_at, report.occurrence_count)

    def _find_bug(self, bug_id: str) -> tuple[Optional[Path], Optional[BugReport]]:
        """在所有状态目录中查找 Bug

        返回 (目录路径, BugReport)，未找到返回 (None, None)。
        """
        for status_dir in (_OPEN_DIR, _TRIAGED_DIR, _FIXED_DIR, _IGNORED_DIR):
            json_path = status_dir / f"{bug_id}.json"
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return status_dir, BugReport(**data)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"读取 Bug 报告失败 {json_path}: {e}")
                    return None, None
        return None, None

    def _status_to_dir(self, status: str) -> Optional[Path]:
        """将状态映射到目录"""
        mapping = {
            BUG_STATUS_OPEN: _OPEN_DIR,
            BUG_STATUS_TRIAGED: _TRIAGED_DIR,
            BUG_STATUS_FIXED: _FIXED_DIR,
            BUG_STATUS_IGNORED: _IGNORED_DIR,
        }
        return mapping.get(status)

    # ----------------------------------------------------------
    # 索引管理
    # ----------------------------------------------------------

    def _load_index(self) -> dict[str, Any]:
        """加载 Bug 索引"""
        if not _INDEX_PATH.exists():
            return {"bugs": [], "updated_at": ""}
        try:
            with open(_INDEX_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"加载 Bug 索引失败: {e}")
            return {"bugs": [], "updated_at": ""}

    def _save_index(self, index: dict[str, Any]) -> None:
        """保存 Bug 索引"""
        try:
            _FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
            index["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(_INDEX_PATH, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"保存 Bug 索引失败: {e}")

    def _add_to_index(self, report: BugReport) -> None:
        """将新 Bug 添加到索引"""
        index = self._load_index()
        entry = BugIndexEntry(
            bug_id=report.bug_id,
            title=report.title,
            component=report.component,
            severity=report.severity,
            status=report.status,
            created_at=report.created_at,
            updated_at=report.updated_at,
            dedupe_hash=report.dedupe_hash,
            occurrence_count=report.occurrence_count,
        )
        index.setdefault("bugs", []).append(entry.model_dump())
        self._save_index(index)

    def _update_index_entry(
        self,
        bug_id: str,
        new_status: str,
        updated_at: str,
        occurrence_count: Optional[int] = None,
    ) -> None:
        """更新索引中的 Bug 条目"""
        index = self._load_index()
        for entry in index.get("bugs", []):
            if entry.get("bug_id") == bug_id:
                entry["status"] = new_status
                entry["updated_at"] = updated_at
                if occurrence_count is not None:
                    entry["occurrence_count"] = occurrence_count
                break
        self._save_index(index)

    # ----------------------------------------------------------
    # Markdown 渲染
    # ----------------------------------------------------------

    def _render_markdown(self, report: BugReport) -> str:
        """将 Bug 报告渲染为 Markdown 格式"""
        lines = [
            f"# Bug: {report.title}",
            "",
            f"- **Bug ID**: {report.bug_id}",
            f"- **状态**: {report.status}",
            f"- **严重程度**: {report.severity}",
            f"- **组件**: {report.component}",
            f"- **创建时间**: {report.created_at}",
            f"- **更新时间**: {report.updated_at}",
            f"- **出现次数**: {report.occurrence_count}",
            f"- **去重哈希**: {report.dedupe_hash}",
            "",
            "## 摘要",
            "",
            report.summary,
            "",
        ]

        if report.user_action:
            lines += ["## 用户操作", "", report.user_action, ""]

        if report.endpoint_or_page:
            lines += ["## 触发端点/页面", "", f"`{report.endpoint_or_page}`", ""]

        if report.exception_type or report.exception_message:
            lines += ["## 异常信息", ""]
            if report.exception_type:
                lines.append(f"- **异常类型**: `{report.exception_type}`")
            if report.exception_message:
                lines.append(f"- **异常消息**: `{report.exception_message}`")
            lines.append("")

        if report.sanitized_traceback:
            lines += ["## 堆栈跟踪（已脱敏）", "", "```", report.sanitized_traceback, "```", ""]

        if report.reproduction_steps:
            lines += ["## 复现步骤", ""]
            for i, step in enumerate(report.reproduction_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        if report.runtime_context:
            lines += ["## 运行时上下文", "", "```json"]
            lines.append(json.dumps(report.runtime_context, indent=2, ensure_ascii=False))
            lines += ["```", ""]

        if report.config_snapshot_masked:
            lines += ["## 配置快照（已脱敏）", "", "```json"]
            lines.append(json.dumps(report.config_snapshot_masked, indent=2, ensure_ascii=False))
            lines += ["```", ""]

        if report.related_log_files:
            lines += ["## 相关日志文件", ""]
            for lf in report.related_log_files:
                lines.append(f"- `{lf}`")
            lines.append("")

        return "\n".join(lines)


# ============================================================
# 模块级单例
# ============================================================

_feedback_service: Optional[FeedbackService] = None


def get_feedback_service() -> FeedbackService:
    """获取全局反馈服务单例"""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service
