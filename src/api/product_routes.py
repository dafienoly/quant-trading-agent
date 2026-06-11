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


def _get_bug_fix_workflow():
    """获取共享的 BugFixWorkflow 单例"""
    from src.product_app.bug_fix_workflow import BugFixWorkflow
    if not hasattr(_get_bug_fix_workflow, "_instance"):
        _get_bug_fix_workflow._instance = BugFixWorkflow()
    return _get_bug_fix_workflow._instance


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


@router.get("/feedback/{bug_id}/analysis")
def get_bug_analysis(bug_id: str) -> dict[str, Any]:
    """获取 Bug 分析报告和修复方案"""
    workflow = _get_bug_fix_workflow()
    status_info = workflow.get_bug_status(bug_id)
    if status_info is None:
        return {"status": "error", "message": f"Bug not found: {bug_id}"}
    bug_report = workflow.get_bug_report(bug_id) or {}
    return {
        "status": "ok",
        "bug_id": bug_id,
        "workflow_status": status_info,
        "analysis_report": bug_report.get("analysis_report"),
        "fix_proposal": bug_report.get("fix_proposal"),
        "fix_result": bug_report.get("fix_result"),
        "approval_status": bug_report.get("approval_status", "pending"),
        "approval_comment": bug_report.get("approval_comment", ""),
    }


@router.post("/feedback/{bug_id}/approve")
def approve_bug_fix(bug_id: str, comment: str = Query("", description="Approval comment")) -> dict[str, Any]:
    """审批通过 Bug 修复方案"""
    workflow = _get_bug_fix_workflow()
    result = workflow.approve_fix(bug_id, comment=comment)
    return result


@router.post("/feedback/{bug_id}/reject")
def reject_bug_fix(bug_id: str, comment: str = Query("", description="Rejection reason")) -> dict[str, Any]:
    """拒绝 Bug 修复方案"""
    workflow = _get_bug_fix_workflow()
    result = workflow.reject_fix(bug_id, comment=comment)
    return result


@router.get("/feedback/{bug_id}/fix-status")
def get_bug_fix_status(bug_id: str) -> dict[str, Any]:
    """获取 Bug 修复进度"""
    workflow = _get_bug_fix_workflow()
    status_info = workflow.get_bug_status(bug_id)
    if status_info is None:
        return {"status": "error", "message": f"Bug not found: {bug_id}"}
    return {
        "status": "ok",
        "bug_id": bug_id,
        "fix_status": status_info,
    }


# ============================================================
# Live Data Closed-Loop API (Phase B)
# ============================================================

def _get_live_data_service():
    """获取共享的 LiveDataService 单例"""
    from src.product_app.live_data_service import get_live_data_service
    return get_live_data_service()


def _get_diagnostics_service():
    """获取共享的 ProviderDiagnosticsService 单例"""
    from src.product_app.provider_diagnostics_service import ProviderDiagnosticsService
    from src.product_app.live_data_service import get_live_data_service
    if not hasattr(_get_diagnostics_service, "_instance"):
        lds = get_live_data_service()
        _get_diagnostics_service._instance = ProviderDiagnosticsService(
            realtime_hub=lds._realtime_hub,
            daily_bars_hub=lds._daily_bars_hub,
            fundamentals_hub=lds._fundamentals_hub,
        )
    return _get_diagnostics_service._instance


@router.get("/live-data/providers")
def get_live_providers() -> dict[str, Any]:
    """获取 provider 配置、能力和当前熔断状态"""
    from src.data_gateway.provider_contracts import DataCapability

    lds = _get_live_data_service()
    health_realtime = lds._realtime_hub.get_health(DataCapability.REALTIME_QUOTES)
    health_daily = lds._daily_bars_hub.get_health(DataCapability.DAILY_BARS)
    health_fundamentals = lds._fundamentals_hub.get_health(DataCapability.FUNDAMENTALS)

    def _health_to_dict(h_list):
        return {
            h.provider: {
                "status": h.status,
                "latency_ms": h.latency_ms,
                "row_count": h.row_count,
                "error": h.error,
                "last_success_at": h.last_success_at,
            }
            for h in h_list
        }

    return {
        "status": "ok",
        "provider_order": lds._provider_order,
        "realtime_quotes": _health_to_dict(health_realtime),
        "daily_bars": _health_to_dict(health_daily),
        "fundamentals": _health_to_dict(health_fundamentals),
    }


