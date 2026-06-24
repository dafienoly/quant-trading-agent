"""Integrated Streamlit product dashboard for the Quant Trading Agent demo."""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests
import streamlit as st

from src.ui_report.i18n import t

DEFAULT_API_BASE = "http://localhost:8000"
API_TIMEOUT = 8


PAGE_CSS = """
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
.status-card {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  padding: 14px 16px;
  background: #ffffff;
  min-height: 92px;
}
.status-label {
  font-size: 0.78rem;
  color: #62748e;
  margin-bottom: 6px;
}
.status-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #102a43;
}
.status-note {
  font-size: 0.82rem;
  color: #62748e;
  margin-top: 5px;
}
.safe-banner {
  border-left: 4px solid #0f766e;
  background: #ecfdf5;
  padding: 10px 12px;
  border-radius: 6px;
  color: #134e4a;
}
.warn-banner {
  border-left: 4px solid #b45309;
  background: #fffbeb;
  padding: 10px 12px;
  border-radius: 6px;
  color: #78350f;
}
.danger-banner {
  border-left: 4px solid #b91c1c;
  background: #fef2f2;
  padding: 10px 12px;
  border-radius: 6px;
  color: #7f1d1d;
}
.step-indicator {
  display: flex;
  align-items: center;
  gap: 0;
  margin: 8px 0;
}
.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  position: relative;
}
.step-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 700;
  color: #fff;
  background: #334155;
  border: 2px solid #475569;
  z-index: 1;
}
.step-dot.step-completed {
  background: #059669;
  border-color: #10b981;
}
.step-dot.step-current {
  background: #2563eb;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.3);
}
.step-label {
  font-size: 0.65rem;
  color: #94a3b8;
  margin-top: 4px;
  text-align: center;
  white-space: nowrap;
}
.step-label.step-label-completed {
  color: #10b981;
}
.step-label.step-label-current {
  color: #3b82f6;
  font-weight: 600;
}
.step-connector {
  flex: 1;
  height: 2px;
  background: #334155;
  margin-top: -12px;
}
.step-connector.step-connector-completed {
  background: #059669;
}
</style>
"""


def _api_base() -> str:
    return st.session_state.get("api_base", DEFAULT_API_BASE).rstrip("/")


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{_api_base()}{path}", params=params, timeout=API_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        _report_error("dashboard", f"GET {path} returned HTTP {response.status_code}")
    except Exception as exc:
        _report_error("dashboard", f"GET {path} failed: {exc}")
    return None


