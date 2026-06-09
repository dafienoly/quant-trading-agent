"""量化交易盯盘面板

Streamlit 前端，提供实时盯盘、信号列表、风控状态监控。
核心约束：只读展示，不提供任何下单操作。
"""
import streamlit as st

from src.config.settings import ENABLE_LIVE_TRADING, MAX_TRADING_LEVEL
from src.risk_engine.models import KillSwitchState
from src.risk_engine.runtime import RuntimeRiskEngine


def render_risk_status(risk_engine: RuntimeRiskEngine):
    """渲染风控状态面板"""
    st.subheader("风控状态")

    decision = risk_engine.check_realtime_snapshot(quotes=[])

    col1, col2, col3 = st.columns(3)
    with col1:
        status_color = "green" if decision.risk_pass else "red"
        st.markdown(f"**风控状态:** :{status_color}[{'通过' if decision.risk_pass else '阻断'}]")
    with col2:
        st.markdown(f"**交易模式:** {decision.trading_mode}")
    with col3:
        st.markdown(f"**实盘交易:** {'启用' if ENABLE_LIVE_TRADING else '禁用'}")

    if decision.messages:
        st.warning(" / ".join(decision.messages))

    if risk_engine.kill_switch.active:
        st.error(f"Kill Switch 已激活: {risk_engine.kill_switch.reason}")


def render_signal_panel(signals: list[dict]):
    """渲染信号列表"""
    st.subheader("最新信号")

    if not signals:
        st.info("暂无信号")
        return

    for sig in signals:
        signal_type = sig.get("signal_type", "UNKNOWN")
        symbol = sig.get("symbol", "")
        reason = sig.get("reason", "")

        if "BUY" in signal_type:
            st.success(f"**{signal_type}** {symbol} — {reason}")
        elif "SELL" in signal_type:
            st.error(f"**{signal_type}** {symbol} — {reason}")
        else:
            st.info(f"**{signal_type}** {symbol} — {reason}")


def render_watchlist(watchlist_data: list[dict] | None = None):
    """渲染候选股列表"""
    st.subheader("候选股监控")

    if not watchlist_data:
        st.info("暂无候选股数据")
        return

    for item in watchlist_data:
        symbol = item.get("symbol", "")
        name = item.get("name", "")
        total_score = item.get("total_score", 0)
        st.metric(label=f"{name} ({symbol})", value=f"{total_score:.1f}分")


def _fetch_signals_from_api() -> list[dict]:
    """从 API 获取最新信号数据"""
    try:
        import requests
        resp = requests.get("http://localhost:8000/signals/latest", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("signals", [])
    except Exception:
        pass
    return []


def main():
    st.set_page_config(page_title="量化交易盯盘", layout="wide")
    st.title("量化交易盯盘面板")

    st.sidebar.header("系统信息")
    st.sidebar.markdown(f"- 交易模式: `{MAX_TRADING_LEVEL}`")
    st.sidebar.markdown(f"- 实盘交易: `{'启用' if ENABLE_LIVE_TRADING else '禁用'}`")
    st.sidebar.markdown(f"- 下单功能: `不可用`")

    risk_engine = RuntimeRiskEngine()

    tab1, tab2, tab3 = st.tabs(["风控状态", "信号列表", "候选股"])

    with tab1:
        render_risk_status(risk_engine)

    with tab2:
        signals = _fetch_signals_from_api()
        render_signal_panel(signals)

    with tab3:
        render_watchlist()


if __name__ == "__main__":
    main()
