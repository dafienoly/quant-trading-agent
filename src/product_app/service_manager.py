"""服务管理器 — 后台作业调度与状态管理

管理后台轮询作业：行情刷新、候选股监控、信号生成、风控快照、回测、反馈压缩。
每个作业有明确状态：IDLE / QUEUED / RUNNING / SUCCEEDED / FAILED / CANCELLED
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

from src.config.settings import DEFAULT_DATA_PROVIDER
from src.product_app.market_data import fetch_product_quotes


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


class JobState(str, Enum):
    IDLE = "IDLE"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobInfo:
    """作业信息"""

    def __init__(self, name: str, state: JobState = JobState.IDLE):
        self.name = name
        self.state = state
        self.last_run_at: str = ""
        self.last_result: str = ""
        self.error_message: str = ""
        self.job_id: str = ""
        self.started_at: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "last_run_at": self.last_run_at,
            "last_result": self.last_result,
            "error_message": self.error_message,
            "job_id": self.job_id,
            "started_at": self.started_at,
        }


class ServiceManager:
    """服务管理器

    管理后台轮询作业的启动、停止和状态查询。
    状态持久化到 runtime/state/jobs.json。
    """


    _last_refresh_result: dict | None = None

    def get_refresh_status(self) -> dict:
        if self._last_refresh_result is None:
            return {"status": "IDLE"}
        return dict(self._last_refresh_result)

    def _set_refresh_result(self, status: str, data: list | None = None, error: str | None = None) -> None:
        self._last_refresh_result = {
            "status": status,
            "data": data,
            "error": error,
        }

    def __init__(self, state_dir: str = "runtime/state"):
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._bug_watchdog = None
        self._jobs: dict[str, JobInfo] = {
            "quote_refresh": JobInfo("quote_refresh"),
            "watchlist_monitor": JobInfo("watchlist_monitor"),
            "signal_generation": JobInfo("signal_generation"),
            "risk_snapshot": JobInfo("risk_snapshot"),
            "backtest": JobInfo("backtest"),
            "feedback_compaction": JobInfo("feedback_compaction"),
            "bug_fix_agent": JobInfo("bug_fix_agent"),
        }
        self._load_state()

    def _load_state(self):
        """从文件加载作业状态"""
        filepath = self._state_dir / "jobs.json"
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, info in data.items():
                    if name in self._jobs:
                        job = self._jobs[name]
                        job.state = JobState(info.get("state", "IDLE"))
                        job.last_run_at = info.get("last_run_at", "")
                        job.last_result = info.get("last_result", "")
                        job.error_message = info.get("error_message", "")
            except Exception as e:
                logger.warning(f"ServiceManager: 加载作业状态失败 {e}")

    def _save_state(self):
        """持久化作业状态"""
        filepath = self._state_dir / "jobs.json"
        try:
            data = {name: job.to_dict() for name, job in self._jobs.items()}
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"ServiceManager: 保存作业状态失败 {e}")

    def list_jobs(self) -> list[dict]:
        """列出所有作业及其状态"""
        return [job.to_dict() for job in self._jobs.values()]

    def get_job_status(self, job_name: str) -> dict | None:
        """获取单个作业状态"""
        if job_name in self._jobs:
            return self._jobs[job_name].to_dict()
        return None

    def start_job(self, job_name: str, params: dict | None = None) -> dict:
        """启动作业"""
        if job_name not in self._jobs:
            return {"status": "error", "message": f"未知作业: {job_name}"}

        job = self._jobs[job_name]
        if job.state == JobState.RUNNING:
            return {"status": "error", "message": f"作业 {job_name} 正在运行中"}

        job.state = JobState.QUEUED
        job.job_id = f"{job_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        job.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        job.error_message = ""

        if job_name == "bug_fix_agent":
            if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
                message = "DEEPSEEK_API_KEY is required before starting bug_fix_agent"
                job.state = JobState.FAILED
                job.error_message = message
                job.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_state()
                return {"status": "error", "message": message}
            return self._start_persistent_job(job_name, job, params or {})

        # 在线程中执行作业
        def _run():
            job.state = JobState.RUNNING
            self._save_state()
            try:
                self._execute_job(job_name, params or {})
                job.state = JobState.SUCCEEDED
                job.last_result = "ok"
            except Exception as e:
                job.state = JobState.FAILED
                job.error_message = str(e)
                logger.error(f"ServiceManager: 作业 {job_name} 失败: {e}")
                # 生成反馈 bug 记录
                try:
                    from src.product_app.feedback import get_feedback_service
                    get_feedback_service().write_bug_report(
                        component=f"job_{job_name}",
                        title=f"后台作业 {job_name} 执行失败",
                        summary=str(e),
                        exception_type=type(e).__name__,
                        exception_message=str(e),
                    )
                except Exception:
                    logger.error("ServiceManager: 写入反馈记录失败")
            finally:
                job.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_state()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return {"status": "ok", "job_id": job.job_id, "message": f"作业 {job_name} 已启动"}

    def _start_persistent_job(self, job_name: str, job: JobInfo, params: dict) -> dict:
        """启动需要常驻的后台作业。

        `bug_fix_agent` 启动 watchdog 后必须保持 RUNNING，否则无法反映自动
        分析服务是否仍在监听，也无法通过 stop_job 正常停止。
        """
        if job_name == "bug_fix_agent" and self._bug_watchdog is not None and self._bug_watchdog.is_running():
            job.state = JobState.RUNNING
            self._save_state()
            return {"status": "error", "message": f"作业 {job_name} 正在运行中"}

        def _run():
            job.state = JobState.RUNNING
            self._save_state()
            try:
                self._execute_job(job_name, params)
                job.last_result = "watching"
                self._save_state()

                while (
                    job_name == "bug_fix_agent"
                    and self._bug_watchdog is not None
                    and self._bug_watchdog.is_running()
                ):
                    time.sleep(1)

                if job.state == JobState.RUNNING:
                    job.state = JobState.SUCCEEDED
                    job.last_result = "stopped"
            except Exception as e:
                job.state = JobState.FAILED
                job.error_message = str(e)
                logger.error(f"ServiceManager: 常驻作业 {job_name} 失败: {e}")
                try:
                    from src.product_app.feedback import get_feedback_service
                    get_feedback_service().write_bug_report(
                        component=f"job_{job_name}",
                        title=f"后台作业 {job_name} 执行失败",
                        summary=str(e),
                        exception_type=type(e).__name__,
                        exception_message=str(e),
                    )
                except Exception:
                    logger.error("ServiceManager: 写入反馈记录失败")
            finally:
                job.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_state()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return {"status": "ok", "job_id": job.job_id, "message": f"作业 {job_name} 已启动"}

    def stop_job(self, job_name: str) -> dict:
        """停止作业"""
        if job_name not in self._jobs:
            return {"status": "error", "message": f"未知作业: {job_name}"}

        job = self._jobs[job_name]
        watchdog_running = (
            job_name == "bug_fix_agent"
            and self._bug_watchdog is not None
            and self._bug_watchdog.is_running()
        )
        if job.state != JobState.RUNNING and not watchdog_running:
            return {"status": "error", "message": f"作业 {job_name} 未在运行中"}

        job.state = JobState.CANCELLED
        if job_name == "bug_fix_agent" and self._bug_watchdog is not None:
            self._bug_watchdog.stop()
            self._bug_watchdog = None
        job.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_state()
        return {"status": "ok", "message": f"作业 {job_name} 已取消"}

    def _execute_job(self, job_name: str, params: dict):
        """执行具体作业逻辑"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if job_name == "quote_refresh":
            logger.info(f"[{now}] 行情刷新作业执行")
            try:
                quote_result = fetch_product_quotes(
                    params.get("symbols", ""),
                    provider=str(params.get("provider", DEFAULT_DATA_PROVIDER)),
                    allow_demo=_as_bool(params.get("allow_demo"), default=True),
                    force_live=_as_bool(params.get("force_live"), default=False),
                )
                quote_result["updated_at"] = now
                self._write_state_file("latest_quotes.json", quote_result)
                self._set_refresh_result("SUCCEEDED", data=list(quote_result.keys()))
            except Exception as exc:
                self._set_refresh_result("FAILED", error=str(exc))
                try:
                    from src.product_app.feedback_service import get_feedback_service
                    fb = get_feedback_service()
                    fb.write_bug_report(
                        title="行情刷新失败",
                        description=f"quote_refresh 执行失败：{exc}",
                        category="market_data",
                        severity="warning",
                    )
                except Exception:
                    pass
                raise

        elif job_name == "watchlist_monitor":
            logger.info(f"[{now}] 候选股监控作业执行")
            self._write_state_file("latest_signals.json", {"updated_at": now})

        elif job_name == "signal_generation":
            logger.info(f"[{now}] 信号生成作业执行")
            self._write_state_file("latest_signals.json", {"updated_at": now})

        elif job_name == "risk_snapshot":
            logger.info(f"[{now}] 风控快照作业执行")
            self._write_state_file("latest_risk.json", {"updated_at": now})

        elif job_name == "backtest":
            logger.info(f"[{now}] 回测作业执行: {params}")
            job_id = params.get("job_id", "unknown")
            self._write_state_file(f"backtests/{job_id}.json", {
                "job_id": job_id, "status": "completed", "updated_at": now,
            })

        elif job_name == "feedback_compaction":
            logger.info(f"[{now}] 反馈压缩作业执行")

        elif job_name == "bug_fix_agent":
            logger.info(f"[{now}] Bug 修复 Agent 作业执行")
            from src.product_app.bug_watchdog import BugWatchdog
            from src.product_app.bug_fix_workflow import BugFixWorkflow

            workflow = BugFixWorkflow()

            def _on_new_bug(bug_id: str, bug_report: dict) -> None:
                """新 Bug 回调：触发自动分析流程"""
                try:
                    result = workflow.process_bug(bug_id)
                    logger.info(f"Bug 自动处理结果: {result}")
                except Exception as e:
                    logger.error(f"Bug 自动处理失败 (bug_id={bug_id}): {e}")

            watchdog = BugWatchdog(on_new_bug_callback=_on_new_bug)
            watchdog.start()
            # Store watchdog reference for later stop
            self._bug_watchdog = watchdog
            logger.info("Bug 修复 Agent 已启动，监控 feedback/bugs/open/ 目录")

    def _write_state_file(self, filename: str, data: dict):
        """写入状态文件"""
        filepath = self._state_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"ServiceManager: 写入状态文件失败 {e}")


# 全局单例
_service_manager: ServiceManager | None = None


def get_service_manager() -> ServiceManager:
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager



