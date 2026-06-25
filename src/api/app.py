"""Phase 5 API

提供风控状态、最新信号、行情查询、订单管理和回测触发的接口。
Phase 5 新增：订单管理端点（LEVEL_2 人工确认模式）
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from src.config.settings import ENABLE_LIVE_TRADING, MAX_TRADING_LEVEL
from src.risk_engine.runtime import RuntimeRiskEngine


def create_app(
    risk_engine: RuntimeRiskEngine | None = None,
    signal_service: Any = None,
    execution_service: Any = None,
) -> FastAPI:
    app = FastAPI(title="Quant Trading Agent", version="0.5.0")
    _risk_engine = risk_engine or RuntimeRiskEngine()
    _signal_service = signal_service
    _execution_service = execution_service

    # 注册产品路由
    from src.api.product_routes import router as product_router
    app.include_router(product_router, prefix="/product", tags=["product"])

    # 注册 AgentOps 只读观测路由
    from src.api.agentops_routes import router as agentops_router
    app.include_router(agentops_router, prefix="/product/agentops", tags=["agentops"])

    # 注册 V16.2 市场数据 Relay 路由
    from src.api.market_routes import router as market_router
    app.include_router(market_router, prefix="/product/market", tags=["market"])

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "max_trading_level": MAX_TRADING_LEVEL,
            "enable_live_trading": ENABLE_LIVE_TRADING,
        }

    @app.get("/risk/status")
    def risk_status() -> dict:
        """风控状态查询

        返回 Kill Switch 状态和风控引擎配置信息。
        不使用空行情触发 EMPTY_QUOTES 误报 (L5 fix)。
        """
        kill_switch = _risk_engine.kill_switch
        return {
            "risk_pass": not kill_switch.active,
            "level": "BLOCK" if kill_switch.active else "OK",
            "trading_mode": MAX_TRADING_LEVEL,
            "kill_switch_active": kill_switch.active,
            "kill_switch_reason": kill_switch.reason if kill_switch.active else "",
            "max_quote_delay_seconds": _risk_engine.max_quote_delay_seconds,
        }

    @app.get("/signals/latest")
    def signals_latest() -> dict:
        if _signal_service and _signal_service.last_result:
            return _signal_service.last_result
        return {"risk_pass": False, "signals": [], "orders": [], "risk_messages": ["no signal data"]}

    @app.post("/signals/refresh")
    def signals_refresh() -> dict:
        """手动触发信号刷新（仅开发/调试模式使用）"""
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
        }

    # ===== Phase 5: 订单管理端点 (EXECUTION_POLICY 5) =====

    @app.get("/orders/pending")
    def orders_pending() -> dict:
        """查询待确认订单列表"""
        if not _execution_service:
            return {"orders": [], "message": "ExecutionService not configured"}
        pending = _execution_service.pending_orders
        return {
            "count": len(pending),
            "orders": [o.model_dump() for o in pending.values()],
        }

    @app.get("/orders/{order_id}")
    def order_detail(order_id: str) -> dict:
        """查询订单详情"""
        if not _execution_service:
            return {"error": "ExecutionService not configured"}
        all_orders = _execution_service.all_orders
        if order_id in all_orders:
            return all_orders[order_id].model_dump()
        return {"error": "Order not found", "order_id": order_id}

    @app.post("/orders/{order_id}/confirm")
    def order_confirm(order_id: str) -> dict:
        """确认订单 (EXECUTION_POLICY 5: 必须逐笔确认，禁止一键确认)"""
        if not _execution_service:
            return {"status": "error", "message": "ExecutionService not configured"}
        if _execution_service.trading_mode not in ("LEVEL_2_HUMAN_CONFIRM", "LEVEL_3_AUTO"):
            return {"status": "error", "message": "当前模式不允许确认订单"}
        order = _execution_service.confirm_order(order_id, confirmed_by="api_user")
        if order:
            return {"status": "ok", "order": order.model_dump()}
        return {"status": "error", "message": "订单不在待确认队列"}

    @app.post("/orders/{order_id}/reject")
    def order_reject(order_id: str, reason: str = Query("", description="拒绝原因")) -> dict:
        """拒绝订单"""
        if not _execution_service:
            return {"status": "error", "message": "ExecutionService not configured"}
        order = _execution_service.reject_order(order_id, reason=reason)
        if order:
            return {"status": "ok", "order": order.model_dump()}
        return {"status": "error", "message": "订单不在待确认队列"}

    @app.post("/orders/{order_id}/cancel")
    def order_cancel(order_id: str) -> dict:
        """撤销订单"""
        if not _execution_service:
            return {"status": "error", "message": "ExecutionService not configured"}
        order = _execution_service.cancel_order(order_id)
        if order:
            return {"status": "ok", "order": order.model_dump()}
        return {"status": "error", "message": "订单不在待确认队列"}

    @app.get("/account")
    def account_info() -> dict:
        """查询账户信息"""
        if not _execution_service:
            return {"error": "ExecutionService not configured"}
        account = _execution_service.query_account()
        return account.model_dump()

    @app.get("/positions")
    def positions() -> dict:
        """查询持仓"""
        if not _execution_service:
            return {"positions": [], "message": "ExecutionService not configured"}
        positions = _execution_service.query_positions()
        return {"count": len(positions), "positions": [p.model_dump() for p in positions]}

    @app.websocket("/ws/signals")
    async def websocket_signals(websocket: WebSocket):
        """WebSocket 实时信号推送"""
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


# Module-level app instance for uvicorn
app = create_app()