@router.post("/live-data/diagnose")
def diagnose_live_providers(
    symbols: str = Query("600000.SH,000001.SZ", description="Comma-separated symbols for diagnosis"),
    capabilities: str = Query("realtime_quotes,daily_bars,fundamentals", description="Comma-separated capabilities"),
) -> dict[str, Any]:
    """执行数据源诊断"""
    from src.data_gateway.provider_contracts import DataCapability

    diag_service = _get_diagnostics_service()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    cap_list = []
    cap_map = {
        "realtime_quotes": DataCapability.REALTIME_QUOTES,
        "daily_bars": DataCapability.DAILY_BARS,
        "fundamentals": DataCapability.FUNDAMENTALS,
    }
    for cap_str in capabilities.split(","):
        cap_str = cap_str.strip()
        if cap_str in cap_map:
            cap_list.append(cap_map[cap_str])

    return diag_service.diagnose(symbols=symbol_list, capabilities=cap_list)


@router.get("/live-data/quotes")
def get_live_quotes(
    symbols: str = Query("600000.SH,000001.SZ", description="Comma-separated symbols"),
    pool_type: str = Query("watchlist", description="watchlist or theme_pool"),
) -> dict[str, Any]:
    """获取真实实时行情（live closed-loop）"""
    lds = _get_live_data_service()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return lds.get_realtime_quotes(symbol_list, pool_type=pool_type, allow_demo=False)


@router.get("/live-data/daily-bars")
def get_live_daily_bars(
    symbols: str = Query("600000.SH,000001.SZ", description="Comma-separated symbols"),
    start_date: str = Query("20250101", description="Start date YYYYMMDD or YYYY-MM-DD"),
    end_date: str = Query("20251231", description="End date YYYYMMDD or YYYY-MM-DD"),
    adjust: str = Query("qfq", description="Adjustment type: qfq/hfq/empty"),
) -> dict[str, Any]:
    """获取真实历史日线（live closed-loop）"""
    lds = _get_live_data_service()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return lds.get_daily_bars(symbol_list, start_date, end_date, adjust=adjust)


@router.get("/live-data/fundamentals")
def get_live_fundamentals(
    symbols: str = Query("600000.SH,000001.SZ", description="Comma-separated symbols"),
) -> dict[str, Any]:
    """获取真实基础财务数据（live closed-loop）"""
    lds = _get_live_data_service()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return lds.get_fundamentals(symbol_list)


@router.post("/live-data/research-context")
def build_research_context(
    symbols: str = Query("600000.SH,000001.SZ", description="Comma-separated symbols"),
    start_date: str = Query("20250101", description="Start date"),
    end_date: str = Query("20251231", description="End date"),
) -> dict[str, Any]:
    """构建完整研究上下文（日线+财务+健康决策）"""
    lds = _get_live_data_service()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return lds.build_research_context(symbol_list, start_date, end_date)


# ============================================================
# Stock Pool API (Phase C)
# ============================================================

def _get_stock_pool_service():
    """获取 StockPoolService 单例"""
    from src.product_app.stock_pool_service import get_stock_pool_service
    return get_stock_pool_service()


def _get_theme_pool_service():
    """获取 ThemePoolService 单例"""
    from src.product_app.stock_pool_service import get_theme_pool_service
    return get_theme_pool_service()


@router.get("/pools")
def list_pools() -> dict[str, Any]:
    """列出所有股票池"""
    sps = _get_stock_pool_service()
    tps = _get_theme_pool_service()
    watchlist = sps.get_pool("default")
    theme_pool = tps.get_theme_pool()
    return {
        "status": "ok",
        "watchlist": watchlist,
        "theme_pool": {
            "pool_id": theme_pool.get("pool_id", ""),
            "name": theme_pool.get("name", ""),
            "stock_count": len(theme_pool.get("stocks", [])),
            "tags": theme_pool.get("tags", []),
        },
    }


@router.get("/pools/{pool_id}")
def get_pool(pool_id: str) -> dict[str, Any]:
    """获取指定股票池内容"""
    if pool_id == "ai_semiconductor":
        tps = _get_theme_pool_service()
        return {"status": "ok", "pool": tps.get_theme_pool()}
    sps = _get_stock_pool_service()
    pool = sps.get_pool(pool_id)
    return {"status": "ok", "pool": pool}


@router.post("/pools/watchlist")
def update_watchlist(
    action: str = Query("add", description="add or remove"),
    symbols: str = Query(..., description="Comma-separated symbols"),
    pool_id: str = Query("default", description="Pool ID"),
) -> dict[str, Any]:
    """添加或删除自选股"""
    sps = _get_stock_pool_service()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if action == "add":
        result = sps.add_symbols(pool_id, symbol_list)
    elif action == "remove":
        result = sps.remove_symbols(pool_id, symbol_list)
    else:
        return {"status": "error", "message": f"Unknown action: {action}"}
    return result


@router.post("/pools/validate")
def validate_symbols(
    symbols: str = Query(..., description="Comma-separated symbols to validate"),
) -> dict[str, Any]:
    """验证股票代码是否允许进入实盘闭环"""
    sps = _get_stock_pool_service()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    validation = sps.validate_symbols(symbol_list)
    return {
        "status": "ok",
        "validation": [v.__dict__ if hasattr(v, "__dict__") else v for v in validation],
    }


# ============================================================
# Signal API (Phase D)
# ============================================================

def _get_live_signal_orchestrator():
    """获取 LiveSignalOrchestrator 单例"""
    from src.product_app.live_signal_orchestrator import get_live_signal_orchestrator
    return get_live_signal_orchestrator()


@router.post("/signal/draft")
def generate_signal_draft(
    symbols: str = Query(..., description="Comma-separated symbols"),
    start_date: str = Query("20250101", description="Start date"),
    end_date: str = Query("20251231", description="End date"),
    trading_mode: str = Query("LEVEL_1_SIGNAL_ONLY", description="Trading mode"),
) -> dict[str, Any]:
    """生成信号草稿（含数据健康证据链）"""
    orchestrator = _get_live_signal_orchestrator()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return orchestrator.generate_signal_draft(
        symbols=symbol_list,
        start_date=start_date,
        end_date=end_date,
        trading_mode=trading_mode,
    )


@router.get("/signal/{signal_id}")
def get_signal_status(signal_id: str) -> dict[str, Any]:
    """获取信号状态"""
    orchestrator = _get_live_signal_orchestrator()
    return orchestrator.get_signal_status(signal_id)


# ============================================================
# Search & Theme Evidence API (Phase E)
# ============================================================

def _get_search_provider_hub():
    """获取 SearchProviderHub 单例"""
    from src.product_app.search_provider_hub import get_search_provider_hub
    return get_search_provider_hub()


def _get_theme_evidence_service():
    """获取 ThemeEvidenceService 单例"""
    from src.product_app.theme_evidence_service import get_theme_evidence_service
    return get_theme_evidence_service()


@router.post("/search")
def search_web(
    query: str = Query(..., description="Search query"),
    max_results: int = Query(5, description="Max results"),
) -> dict[str, Any]:
    """搜索互联网信息（受预算控制）"""
    hub = _get_search_provider_hub()
    return hub.search(query, max_results=max_results)


@router.get("/theme-evidence")
def get_theme_evidence(
    symbols: str = Query(..., description="Comma-separated symbols"),
    theme_tag: str = Query(None, description="Optional theme tag filter"),
) -> dict[str, Any]:
    """获取主题证据（主题池+搜索新闻）"""
    service = _get_theme_evidence_service()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return service.get_theme_evidence(symbol_list, theme_tag=theme_tag)
