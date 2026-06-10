"""Integrated Streamlit product dashboard for the Quant Trading Agent demo."""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests
import streamlit as st

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


def _banner(kind: str, text: str) -> None:
    css = {"safe": "safe-banner", "warn": "warn-banner", "danger": "danger-banner"}[kind]
    st.markdown(f'<div class="{css}">{text}</div>', unsafe_allow_html=True)


def render_system() -> None:
    st.subheader("System")
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
        _card("API", health.get("api_status", "unknown"), health.get("timestamp", ""))
    with col2:
        _card("Data provider", health.get("data_source", "unknown"), "demo fallback is explicit")
    with col3:
        _card("Risk", health.get("risk_status", "UNKNOWN"), "Risk Agent keeps veto power")
    with col4:
        _card("Trading mode", health.get("trading_mode", "UNKNOWN"), "LEVEL_3 is not exposed")

    if dashboard:
        account = dashboard.get("account", {})
        st.markdown("### Paper Account")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total assets", f"{account.get('total_assets', 0):,.0f}")
        c2.metric("Cash", f"{account.get('cash', 0):,.0f}")
        c3.metric("Market value", f"{account.get('market_value', 0):,.0f}")
        c4.metric("Daily PnL", f"{account.get('daily_pnl', 0):,.0f}", f"{account.get('daily_pnl_pct', 0):.2%}")


