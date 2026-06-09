"""量化交易产品仪表板

一体化产品入口，9 个标签页覆盖全部产品功能。
连接 FastAPI 后端 (http://localhost:8000)，支持 Demo 数据回退。

运行方式:
    python -m streamlit run src/ui_report/product_dashboard.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

API_BASE = "http://localhost:8000"
API_TIMEOUT = 5

# ============================================================
# 通用工具函数
# ============================================================

def _api_get(path: str, params: dict | None = None) -> dict | None:
    """GET 请求封装，失败返回 None"""
    import requests
    try:
        resp = requests.get(f"{API_BASE}{path}", params=params, timeout=API_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _api_post(path: str, params: dict | None = None) -> dict | None:
    """POST 请求封装，失败返回 None"""
    import requests
    try:
        resp = requests.post(f"{API_BASE}{path}", params=params, timeout=API_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _report_error(component: str, message: str) -> None:
    """向反馈系统报告错误"""
    try:
        import requests
        requests.post(f"{API_BASE}/product/feedback", json={
            "component": component,
            "message": message,
        }, timeout=2)
    except Exception:
        pass


def _pct_fmt(val: float) -> str:
    """格式化涨跌幅"""
    if val is None:
        return "-"
    if val > 0:
        return f"+{val:.2f}%"
    return f"{val:.2f}%"


def _pct_color(val: float) -> str:
    """涨跌幅颜色"""
    if val is None:
        return "gray"
    if val > 0:
        return "red"
    if val < 0:
        return "green"
    return "gray"


# ============================================================
# 1. 系统状态 (Home)
# ============================================================

def render_home() -> None:
    """渲染系统状态首页"""
    health = _api_get("/product/health")
    dashboard = _api_get("/product/dashboard")

    if health is None and dashboard is None:
        st.error("⚠️ 无法连接后端 API，请确认 FastAPI 服务已启动 (http://localhost:8000)")
        st.code("python -m uvicorn src.api.app:create_app --factory --port 8000")
        return

    # --- 顶部状态栏 ---
    col1, col2, col3, col4 = st.columns(4)

    api_ok = health is not None
    with col1:
        status_icon = "🟢" if api_ok else "🔴"
        status_text = "在线" if api_ok else "离线"
        st.metric("API 状态", f"{status_icon} {status_text}")

    with col2:
        if health:
            ds = health.get("data_source", "unknown")
            ds_icon = "📊" if ds == "akshare" else "🧪"
            st.metric("数据源", f"{ds_icon} {ds}")
        else:
            st.metric("数据源", "❓ 未知")

    with col3:
        if health:
            risk_ok = health.get("risk_status", "UNKNOWN")
            risk_icon = "🟢" if risk_ok == "OK" else "🔴"
            st.metric("风控状态", f"{risk_icon} {risk_ok}")
        else:
            st.metric("风控状态", "❓ 未知")

    with col4:
        if health:
            mode = health.get("trading_mode", "UNKNOWN")
            st.metric("交易模式", mode)
        else:
            st.metric("交易模式", "❓ 未知")

    st.divider()

    # --- 第二行状态 ---
    col5, col6, col7 = st.columns(3)

    with col5:
        if health:
            is_live = health.get("is_live", False)
            mode_label = "🔴 实盘" if is_live else "🧪 模拟"
            st.metric("交易环境", mode_label)
        else:
            st.metric("交易环境", "❓ 未知")

    with col6:
        if health:
            is_demo = health.get("is_demo", True)
            demo_label = "🧪 Demo 模式" if is_demo else "📊 实时数据"
            st.metric("数据模式", demo_label)
        else:
            st.metric("数据模式", "❓ 未知")

    with col7:
        if health:
            backlog = health.get("feedback_backlog", 0)
            st.metric("反馈积压", f"{backlog} 条")
        else:
            st.metric("反馈积压", "❓ 未知")

    # --- Kill Switch 警告 ---
    if health and health.get("kill_switch_active"):
        st.error(f"🚨 Kill Switch 已激活: {health.get('kill_switch_reason', '未知原因')}")

    # --- 市场休市提示 ---
    if health and health.get("is_demo"):
        st.info("🕐 当前为非交易时段或 Demo 模式，显示的是确定性演示数据")

    # --- 账户概览 ---
    if dashboard and dashboard.get("account"):
        st.subheader("账户概览")
        acct = dashboard["account"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总资产", f"{acct.get('total_assets', 0):,.0f}")
        c2.metric("可用现金", f"{acct.get('cash', 0):,.0f}")
        c3.metric("持仓市值", f"{acct.get('market_value', 0):,.0f}")
        daily_pnl = acct.get("daily_pnl", 0)
        c4.metric("当日盈亏", f"{daily_pnl:,.0f}", delta=f"{acct.get('daily_pnl_pct', 0):.2%}")


# ============================================================
# 2. 实时行情 (Market)
# ============================================================

def render_market() -> None:
    """渲染实时行情"""
    dashboard = _api_get("/product/dashboard")

    # --- 控制栏 ---
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 1])

    with ctrl_col1:
        search = st.text_input("🔍 股票代码/名称搜索", key="market_search")

    with ctrl_col2:
        refresh_interval = st.slider("自动刷新间隔（秒）", 5, 60, 30, key="refresh_interval")

    with ctrl_col3:
        if st.button("🔄 手动刷新", key="market_refresh"):
            st.rerun()

    # --- 数据源和状态标签 ---
    if dashboard:
        is_demo = dashboard.get("is_demo", True)
        ds = dashboard.get("data_source", "unknown")
        badge = "🧪 Demo 数据" if is_demo else f"📊 {ds}"

        col_badge, col_delay = st.columns(2)
        with col_badge:
            st.markdown(f"**数据源:** {badge}")
        with col_delay:
            ts = dashboard.get("timestamp", "")
            st.markdown(f"**更新时间:** {ts}")

    # --- 行情表格 ---
    if dashboard and dashboard.get("quotes"):
        quotes = dashboard["quotes"]

        # 搜索过滤
        if search:
            search_lower = search.lower()
            quotes = [
                q for q in quotes
                if search_lower in q.get("symbol", "").lower()
                or search_lower in str(q.get("name", "")).lower()
            ]

        if quotes:
            rows = []
            for q in quotes:
                pct = q.get("pct_change")
                rows.append({
                    "代码": q.get("symbol", ""),
                    "名称": _get_stock_name(q.get("symbol", "")),
                    "最新价": q.get("last_price", 0),
                    "涨跌幅(%)": pct if pct is not None else 0,
                    "成交量": q.get("volume", 0),
                    "成交额": q.get("amount", 0),
                    "状态": q.get("status", "UNKNOWN"),
                })

            df = pd.DataFrame(rows)

            # 涨跌幅着色
            def _color_pct(val):
                if val is None:
                    return "color: gray"
                if val > 0:
                    return "color: red"
                if val < 0:
                    return "color: green"
                return "color: gray"

            styled = df.style.map(_color_pct, subset=["涨跌幅(%)"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info("未找到匹配的股票")
    else:
        st.warning("暂无行情数据，请确认后端服务已启动")

    # --- 自动刷新 ---
    if refresh_interval:
        import time
        st.empty()  # placeholder for auto-refresh
        st.markdown(f"<small>自动刷新间隔: {refresh_interval}s（需手动刷新页面）</small>", unsafe_allow_html=True)


def _get_stock_name(symbol: str) -> str:
    """根据代码获取股票名称"""
    from src.product_app.demo_data import DEMO_STOCKS
    for s in DEMO_STOCKS:
        if s["symbol"] == symbol:
            return s["name"]
    return symbol


# ============================================================
# 3. 候选股监控 (Watchlist)
# ============================================================

def render_watchlist() -> None:
    """渲染候选股监控"""
    dashboard = _api_get("/product/dashboard")

    if not dashboard:
        st.warning("无法获取数据")
        return

    watchlist = dashboard.get("watchlist", [])
    if not watchlist:
        st.info("暂无候选股数据")
        return

    # 交易模式提示
    trading_mode = dashboard.get("trading_mode", "")
    if trading_mode == "LEVEL_1_SIGNAL_ONLY":
        st.info("📋 当前为 LEVEL_1_SIGNAL_ONLY 模式，仅生成信号，不会产生任何订单")

    # 候选股表格
    rows = []
    for w in watchlist:
        pct = w.get("pct_change", 0) or 0
        rows.append({
            "代码": w.get("symbol", ""),
            "名称": w.get("name", ""),
            "最新价": w.get("last_price", 0),
            "涨跌幅(%)": pct,
            "板块": _sector_label(w.get("sector", "")),
            "状态": w.get("status", "UNKNOWN"),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 风控阻断提示
    risk = dashboard.get("risk", {})
    if risk and not risk.get("risk_pass", True):
        st.error(f"🚫 风控阻断: {' / '.join(risk.get('messages', []))}")

    # 触发的信号提醒
    signals = dashboard.get("signals", [])
    buy_signals = [s for s in signals if s.get("signal_type") == "BUY"]
    sell_signals = [s for s in signals if s.get("signal_type") == "SELL"]

    if buy_signals:
        st.success(f"📈 {len(buy_signals)} 只股票触发买入信号")
    if sell_signals:
        st.error(f"📉 {len(sell_signals)} 只股票触发卖出信号")


def _sector_label(sector: str) -> str:
    """板块代码转中文标签"""
    labels = {
        "pcb_ccl": "PCB/CCL",
        "advanced_packaging": "先进封装",
        "equipment_material": "设备/材料",
        "optical_module_cpo": "光模块/CPO",
        "memory_hbm": "存储/HBM",
    }
    return labels.get(sector, sector)


# ============================================================
# 4. 因子分析 (Factor Lab)
# ============================================================

def render_factor_lab() -> None:
    """渲染因子分析"""
    dashboard = _api_get("/product/dashboard")

    # --- 选择器 ---
    if dashboard and dashboard.get("watchlist"):
        symbols = [f"{w['symbol']} {w.get('name', '')}" for w in dashboard["watchlist"]]
    else:
        from src.product_app.demo_data import DEMO_STOCKS
        symbols = [f"{s['symbol']} {s['name']}" for s in DEMO_STOCKS]

    selected = st.multiselect("选择股票", symbols, default=symbols[:5], key="factor_symbols")
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date = st.date_input("开始日期", value=None, key="factor_start")
    with date_col2:
        end_date = st.date_input("结束日期", value=None, key="factor_end")

    if st.button("🔬 计算因子评分", key="compute_factors"):
        symbol_codes = [s.split()[0] for s in selected]
        params = {"symbols": ",".join(symbol_codes)}
        if start_date:
            params["start_date"] = start_date.strftime("%Y%m%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y%m%d")

        with st.spinner("正在计算因子评分..."):
            result = _api_post("/product/factors/compute", params=params)

        if result and result.get("factors"):
            factors = result["factors"]
            rows = []
            for f in factors:
                rows.append({
                    "代码": f.get("symbol", ""),
                    "名称": f.get("name", ""),
                    "技术面": f.get("technical_score", 0),
                    "基本面": f.get("fundamental_score", 0),
                    "情绪面": f.get("sentiment_score", 0),
                    "政策面": f.get("policy_score", 0),
                    "综合评分": f.get("total_score", 0),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.success(f"✅ 因子计算完成，共 {len(factors)} 只股票")

            # 因子说明
            st.markdown("#### 因子说明")
            st.markdown("""
