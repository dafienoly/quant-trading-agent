"""Product-facing API routes for the local demo dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Query

from src.config.settings import (
    BACKTEST_COMMISSION_RATE,
    BACKTEST_SLIPPAGE,
    BACKTEST_STAMP_DUTY,
    DEFAULT_DATA_PROVIDER,
    ENABLE_LIVE_TRADING,
    MAX_TRADING_LEVEL,
)
from src.data_gateway.realtime_provider import normalize_quote_symbol
from src.product_app.config_service import SAFE_CONFIG_GROUPS, get_config_service
from src.product_app.demo_data import (
    DEMO_STOCKS,
    get_demo_account,
    get_demo_factors,
    get_demo_positions,
    get_demo_signals,
    is_demo_mode,
)
from src.product_app.feedback import get_feedback_service
from src.product_app.market_data import default_symbols, fetch_product_quotes, parse_symbols
from src.risk_engine.runtime import RuntimeRiskEngine

router = APIRouter()

_risk_engine = RuntimeRiskEngine()
_config_service = get_config_service()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@router.get("/health")
def product_health() -> dict[str, Any]:
    kill_switch = _risk_engine.kill_switch
    config = _config_service.get_config(masked=True)
    provider = str(config.get("DEFAULT_DATA_PROVIDER", DEFAULT_DATA_PROVIDER))
    return {
        "status": "ok",
        "timestamp": _now(),
        "api_status": "running",
        "data_source": "demo" if is_demo_mode() else provider,
        "risk_status": "BLOCK" if kill_switch.active else "OK",
        "trading_mode": config.get("MAX_TRADING_LEVEL", MAX_TRADING_LEVEL),
        "is_live": bool(config.get("ENABLE_LIVE_TRADING", ENABLE_LIVE_TRADING)),
        "is_demo": is_demo_mode(),
        "kill_switch_active": kill_switch.active,
        "kill_switch_reason": kill_switch.reason if kill_switch.active else "",
        "feedback_backlog": len(get_feedback_service().get_open_bugs()),
    }


@router.get("/quotes")
def product_quotes(
    symbols: str = Query("", description="Comma-separated symbols, e.g. 002463.SZ,600584.SH"),
    provider: str = Query(DEFAULT_DATA_PROVIDER, description="akshare or aktools"),
    allow_demo: bool = Query(True, description="Fallback to deterministic demo data on failure"),
    force_live: bool = Query(False, description="Try realtime provider even outside trading hours"),
) -> dict[str, Any]:
    return fetch_product_quotes(
        parse_symbols(symbols),
        provider=provider,
        allow_demo=allow_demo,
        force_live=force_live,
    )


@router.get("/dashboard")
def product_dashboard() -> dict[str, Any]:
    config = _config_service.get_config(masked=True)
    provider = str(config.get("DEFAULT_DATA_PROVIDER", DEFAULT_DATA_PROVIDER))
    quote_result = fetch_product_quotes(default_symbols(), provider=provider, allow_demo=True)
    quotes = quote_result["quotes"]

    risk_decision = _risk_engine.check_realtime_snapshot(quotes=quotes)
    quote_by_code = {
        str(q.get("symbol", "")).split(".", 1)[0]: q
        for q in quotes
    }

    watchlist = []
    for stock in DEMO_STOCKS:
        quote = quote_by_code.get(stock["symbol"], {})
        watchlist.append(
            {
                "symbol": normalize_quote_symbol(stock["symbol"]),
                "name": stock["name"],
                "market": stock["market"],
                "sector": stock["sector"],
                "last_price": quote.get("last_price", 0),
                "pct_change": quote.get("pct_change", 0),
                "status": quote.get("status", "UNKNOWN"),
            }
        )

    return {
        "timestamp": _now(),
        "is_demo": quote_result["is_demo"],
        "data_source": quote_result["provider"],
        "quote_status": quote_result["status"],
        "quote_messages": quote_result.get("messages", []),
        "quotes": quotes,
        "signals": [signal.model_dump() for signal in get_demo_signals()] if quote_result["is_demo"] else [],
        "risk": {
            "risk_pass": risk_decision.risk_pass,
            "level": risk_decision.level.value,
            "trading_mode": risk_decision.trading_mode,
            "messages": risk_decision.messages,
            "kill_switch_active": _risk_engine.kill_switch.active,
            "kill_switch_reason": _risk_engine.kill_switch.reason if _risk_engine.kill_switch.active else "",
        },
        "account": get_demo_account().model_dump(),
        "positions": [position.model_dump() for position in get_demo_positions()],
        "factors": [factor.model_dump() for factor in get_demo_factors()],
        "watchlist": watchlist,
        "pending_orders": [],
        "trading_mode": config.get("MAX_TRADING_LEVEL", MAX_TRADING_LEVEL),
        "is_live": bool(config.get("ENABLE_LIVE_TRADING", ENABLE_LIVE_TRADING)),
    }


@router.post("/factors/compute")
def compute_factors(
    symbols: str = Query(..., description="Comma-separated symbols"),
    start_date: str = Query("", description="YYYYMMDD"),
    end_date: str = Query("", description="YYYYMMDD"),
) -> dict[str, Any]:
    symbol_codes = {normalize_quote_symbol(s).split(".", 1)[0] for s in symbols.split(",") if s.strip()}
    factors = [
        factor.model_dump()
        for factor in get_demo_factors()
        if not symbol_codes or factor.symbol in symbol_codes
    ]
    return {
        "status": "ok",
        "is_demo": True,
        "start_date": start_date,
        "end_date": end_date,
        "factors": factors,
        "warnings": [
            "Demo factor data is deterministic and suitable for UI/product verification only.",
            "Free data sources may not cover delisted stocks; report survivor-bias risk.",
        ],
    }


@router.get("/jobs")
def list_jobs() -> dict[str, Any]:
    from src.product_app.service_manager import get_service_manager

    return {"jobs": get_service_manager().list_jobs()}


@router.post("/jobs/{job_name}/start")
def start_job(
    job_name: str,
    symbols: str = Query("", description="Optional quote_refresh symbols"),
    provider: str = Query(DEFAULT_DATA_PROVIDER, description="akshare or aktools"),
    allow_demo: bool = Query(True, description="Allow quote_refresh demo fallback"),
    force_live: bool = Query(False, description="Force quote_refresh realtime provider"),
) -> dict[str, Any]:
    from src.product_app.service_manager import get_service_manager

    params: dict[str, Any] = {}
    if job_name == "quote_refresh":
        params = {
            "symbols": symbols,
            "provider": provider,
            "allow_demo": allow_demo,
            "force_live": force_live,
        }
    return get_service_manager().start_job(job_name, params=params)


@router.post("/jobs/{job_name}/stop")
def stop_job(job_name: str) -> dict[str, Any]:
    from src.product_app.service_manager import get_service_manager

    return get_service_manager().stop_job(job_name)


@router.post("/jobs/backtest/start")
def start_backtest(
    strategy: str = Query("demo_semiconductor_rotation"),
    symbols: str = Query(""),
    start_date: str = Query("20250101"),
    end_date: str = Query("20251231"),
    initial_capital: float = Query(1000000.0),
    commission_rate: float = Query(BACKTEST_COMMISSION_RATE),
    stamp_duty_rate: float = Query(BACKTEST_STAMP_DUTY),
    slippage: float = Query(BACKTEST_SLIPPAGE),
) -> dict[str, Any]:
    warnings = []
    if commission_rate == 0 or stamp_duty_rate == 0 or slippage == 0:
        warnings.append("Backtest assumptions must include commission, stamp duty, and slippage.")

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
            "limit_and_suspend_handling": True,
        },
        "performance": {
            "annual_return": 0.187,
            "max_drawdown": -0.123,
            "sharpe_ratio": 1.56,
            "win_rate": 0.58,
            "total_trades": 42,
        },
        "trades": [
            {"date": "2025-02-15", "symbol": "002463.SZ", "side": "BUY", "price": 35.80, "quantity": 3000, "pnl": 0},
            {"date": "2025-04-20", "symbol": "002463.SZ", "side": "SELL", "price": 38.52, "quantity": 3000, "pnl": 8160.0},
        ],
        "warnings": warnings,
        "disclaimer": "Demo backtest results are not investment advice.",
    }


@router.get("/config")
def get_config() -> dict[str, Any]:
    config = _config_service.get_config(masked=True)
    groups = {
        group_name: {key: config.get(key) for key in keys if key in config}
        for group_name, keys in SAFE_CONFIG_GROUPS.items()
    }
    return {
        "config": config,
        "groups": groups,
        "validation": _config_service.validate_config().model_dump(),
    }


@router.post("/config")
def update_config(key: str = Query(...), value: str = Query(...)) -> dict[str, Any]:
    return _config_service.update_config(key, value)


@router.post("/config/confirm-upgrade")
def confirm_upgrade(key: str = Query(...), value: str = Query(...)) -> dict[str, Any]:
    return _config_service.confirm_upgrade(key, value)


@router.post("/config/restore-defaults")
def restore_defaults() -> dict[str, Any]:
    return {
        "status": "ok",
        "message": "Configuration restored to safe defaults.",
        "config": _config_service.restore_defaults(),
    }


@router.get("/feedback")
def get_feedback() -> dict[str, Any]:
    feedback_service = get_feedback_service()
    bugs = feedback_service.get_open_bugs()
    return {
        "bugs": [bug.model_dump() for bug in bugs],
        "count": len(bugs),
        "export_path": "feedback/bugs/open",
    }


@router.post("/feedback")
def create_feedback(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    component = str(payload.get("component", "ui"))
    message = str(payload.get("message", "Product UI reported an error"))
    bug_id = get_feedback_service().write_bug_report(
        component=component,
        title=f"{component} error",
        summary=message,
        severity=str(payload.get("severity", "medium")),
        user_action=str(payload.get("user_action", "")),
        endpoint_or_page=str(payload.get("endpoint_or_page", "")),
        exception_type=str(payload.get("exception_type", "")),
        exception_message=message,
        runtime_context=dict(payload.get("runtime_context", {})),
    )
    return {"status": "ok" if bug_id else "error", "bug_id": bug_id}


@router.post("/feedback/{bug_id}/status")
def update_bug_status(bug_id: str, status: str = Query(...)) -> dict[str, Any]:
    success = get_feedback_service().update_bug_status(bug_id, status)
    if success:
        return {"status": "ok", "bug_id": bug_id, "new_status": status}
    return {"status": "error", "message": f"Failed to update bug status: {bug_id}"}