def render_market() -> None:
    st.subheader("Realtime Market")
    st.caption("Fetch live snapshots from AkShare or AkTools. Demo fallback is clearly labeled.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        symbols = st.text_input("Symbols", "002463.SZ,600584.SH,603228.SH", help="Comma-separated A-share or HK symbols.", key="market_symbols")
    with col2:
        provider = st.selectbox("Data provider", ["akshare", "aktools"], index=0, key="market_provider")
    with col3:
        force_live = st.checkbox("Force realtime fetch", value=False, key="market_force_live")

    allow_demo = st.checkbox("Allow demo fallback", value=True, key="market_allow_demo")
    col4, col5 = st.columns(2)
    refresh = col4.button("Refresh quotes", type="primary", width="stretch")
    start_job = col5.button("Start background snapshot", width="stretch")

    params = {
        "symbols": symbols,
        "provider": provider,
        "allow_demo": str(allow_demo).lower(),
        "force_live": str(force_live or refresh).lower(),
    }
    if start_job:
        job_result = _post("/product/jobs/quote_refresh/start", params=params)
        if job_result and job_result.get("status") == "ok":
            st.success(f"quote_refresh started: {job_result.get('job_id')}")
        else:
            _banner("danger", f"quote_refresh failed to start: {job_result}")

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
        _banner("danger", "Unable to fetch quote data.")
        return

    status = result.get("status", "unknown")
    if result.get("is_demo"):
        _banner("warn", f"Showing demo data. Status: {status}. {' '.join(result.get('messages', []))}")
    else:
        _banner("safe", f"Showing realtime data from {result.get('provider')}. Updated at {result.get('timestamp')}.")

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


def render_watchlist() -> None:
    st.subheader("Watchlist")
    dashboard = _get("/product/dashboard")
    if not dashboard:
        _banner("danger", "Dashboard data is unavailable.")
        return

    if dashboard.get("trading_mode") == "LEVEL_1_SIGNAL_ONLY":
        _banner("safe", "LEVEL_1 signal-only mode: watchlist alerts cannot create orders.")

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
        _banner("danger", "Risk blocked: " + " / ".join(risk.get("messages", [])))


def render_factor_lab() -> None:
    st.subheader("Factor Lab")
    dashboard = _get("/product/dashboard") or {}
    watchlist = dashboard.get("watchlist", [])
    options = [item.get("symbol", "") for item in watchlist] or ["002463.SZ", "600584.SH"]
    selected = st.multiselect("Symbols", options, default=options[:5], key="factor_symbols")
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start date", value=None, key="factor_start_date")
    end_date = col2.date_input("End date", value=None, key="factor_end_date")

    params = {"symbols": ",".join(selected)}
    if start_date:
        params["start_date"] = start_date.strftime("%Y%m%d")
    if end_date:
        params["end_date"] = end_date.strftime("%Y%m%d")

    if st.button("Compute factors", type="primary", key="compute_factors_btn"):
        result = _post("/product/factors/compute", params=params)
    else:
        result = {"factors": dashboard.get("factors", []), "warnings": []}

    for warning in result.get("warnings", []):
        _banner("warn", warning)

    rows = []
    for factor in result.get("factors", []):
        rows.append(
            {
                "Symbol": factor.get("symbol"),
                "Name": factor.get("name"),
                "Sector": factor.get("sector"),
                "Technical": factor.get("technical_score"),
                "Fundamental": factor.get("fundamental_score"),
                "Sentiment": factor.get("sentiment_score"),
                "Theme": factor.get("policy_score"),
                "Total": factor.get("total_score"),
            }
        )
    st.dataframe(_df(rows), width="stretch", hide_index=True)


def render_backtest() -> None:
    st.subheader("Backtest")
    col1, col2, col3 = st.columns(3)
    symbols = col1.text_input("Symbols", "002463.SZ,600584.SH", key="backtest_symbols")
    start_date = col2.text_input("Start date", "20250101", key="backtest_start_date")
    end_date = col3.text_input("End date", "20251231", key="backtest_end_date")

    col4, col5, col6, col7 = st.columns(4)
    capital = col4.number_input("Initial capital", min_value=10000.0, value=1000000.0, step=10000.0, key="backtest_capital")
    commission = col5.number_input("Commission", min_value=0.0, value=0.0003, format="%.4f", key="backtest_commission")
    stamp = col6.number_input("Stamp duty", min_value=0.0, value=0.0010, format="%.4f", key="backtest_stamp")
    slippage = col7.number_input("Slippage", min_value=0.0, value=0.0010, format="%.4f", key="backtest_slippage")

    if commission == 0 or stamp == 0 or slippage == 0:
        _banner("warn", "Backtest policy requires commission, stamp duty, and slippage.")

    if st.button("Run backtest", type="primary", key="run_backtest_btn"):
        result = _post(
            "/product/jobs/backtest/start",
            params={
                "symbols": symbols,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": capital,
                "commission_rate": commission,
                "stamp_duty_rate": stamp,
                "slippage": slippage,
            },
        )
        if result:
            st.success(f"Backtest job created: {result.get('job_id')}")
            perf = result.get("performance", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Annual return", f"{perf.get('annual_return', 0):.2%}")
            c2.metric("Max drawdown", f"{perf.get('max_drawdown', 0):.2%}")
            c3.metric("Sharpe", f"{perf.get('sharpe_ratio', 0):.2f}")
            c4.metric("Win rate", f"{perf.get('win_rate', 0):.2%}")
            st.dataframe(_df(result.get("trades", [])), width="stretch", hide_index=True)


def render_signals() -> None:
    st.subheader("Signals")
    dashboard = _get("/product/dashboard")
    if not dashboard:
        _banner("danger", "Signal data is unavailable.")
        return

    rows = []
    for signal in dashboard.get("signals", []):
        rows.append(
            {
                "Signal": signal.get("signal_type"),
                "Symbol": signal.get("symbol"),
                "Name": signal.get("stock_name"),
                "Score": signal.get("score"),
                "Trigger": signal.get("price_trigger"),
                "Stop": signal.get("stop_loss_price"),
                "Take profit": signal.get("take_profit_price"),
                "Reason": signal.get("reason"),
                "Risk note": signal.get("risk_note"),
            }
        )
    st.dataframe(_df(rows), width="stretch", hide_index=True)


def render_human_confirmation() -> None:
    st.subheader("Human Confirmation")
    _banner("warn", "Buy orders require per-order confirmation. Batch buy confirmation is forbidden.")
    pending = _get("/orders/pending") or {"orders": []}
    orders = pending.get("orders", [])

    if not orders:
        st.info("No pending orders.")
        return

    for order in orders:
        title = f"{order.get('side')} {order.get('stock_name', '')} {order.get('symbol')} x{order.get('quantity')} @ {order.get('limit_price')}"
        with st.expander(title):
            st.json(order)
            col1, col2, col3 = st.columns(3)
            if col1.button("Confirm this order", key=f"confirm_{order.get('order_id')}", type="primary"):
                st.write(_post(f"/orders/{order.get('order_id')}/confirm"))
                st.rerun()
            if col2.button("Reject", key=f"reject_{order.get('order_id')}"):
                st.write(_post(f"/orders/{order.get('order_id')}/reject"))
                st.rerun()
            if col3.button("Cancel", key=f"cancel_{order.get('order_id')}"):
                st.write(_post(f"/orders/{order.get('order_id')}/cancel"))
                st.rerun()


def render_configuration() -> None:
    st.subheader("Configuration")
    config_data = _get("/product/config")
    if not config_data:
        _banner("danger", "Configuration API is unavailable.")
        return

    validation = config_data.get("validation", {})
    for error in validation.get("errors", []):
        _banner("danger", error)
    for warning in validation.get("warnings", []):
        _banner("warn", warning)

    config = config_data.get("config", {})
    provider = st.selectbox(
        "Data provider",
        ["akshare", "aktools"],
        index=0 if config.get("DEFAULT_DATA_PROVIDER", "akshare") == "akshare" else 1,
        key="config_provider",
    )
    log_level = st.selectbox("Log level", ["DEBUG", "INFO", "WARNING", "ERROR"], index=1, key="config_log_level")
    max_single = st.slider("Max single stock position", 0.01, 0.50, float(config.get("MAX_SINGLE_STOCK_POSITION", 0.15)), 0.01, key="config_max_single")
    max_sector = st.slider("Max sector position", 0.10, 1.00, float(config.get("MAX_SECTOR_POSITION", 0.60)), 0.05, key="config_max_sector")
    min_cash = st.slider("Minimum cash ratio", 0.0, 0.50, float(config.get("MIN_CASH_RATIO", 0.20)), 0.05, key="config_min_cash")

    mode = st.selectbox(
        "Trading mode",
        ["LEVEL_0", "LEVEL_1_SIGNAL_ONLY", "LEVEL_2_HUMAN_CONFIRM", "LEVEL_3_AUTO"],
        index=1,
        key="config_trading_mode",
    )
    if mode == "LEVEL_3_AUTO":
        _banner("danger", "LEVEL_3_AUTO is blocked in Demo V1.")
    elif mode == "LEVEL_2_HUMAN_CONFIRM":
        _banner("warn", "LEVEL_2 requires explicit confirmation and keeps BROKER_ADAPTER=paper.")

    if st.button("Save safe configuration", type="primary", key="save_config_btn"):
        updates = {
            "DEFAULT_DATA_PROVIDER": provider,
            "LOG_LEVEL": log_level,
            "MAX_SINGLE_STOCK_POSITION": str(max_single),
            "MAX_SECTOR_POSITION": str(max_sector),
            "MIN_CASH_RATIO": str(min_cash),
        }
        results = [_post("/product/config", params={"key": key, "value": value}) for key, value in updates.items()]
        if all(result and result.get("success") for result in results):
            st.success("Configuration saved.")
        else:
            st.error("Some configuration updates failed.")

    if st.button("Restore safe defaults", key="restore_defaults_btn"):
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
    with st.expander("🔍 Analysis Report", expanded=False):
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
    with st.expander("🔧 Fix Proposal", expanded=False):
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
    st.subheader("Feedback")
    data = _get("/product/feedback")
    if not data:
        _banner("danger", "Feedback API is unavailable.")
        return

    _card("Open bugs", str(data.get("count", 0)), data.get("export_path", "feedback/bugs/open"))
    bugs = data.get("bugs", [])
    if not bugs:
        st.info("No open bug reports.")
        return

    for bug in bugs:
        bug_id = bug.get("bug_id")
        bug_status = (bug.get("status") or "open").lower()
        severity = bug.get("severity", "").upper()
        title = bug.get("title", "")

        with st.expander(f"{severity} {bug_id}: {title}"):
            # --- Bug Status Step Indicator ---
            st.markdown("**Workflow Status**")
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
                    if st.button("✅ Approve", key=f"approve_{bug_id}", type="primary"):
                        result = _post(f"/product/feedback/{bug_id}/approve", params={"comment": "Approved via dashboard"})
                        if result:
                            st.success("Bug fix approved!")
                            st.rerun()
                        else:
                            st.error("Failed to approve bug fix.")
                with reject_col:
                    if st.button("❌ Reject", key=f"reject_{bug_id}"):
                        result = _post(f"/product/feedback/{bug_id}/reject", params={"comment": "Rejected via dashboard"})
                        if result:
                            st.warning("Bug fix rejected.")
                            st.rerun()
                        else:
                            st.error("Failed to reject bug fix.")
            else:
                col1, col2, col3 = st.columns(3)
                if col1.button("Mark triaged", key=f"triage_{bug_id}"):
                    st.write(_post(f"/product/feedback/{bug_id}/status", params={"status": "triaged"}))
                    st.rerun()
                if col2.button("Mark fixed", key=f"fixed_{bug_id}"):
                    st.write(_post(f"/product/feedback/{bug_id}/status", params={"status": "fixed"}))
                    st.rerun()
                if col3.button("Ignore", key=f"ignore_{bug_id}"):
                    st.write(_post(f"/product/feedback/{bug_id}/status", params={"status": "ignored"}))
                    st.rerun()

            # --- Raw Bug Data ---
            with st.expander("Raw Bug Data"):
                st.json(bug)


def main() -> None:
    st.set_page_config(page_title="QuantAgent Product Demo", layout="wide", initial_sidebar_state="expanded")
    st.markdown(PAGE_CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.title("QuantAgent")
        st.caption("Product demo cockpit")
        st.session_state["api_base"] = st.text_input("API base URL", st.session_state.get("api_base", DEFAULT_API_BASE), key="sidebar_api_base")
        st.divider()
        st.caption("Safety invariant: live automatic trading is not exposed in this demo.")

    st.title("Quant Trading Agent")
    st.caption("Integrated entry for market data, watchlist, factors, backtests, signals, human confirmation, configuration, and feedback.")

    tabs = st.tabs(
        [
            "System",
            "Realtime Market",
            "Watchlist",
            "Factor Lab",
            "Backtest",
            "Signals",
            "Human Confirmation",
            "Configuration",
            "Feedback",
        ]
    )

    with tabs[0]:
        render_system()
    with tabs[1]:
        render_market()
    with tabs[2]:
        render_watchlist()
    with tabs[3]:
        render_factor_lab()
    with tabs[4]:
        render_backtest()
    with tabs[5]:
        render_signals()
    with tabs[6]:
        render_human_confirmation()
    with tabs[7]:
        render_configuration()
    with tabs[8]:
        render_feedback()


if __name__ == "__main__":
    main()
