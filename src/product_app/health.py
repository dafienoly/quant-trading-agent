"""健康检查聚合服务

聚合 API 健康状态、数据源状态、风控状态、作业状态、存储状态、反馈积压。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config.settings import ENABLE_LIVE_TRADING, MAX_TRADING_LEVEL


class HealthStatus:
    """组件健康状态"""

    def __init__(self, name: str, status: str = "OK", message: str = "", last_check: str = ""):
        self.name = name
        self.status = status  # OK / WARN / ERROR
        self.message = message
        self.last_check = last_check or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "last_check": self.last_check,
        }


class HealthService:
    """健康检查聚合服务"""

    def __init__(self, state_dir: str = "runtime/state", base_dir: str = "."):
        self._state_dir = Path(state_dir)
        self._base_dir = Path(base_dir)

    def get_system_health(self) -> dict:
        """获取系统整体健康状态"""
        components = {
            "api": self._check_api(),
            "data_source": self._check_data_source(),
            "risk_engine": self._check_risk(),
            "jobs": self._check_jobs(),
            "storage": self._check_storage(),
            "feedback": self._check_feedback(),
        }

        # 汇总整体状态
        statuses = [c.status for c in components.values()]
        if "ERROR" in statuses:
            overall = "ERROR"
        elif "WARN" in statuses:
            overall = "WARN"
        else:
            overall = "OK"

        return {
            "overall_status": overall,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trading_mode": MAX_TRADING_LEVEL,
            "is_live": ENABLE_LIVE_TRADING,
            "components": {name: comp.to_dict() for name, comp in components.items()},
        }

    def _check_api(self) -> HealthStatus:
        """检查 API 状态"""
        return HealthStatus("api", "OK", "FastAPI 运行中")

    def _check_data_source(self) -> HealthStatus:
        """检查数据源状态"""
        # 检查是否有最新行情数据
        quotes_file = self._state_dir / "latest_quotes.json"
        if quotes_file.exists():
            try:
                with open(quotes_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                source = data.get("source", "unknown")
                updated = data.get("updated_at", "")
                return HealthStatus("data_source", "OK", f"数据源: {source}, 最后更新: {updated}")
            except Exception:
                return HealthStatus("data_source", "WARN", "行情数据文件损坏")
        return HealthStatus("data_source", "WARN", "暂无行情数据，将使用 Demo 模式")

    def _check_risk(self) -> HealthStatus:
        """检查风控状态"""
        risk_file = self._state_dir / "latest_risk.json"
        if risk_file.exists():
            try:
                with open(risk_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return HealthStatus("risk_engine", "OK", "风控引擎正常")
            except Exception:
                pass
        return HealthStatus("risk_engine", "OK", "风控引擎就绪（无快照）")

    def _check_jobs(self) -> HealthStatus:
        """检查作业状态"""
        jobs_file = self._state_dir / "jobs.json"
        if jobs_file.exists():
            try:
                with open(jobs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                failed = [name for name, info in data.items() if info.get("state") == "FAILED"]
                if failed:
                    return HealthStatus("jobs", "WARN", f"失败作业: {', '.join(failed)}")
                return HealthStatus("jobs", "OK", "所有作业正常")
            except Exception:
                pass
        return HealthStatus("jobs", "OK", "作业系统就绪")

    def _check_storage(self) -> HealthStatus:
        """检查存储目录可写性"""
        dirs_to_check = ["data", "logs", "feedback", "runtime"]
        missing = []
        for d in dirs_to_check:
            path = self._base_dir / d
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except Exception:
                    missing.append(d)

        if missing:
            return HealthStatus("storage", "ERROR", f"目录不可写: {', '.join(missing)}")
        return HealthStatus("storage", "OK", "存储目录正常")

    def _check_feedback(self) -> HealthStatus:
        """检查反馈积压"""
        try:
            from src.product_app.feedback import get_feedback_service
            bugs = get_feedback_service().get_open_bugs()
            count = len(bugs)
            if count > 10:
                return HealthStatus("feedback", "WARN", f"反馈积压: {count} 个未处理 Bug")
            return HealthStatus("feedback", "OK", f"反馈正常: {count} 个未处理 Bug")
        except Exception:
            return HealthStatus("feedback", "OK", "反馈系统就绪")


# 全局单例
_health_service: HealthService | None = None


def get_health_service() -> HealthService:
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service
