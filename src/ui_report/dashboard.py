"""量化交易盯盘面板

Streamlit 前端，提供实时盯盘、信号列表、风控状态监控和订单确认。
Phase 5 新增：订单确认页面 (EXECUTION_POLICY 5)
"""
import streamlit as st

from src.config.settings import ENABLE_LIVE_TRADING, MAX_TRADING_LEVEL
from src.risk_engine.models import KillSwitchState
from src.risk_engine.runtime import RuntimeRiskEngine


def render_risk_status(risk_engine: RuntimeRiskEngine):
    """渲染风控状态面板"""
    st.subheader("风控状态")

    kill_switch_active = risk_engine.kill_switch.active

    col1, col2, col3 = st.columns(3)
    with col1:
        status_color = "green" if not kill_switch_active else "red"
        status_text = "风控正常" if not kill_switch_active else "Kill Switch 已激活"
        st.markdown(f"**风控状态:** :{status_color}[{status_text}]")
    with col2:
        st.markdown(f"**交易模式:** {risk_engine.kill_switch.reason or '正常'}")
    with col3:
        st.markdown(f"**实盘交易:** {'启用' if ENABLE_LIVE_TRADING else '禁用'}")

    if kill_switch_active:
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


def render_order_confirmation():
    """渲染订单确认面板 (EXECUTION_POLICY 5)

    禁止提供「全部确认」「一键确认」功能，必须逐笔操作。
    """
    st.subheader("待确认订单")

    try:
        import requests
        resp = requests.get("http://localhost:8000/orders/pending", timeout=5)
        if resp.status_code != 200:
            st.info("无法连接交易服务")
            return
        data = resp.json()
    except Exception:
        st.info("无法连接交易服务")
        return

    orders = data.get("orders", [])
    if not orders:
        st.info("暂无待确认订单")
        return

    for order in orders:
        order_id = order.get("order_id", "")
        symbol = order.get("symbol", "")
        side = order.get("side", "")
        limit_price = order.get("limit_price", 0)
        quantity = order.get("quantity", 0)
        stock_name = order.get("stock_name", "")
        strategy = order.get("strategy_name", "")
        stop_loss = order.get("stop_loss_price", 0)
        take_profit = order.get("take_profit_price", 0)
        risk_note = order.get("risk_note", "")

        amount = limit_price * quantity

        with st.expander(f"{'买入' if side == 'BUY' else '卖出'} {stock_name}({symbol}) x{quantity}@{limit_price:.2f} = {amount:,.0f}元"):
            col_info, col_action = st.columns([2, 1])

            with col_info:
                st.markdown(f"**订单ID:** {order_id}")
                st.markdown(f"**方向:** {'买入' if side == 'BUY' else '卖出'}")
                st.markdown(f"**价格:** {limit_price:.2f}")
                st.markdown(f"**数量:** {quantity}")
                st.markdown(f"**金额:** {amount:,.0f}元")
                st.markdown(f"**策略:** {strategy}")
                if stop_loss > 0:
                    st.markdown(f"**止损位:** {stop_loss:.2f}")
                if take_profit > 0:
                    st.markdown(f"**止盈位:** {take_profit:.2f}")
                if risk_note:
                    st.warning(f"**风险提示:** {risk_note}")

            with col_action:
                # 逐笔确认 (EXECUTION_POLICY 5: 禁止一键确认)
                if st.button("确认", key=f"confirm_{order_id}"):
                    try:
                        r = requests.post(f"http://localhost:8000/orders/{order_id}/confirm", timeout=5)
                        if r.status_code == 200 and r.json().get("status") == "ok":
                            st.success("订单已确认并执行")
                            st.rerun()
                        else:
                            st.error(f"确认失败: {r.json().get('message', '未知错误')}")
                    except Exception as e:
                        st.error(f"确认失败: {e}")

                if st.button("拒绝", key=f"reject_{order_id}"):
                    try:
                        r = requests.post(f"http://localhost:8000/orders/{order_id}/reject", timeout=5)
                        if r.status_code == 200 and r.json().get("status") == "ok":
                            st.success("订单已拒绝")
                            st.rerun()
                        else:
                            st.error(f"拒绝失败: {r.json().get('message', '未知错误')}")
                    except Exception as e:
                        st.error(f"拒绝失败: {e}")


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


def main() -> None:
    """主入口 — 重定向到产品仪表板"""
    from src.ui_report.product_dashboard import main as product_main
    product_main()


if __name__ == "__main__":
    main()
