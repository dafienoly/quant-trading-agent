"""Phase 4 API

提供风控状态、最新信号、行情查询和回测触发的只读/安全接口。
核心约束：不提供任何写入/下单端点。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from src.config.settings import ENABLE_LIVE_TRADING, MAX_TRADING_LEVEL
from src.risk_engine.models import KillSwitchState, RiskDecision, RiskLevel
from src.risk_engine.runtime import RuntimeRiskEngine


def create_app(
    risk_engine: RuntimeRiskEngine | None = None,
    signal_service: Any = None,
) -> FastAPI:
    app = FastAPI(title="Quant Trading Agent", version="0.4.0")
    _risk_engine = risk_engine or RuntimeRiskEngine()
    _signal_service = signal_service

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "max_trading_level": MAX_TRADING_LEVEL,
            "enable_live_trading": ENABLE_LIVE_TRADING,
        }

    @app.get("/risk/status")
    def risk_status() -> dict:
        decision = _risk_engine.check_realtime_snapshot(
            quotes=[], trading_mode=MAX_TRADING_LEVEL,
        )
        return decision.model_dump()

    @app.get("/signals/latest")
    def signals_latest() -> dict:
        if _signal_service and _signal_service.last_result:
            return _signal_service.last_result
        return {"risk_pass": False, "signals": [], "orders": [], "risk_messages": ["no signal data"]}

    @app.post("/signals/refresh")
    def signals_refresh() -> dict:
        """手动触发信号刷新（仅开发/调试模式使用）

        调用 SignalService.run_once() 获取最新信号数据。
        生产环境应使用后台调度器定时调用。
        """
        if not _signal_service:
            return {"status": "error", "message": "SignalService not configured"}
        try:
            result = _signal_service.run_once()
            return result or {"status": "ok", "message": "Signal refresh completed, no result"}
        except Exception as e:
            return {"status": "error", "message": f"Signal refresh failed: {e}"}

    @app.get("/quotes/{symbol}")
    def quote_detail(symbol: str) -> dict:
        return {
            "symbol": symbol,
            "message": "Quote data requires realtime provider connection",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @app.get("/backtest/run")
    def backtest_run(
        start_date: str = Query(..., description="回测开始日期 YYYYMMDD"),
        end_date: str = Query(..., description="回测结束日期 YYYYMMDD"),
        initial_capital: float = Query(1000000.0, description="初始资金"),
    ) -> dict:
        return {
            "status": "rejected",
            "reason": "Backtest must be triggered via CLI script (scripts/run_backtest.py), not API",
            "hint": "API backtest trigger will be available after security review in Phase 5",
        }

    @app.websocket("/ws/signals")
    async def websocket_signals(websocket: WebSocket):
        """WebSocket 实时信号推送

        客户端连接后，每 5 秒推送最新信号数据。
        推送内容为只读信号，不包含任何交易指令。
        """
        await websocket.accept()
        try:
            while True:
                if _signal_service and _signal_service.last_result:
                    data = _signal_service.last_result
                else:
                    data = {"risk_pass": False, "signals": [], "orders": [], "risk_messages": ["no signal data"]}
                await websocket.send_json(data)
                await asyncio.sleep(5)
        except WebSocketDisconnect:
            pass

    return app