- **技术面**: 基于价格趋势、动量、成交量等技术指标的综合评分
- **基本面**: 基于财务指标、估值、盈利能力等的综合评分
- **情绪面**: 基于市场情绪、资金流向等的综合评分
- **政策面**: 基于行业政策、产业趋势等的综合评分
- **综合评分**: 各因子加权汇总，≥82 触发买入，≤58 触发卖出
            """)

            # 警告
            warnings = result.get("warnings", [])
            for w in warnings:
                st.warning(f"⚠️ {w}")
        else:
            st.error("因子计算失败，请检查后端服务")
    else:
        # 显示 Dashboard 中的因子数据
        if dashboard and dashboard.get("factors"):
            factors = dashboard["factors"]
            rows = []
            for f in factors:
                rows.append({
                    "代码": f.get("symbol", ""),
                    "名称": f.get("name", ""),
                    "技术面": f.get("technical_score", 0),
                    "基本面": f.get("fundamental_score", 0),
                    "情绪面": f.get("sentiment_score", 0),
                    "政策面": f.get("policy_score", 0),
                    "综合评分": f.get("total_score", 0),
                })
            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)

        st.warning("⚠️ 因子数据存在幸存者偏差：仅包含当前在池股票")
        st.warning("⚠️ 部分因子可能存在数据缺失，请结合原始数据验证")


# ============================================================
# 5. 回测实验室 (Backtest Lab)
# ============================================================

def render_backtest_lab() -> None:
    """渲染回测实验室"""
    st.markdown("### 回测实验室")

    # --- 参数设置 ---
    col1, col2 = st.columns(2)

    with col1:
        strategy = st.selectbox("策略", [
            "demo_semiconductor_rotation",
            "sector_rotation",
            "momentum_breakout",
        ], key="bt_strategy")

        symbols_input = st.text_input("股票代码（逗号分隔）", "002463,002916,002371", key="bt_symbols")

    with col2:
        bt_start = st.date_input("开始日期", value=None, key="bt_start")
        bt_end = st.date_input("结束日期", value=None, key="bt_end")
        initial_capital = st.number_input("初始资金", min_value=100000, value=1000000, step=100000, key="bt_capital")

    # --- 成本参数 ---
    with st.expander("⚙️ 交易成本参数", expanded=False):
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            commission = st.number_input("手续费率", min_value=0.0, value=0.0003, step=0.0001, format="%.4f", key="bt_commission")
        with cc2:
            stamp_duty = st.number_input("印花税率", min_value=0.0, value=0.001, step=0.0001, format="%.4f", key="bt_stamp")
        with cc3:
            slippage = st.number_input("滑点", min_value=0.0, value=0.001, step=0.0001, format="%.4f", key="bt_slippage")

    # --- 运行回测 ---
    if st.button("🚀 运行回测", key="run_backtest"):
        params = {
            "strategy": strategy,
            "symbols": symbols_input,
            "initial_capital": initial_capital,
            "commission_rate": commission,
            "stamp_duty_rate": stamp_duty,
            "slippage": slippage,
        }
        if bt_start:
            params["start_date"] = bt_start.strftime("%Y%m%d")
        if bt_end:
            params["end_date"] = bt_end.strftime("%Y%m%d")

        with st.spinner("回测运行中..."):
            result = _api_post("/product/jobs/backtest/start", params=params)

        if result:
            st.success(f"✅ 回测完成! Job ID: {result.get('job_id', 'N/A')}")

            # 性能摘要
            perf = result.get("performance", {})
            if perf:
                st.markdown("#### 📊 性能摘要")
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("年化收益", f"{perf.get('annual_return', 0):.1%}")
                p2.metric("最大回撤", f"{perf.get('max_drawdown', 0):.1%}")
                p3.metric("夏普比率", f"{perf.get('sharpe_ratio', 0):.2f}")
                p4.metric("胜率", f"{perf.get('win_rate', 0):.1%}")

            # 成本假设
            costs = result.get("cost_assumptions", {})
            if costs:
                st.markdown("#### 💰 成本假设")
                st.json(costs)

            # 交易列表
            trades = result.get("trades", [])
            if trades:
                st.markdown("#### 📋 交易列表")
                trade_df = pd.DataFrame(trades)
                st.dataframe(trade_df, use_container_width=True, hide_index=True)

            # 警告
            warnings = result.get("warnings", [])
            for w in warnings:
                st.warning(f"⚠️ {w}")

            # 免责声明
            disclaimer = result.get("disclaimer", "")
            if disclaimer:
                st.info(f"ℹ️ {disclaimer}")
        else:
            st.error("回测运行失败，请检查后端服务")

    # --- 无成本假设阻断 ---
    if commission == 0 and stamp_duty == 0 and slippage == 0:
        st.error("🚫 回测必须包含交易成本假设（手续费/印花税/滑点），不含成本的回测结果不可信")


# ============================================================
# 6. 信号中心 (Signal Center)
# ============================================================

def render_signal_center() -> None:
    """渲染信号中心"""
    dashboard = _api_get("/product/dashboard")

    # --- 手动刷新 ---
    if st.button("🔄 刷新信号", key="signal_refresh"):
        refresh_result = _api_post("/signals/refresh")
        if refresh_result:
            st.success("✅ 信号已刷新")
            st.rerun()
        else:
            st.warning("信号刷新失败，可能 SignalService 未配置")
            dashboard = _api_get("/product/dashboard")

    if not dashboard:
        st.warning("无法获取信号数据")
        return

    signals = dashboard.get("signals", [])
    if not signals:
        st.info("暂无信号数据")
        return

    # --- 信号表格 ---
    rows = []
    for s in signals:
        sig_type = s.get("signal_type", "UNKNOWN")
        rows.append({
            "信号ID": s.get("signal_id", ""),
            "代码": s.get("symbol", ""),
            "名称": s.get("stock_name", ""),
            "方向": sig_type,
            "子类型": s.get("sub_type", ""),
            "评分": s.get("score", 0),
            "触发价": s.get("price_trigger", 0),
            "板块": _sector_label(s.get("sector", "")),
            "时间": s.get("created_at", ""),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # --- 信号详情 ---
    st.markdown("#### 信号详情")
    for s in signals:
        sig_type = s.get("signal_type", "UNKNOWN")
        symbol = s.get("symbol", "")
        name = s.get("stock_name", symbol)
        reason = s.get("reason", "")

        if sig_type == "BUY":
            icon = "📈"
            expander_label = f"{icon} 买入 {name}({symbol})"
        elif sig_type == "SELL":
            icon = "📉"
            expander_label = f"{icon} 卖出 {name}({symbol})"
        else:
            icon = "👁️"
            expander_label = f"{icon} 持有 {name}({symbol})"

        with st.expander(expander_label):
            st.markdown(f"**信号解释:** {reason}")
            st.markdown(f"**止损位:** {s.get('stop_loss_price', 0):.2f}")
            st.markdown(f"**止盈位:** {s.get('take_profit_price', 0):.2f}")
            st.markdown(f"**建议仓位:** {s.get('position_pct', 0):.0%}")

            risk_note = s.get("risk_note", "")
            if risk_note:
                st.warning(f"⚠️ 风险提示: {risk_note}")

            # 订单草稿可用性
            trading_mode = dashboard.get("trading_mode", "")
            if trading_mode == "LEVEL_1_SIGNAL_ONLY":
                st.info("📋 当前模式 (LEVEL_1) 不生成订单草稿")
            elif trading_mode == "LEVEL_2_HUMAN_CONFIRM":
                st.info("📝 当前模式 (LEVEL_2) 可生成订单草稿，需人工确认")
            elif trading_mode == "LEVEL_3_AUTO":
                st.info("🤖 当前模式 (LEVEL_3) 可自动生成并执行订单")

    # --- 股票池过滤结果 ---
    risk = dashboard.get("risk", {})
    if risk:
        st.markdown("#### 风控检查结果")
        if risk.get("risk_pass"):
            st.success("✅ 风控检查通过")
        else:
            st.error(f"🚫 风控阻断: {' / '.join(risk.get('messages', []))}")

    # --- 建议操作 ---
    buy_count = sum(1 for s in signals if s.get("signal_type") == "BUY")
    sell_count = sum(1 for s in signals if s.get("signal_type") == "SELL")
    if buy_count > 0:
        st.success(f"📈 建议关注 {buy_count} 只买入信号股票")
    if sell_count > 0:
        st.error(f"📉 建议处理 {sell_count} 只卖出信号股票")


# ============================================================
# 7. 人工确认 (Human Confirm)
# ============================================================

def render_human_confirm() -> None:
    """渲染人工确认页面"""
    # --- 获取待确认订单 ---
    pending_data = _api_get("/orders/pending")
    dashboard = _api_get("/product/dashboard")

    if not pending_data:
        st.warning("无法连接交易服务")
        return

    orders = pending_data.get("orders", [])

    # --- 账户摘要 ---
    if dashboard and dashboard.get("account"):
        acct = dashboard["account"]
        st.markdown("#### 💰 账户摘要")
        a1, a2, a3 = st.columns(3)
        a1.metric("总资产", f"{acct.get('total_assets', 0):,.0f}")
        a2.metric("可用现金", f"{acct.get('cash', 0):,.0f}")
        a3.metric("持仓市值", f"{acct.get('market_value', 0):,.0f}")

    # --- 持仓摘要 ---
    if dashboard and dashboard.get("positions"):
        positions = dashboard["positions"]
        st.markdown("#### 📊 持仓摘要")
        pos_rows = []
        for p in positions:
            pos_rows.append({
                "代码": p.get("symbol", ""),
                "名称": p.get("name", ""),
                "数量": p.get("quantity", 0),
                "成本价": p.get("cost_price", 0),
                "现价": p.get("current_price", 0),
                "市值": p.get("market_value", 0),
                "盈亏": p.get("pnl", 0),
                "盈亏%": f"{p.get('pnl_pct', 0):.2%}",
            })
        if pos_rows:
            st.dataframe(pd.DataFrame(pos_rows), use_container_width=True, hide_index=True)

    # --- 待确认订单 ---
    st.markdown("#### 📋 待确认订单")

    if not orders:
        st.info("暂无待确认订单")
        return

    # 批量操作按钮（仅允许批量拒绝/取消，禁止批量确认）
    batch_col1, batch_col2 = st.columns(2)
    with batch_col1:
        if st.button("🚫 批量拒绝所有", key="batch_reject_all"):
            rejected = 0
            for o in orders:
                if o.get("side") != "BUY":  # 买入订单不允许批量操作
                    result = _api_post(f"/orders/{o.get('order_id', '')}/reject")
                    if result and result.get("status") == "ok":
                        rejected += 1
            if rejected > 0:
                st.success(f"已拒绝 {rejected} 个非买入订单")
                st.rerun()
            else:
                st.info("没有可批量拒绝的订单（买入订单不允许批量操作）")

    with batch_col2:
        if st.button("❌ 批量取消所有", key="batch_cancel_all"):
            cancelled = 0
            for o in orders:
                result = _api_post(f"/orders/{o.get('order_id', '')}/cancel")
                if result and result.get("status") == "ok":
                    cancelled += 1
            if cancelled > 0:
                st.success(f"已取消 {cancelled} 个订单")
                st.rerun()

    st.warning("⚠️ 买入订单必须逐笔确认，禁止一键确认 (EXECUTION_POLICY 5)")

    # --- 逐笔订单 ---
    for order in orders:
        order_id = order.get("order_id", "")
        symbol = order.get("symbol", "")
        side = order.get("side", "")
        limit_price = order.get("limit_price", 0)
        quantity = order.get("quantity", 0)
        stock_name = order.get("stock_name", "")
        stop_loss = order.get("stop_loss_price", 0)
        take_profit = order.get("take_profit_price", 0)
        risk_note = order.get("risk_note", "")
        signal_id = order.get("signal_id", "")
        risk_check_id = order.get("risk_check_id", "")
        order_state = order.get("status", "")

        amount = limit_price * quantity
        side_label = "买入" if side == "BUY" else "卖出"

        with st.expander(f"{'🟢' if side == 'BUY' else '🔴'} {side_label} {stock_name}({symbol}) x{quantity}@{limit_price:.2f} = {amount:,.0f}元"):
            # 订单详情
            info_col, action_col = st.columns([3, 1])

            with info_col:
                st.markdown(f"**订单ID:** `{order_id}`")
                st.markdown(f"**信号ID:** `{signal_id}`")
                st.markdown(f"**风控检查ID:** `{risk_check_id}`")
                st.markdown(f"**订单状态:** {order_state}")
                st.markdown(f"**方向:** {side_label}")
                st.markdown(f"**价格:** {limit_price:.2f}")
                st.markdown(f"**数量:** {quantity}")
                st.markdown(f"**金额:** {amount:,.0f}元")
                if stop_loss > 0:
                    st.markdown(f"**止损位:** {stop_loss:.2f}")
                if take_profit > 0:
                    st.markdown(f"**止盈位:** {take_profit:.2f}")
                if risk_note:
                    st.warning(f"⚠️ 风险提示: {risk_note}")

            with action_col:
                # 逐笔确认（买入订单必须逐笔确认）
                if st.button("✅ 确认", key=f"confirm_{order_id}"):
                    result = _api_post(f"/orders/{order_id}/confirm")
                    if result and result.get("status") == "ok":
                        st.success("订单已确认并执行")
                        st.rerun()
                    else:
                        msg = result.get("message", "未知错误") if result else "API 连接失败"
                        st.error(f"确认失败: {msg}")

                if st.button("❌ 拒绝", key=f"reject_{order_id}"):
                    result = _api_post(f"/orders/{order_id}/reject")
                    if result and result.get("status") == "ok":
                        st.success("订单已拒绝")
                        st.rerun()
                    else:
                        msg = result.get("message", "未知错误") if result else "API 连接失败"
                        st.error(f"拒绝失败: {msg}")


# ============================================================
# 8. 配置中心 (Configuration)
# ============================================================

def render_configuration() -> None:
    """渲染配置中心"""
    config_data = _api_get("/product/config")

    if not config_data:
        st.error("无法获取配置数据")
        return

    config = config_data.get("config", {})
    groups = config_data.get("groups", {})
    validation = config_data.get("validation", {})

    # --- 验证消息 ---
    if validation.get("errors"):
        for err in validation["errors"]:
            st.error(f"🚫 {err}")
    if validation.get("warnings"):
        for warn in validation["warnings"]:
            st.warning(f"⚠️ {warn}")

    # --- 交易模式 ---
    st.markdown("### 🔧 交易模式")
    trading_mode = config.get("MAX_TRADING_LEVEL", "LEVEL_1_SIGNAL_ONLY")
    mode_options = ["LEVEL_0", "LEVEL_1_SIGNAL_ONLY", "LEVEL_2_HUMAN_CONFIRM", "LEVEL_3_AUTO"]
    mode_labels = {
        "LEVEL_0": "LEVEL_0 - 观察模式",
        "LEVEL_1_SIGNAL_ONLY": "LEVEL_1 - 仅信号模式",
        "LEVEL_2_HUMAN_CONFIRM": "LEVEL_2 - 人工确认模式",
        "LEVEL_3_AUTO": "LEVEL_3 - 自动交易 (Demo V1 不可用)",
    }

    new_mode = st.selectbox(
        "交易模式",
        mode_options,
        index=mode_options.index(trading_mode) if trading_mode in mode_options else 0,
        format_func=lambda x: mode_labels.get(x, x),
        key="cfg_trading_mode",
    )

    if new_mode == "LEVEL_3_AUTO":
        st.error("🚫 LEVEL_3_AUTO（自动交易）在 Demo V1 中不可用")

    # LEVEL_2 升级确认
    if new_mode == "LEVEL_2_HUMAN_CONFIRM" and trading_mode != "LEVEL_2_HUMAN_CONFIRM":
        st.warning("⚠️ 升级到 LEVEL_2_HUMAN_CONFIRM 需要：")
        st.markdown("1. 确认了解人工确认流程")
        st.markdown("2. BROKER_ADAPTER 将强制设为 paper")
        if st.button("🔑 确认升级到 LEVEL_2", key="confirm_level2_upgrade"):
            result = _api_post("/product/config/confirm-upgrade",
                               params={"key": "MAX_TRADING_LEVEL", "value": "LEVEL_2_HUMAN_CONFIRM"})
            if result and result.get("success"):
                st.success("✅ 已升级为 LEVEL_2_HUMAN_CONFIRM")
                st.rerun()
            else:
                st.error(f"升级失败: {result.get('message', '未知错误') if result else 'API 连接失败'}")
    elif new_mode != trading_mode and new_mode != "LEVEL_3_AUTO":
        if st.button("💾 保存交易模式", key="save_trading_mode"):
            result = _api_post("/product/config", params={"key": "MAX_TRADING_LEVEL", "value": new_mode})
            if result and result.get("success"):
                st.success("✅ 交易模式已更新")
                st.rerun()
            else:
                msg = result.get("message", "未知错误") if result else "API 连接失败"
                st.error(f"更新失败: {msg}")

    st.divider()

    # --- 数据源设置 ---
    st.markdown("### 📊 数据源设置")
    ds_col1, ds_col2 = st.columns(2)
    with ds_col1:
        current_provider = config.get("DEFAULT_DATA_PROVIDER", "akshare")
        provider = st.selectbox("默认数据源", ["akshare", "aktools"], 
                                index=["akshare", "aktools"].index(current_provider) if current_provider in ["akshare", "aktools"] else 0,
                                key="cfg_data_provider")
    with ds_col2:
        eastmoney = st.checkbox("启用东方财富", value=bool(config.get("EASTMONEY_ENABLED", True)), key="cfg_eastmoney")
    sina = st.checkbox("启用新浪行情", value=bool(config.get("SINA_QUOTE_ENABLED", True)), key="cfg_sina")

    st.divider()

    # --- 风控参数 ---
    st.markdown("### 🛡️ 风控参数")
    risk_col1, risk_col2 = st.columns(2)

    with risk_col1:
        max_single = st.slider("单票最大仓位", 0.01, 0.50,
                               float(config.get("MAX_SINGLE_STOCK_POSITION", 0.15)),
                               step=0.01, format="%.2f", key="cfg_max_single")
        max_sector = st.slider("板块最大仓位", 0.10, 1.00,
                               float(config.get("MAX_SECTOR_POSITION", 0.60)),
                               step=0.05, format="%.2f", key="cfg_max_sector")
        min_cash = st.slider("最低现金比例", 0.0, 0.50,
                             float(config.get("MIN_CASH_RATIO", 0.20)),
                             step=0.05, format="%.2f", key="cfg_min_cash")

    with risk_col2:
        loss_warn = st.slider("单票亏损警戒线", -0.20, 0.0,
                              float(config.get("SINGLE_STOCK_LOSS_WARN", -0.05)),
                              step=0.01, format="%.2f", key="cfg_loss_warn")
        loss_stop = st.slider("单票止损线", -0.20, 0.0,
                              float(config.get("SINGLE_STOCK_LOSS_STOP", -0.08)),
                              step=0.01, format="%.2f", key="cfg_loss_stop")
        daily_warn = st.slider("日亏损警戒线", -0.10, 0.0,
                               float(config.get("DAILY_LOSS_WARN", -0.02)),
                               step=0.005, format="%.3f", key="cfg_daily_warn")

    # 验证止损线 < 警戒线
    if loss_stop >= loss_warn:
        st.error("🚫 止损线必须小于警戒线")

    st.divider()

    # --- 回测默认参数 ---
    st.markdown("### 📈 回测默认参数")
    bt_col1, bt_col2, bt_col3 = st.columns(3)
    with bt_col1:
        bt_commission = st.number_input("手续费率", min_value=0.0,
                                        value=float(config.get("BACKTEST_COMMISSION_RATE", 0.0003)),
                                        step=0.0001, format="%.4f", key="cfg_bt_commission")
    with bt_col2:
        bt_stamp = st.number_input("印花税率", min_value=0.0,
                                   value=float(config.get("BACKTEST_STAMP_DUTY", 0.001)),
                                   step=0.0001, format="%.4f", key="cfg_bt_stamp")
    with bt_col3:
        bt_slip = st.number_input("滑点", min_value=0.0,
                                  value=float(config.get("BACKTEST_SLIPPAGE", 0.001)),
                                  step=0.0001, format="%.4f", key="cfg_bt_slip")

    st.divider()

    # --- UI/运行时设置 ---
    st.markdown("### ⚙️ UI/运行时设置")
    log_level = st.selectbox("日志级别", ["DEBUG", "INFO", "WARNING", "ERROR"],
                             index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                                 config.get("LOG_LEVEL", "INFO")),
                             key="cfg_log_level")

    st.divider()

    # --- 保存/恢复 ---
    save_col1, save_col2 = st.columns(2)
    with save_col1:
        if st.button("💾 保存配置", key="save_config", type="primary"):
            # 收集所有修改的配置
            updates = []
            config_updates = {
                "DEFAULT_DATA_PROVIDER": provider,
                "EASTMONEY_ENABLED": str(eastmoney),
                "SINA_QUOTE_ENABLED": str(sina),
                "MAX_SINGLE_STOCK_POSITION": str(max_single),
                "MAX_SECTOR_POSITION": str(max_sector),
                "MIN_CASH_RATIO": str(min_cash),
                "SINGLE_STOCK_LOSS_WARN": str(loss_warn),
                "SINGLE_STOCK_LOSS_STOP": str(loss_stop),
                "DAILY_LOSS_WARN": str(daily_warn),
                "BACKTEST_COMMISSION_RATE": str(bt_commission),
                "BACKTEST_STAMP_DUTY": str(bt_stamp),
                "BACKTEST_SLIPPAGE": str(bt_slip),
                "LOG_LEVEL": log_level,
            }
            for k, v in config_updates.items():
                result = _api_post("/product/config", params={"key": k, "value": v})
                if result and result.get("success"):
                    updates.append(k)

            if updates:
                st.success(f"✅ 已保存 {len(updates)} 项配置")
            else:
                st.error("配置保存失败")

    with save_col2:
        if st.button("🔄 恢复默认", key="restore_defaults"):
            result = _api_post("/product/config/restore-defaults")
            if result and result.get("status") == "ok":
                st.success("✅ 配置已恢复默认值")
                st.rerun()
            else:
                st.error("恢复默认配置失败")


# ============================================================
# 9. 反馈中心 (Feedback)
# ============================================================

def render_feedback() -> None:
    """渲染反馈中心"""
    feedback_data = _api_get("/product/feedback")

    if not feedback_data:
        st.warning("无法获取反馈数据")
        return

    bugs = feedback_data.get("bugs", [])
    count = feedback_data.get("count", 0)

    st.metric("Open Bug 数量", count)

    if not bugs:
        st.info("🎉 暂无 Open 状态的 Bug")
        return

    # --- Bug 列表 ---
    rows = []
    for b in bugs:
        rows.append({
            "Bug ID": b.get("bug_id", ""),
            "标题": b.get("title", ""),
            "组件": b.get("component", ""),
            "严重程度": b.get("severity", ""),
            "状态": b.get("status", ""),
            "出现次数": b.get("occurrence_count", 1),
            "创建时间": b.get("created_at", ""),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # --- Bug 详情 ---
    st.markdown("#### Bug 详情")
    for b in bugs:
        bug_id = b.get("bug_id", "")
        title = b.get("title", "")
        severity = b.get("severity", "")
        with st.expander(f"[{severity.upper()}] {bug_id}: {title}"):
            st.markdown(f"**摘要:** {b.get('summary', '')}")
            st.markdown(f"**组件:** {b.get('component', '')}")
            st.markdown(f"**严重程度:** {severity}")
            st.markdown(f"**状态:** {b.get('status', '')}")
            st.markdown(f"**出现次数:** {b.get('occurrence_count', 1)}")
            st.markdown(f"**创建时间:** {b.get('created_at', '')}")
            st.markdown(f"**更新时间:** {b.get('updated_at', '')}")

            if b.get("user_action"):
                st.markdown(f"**用户操作:** {b['user_action']}")
            if b.get("endpoint_or_page"):
                st.markdown(f"**触发端点:** `{b['endpoint_or_page']}`")
            if b.get("exception_type"):
                st.markdown(f"**异常类型:** `{b['exception_type']}`")
            if b.get("exception_message"):
                st.markdown(f"**异常消息:** `{b['exception_message']}`")

            # 状态操作按钮
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                if st.button("📋 已分诊", key=f"triage_{bug_id}"):
                    result = _api_post(f"/product/feedback/{bug_id}/status", params={"status": "triaged"})
                    if result and result.get("status") == "ok":
                        st.success("已标记为分诊")
                        st.rerun()
                    else:
                        st.error("操作失败")
            with btn_col2:
                if st.button("✅ 已修复", key=f"fix_{bug_id}"):
                    result = _api_post(f"/product/feedback/{bug_id}/status", params={"status": "fixed"})
                    if result and result.get("status") == "ok":
                        st.success("已标记为修复")
                        st.rerun()
                    else:
                        st.error("操作失败")
            with btn_col3:
                if st.button("🔇 忽略", key=f"ignore_{bug_id}"):
                    result = _api_post(f"/product/feedback/{bug_id}/status", params={"status": "ignored"})
                    if result and result.get("status") == "ok":
                        st.success("已标记为忽略")
                        st.rerun()
                    else:
                        st.error("操作失败")

    # --- 导出路径 ---
    st.markdown("#### 📁 导出路径")
    st.code("feedback/bugs/")


# ============================================================
# 主入口
# ============================================================

def main() -> None:
    st.set_page_config(
        page_title="量化交易产品仪表板",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.title("📊 量化交易产品仪表板")

    tab_labels = [
        "🏠 系统状态",
        "📈 实时行情",
        "👁️ 候选股监控",
        "🔬 因子分析",
        "🧪 回测实验室",
        "📡 信号中心",
        "✋ 人工确认",
        "⚙️ 配置中心",
        "🐛 反馈中心",
    ]

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        render_home()

    with tabs[1]:
        render_market()

    with tabs[2]:
        render_watchlist()

    with tabs[3]:
        render_factor_lab()

    with tabs[4]:
        render_backtest_lab()

    with tabs[5]:
        render_signal_center()

    with tabs[6]:
        render_human_confirm()

    with tabs[7]:
        render_configuration()

    with tabs[8]:
        render_feedback()


if __name__ == "__main__":
    main()