def _post(path: str, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        response = requests.post(f"{_api_base()}{path}", params=params, json=json, timeout=API_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        _report_error("dashboard", f"POST {path} returned HTTP {response.status_code}")
    except Exception as exc:
        _report_error("dashboard", f"POST {path} failed: {exc}")
    return None


def _report_error(component: str, message: str) -> None:
    try:
        requests.post(
            f"{_api_base()}/product/feedback",
            json={
                "component": component,
                "message": message,
                "endpoint_or_page": "product_dashboard",
            },
            timeout=2,
        )
    except Exception:
        pass


def _df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _symbol_code(symbol: str) -> str:
    return str(symbol).split(".", 1)[0]


def _format_pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}%"


def _card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
<div class="status-card">
          <div class="status-label">{label}</div>
          <div class="status-value">{value}</div>
          <div class="status-note">{note}</div>
        </div>
""",
        unsafe_allow_html=True,
    )


def _job_by_name(jobs_data: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
    if not jobs_data:
        return None
    return next((job for job in jobs_data.get("jobs", []) if job.get("name") == name), None)


def _banner(kind: str, text: str) -> None:
    css = {"safe": "safe-banner", "warn": "warn-banner", "danger": "danger-banner"}[kind]
    st.markdown(f'<div class="{css}">{text}</div>', unsafe_allow_html=True)


def render_system() -> None:
    st.subheader(t("system"))
    health = _get("/product/health")
    dashboard = _get("/product/dashboard")

    if not health:
        _banner("danger", "API is offline. Start it with: python -m uvicorn src.api.app:app --port 8000")
        return

    if health.get("is_live"):
        _banner("danger", "Live trading is enabled. Demo delivery should normally run with paper trading.")
    else:
        _banner("safe", "Live trading is disabled. Product demo is running in safe paper/signal mode.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _card(t("api"), health.get("api_status", "unknown"), health.get("timestamp", ""))
    with col2:
        _card(t("data_provider"), health.get("data_source", "unknown"), t("demo_fallback_explicit"))
    with col3:
        _card(t("risk"), health.get("risk_status", "UNKNOWN"), t("risk_veto"))
    with col4:
        _card(t("trading_mode"), health.get("trading_mode", "UNKNOWN"), t("level_3_not_exposed"))

    if dashboard:
        account = dashboard.get("account", {})
        st.markdown(f"### {t('paper_account')}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("total_assets"), f"{account.get('total_assets', 0):,.0f}")
        c2.metric(t("cash"), f"{account.get('cash', 0):,.0f}")
        c3.metric(t("market_value"), f"{account.get('market_value', 0):,.0f}")
        c4.metric(t("daily_pnl"), f"{account.get('daily_pnl', 0):,.0f}", f"{account.get('daily_pnl_pct', 0):.2%}")


def render_market() -> None:
    st.subheader(t("realtime_market"))
    st.caption(t("realtime_market_caption"))

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        symbols = st.text_input(t("symbols"), "002463.SZ,600584.SH,603228.SH", help=t("symbols_help"), key="market_symbols")
    with col2:
        provider = st.selectbox(t("data_provider_select"), ["akshare", "aktools"], index=0, key="market_provider")
    with col3:
        force_live = st.checkbox(t("force_realtime_fetch"), value=False, key="market_force_live")

    allow_demo = st.checkbox(t("allow_demo_fallback"), value=True, key="market_allow_demo")
    col4, col5 = st.columns(2)
    refresh = col4.button(t("refresh_quotes"), type="primary", width="stretch")
    start_job = col5.button(t("start_bg_snapshot"), width="stretch")

    params = {
        "symbols": symbols,
        "provider": provider,
        "allow_demo": str(allow_demo).lower(),
        "force_live": str(force_live or refresh).lower(),
    }
    if start_job:
        job_result = _post("/product/jobs/quote_refresh/start", params=params)
        if job_result and job_result.get("status") == "ok":
            st.success(f"quote_refresh {t('bg_snapshot_started')}: {job_result.get('job_id')}")
        else:
            _banner("danger", f"quote_refresh {t('bg_snapshot_failed')}: {job_result}")

    result = _get("/product/quotes", params=params)
    jobs = _get("/product/jobs") or {}
    quote_job = next((job for job in jobs.get("jobs", []) if job.get("name") == "quote_refresh"), None)
    if quote_job:
        st.caption(
            "quote_refresh: "
            f"{quote_job.get('state')} | last_run={quote_job.get('last_run_at', '')} "
            f"| result={quote_job.get('last_result', '')}"
        )

    if not result:
        _banner("danger", t("unable_fetch_quotes"))
        return

    status = result.get("status", "unknown")
    if result.get("is_demo"):
        _banner("warn", f"{t('showing_demo_data')}. {t('status')}: {status}. {' '.join(result.get('messages', []))}")
    else:
        _banner("safe", t("showing_realtime_data").format(provider=result.get('provider'), timestamp=result.get('timestamp')))

    rows = []
    for quote in result.get("quotes", []):
        rows.append(
            {
                "Symbol": quote.get("symbol"),
                "Name": quote.get("name", ""),
                "Market": quote.get("market", ""),
                "Last": quote.get("last_price", 0),
                "Change": _format_pct(quote.get("pct_change")),
                "Volume": quote.get("volume", 0),
                "Amount": quote.get("amount", 0),
                "Status": quote.get("status", "UNKNOWN"),
                "Source": quote.get("data_source", result.get("provider", "")),
                "Updated": quote.get("updated_at", quote.get("datetime", "")),
            }
        )
    st.dataframe(_df(rows), width="stretch", hide_index=True)


def render_readonly_monitoring() -> None:
    """V16.0b 只读行情监控 Dashboard 区块"""
    st.subheader("只读行情监控")
    watchlist = []
    try:
        with open("runtime/state/watchlist.json") as f:
            raw = f.read()
            watchlist = [s.strip() for s in raw.split("\n") if s.strip()]
    except FileNotFoundError:
        pass

    if watchlist:
        for sym in watchlist[:10]:
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(sym)
            col2.write("等待刷新数据")
            col3.markdown("🧪 HEALTHY" if "未知" not in "等待" else "⚠️ STALE")

    try:
        r = requests.get(f"{DEFAULT_API_BASE}/product/refresh-status", timeout=3)
        rs = r.json()
        st.write(f"最近刷新状态：{rs.get('status', 'IDLE')}")
    except Exception:
        st.write("最近刷新状态：查询失败")

    try:
        r = requests.get(f"{DEFAULT_API_BASE}/product/signal-observation", timeout=3)
        sig = r.json()
        if sig.get("status") == "OK":
            blocked = [o for o in sig.get("observations", []) if o.get("status") == "BLOCKED"]
            healthy = [o for o in sig.get("observations", []) if o.get("status") == "HEALTHY"]
            if healthy:
                st.success(f"可观测信号：{len(healthy)} 只")
            if blocked:
                st.warning(f"被阻断信号：{len(blocked)} 只")
    except Exception:
        pass


def render_watchlist() -> None:
    st.subheader(t("watchlist"))
    dashboard = _get("/product/dashboard")
    if not dashboard:
        _banner("danger", t("dashboard_unavailable"))
        return

    if dashboard.get("trading_mode") == "LEVEL_1_SIGNAL_ONLY":
        _banner("safe", t("level1_signal_only"))

    rows = []
    for item in dashboard.get("watchlist", []):
        rows.append(
            {
                "Symbol": item.get("symbol"),
                "Name": item.get("name"),
                "Sector": item.get("sector"),
                "Last": item.get("last_price", 0),
                "Change": _format_pct(item.get("pct_change")),
                "Risk status": item.get("status", "UNKNOWN"),
            }
        )
    st.dataframe(_df(rows), width="stretch", hide_index=True)

    risk = dashboard.get("risk", {})
    if not risk.get("risk_pass", True):
        _banner("danger", t("risk_blocked") + ": " + " / ".join(risk.get("messages", [])))


def render_factor_lab() -> None:
    st.subheader(t("factor_lab"))
    st.caption(t("factor_lab_caption"))
    symbols = st.text_input(t("symbols"), "600000.SH,000001.SZ", key="factor_symbols")
    col1, col2 = st.columns(2)
    start_date = col1.text_input(t("start_date"), "20250101", key="factor_start_date")
    end_date = col2.text_input(t("end_date"), "20251231", key="factor_end_date")

    if st.button(t("compute_live_factors"), type="primary", key="compute_factors_btn"):
        result = _post(
            "/product/live-factors/compute",
            params={"symbols": symbols, "start_date": start_date, "end_date": end_date},
        )
        if result:
            data_status = result.get("data_status", "UNKNOWN")
            if data_status == "FAILED":
                _banner("danger", f"{t('factor_compute_failed')} Data status: {data_status}")
            elif data_status == "WARN":
                _banner("warn", f"{t('factor_compute_partial')} Data status: {data_status}")
            else:
                _banner("safe", f"{t('factor_compute_ok')} Data status: {data_status}")
            rows = []
            for factor in result.get("factors", []):
                rows.append({
                    "Symbol": factor.get("symbol"),
                    "Date": factor.get("trade_date"),
                    "SMA_5": factor.get("sma_5"),
                    "SMA_20": factor.get("sma_20"),
                    "RSI": factor.get("rsi_14"),
                    "MACD": factor.get("macd_line"),
                    "BOLL_Mid": factor.get("boll_middle"),
                })
            st.dataframe(_df(rows), hide_index=True)
            with st.expander(t("data_health")):
                st.json(result.get("data_health", {}))
        else:
            _banner("danger", t("failed_to_compute"))


def render_backtest() -> None:
    st.subheader(t("backtest"))
    st.caption(t("backtest_caption"))
    col1, col2, col3 = st.columns(3)
    symbols = col1.text_input(t("symbols"), "600000.SH,000001.SZ", key="backtest_symbols")
    start_date = col2.text_input(t("start_date"), "20250101", key="backtest_start_date")
    end_date = col3.text_input(t("end_date"), "20251231", key="backtest_end_date")

    if st.button(t("run_live_backtest"), type="primary", key="run_backtest_btn"):
        result = _post(
            "/product/live-backtests/run",
            params={"symbols": symbols, "start_date": start_date, "end_date": end_date},
        )
        if result:
            bt_status = result.get("status", "unknown")
            data_status = result.get("data_status", "UNKNOWN")
            if bt_status == "failed" or data_status == "FAILED":
                _banner("danger", f"{t('backtest_failed')} Data status: {data_status}")
            elif bt_status == "insufficient_data":
                _banner("warn", t("backtest_insufficient_data"))
            else:
                _banner("safe", f"{t('backtest_completed')} Strategy: {result.get('strategy', '')}. Data status: {data_status}")
                results = result.get("results", {})
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(t("total_return"), f"{results.get('total_return', 0):.2%}")
                c2.metric(t("max_drawdown"), f"{results.get('max_drawdown', 0):.2%}")
                c3.metric(t("sharpe"), f"{results.get('sharpe_ratio', 0):.2f}")
                c4.metric(t("win_rate"), f"{results.get('win_rate', 0):.2%}")
            with st.expander(t("data_health")):
                st.json(result.get("health", {}))
        else:
            _banner("danger", t("failed_to_run_backtest"))


def render_signals() -> None:
    st.subheader(t("signals"))
    dashboard = _get("/product/dashboard")
    if not dashboard:
        _banner("danger", t("signal_unavailable"))
        return

    rows = []
    for signal in dashboard.get("signals", []):
        rows.append(
            {
                t("signal"): signal.get("signal_type"),
                "Symbol": signal.get("symbol"),
                "Name": signal.get("stock_name"),
                t("score"): signal.get("score"),
                t("trigger"): signal.get("price_trigger"),
                t("stop"): signal.get("stop_loss_price"),
                t("take_profit"): signal.get("take_profit_price"),
                t("reason"): signal.get("reason"),
                t("risk_note"): signal.get("risk_note"),
            }
        )
    st.dataframe(_df(rows), width="stretch", hide_index=True)


def render_human_confirmation() -> None:
    st.subheader(t("human_confirmation"))
    _banner("warn", t("buy_orders_warning"))
    pending = _get("/orders/pending") or {"orders": []}
    orders = pending.get("orders", [])

    if not orders:
        st.info(t("no_pending_orders"))
        return

    for order in orders:
        title = f"{order.get('side')} {order.get('stock_name', '')} {order.get('symbol')} x{order.get('quantity')} @ {order.get('limit_price')}"
        with st.expander(title):
            st.json(order)
            col1, col2, col3 = st.columns(3)
            if col1.button(t("confirm_order"), key=f"confirm_{order.get('order_id')}", type="primary"):
                st.write(_post(f"/orders/{order.get('order_id')}/confirm"))
                st.rerun()
            if col2.button(t("reject"), key=f"reject_{order.get('order_id')}"):
                st.write(_post(f"/orders/{order.get('order_id')}/reject"))
                st.rerun()
            if col3.button(t("cancel"), key=f"cancel_{order.get('order_id')}"):
                st.write(_post(f"/orders/{order.get('order_id')}/cancel"))
                st.rerun()


def render_configuration() -> None:
    st.subheader(t("configuration"))
    config_data = _get("/product/config")
    if not config_data:
        _banner("danger", t("config_unavailable"))
        return

    validation = config_data.get("validation", {})
    for error in validation.get("errors", []):
        _banner("danger", error)
    for warning in validation.get("warnings", []):
        _banner("warn", warning)

    config = config_data.get("config", {})
    provider = st.selectbox(
        t("data_provider_select"),
        ["akshare", "aktools"],
        index=0 if config.get("DEFAULT_DATA_PROVIDER", "akshare") == "akshare" else 1,
        key="config_provider",
    )
    log_level = st.selectbox(t("log_level"), ["DEBUG", "INFO", "WARNING", "ERROR"], index=1, key="config_log_level")
    max_single = st.slider(t("max_single_position"), 0.01, 0.50, float(config.get("MAX_SINGLE_STOCK_POSITION", 0.15)), 0.01, key="config_max_single")
    max_sector = st.slider(t("max_sector_position"), 0.10, 1.00, float(config.get("MAX_SECTOR_POSITION", 0.60)), 0.05, key="config_max_sector")
    min_cash = st.slider(t("min_cash_ratio"), 0.0, 0.50, float(config.get("MIN_CASH_RATIO", 0.20)), 0.05, key="config_min_cash")

    mode = st.selectbox(
        t("trading_mode"),
        ["LEVEL_0", "LEVEL_1_SIGNAL_ONLY", "LEVEL_2_HUMAN_CONFIRM"],
        index=1,
        key="config_trading_mode",
    )
    if mode == "LEVEL_3_AUTO":
        _banner("danger", t("level3_blocked"))
    elif mode == "LEVEL_2_HUMAN_CONFIRM":
        _banner("warn", t("level2_warning"))

    if st.button(t("save_safe_config"), type="primary", key="save_config_btn"):
        updates = {
            "DEFAULT_DATA_PROVIDER": provider,
            "LOG_LEVEL": log_level,
            "MAX_SINGLE_STOCK_POSITION": str(max_single),
            "MAX_SECTOR_POSITION": str(max_sector),
            "MIN_CASH_RATIO": str(min_cash),
        }
        results = [_post("/product/config", params={"key": key, "value": value}) for key, value in updates.items()]
        if all(result and result.get("success") for result in results):
            st.success(t("config_saved"))
        else:
            st.error(t("config_failed"))

    if st.button(t("restore_safe_defaults"), key="restore_defaults_btn"):
        st.write(_post("/product/config/restore-defaults"))
        st.rerun()


BUG_WORKFLOW_STATES = ["open", "analyzing", "proposed", "approved", "fixing", "verified", "fixed"]


def _render_status_steps(current_status: str) -> None:
    """Render a horizontal step indicator for the bug workflow status machine."""
    current_status = (current_status or "open").lower()
    current_idx = BUG_WORKFLOW_STATES.index(current_status) if current_status in BUG_WORKFLOW_STATES else 0

    items_html = []
    for i, state in enumerate(BUG_WORKFLOW_STATES):
        if i < current_idx:
            dot_cls = "step-completed"
            label_cls = "step-label-completed"
        elif i == current_idx:
            dot_cls = "step-current"
            label_cls = "step-label-current"
        else:
            dot_cls = ""
            label_cls = ""
        items_html.append(
            f'<div class="step-item">'
            f'<div class="step-dot {dot_cls}">{i + 1}</div>'
            f'<div class="step-label {label_cls}">{state}</div>'
            f'</div>'
        )
        if i < len(BUG_WORKFLOW_STATES) - 1:
            conn_cls = "step-connector-completed" if i < current_idx else ""
            items_html.append(f'<div class="step-connector {conn_cls}"></div>')

    st.markdown(
        f'<div class="step-indicator">{"".join(items_html)}</div>',
        unsafe_allow_html=True,
    )


def _render_analysis_report(report: dict[str, Any]) -> None:
    """Render an expandable section for a bug's analysis report."""
    with st.expander(f"🔍 {t('analysis_report')}", expanded=False):
        root_cause = report.get("root_cause", "")
        if root_cause:
            st.markdown("**Root Cause:**")
            st.write(root_cause)
        affected_files = report.get("affected_files", [])
        if affected_files:
            st.markdown("**Affected Files:**")
            if isinstance(affected_files, list):
                for f in affected_files:
                    st.markdown(f"- `{f}`")
            else:
                st.write(affected_files)
        fix_steps = report.get("fix_steps", [])
        if fix_steps:
            st.markdown("**Fix Steps:**")
            if isinstance(fix_steps, list):
                for idx, step in enumerate(fix_steps, 1):
                    st.markdown(f"{idx}. {step}")
            else:
                st.write(fix_steps)
        risk_level = report.get("risk_level", "")
        if risk_level:
            risk_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            emoji = risk_colors.get(risk_level.lower(), "⚪")
            st.markdown(f"**Risk Level:** {emoji} {risk_level}")
        estimated_impact = report.get("estimated_impact", "")
        if estimated_impact:
            st.markdown(f"**Estimated Impact:** {estimated_impact}")
        extra_keys = set(report.keys()) - {"root_cause", "affected_files", "fix_steps", "risk_level", "estimated_impact"}
        if extra_keys:
            st.markdown("**Additional Details:**")
            st.json({k: report[k] for k in extra_keys})


def _render_fix_proposal(proposal: dict[str, Any]) -> None:
    """Render an expandable section for a bug's fix proposal."""
    with st.expander(f"🔧 {t('fix_proposal')}", expanded=False):
        fix_desc = proposal.get("fix_description", "")
        if fix_desc:
            st.markdown("**Fix Description:**")
            st.write(fix_desc)
        code_changes = proposal.get("code_changes", "")
        if code_changes:
            st.markdown("**Code Changes:**")
            if isinstance(code_changes, (list, dict)):
                st.json(code_changes)
            else:
                st.code(str(code_changes))
        risk_level = proposal.get("risk_level", "")
        if risk_level:
            risk_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            emoji = risk_colors.get(risk_level.lower(), "⚪")
            st.markdown(f"**Risk Level:** {emoji} {risk_level}")
        test_suggestions = proposal.get("test_suggestions", "")
        if test_suggestions:
            st.markdown("**Test Suggestions:**")
            if isinstance(test_suggestions, list):
                for s in test_suggestions:
                    st.markdown(f"- {s}")
            else:
                st.write(test_suggestions)
        extra_keys = set(proposal.keys()) - {"fix_description", "code_changes", "risk_level", "test_suggestions"}
        if extra_keys:
            st.markdown("**Additional Details:**")
            st.json({k: proposal[k] for k in extra_keys})


def _render_fix_result(result: dict[str, Any]) -> None:
    """Render the fix execution result (success/failure, test output, commit hash)."""
    success = result.get("success", False)
    if success:
        st.success("✅ Fix applied successfully")
    else:
        st.error("❌ Fix failed")
    test_output = result.get("test_output", "")
    if test_output:
        with st.expander("Test Output"):
            st.code(str(test_output))
    commit_hash = result.get("commit_hash", "")
    if commit_hash:
        st.markdown(f"**Commit:** `{commit_hash}`")
    error_msg = result.get("error", "")
    if error_msg:
        st.error(f"Error: {error_msg}")
    extra_keys = set(result.keys()) - {"success", "test_output", "commit_hash", "error"}
    if extra_keys:
        st.json({k: result[k] for k in extra_keys})


def render_feedback() -> None:
    st.subheader(t("feedback"))
    data = _get("/product/feedback")
    if not data:
        _banner("danger", t("feedback_unavailable"))
        return

    jobs_data = _get("/product/jobs") or {}
    bug_agent_job = _job_by_name(jobs_data, "bug_fix_agent")
    agent_state = bug_agent_job.get("state", t("unknown")) if bug_agent_job else t("unknown")
    agent_note = ""
    if bug_agent_job:
        agent_note = bug_agent_job.get("error_message") or bug_agent_job.get("last_result") or bug_agent_job.get("last_run_at", "")

    agent_col, bug_col = st.columns(2)
    with agent_col:
        _card(t("bug_fix_agent"), str(agent_state), agent_note)
    with bug_col:
        _card(t("open_bugs"), str(data.get("count", 0)), data.get("export_path", "feedback/bugs/open"))

    start_col, stop_col = st.columns(2)
    if start_col.button(t("start_bug_fix_agent"), key="start_bug_fix_agent", type="primary"):
        result = _post("/product/jobs/bug_fix_agent/start")
        if result and result.get("status") == "ok":
            st.success(result.get("message", t("ok")))
            st.rerun()
        else:
            st.error(f"{t('agent_start_failed')}: {result}")
    if stop_col.button(t("stop_bug_fix_agent"), key="stop_bug_fix_agent"):
        result = _post("/product/jobs/bug_fix_agent/stop")
        if result and result.get("status") == "ok":
            st.success(result.get("message", t("ok")))
            st.rerun()
        else:
            st.error(f"{t('agent_stop_failed')}: {result}")

    bugs = data.get("bugs", [])
    if not bugs:
        st.info(t("no_open_bugs"))
        return

    for bug in bugs:
        bug_id = bug.get("bug_id")
        bug_status = (bug.get("status") or "open").lower()
        severity = bug.get("severity", "").upper()
        title = bug.get("title", "")

        with st.expander(f"{severity} {bug_id}: {title}"):
            # --- Bug Status Step Indicator ---
            st.markdown(f"**{t('workflow_status')}**")
            _render_status_steps(bug_status)

            st.divider()

            # --- Summary ---
            summary = bug.get("summary", "")
            if summary:
                st.write(summary)

            # --- Analysis Report ---
            analysis_report = bug.get("analysis_report")
            if analysis_report and isinstance(analysis_report, dict):
                _render_analysis_report(analysis_report)

            # --- Fix Proposal ---
            fix_proposal = bug.get("fix_proposal")
            if fix_proposal and isinstance(fix_proposal, dict):
                _render_fix_proposal(fix_proposal)

            # --- Fix Result ---
            fix_result = bug.get("fix_result")
            if fix_result and isinstance(fix_result, dict):
                _render_fix_result(fix_result)

            st.divider()

            # --- Action Buttons ---
            if bug_status == "proposed":
                approve_col, reject_col = st.columns(2)
                with approve_col:
                    if st.button(f"✅ {t('approve')}", key=f"approve_{bug_id}", type="primary"):
                        result = _post(f"/product/feedback/{bug_id}/approve", params={"comment": t("approve_comment")})
                        if result:
                            st.success(t("approve_success"))
                            st.rerun()
                        else:
                            st.error(t("approve_failed"))
                with reject_col:
                    if st.button(f"❌ {t('reject')}", key=f"reject_{bug_id}"):
                        result = _post(f"/product/feedback/{bug_id}/reject", params={"comment": t("reject_comment")})
                        if result:
                            st.warning(t("reject_success"))
                            st.rerun()
                        else:
                            st.error(t("reject_failed"))
            else:
                col1, col2, col3 = st.columns(3)
                if col1.button(t("mark_triaged"), key=f"triage_{bug_id}"):
                    st.write(_post(f"/product/feedback/{bug_id}/status", params={"status": "triaged"}))
                    st.rerun()
                if col2.button(t("mark_fixed"), key=f"fixed_{bug_id}"):
                    st.write(_post(f"/product/feedback/{bug_id}/status", params={"status": "fixed"}))
                    st.rerun()
                if col3.button(t("ignore"), key=f"ignore_{bug_id}"):
                    st.write(_post(f"/product/feedback/{bug_id}/status", params={"status": "ignored"}))
                    st.rerun()

            # --- Raw Bug Data ---
            with st.expander(t("raw_bug_data")):
                st.json(bug)


def render_live_data() -> None:
    """Live Data Closed-Loop: 数据源诊断、实时行情、因子、回测、信号。"""
    st.subheader(t("live_data"))
    st.caption(t("live_data_caption"))

    # ── Provider Diagnosis ───────────────────────────────────────
    with st.expander(t("provider_diagnosis"), expanded=False):
        if st.button(t("run_diagnosis"), key="live_diagnose_btn"):
            diag = _post("/product/live-data/diagnose")
            if diag:
                for cap_name, cap_result in diag.get("results", {}).items():
                    st.markdown(f"**{cap_name}**")
                    st.json(cap_result)
            else:
                _banner("danger", t("diagnosis_failed"))

    # ── Provider Status ──────────────────────────────────────────
    providers = _get("/product/live-data/providers")
    if providers:
        st.markdown(f"**{t('provider_status')}**")
        rows = []
        for cap_name, prov_dict in providers.get("realtime_quotes", {}).items():
            rows.append({"Capability": "realtime", t("provider"): cap_name, t("status"): prov_dict.get("status", "unknown"), t("latency_ms"): prov_dict.get("latency_ms", 0)})
        for cap_name, prov_dict in providers.get("daily_bars", {}).items():
            rows.append({"Capability": "daily_bars", t("provider"): cap_name, t("status"): prov_dict.get("status", "unknown"), t("latency_ms"): prov_dict.get("latency_ms", 0)})
        for cap_name, prov_dict in providers.get("fundamentals", {}).items():
            rows.append({"Capability": "fundamentals", t("provider"): cap_name, t("status"): prov_dict.get("status", "unknown"), t("latency_ms"): prov_dict.get("latency_ms", 0)})
        st.dataframe(_df(rows), hide_index=True)

    # ── Realtime Quotes ──────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"**{t('realtime_quotes_title')}**")
    live_symbols = st.text_input(t("symbols"), "600000.SH,000001.SZ", key="live_symbols")
    if st.button(t("fetch_live_quotes"), key="live_quotes_btn"):
        result = _get("/product/live-data/quotes", params={"symbols": live_symbols})
        if result:
            data_status = result.get("data_status", "UNKNOWN")
            if data_status == "FAILED":
                _banner("danger", f"{t('realtime_failed_blocked')} Provider: {result.get('chosen_provider', '')}.")
            elif data_status == "WARN":
                _banner("warn", f"{t('realtime_partial')} Provider: {result.get('chosen_provider', '')}.")
            else:
                _banner("safe", f"{t('realtime_ok')} Provider: {result.get('chosen_provider', '')}.")
            rows = []
            for q in result.get("quotes", []):
                rows.append({
                    "Symbol": q.get("symbol"),
                    "Name": q.get("name", ""),
                    "Last": q.get("last_price", 0),
                    "Change": _format_pct(q.get("pct_change")),
                    "Volume": q.get("volume", 0),
                    t("provider"): result.get("chosen_provider", ""),
                })
            st.dataframe(_df(rows), hide_index=True)
            with st.expander(t("live_data")):
                st.json(result.get("data_delay_report", {}))
        else:
            _banner("danger", t("failed_to_build"))

    # ── Live Signal Draft ────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"**{t('signal_draft')}**")
    signal_symbols = st.text_input(t("symbols"), "600000.SH,000001.SZ", key="live_signal_symbols")
    signal_start = st.text_input(t("start_date"), "20250101", key="live_signal_start")
    signal_end = st.text_input(t("end_date"), "20251231", key="live_signal_end")
    signal_mode = st.selectbox(t("trading_mode"), ["LEVEL_1_SIGNAL_ONLY", "LEVEL_2_HUMAN_CONFIRM"], index=0, key="live_signal_mode")
    if st.button(t("generate_signal_draft"), type="primary", key="live_signal_btn"):
        result = _post(
            "/product/signal/draft",
            params={
                "symbols": signal_symbols,
                "start_date": signal_start,
                "end_date": signal_end,
                "trading_mode": signal_mode,
            },
        )
        if result:
            status = result.get("status", "unknown")
            if status == "blocked":
                _banner("danger", f"{t('signal_blocked')} Data health: {result.get('evidence', {}).get('data_health', {}).get('data_status', 'UNKNOWN')}")
            else:
                _banner("safe", f"{t('signal_draft_info')}: {result.get('signal_type', 'hold')} (confidence: {result.get('confidence', 0):.4f})")
            with st.expander(t("signal_draft_info")):
                st.json(result)
        else:
            _banner("danger", t("failed_to_build"))

    # ── Research Context ─────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"**{t('research_context')}**")
    if st.button(t("build_research_context"), key="live_research_btn"):
        result = _post(
            "/product/live-data/research-context",
            params={"symbols": live_symbols, "start_date": "20250101", "end_date": "20251231"},
        )
        if result:
            health = result.get("health", {})
            if health.get("data_status") == "FAILED":
                _banner("danger", f"{t('data_health_failed')} allow_signal={health.get('allow_signal')}")
            elif health.get("data_status") == "WARN":
                _banner("warn", f"{t('data_health_warn')} allow_signal={health.get('allow_signal')}")
            else:
                _banner("safe", f"{t('data_health_ok')} allow_signal={health.get('allow_signal')}")
            with st.expander(t("data_health")):
                st.json(result)
        else:
            _banner("danger", t("failed_to_build"))


def main() -> None:
    st.set_page_config(page_title=t("page_title"), layout="wide", initial_sidebar_state="expanded")
    st.markdown(PAGE_CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.title(t("sidebar_title"))
        st.caption(t("sidebar_caption"))
        st.session_state["api_base"] = st.text_input(t("sidebar_api_label"), st.session_state.get("api_base", DEFAULT_API_BASE), key="sidebar_api_base")
        lang = st.selectbox(t("language"), ["中文", "English"], index=0 if st.session_state.get("ui_language", "zh") == "zh" else 1, key="sidebar_lang_selector")
        st.session_state["ui_language"] = "zh" if lang == "中文" else "en"
        st.divider()
        st.caption(t("safety_invariant"))

    st.title(t("app_title"))
    st.caption(t("app_subtitle"))

    tabs = st.tabs(
        [
            t("tab_system"),
            t("tab_live_data"),
            t("tab_realtime_market"),
            t("tab_watchlist"),
            t("tab_factor_lab"),
            t("tab_backtest"),
            t("tab_signals"),
            t("tab_human_confirmation"),
            t("tab_configuration"),
            t("tab_feedback"),
        ]
    )

    with tabs[0]:
        render_system()
    with tabs[1]:
        render_live_data()
    with tabs[2]:
        render_market()
    with tabs[3]:
        render_watchlist()
    with tabs[4]:
        render_factor_lab()
    with tabs[5]:
        render_backtest()
    with tabs[6]:
        render_signals()
    with tabs[7]:
        render_human_confirmation()
    with tabs[8]:
        render_configuration()
    with tabs[9]:
        render_feedback()


if __name__ == "__main__":
    main()
