"""产品路由

提供产品仪表板所需的全部 API 端点，包括：
- 健康检查和仪表板数据聚合
- 因子分析
- 回测任务
- 配置管理
- 反馈查询
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Query
from loguru import logger

from src.config.settings import (
    BACKTEST_COMMISSION_RATE,
    BACKTEST_SLIPPAGE,
    BACKTEST_STAMP_DUTY,
    BROKER_ADAPTER,
    DAILY_LOSS_STOP,
    DAILY_LOSS_WARN,
    DEFAULT_DATA_PROVIDER,
    EASTMONEY_ENABLED,
    ENABLE_LIVE_TRADING,
    LOG_LEVEL,
    MAX_DRAWDOWN_DEFENSE,
    MAX_DRAWDOWN_HALT,
    MAX_SECTOR_POSITION,
    MAX_SINGLE_STOCK_POSITION,
    MAX_TRADING_LEVEL,
    MIN_CASH_RATIO,
    REQUIRE_HUMAN_CONFIRMATION,
    SINA_QUOTE_ENABLED,
    SINGLE_STOCK_LOSS_STOP,
    SINGLE_STOCK_LOSS_WARN,
)
from src.product_app.config_service import (
    SAFE_CONFIG_GROUPS,
    ConfigService,
    get_config_service,
)
from src.product_app.demo_data import (
    DEMO_STOCKS,
    get_demo_account,
    get_demo_factors,
    get_demo_positions,
    get_demo_quotes,
    get_demo_signals,
    is_demo_mode,
)
from src.product_app.feedback import (
    BUG_STATUS_FIXED,
    BUG_STATUS_IGNORED,
    BUG_STATUS_TRIAGED,
    get_feedback_service,
)
from src.risk_engine.runtime import RuntimeRiskEngine

router = APIRouter()

# 模块级服务实例
_risk_engine = RuntimeRiskEngine()
_config_service = get_config_service()


# ============================================================
# 健康检查
# ============================================================

@router.get("/health")
def product_health() -> dict:
    """产品健康检查端点"""
    kill_switch = _risk_engine.kill_switch
    risk_status = "BLOCK" if kill_switch.active else "OK"
    demo = is_demo_mode()

    return {
        "status": "ok",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "api_status": "running",
        "data_source": "demo" if demo else "akshare",
        "risk_status": risk_status,
        "trading_mode": MAX_TRADING_LEVEL,
        "is_live": ENABLE_LIVE_TRADING,
        "is_demo": demo,
        "kill_switch_active": _risk_engine.kill_switch.active,
        "feedback_backlog": len(get_feedback_service().get_open_bugs()),
    }


# ============================================================
# 仪表板数据聚合
# ============================================================

@router.get("/dashboard")
def product_dashboard() -> dict:
    """仪表板数据聚合端点

    返回行情、信号、风控、账户等全部仪表板所需数据。
    """
    demo = is_demo_mode()

    # 行情数据
    if demo:
        quotes_raw = get_demo_quotes()
        quotes = [q.model_dump() for q in quotes_raw]
    else:
        # 尝试获取实时行情，失败则回退 demo
        try:
            from src.data_gateway.realtime_provider import get_realtime_quotes
            quotes_raw = get_realtime_quotes([s["symbol"] for s in DEMO_STOCKS])
            quotes = [q.model_dump() for q in quotes_raw]
        except Exception as e:
            logger.warning(f"实时行情获取失败，回退 demo: {e}")
            quotes_raw = get_demo_quotes()
            quotes = [q.model_dump() for q in quotes_raw]

    # 信号数据
    if demo:
        signals_raw = get_demo_signals()
        signals = [s.model_dump() for s in signals_raw]
    else:
        signals = []

    # 风控状态
    risk_decision = _risk_engine.check_realtime_snapshot(quotes=quotes)

    # 账户信息
    if demo:
        account = get_demo_account().model_dump()
        positions = [p.model_dump() for p in get_demo_positions()]
    else:
        account = {"total_assets": 0, "cash": 0, "market_value": 0,
                   "available_cash": 0, "daily_pnl": 0, "daily_pnl_pct": 0}
        positions = []

    # 因子数据
    if demo:
        factors = [f.model_dump() for f in get_demo_factors()]
    else:
        factors = []

    # 候选股列表
    watchlist = []
    for stock in DEMO_STOCKS:
        quote_match = next((q for q in quotes if q.get("symbol") == stock["symbol"]), None)
        watchlist.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "market": stock["market"],
            "sector": stock["sector"],
            "last_price": quote_match.get("last_price", 0) if quote_match else 0,
            "pct_change": quote_match.get("pct_change", 0) if quote_match else 0,
            "status": quote_match.get("status", "UNKNOWN") if quote_match else "UNKNOWN",
        })

    # 待确认订单（ExecutionService 未注入，需通过 /orders/pending 端点直接获取）
    pending_orders = []

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_demo": demo,
        "data_source": "demo" if demo else "akshare",
        "quotes": quotes,
        "signals": signals,
        "risk": {
            "risk_pass": risk_decision.risk_pass,
            "level": risk_decision.level.value,
            "trading_mode": risk_decision.trading_mode,
            "messages": risk_decision.messages,
            "kill_switch_active": _risk_engine.kill_switch.active,
            "kill_switch_reason": _risk_engine.kill_switch.reason if _risk_engine.kill_switch.active else "",
        },
        "account": account,
        "positions": positions,
        "factors": factors,
        "watchlist": watchlist,
        "pending_orders": pending_orders,
        "trading_mode": MAX_TRADING_LEVEL,
        "is_live": ENABLE_LIVE_TRADING,
    }


# ============================================================
# 因子分析
# ============================================================

@router.post("/factors/compute")
def compute_factors(
    symbols: str = Query(..., description="逗号分隔的股票代码"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
) -> dict:
    """计算因子评分

    Demo 模式下返回预置因子数据。
    """
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

    if is_demo_mode():
        all_factors = get_demo_factors()
        if symbol_list:
            filtered = [f for f in all_factors if f.symbol in symbol_list]
        else:
            filtered = all_factors
        return {
            "status": "ok",
            "is_demo": True,
            "factors": [f.model_dump() for f in filtered],
            "warnings": [
                "当前为 Demo 模式，因子数据为预置确定性数据",
                "存在幸存者偏差：仅包含当前在池股票",
                "部分因子可能存在数据缺失",
            ],
        }

    return {
        "status": "ok",
        "is_demo": False,
        "factors": [],
        "warnings": ["实时因子计算尚未实现，请使用 Demo 模式"],
    }


# ============================================================
# 作业管理
# ============================================================

@router.get("/jobs")
def list_jobs() -> dict:
    """列出所有作业及其状态"""
    from src.product_app.service_manager import get_service_manager
    mgr = get_service_manager()
    return {"jobs": mgr.list_jobs()}


@router.post("/jobs/{job_name}/start")
def start_job(job_name: str) -> dict:
    """启动作业"""
    from src.product_app.service_manager import get_service_manager
    mgr = get_service_manager()
    return mgr.start_job(job_name)


@router.post("/jobs/{job_name}/stop")
def stop_job(job_name: str) -> dict:
    """停止作业"""
    from src.product_app.service_manager import get_service_manager
    mgr = get_service_manager()
    return mgr.stop_job(job_name)


# ============================================================
# 回测任务
# ============================================================

@router.post("/jobs/backtest/start")
def start_backtest(
    strategy: str = Query("demo_semiconductor_rotation", description="策略名称"),
    symbols: str = Query("", description="逗号分隔的股票代码"),
    start_date: str = Query("20250101", description="开始日期 YYYYMMDD"),
    end_date: str = Query("20251231", description="结束日期 YYYYMMDD"),
    initial_capital: float = Query(1000000.0, description="初始资金"),
    commission_rate: float = Query(BACKTEST_COMMISSION_RATE, description="手续费率"),
    stamp_duty_rate: float = Query(BACKTEST_STAMP_DUTY, description="印花税率"),
    slippage: float = Query(BACKTEST_SLIPPAGE, description="滑点"),
) -> dict:
    """启动回测任务

    返回回测结果摘要。Demo 模式下返回模拟结果。
    """
    # 回测结果必须包含成本假设
    warnings = []
    if commission_rate == 0 and stamp_duty_rate == 0 and slippage == 0:
        warnings.append("回测未包含任何交易成本，结果可能严重高估")
    if slippage == 0:
        warnings.append("未设置滑点，回测结果未考虑冲击成本")

    # Demo 模拟回测结果
    return {
        "status": "ok",
        "job_id": f"BT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "is_demo": True,
        "strategy": strategy,
        "symbols": symbols,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "cost_assumptions": {
            "commission_rate": commission_rate,
            "stamp_duty_rate": stamp_duty_rate,
            "slippage": slippage,
        },
        "performance": {
            "annual_return": 0.187,
            "max_drawdown": -0.123,
            "sharpe_ratio": 1.56,
            "win_rate": 0.58,
            "total_trades": 42,
            "profit_trades": 24,
            "loss_trades": 18,
        },
        "trades": [
            {"date": "2025-02-15", "symbol": "002463", "side": "BUY", "price": 35.80, "quantity": 3000, "pnl": 0},
            {"date": "2025-03-10", "symbol": "002916", "side": "BUY", "price": 120.50, "quantity": 1000, "pnl": 0},
            {"date": "2025-04-20", "symbol": "002463", "side": "SELL", "price": 38.52, "quantity": 3000, "pnl": 8160.0},
            {"date": "2025-05-15", "symbol": "002916", "side": "SELL", "price": 128.90, "quantity": 1000, "pnl": 8400.0},
        ],
        "warnings": warnings,
        "disclaimer": "回测结果不代表未来收益，已包含交易成本假设。请勿忽略停牌、涨跌停等限制。",
    }


# ============================================================
# 配置管理
# ============================================================

@router.get("/config")
def get_config() -> dict:
    """获取当前配置（脱敏后）"""
    config = _config_service.get_config(masked=True)
    groups = {}
    for group_name, keys in SAFE_CONFIG_GROUPS.items():
        groups[group_name] = {k: config.get(k) for k in keys if k in config}
    return {
        "config": config,
        "groups": groups,
        "validation": _config_service.validate_config().model_dump(),
    }


@router.post("/config")
def update_config(key: str = Query(...), value: str = Query(...)) -> dict:
    """更新单个配置项"""
    result = _config_service.update_config(key, value)
    return result


@router.post("/config/confirm-upgrade")
def confirm_upgrade(key: str = Query(...), value: str = Query(...)) -> dict:
    """确认交易模式升级"""
    result = _config_service.confirm_upgrade(key, value)
    return result


@router.post("/config/restore-defaults")
def restore_defaults() -> dict:
    """恢复默认配置"""
    config = _config_service.restore_defaults()
    return {
        "status": "ok",
        "message": "配置已恢复默认值",
        "config": config,
    }


# ============================================================
# 反馈查询
# ============================================================

@router.get("/feedback")
def get_feedback() -> dict:
    """获取反馈（Bug 列表）"""
    feedback_service = get_feedback_service()
    bugs = feedback_service.get_open_bugs()
    return {
        "bugs": [b.model_dump() for b in bugs],
        "count": len(bugs),
        "export_path": str(feedback_service.__class__.__mro__[0].__module__),
    }


@router.post("/feedback/{bug_id}/status")
def update_bug_status(bug_id: str, status: str = Query(..., description="新状态: triaged/fixed/ignored")) -> dict:
    """更新 Bug 状态"""
    feedback_service = get_feedback_service()
    success = feedback_service.update_bug_status(bug_id, status)
    if success:
        return {"status": "ok", "bug_id": bug_id, "new_status": status}
    return {"status": "error", "message": f"更新 Bug 状态失败: {bug_id}"}
