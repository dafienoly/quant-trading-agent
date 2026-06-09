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
# 主题 CSS — 深色专业金融风格
# ============================================================

DARK_THEME_CSS = """
<style>
/* ── 全局 ── */
:root {
    --bg-primary: #0a0e17;
    --bg-card: #111827;
    --bg-card-hover: #1a2332;
    --border: #1e293b;
    --border-accent: #334155;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent-blue: #3b82f6;
    --accent-cyan: #06b6d4;
    --accent-green: #10b981;
    --accent-red: #ef4444;
    --accent-amber: #f59e0b;
    --accent-purple: #8b5cf6;
    --accent-pink: #ec4899;
    --gradient-blue: linear-gradient(135deg, #3b82f6, #06b6d4);
    --gradient-green: linear-gradient(135deg, #10b981, #06b6d4);
    --gradient-red: linear-gradient(135deg, #ef4444, #f59e0b);
    --gradient-purple: linear-gradient(135deg, #8b5cf6, #3b82f6);
    --shadow-card: 0 4px 24px rgba(0,0,0,0.3);
    --shadow-glow-blue: 0 0 20px rgba(59,130,246,0.15);
    --shadow-glow-green: 0 0 20px rgba(16,185,129,0.15);
    --shadow-glow-red: 0 0 20px rgba(239,68,68,0.15);
    --radius: 12px;
    --radius-sm: 8px;
}

/* ── Streamlit 覆盖 ── */
.stApp {
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

/* 隐藏默认顶栏 */
header[data-testid="stHeader"] {
    background: var(--bg-primary) !important;
    border-bottom: 1px solid var(--border) !important;
}

/* Tab 样式 */
.stTabs [data-baseweb="tab-list"] {
    background: var(--bg-card) !important;
    border-radius: var(--radius) !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: var(--radius-sm) !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    padding: 8px 16px !important;
    transition: all 0.2s ease !important;
}
.stTabs [aria-selected="true"] {
    background: var(--accent-blue) !important;
    color: white !important;
    box-shadow: var(--shadow-glow-blue) !important;
}
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
    background: var(--bg-card-hover) !important;
    color: var(--text-primary) !important;
}

/* Metric 卡片 */
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    color: var(--text-muted) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.85rem !important;
}

/* DataFrame 表格 */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow: hidden !important;
}
.stDataFrame table {
    background: var(--bg-card) !important;
}
.stDataFrame th {
    background: #0f172a !important;
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    border-bottom: 2px solid var(--border-accent) !important;
}
.stDataFrame td {
    color: var(--text-primary) !important;
    font-size: 0.85rem !important;
    border-bottom: 1px solid var(--border) !important;
}
.stDataFrame tr:hover td {
    background: var(--bg-card-hover) !important;
}

/* 按钮 */
.stButton button {
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    border: 1px solid var(--border-accent) !important;
}
.stButton button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}
.stButton button[kind="primary"] {
    background: var(--accent-blue) !important;
    border-color: var(--accent-blue) !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}

/* Slider */
.stSlider [data-baseweb="slider"] {
    accent-color: var(--accent-blue) !important;
}

/* Selectbox */
.stSelectbox [data-baseweb="select"] {
    background: var(--bg-card) !important;
    border-color: var(--border-accent) !important;
}

/* Input */
.stTextInput input, .stNumberInput input {
    background: var(--bg-card) !important;
    border-color: var(--border-accent) !important;
    color: var(--text-primary) !important;
    border-radius: var(--radius-sm) !important;
}

/* Divider */
.stDivider {
    border-color: var(--border) !important;
}

/* ── 自定义卡片 ── */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 12px;
    box-shadow: var(--shadow-card);
    transition: all 0.2s ease;
}
.card:hover {
    border-color: var(--border-accent);
    background: var(--bg-card-hover);
}
.card-title {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 8px;
}
.card-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
}
.card-sub {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 4px;
}

/* 状态徽章 */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}
.badge-ok {
    background: rgba(16,185,129,0.15);
    color: #34d399;
    border: 1px solid rgba(16,185,129,0.3);
}
.badge-warn {
    background: rgba(245,158,11,0.15);
    color: #fbbf24;
    border: 1px solid rgba(245,158,11,0.3);
}
.badge-error {
    background: rgba(239,68,68,0.15);
    color: #f87171;
    border: 1px solid rgba(239,68,68,0.3);
}
.badge-info {
    background: rgba(59,130,246,0.15);
    color: #60a5fa;
    border: 1px solid rgba(59,130,246,0.3);
}
.badge-demo {
    background: rgba(139,92,246,0.15);
    color: #a78bfa;
    border: 1px solid rgba(139,92,246,0.3);
}

/* 信号方向标签 */
.sig-buy {
    color: #f87171;
    font-weight: 700;
}
.sig-sell {
    color: #34d399;
    font-weight: 700;
}
.sig-hold {
    color: #94a3b8;
    font-weight: 600;
}

/* 进度条 */
.score-bar {
    height: 6px;
    border-radius: 3px;
    background: var(--border);
    overflow: hidden;
    margin-top: 6px;
}
.score-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
}

/* 顶部品牌栏 */
.brand-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    margin-bottom: 16px;
    border-bottom: 1px solid var(--border);
}
.brand-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
}
.brand-sub {
    font-size: 0.75rem;
    color: var(--text-muted);
}

/* 分区标题 */
.section-header {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin: 20px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

/* 涨跌色 */
.price-up { color: #f87171 !important; }
.price-down { color: #34d399 !important; }
.price-flat { color: #94a3b8 !important; }

/* 警告横幅 */
.alert-banner {
    padding: 12px 16px;
    border-radius: var(--radius-sm);
    margin-bottom: 12px;
    font-size: 0.85rem;
    font-weight: 500;
}
.alert-critical {
    background: rgba(239,68,68,0.12);
    border: 1px solid rgba(239,68,68,0.3);
    color: #f87171;
}
.alert-warning {
    background: rgba(245,158,11,0.12);
    border: 1px solid rgba(245,158,11,0.3);
    color: #fbbf24;
}
.alert-info {
    background: rgba(59,130,246,0.12);
    border: 1px solid rgba(59,130,246,0.3);
    color: #60a5fa;
}

/* 因子仪表盘 */
.gauge-container {
    text-align: center;
    padding: 8px;
}
.gauge-value {
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
}
.gauge-label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-top: 4px;
}

/* 订单卡片 */
.order-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    margin-bottom: 8px;
    border-left: 4px solid;
}
.order-buy { border-left-color: #ef4444; }
.order-sell { border-left-color: #10b981; }

/* 小型统计卡 */
.stat-mini {
    text-align: center;
    padding: 12px;
}
.stat-mini-value {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-primary);
}
.stat-mini-label {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-top: 2px;
}
</style>
"""


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


def _score_color(score: float) -> str:
    """因子评分颜色"""
    if score >= 82:
        return "#ef4444"  # 红-买入
    if score >= 70:
        return "#f59e0b"  # 黄-偏强
    if score >= 58:
        return "#94a3b8"  # 灰-中性
    return "#10b981"  # 绿-卖出


def _score_bar_html(score: float, color: str = None) -> str:
    """评分进度条 HTML"""
    if color is None:
        color = _score_color(score)
    width = min(max(score, 0), 100)
    return f'<div class="score-bar"><div class="score-bar-fill" style="width:{width}%;background:{color}"></div></div>'


def _badge_html(text: str, level: str = "info") -> str:
    """徽章 HTML"""
    return f'<span class="badge badge-{level}">{text}</span>'


def _card_html(title: str, value: str, sub: str = "", border_color: str = None) -> str:
    """卡片 HTML"""
    style = f'border-left: 4px solid {border_color};' if border_color else ''
    sub_html = f'<div class="card-sub">{sub}</div>' if sub else ''
    return f'''<div class="card" style="{style}">
        <div class="card-title">{title}</div>
        <div class="card-value">{value}</div>
        {sub_html}
    </div>'''


def _gauge_html(value: float, label: str, color: str = None) -> str:
    """仪表盘 HTML"""
    if color is None:
        color = _score_color(value)
    return f'''<div class="gauge-container">
        <div class="gauge-value" style="color:{color}">{value:.0f}</div>
        <div class="gauge-label">{label}</div>
        {_score_bar_html(value, color)}
    </div>'''


def _section_header(text: str) -> None:
    """分区标题"""
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


# ============================================================
# 1. 系统状态 (Home)
# ============================================================

def render_home() -> None:
    """渲染系统状态首页"""
    health = _api_get("/product/health")
    dashboard = _api_get("/product/dashboard")

    if health is None and dashboard is None:
        st.markdown(f'''<div class="alert-banner alert-critical">
            无法连接后端 API，请确认 FastAPI 服务已启动<br>
            <code style="color:#94a3b8;font-size:0.8rem">python -m uvicorn src.api.app:app --port 8000</code>
        </div>''', unsafe_allow_html=True)
        return

    # ── Kill Switch 警告 ──
    if health and health.get("kill_switch_active"):
        st.markdown(f'''<div class="alert-banner alert-critical">
            KILL SWITCH 已激活 — {health.get('kill_switch_reason', '未知原因')}
        </div>''', unsafe_allow_html=True)

    # ── Demo 模式提示 ──
    if health and health.get("is_demo"):
        st.markdown('''<div class="alert-banner alert-info">
            当前为非交易时段或 Demo 模式，显示确定性演示数据
        </div>''', unsafe_allow_html=True)

    # ── 状态指标卡片 ──
    _section_header("系统状态")

    col1, col2, col3, col4 = st.columns(4)

    api_ok = health is not None
    with col1:
        if api_ok:
            st.markdown(_card_html("API 状态", "在线", "FastAPI 服务正常", "#10b981"), unsafe_allow_html=True)
        else:
            st.markdown(_card_html("API 状态", "离线", "无法连接", "#ef4444"), unsafe_allow_html=True)

    with col2:
        if health:
            ds = health.get("data_source", "unknown")
            ds_label = ds if ds != "unknown" else "未配置"
            st.markdown(_card_html("数据源", ds_label, "行情数据提供商", "#3b82f6"), unsafe_allow_html=True)
        else:
            st.markdown(_card_html("数据源", "未知", "", "#64748b"), unsafe_allow_html=True)

    with col3:
        if health:
            risk_ok = health.get("risk_status", "UNKNOWN")
            if risk_ok == "OK":
                st.markdown(_card_html("风控状态", "正常", "Kill Switch 未激活", "#10b981"), unsafe_allow_html=True)
            else:
                st.markdown(_card_html("风控状态", "阻断", "交易已暂停", "#ef4444"), unsafe_allow_html=True)
        else:
            st.markdown(_card_html("风控状态", "未知", "", "#64748b"), unsafe_allow_html=True)

    with col4:
        if health:
            mode = health.get("trading_mode", "UNKNOWN")
            mode_map = {
                "LEVEL_1_SIGNAL_ONLY": ("L1 信号", "#3b82f6"),
                "LEVEL_2_HUMAN_CONFIRM": ("L2 人工确认", "#f59e0b"),
                "LEVEL_3_AUTO": ("L3 自动", "#ef4444"),
            }
            label, color = mode_map.get(mode, (mode, "#64748b"))
            st.markdown(_card_html("交易模式", label, mode, color), unsafe_allow_html=True)
        else:
            st.markdown(_card_html("交易模式", "未知", "", "#64748b"), unsafe_allow_html=True)

    # ── 第二行状态 ──
    col5, col6, col7 = st.columns(3)

    with col5:
        if health:
            is_live = health.get("is_live", False)
            if is_live:
                st.markdown(_card_html("交易环境", "实盘", "真实资金交易", "#ef4444"), unsafe_allow_html=True)
            else:
                st.markdown(_card_html("交易环境", "模拟", "PaperBroker 模拟交易", "#10b981"), unsafe_allow_html=True)

    with col6:
        if health:
            is_demo = health.get("is_demo", True)
            if is_demo:
                st.markdown(_card_html("数据模式", "Demo", "预置演示数据", "#8b5cf6"), unsafe_allow_html=True)
            else:
                st.markdown(_card_html("数据模式", "实时", "实时行情数据", "#06b6d4"), unsafe_allow_html=True)

    with col7:
        if health:
            backlog = health.get("feedback_backlog", 0)
            color = "#f59e0b" if backlog > 0 else "#10b981"
            st.markdown(_card_html("反馈积压", f"{backlog} 条", "待处理 Bug", color), unsafe_allow_html=True)

    # ── 账户概览 ──
    if dashboard and dashboard.get("account"):
        _section_header("账户概览")
        acct = dashboard["account"]

        c1, c2, c3, c4 = st.columns(4)
        total = acct.get('total_assets', 0)
        cash = acct.get('cash', 0)
        mv = acct.get('market_value', 0)
        pnl = acct.get('daily_pnl', 0)
        pnl_pct = acct.get('daily_pnl_pct', 0)

        with c1:
            st.metric("总资产", f"{total:,.0f}")
        with c2:
            st.metric("可用现金", f"{cash:,.0f}")
        with c3:
            st.metric("持仓市值", f"{mv:,.0f}")
        with c4:
            delta_color = "normal" if pnl >= 0 else "inverse"
            st.metric("当日盈亏", f"{pnl:,.0f}", delta=f"{pnl_pct:.2%}", delta_color=delta_color)

        # 资产分布进度条
        if total > 0:
            cash_pct = cash / total * 100
            mv_pct = mv / total * 100
            st.markdown(f'''
            <div style="margin-top:8px">
                <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#94a3b8;margin-bottom:4px">
                    <span>现金 {cash_pct:.1f}%</span><span>持仓 {mv_pct:.1f}%</span>
                </div>
                <div style="height:8px;border-radius:4px;background:#1e293b;overflow:hidden">
                    <div style="height:100%;width:{mv_pct}%;background:linear-gradient(90deg,#3b82f6,#06b6d4);border-radius:4px"></div>
                </div>
            </div>''', unsafe_allow_html=True)


# ============================================================
# 2. 实时行情 (Market)
# ============================================================

def render_market() -> None:
    """渲染实时行情"""
    dashboard = _api_get("/product/dashboard")

    # ── 控制栏 ──
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 1])
    with ctrl_col1:
        search = st.text_input("搜索股票代码/名称", placeholder="输入代码或名称...", key="market_search")
    with ctrl_col2:
        refresh_interval = st.slider("刷新间隔（秒）", 5, 60, 30, key="refresh_interval")
    with ctrl_col3:
        if st.button("刷新", key="market_refresh", use_container_width=True):
            st.rerun()

    # ── 数据源标签 ──
    if dashboard:
        is_demo = dashboard.get("is_demo", True)
        ds = dashboard.get("data_source", "unknown")
        if is_demo:
            st.markdown(_badge_html("Demo 数据", "demo"), unsafe_allow_html=True)
        else:
            st.markdown(_badge_html(f"数据源: {ds}", "info"), unsafe_allow_html=True)
        ts = dashboard.get("timestamp", "")
        if ts:
            st.caption(f"更新时间: {ts}")

    # ── 行情表格 ──
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
                pct_val = pct if pct is not None else 0
                pct_str = _pct_fmt(pct)
                pct_class = "price-up" if pct_val > 0 else ("price-down" if pct_val < 0 else "price-flat")
                rows.append({
                    "代码": q.get("symbol", ""),
                    "名称": _get_stock_name(q.get("symbol", "")),
                    "最新价": f"{q.get('last_price', 0):.2f}",
                    "涨跌幅": pct_str,
                    "成交量": f"{q.get('volume', 0):,.0f}",
                    "成交额": f"{q.get('amount', 0):,.0f}",
                    "状态": q.get("status", "UNKNOWN"),
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("未找到匹配的股票")
    else:
        st.warning("暂无行情数据，请确认后端服务已启动")


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
        st.markdown('''<div class="alert-banner alert-info">
            当前为 LEVEL_1 信号模式 — 仅生成信号，不会产生任何订单
        </div>''', unsafe_allow_html=True)

    # 候选股卡片
    _section_header("候选股列表")

    for w in watchlist:
        pct = w.get("pct_change", 0) or 0
        symbol = w.get("symbol", "")
        name = w.get("name", symbol)
        price = w.get("last_price", 0)
        sector = _sector_label(w.get("sector", ""))
        status = w.get("status", "UNKNOWN")

        pct_class = "price-up" if pct > 0 else ("price-down" if pct < 0 else "price-flat")
        border_color = "#ef4444" if pct > 0 else ("#10b981" if pct < 0 else "#64748b")

        st.markdown(f'''<div class="card" style="border-left:4px solid {border_color}">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <span style="font-weight:700;font-size:1rem">{name}</span>
                    <span style="color:#64748b;font-size:0.8rem;margin-left:8px">{symbol}</span>
                    <span style="margin-left:8px">{_badge_html(sector, "info")}</span>
                </div>
                <div style="text-align:right">
                    <div style="font-weight:700;font-size:1.1rem">{price:.2f}</div>
                    <div class="{pct_class}" style="font-size:0.85rem">{_pct_fmt(pct)}</div>
                </div>
            </div>
        </div>''', unsafe_allow_html=True)

    # 风控阻断提示
    risk = dashboard.get("risk", {})
    if risk and not risk.get("risk_pass", True):
        st.markdown(f'''<div class="alert-banner alert-critical">
            风控阻断: {' / '.join(risk.get('messages', []))}
        </div>''', unsafe_allow_html=True)

    # 触发的信号提醒
    signals = dashboard.get("signals", [])
    buy_signals = [s for s in signals if s.get("signal_type") == "BUY"]
    sell_signals = [s for s in signals if s.get("signal_type") == "SELL"]

    if buy_signals:
        st.markdown(f'''<div class="alert-banner alert-warning">
            {len(buy_signals)} 只股票触发买入信号
        </div>''', unsafe_allow_html=True)
    if sell_signals:
        st.markdown(f'''<div class="alert-banner alert-critical">
            {len(sell_signals)} 只股票触发卖出信号
        </div>''', unsafe_allow_html=True)


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

    # ── 选择器 ──
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

    if st.button("计算因子评分", key="compute_factors", type="primary"):
        symbol_codes = [s.split()[0] for s in selected]
        params = {"symbols": ",".join(symbol_codes)}
        if start_date:
            params["start_date"] = start_date.strftime("%Y%m%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y%m%d")

        with st.spinner("正在计算因子评分..."):
            result = _api_post("/product/factors/compute", params=params)

        if result and result.get("factors"):
            _render_factor_results(result)
        else:
            st.error("因子计算失败，请检查后端服务")
    else:
        # 显示 Dashboard 中的因子数据
        if dashboard and dashboard.get("factors"):
            _render_factor_cards(dashboard["factors"])

        st.markdown('''<div class="alert-banner alert-warning">
            因子数据存在幸存者偏差：仅包含当前在池股票。部分因子可能存在数据缺失，请结合原始数据验证。
        </div>''', unsafe_allow_html=True)


def _render_factor_cards(factors: list) -> None:
    """渲染因子评分卡片"""
    _section_header("因子评分")

    for f in factors:
        symbol = f.get("symbol", "")
        name = f.get("name", symbol)
        total = f.get("total_score", 0)
        policy = f.get("policy_score", 0)
        sentiment = f.get("sentiment_score", 0)
        fundamental = f.get("fundamental_score", 0)
        technical = f.get("technical_score", 0)

        # 综合评分颜色
        total_color = _score_color(total)
        action = "买入" if total >= 82 else ("卖出" if total <= 58 else "持有")
        action_badge = "badge-error" if total >= 82 else ("badge-ok" if total <= 58 else "badge-info")

        st.markdown(f'''<div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <div>
                    <span style="font-weight:700;font-size:1rem">{name}</span>
                    <span style="color:#64748b;font-size:0.8rem;margin-left:8px">{symbol}</span>
                </div>
                <div style="display:flex;align-items:center;gap:8px">
                    <span class="badge {action_badge}">{action}</span>
                    <span style="font-size:1.5rem;font-weight:800;color:{total_color}">{total:.0f}</span>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px">
                {_gauge_html(policy, "政策面", _score_color(policy))}
                {_gauge_html(sentiment, "情绪面", _score_color(sentiment))}
                {_gauge_html(fundamental, "基本面", _score_color(fundamental))}
                {_gauge_html(technical, "技术面", _score_color(technical))}
            </div>
        </div>''', unsafe_allow_html=True)


def _render_factor_results(result: dict) -> None:
    """渲染因子计算结果"""
    factors = result.get("factors", [])
    _render_factor_cards(factors)
    st.success(f"因子计算完成，共 {len(factors)} 只股票")

    # 因子说明
    with st.expander("因子说明"):
        st.markdown("""
        - **政策面** (权重 25%): 产业政策对板块的影响评分
        - **情绪面** (权重 30%): 资金流向与市场情绪评分
        - **基本面** (权重 20%): 财务指标与估值水平评分
        - **技术面** (权重 25%): 价格趋势与动量信号评分
        - **综合评分** >= 82 触发买入，<= 58 触发卖出
        """)

    warnings = result.get("warnings", [])
    for w in warnings:
        st.warning(w)


# ============================================================
# 5. 回测实验室 (Backtest Lab)
# ============================================================

def render_backtest_lab() -> None:
    """渲染回测实验室"""

    # ── 参数设置 ──
    _section_header("回测参数")

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

    # ── 成本参数 ──
    with st.expander("交易成本参数"):
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            commission = st.number_input("手续费率", min_value=0.0, value=0.0003, step=0.0001, format="%.4f", key="bt_commission")
        with cc2:
            stamp_duty = st.number_input("印花税率", min_value=0.0, value=0.001, step=0.0001, format="%.4f", key="bt_stamp")
        with cc3:
            slippage = st.number_input("滑点", min_value=0.0, value=0.001, step=0.0001, format="%.4f", key="bt_slippage")

    # ── 无成本假设阻断 ──
    if commission == 0 and stamp_duty == 0 and slippage == 0:
        st.markdown('''<div class="alert-banner alert-critical">
            回测必须包含交易成本假设（手续费/印花税/滑点），不含成本的回测结果不可信
        </div>''', unsafe_allow_html=True)

    # ── 运行回测 ──
    if st.button("运行回测", key="run_backtest", type="primary"):
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
            st.success(f"回测完成! Job ID: {result.get('job_id', 'N/A')}")

            # 性能摘要
            perf = result.get("performance", {})
            if perf:
                _section_header("性能摘要")
                p1, p2, p3, p4 = st.columns(4)

                annual_ret = perf.get('annual_return', 0)
                max_dd = perf.get('max_drawdown', 0)
                sharpe = perf.get('sharpe_ratio', 0)
                win_rate = perf.get('win_rate', 0)

                ret_color = "#10b981" if annual_ret > 0 else "#ef4444"
                dd_color = "#ef4444" if max_dd < -0.15 else "#f59e0b"
                sharpe_color = "#10b981" if sharpe > 1 else ("#f59e0b" if sharpe > 0 else "#ef4444")

                with p1:
                    st.markdown(_card_html("年化收益", f"{annual_ret:.1%}", "", ret_color), unsafe_allow_html=True)
                with p2:
                    st.markdown(_card_html("最大回撤", f"{max_dd:.1%}", "", dd_color), unsafe_allow_html=True)
                with p3:
                    st.markdown(_card_html("夏普比率", f"{sharpe:.2f}", "", sharpe_color), unsafe_allow_html=True)
                with p4:
                    st.markdown(_card_html("胜率", f"{win_rate:.1%}", "", "#3b82f6"), unsafe_allow_html=True)

            # 成本假设
            costs = result.get("cost_assumptions", {})
            if costs:
                _section_header("成本假设")
                st.json(costs)

            # 交易列表
            trades = result.get("trades", [])
            if trades:
                _section_header("交易列表")
                trade_df = pd.DataFrame(trades)
                st.dataframe(trade_df, use_container_width=True, hide_index=True)

            # 警告
            warnings = result.get("warnings", [])
            for w in warnings:
                st.warning(w)

            # 免责声明
            disclaimer = result.get("disclaimer", "")
            if disclaimer:
                st.markdown(f'''<div class="alert-banner alert-info">{disclaimer}</div>''', unsafe_allow_html=True)
        else:
            st.error("回测运行失败，请检查后端服务")


# ============================================================
# 6. 信号中心 (Signal Center)
# ============================================================

def render_signal_center() -> None:
    """渲染信号中心"""
    dashboard = _api_get("/product/dashboard")

    # ── 手动刷新 ──
    if st.button("刷新信号", key="signal_refresh"):
        refresh_result = _api_post("/signals/refresh")
        if refresh_result:
            st.success("信号已刷新")
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

    # ── 信号统计 ──
    buy_count = sum(1 for s in signals if s.get("signal_type") == "BUY")
    sell_count = sum(1 for s in signals if s.get("signal_type") == "SELL")
    hold_count = sum(1 for s in signals if s.get("signal_type") == "HOLD")

    _section_header("信号概览")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(_card_html("买入信号", str(buy_count), "触发买入条件", "#ef4444"), unsafe_allow_html=True)
    with sc2:
        st.markdown(_card_html("卖出信号", str(sell_count), "触发卖出条件", "#10b981"), unsafe_allow_html=True)
    with sc3:
        st.markdown(_card_html("持有信号", str(hold_count), "维持持有", "#64748b"), unsafe_allow_html=True)

    # ── 信号卡片 ──
    _section_header("信号列表")

    for s in signals:
        sig_type = s.get("signal_type", "UNKNOWN")
        symbol = s.get("symbol", "")
        name = s.get("stock_name", symbol)
        score = s.get("score", 0)
        reason = s.get("reason", "")
        stop_loss = s.get("stop_loss_price", 0)
        take_profit = s.get("take_profit_price", 0)
        position_pct = s.get("position_pct", 0)
        risk_note = s.get("risk_note", "")

        if sig_type == "BUY":
            border_color = "#ef4444"
            sig_label = "买入"
            badge_class = "badge-error"
        elif sig_type == "SELL":
            border_color = "#10b981"
            sig_label = "卖出"
            badge_class = "badge-ok"
        else:
            border_color = "#64748b"
            sig_label = "持有"
            badge_class = "badge-info"

        risk_html = f'''<div style="margin-top:8px;font-size:0.8rem;color:#fbbf24">
            风险提示: {risk_note}</div>''' if risk_note else ""

        st.markdown(f'''<div class="card" style="border-left:4px solid {border_color}">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <span class="badge {badge_class}">{sig_label}</span>
                    <span style="font-weight:700;font-size:1rem;margin-left:8px">{name}</span>
                    <span style="color:#64748b;font-size:0.8rem;margin-left:8px">{symbol}</span>
                </div>
                <div style="font-size:1.2rem;font-weight:700;color:{_score_color(score)}">{score:.0f}</div>
            </div>
            <div style="margin-top:8px;font-size:0.85rem;color:#94a3b8">{reason}</div>
            <div style="display:flex;gap:16px;margin-top:8px;font-size:0.8rem">
                <span style="color:#94a3b8">止损 <span style="color:#f87171">{stop_loss:.2f}</span></span>
                <span style="color:#94a3b8">止盈 <span style="color:#34d399">{take_profit:.2f}</span></span>
                <span style="color:#94a3b8">仓位 <span style="color:#60a5fa">{position_pct:.0%}</span></span>
            </div>
            {risk_html}
        </div>''', unsafe_allow_html=True)

    # ── 风控检查结果 ──
    risk = dashboard.get("risk", {})
    if risk:
        _section_header("风控检查结果")
        if risk.get("risk_pass"):
            st.markdown(_badge_html("风控通过", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(f'''<div class="alert-banner alert-critical">
                风控阻断: {' / '.join(risk.get('messages', []))}
            </div>''', unsafe_allow_html=True)


# ============================================================
# 7. 人工确认 (Human Confirm)
# ============================================================

def render_human_confirm() -> None:
    """渲染人工确认页面"""
    pending_data = _api_get("/orders/pending")
    dashboard = _api_get("/product/dashboard")

    if not pending_data:
        st.warning("无法连接交易服务")
        return

    orders = pending_data.get("orders", [])

    # ── 账户摘要 ──
    if dashboard and dashboard.get("account"):
        acct = dashboard["account"]
        _section_header("账户摘要")
        a1, a2, a3 = st.columns(3)
        a1.metric("总资产", f"{acct.get('total_assets', 0):,.0f}")
        a2.metric("可用现金", f"{acct.get('cash', 0):,.0f}")
        a3.metric("持仓市值", f"{acct.get('market_value', 0):,.0f}")

    # ── 持仓摘要 ──
    if dashboard and dashboard.get("positions"):
        positions = dashboard["positions"]
        _section_header("持仓摘要")
        pos_rows = []
        for p in positions:
            pnl = p.get("pnl", 0)
            pos_rows.append({
                "代码": p.get("symbol", ""),
                "名称": p.get("name", ""),
                "数量": p.get("quantity", 0),
                "成本价": f"{p.get('cost_price', 0):.2f}",
                "现价": f"{p.get('current_price', 0):.2f}",
                "市值": f"{p.get('market_value', 0):,.0f}",
                "盈亏": f"{pnl:,.0f}",
                "盈亏%": f"{p.get('pnl_pct', 0):.2%}",
            })
        if pos_rows:
            st.dataframe(pd.DataFrame(pos_rows), use_container_width=True, hide_index=True)

    # ── 待确认订单 ──
    _section_header("待确认订单")

    if not orders:
        st.info("暂无待确认订单")
        return

    # 批量操作
    batch_col1, batch_col2 = st.columns(2)
    with batch_col1:
        if st.button("批量拒绝所有", key="batch_reject_all"):
            rejected = 0
            for o in orders:
                if o.get("side") != "BUY":
                    result = _api_post(f"/orders/{o.get('order_id', '')}/reject")
                    if result and result.get("status") == "ok":
                        rejected += 1
            if rejected > 0:
                st.success(f"已拒绝 {rejected} 个非买入订单")
                st.rerun()
            else:
                st.info("没有可批量拒绝的订单（买入订单不允许批量操作）")

    with batch_col2:
        if st.button("批量取消所有", key="batch_cancel_all"):
            cancelled = 0
            for o in orders:
                result = _api_post(f"/orders/{o.get('order_id', '')}/cancel")
                if result and result.get("status") == "ok":
                    cancelled += 1
            if cancelled > 0:
                st.success(f"已取消 {cancelled} 个订单")
                st.rerun()

    st.markdown('''<div class="alert-banner alert-warning">
        买入订单必须逐笔确认，禁止一键确认 (EXECUTION_POLICY 5)
    </div>''', unsafe_allow_html=True)

    # ── 逐笔订单卡片 ──
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
        order_class = "order-buy" if side == "BUY" else "order-sell"
        side_color = "#ef4444" if side == "BUY" else "#10b981"

        risk_html = f'''<div style="margin-top:6px;font-size:0.8rem;color:#fbbf24">
            风险提示: {risk_note}</div>''' if risk_note else ""

        with st.container():
            st.markdown(f'''<div class="order-card {order_class}">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <span style="color:{side_color};font-weight:700;font-size:0.9rem">{side_label}</span>
                        <span style="font-weight:700;font-size:1rem;margin-left:8px">{stock_name}</span>
                        <span style="color:#64748b;font-size:0.8rem;margin-left:8px">{symbol}</span>
                    </div>
                    <div style="text-align:right">
                        <div style="font-weight:700;font-size:1.1rem">{amount:,.0f} 元</div>
                        <div style="font-size:0.8rem;color:#94a3b8">{quantity} 股 @ {limit_price:.2f}</div>
                    </div>
                </div>
                <div style="display:flex;gap:16px;margin-top:8px;font-size:0.8rem;color:#94a3b8">
                    <span>订单 <code style="color:#60a5fa">{order_id[:12]}...</code></span>
                    <span>信号 <code style="color:#60a5fa">{signal_id[:12]}...</code></span>
                    <span>状态 {_badge_html(order_state, 'info')}</span>
                </div>
                <div style="display:flex;gap:16px;margin-top:6px;font-size:0.8rem">
                    <span style="color:#94a3b8">止损 <span style="color:#f87171">{stop_loss:.2f}</span></span>
                    <span style="color:#94a3b8">止盈 <span style="color:#34d399">{take_profit:.2f}</span></span>
                </div>
                {risk_html}
            </div>''', unsafe_allow_html=True)

            # 操作按钮
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("确认执行", key=f"confirm_{order_id}", type="primary"):
                    result = _api_post(f"/orders/{order_id}/confirm")
                    if result and result.get("status") == "ok":
                        st.success("订单已确认并执行")
                        st.rerun()
                    else:
                        msg = result.get("message", "未知错误") if result else "API 连接失败"
                        st.error(f"确认失败: {msg}")

            with btn_col2:
                if st.button("拒绝", key=f"reject_{order_id}"):
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

    # ── 验证消息 ──
    if validation.get("errors"):
        for err in validation["errors"]:
            st.markdown(f'''<div class="alert-banner alert-critical">{err}</div>''', unsafe_allow_html=True)
    if validation.get("warnings"):
        for warn in validation["warnings"]:
            st.markdown(f'''<div class="alert-banner alert-warning">{warn}</div>''', unsafe_allow_html=True)

    # ── 交易模式 ──
    _section_header("交易模式")
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
        st.markdown('''<div class="alert-banner alert-critical">
            LEVEL_3_AUTO（自动交易）在 Demo V1 中不可用
        </div>''', unsafe_allow_html=True)

    # LEVEL_2 升级确认
    if new_mode == "LEVEL_2_HUMAN_CONFIRM" and trading_mode != "LEVEL_2_HUMAN_CONFIRM":
        st.markdown('''<div class="alert-banner alert-warning">
            升级到 LEVEL_2_HUMAN_CONFIRM 需要：确认了解人工确认流程；BROKER_ADAPTER 将强制设为 paper
        </div>''', unsafe_allow_html=True)
        if st.button("确认升级到 LEVEL_2", key="confirm_level2_upgrade", type="primary"):
            result = _api_post("/product/config/confirm-upgrade",
                               params={"key": "MAX_TRADING_LEVEL", "value": "LEVEL_2_HUMAN_CONFIRM"})
            if result and result.get("success"):
                st.success("已升级为 LEVEL_2_HUMAN_CONFIRM")
                st.rerun()
            else:
                st.error(f"升级失败: {result.get('message', '未知错误') if result else 'API 连接失败'}")
    elif new_mode != trading_mode and new_mode != "LEVEL_3_AUTO":
        if st.button("保存交易模式", key="save_trading_mode"):
            result = _api_post("/product/config", params={"key": "MAX_TRADING_LEVEL", "value": new_mode})
            if result and result.get("success"):
                st.success("交易模式已更新")
                st.rerun()
            else:
                msg = result.get("message", "未知错误") if result else "API 连接失败"
                st.error(f"更新失败: {msg}")

    # ── 数据源设置 ──
    _section_header("数据源设置")
    ds_col1, ds_col2 = st.columns(2)
    with ds_col1:
        current_provider = config.get("DEFAULT_DATA_PROVIDER", "akshare")
        provider = st.selectbox("默认数据源", ["akshare", "aktools"],
                                index=["akshare", "aktools"].index(current_provider) if current_provider in ["akshare", "aktools"] else 0,
                                key="cfg_data_provider")
    with ds_col2:
        eastmoney = st.checkbox("启用东方财富", value=bool(config.get("EASTMONEY_ENABLED", True)), key="cfg_eastmoney")
    sina = st.checkbox("启用新浪行情", value=bool(config.get("SINA_QUOTE_ENABLED", True)), key="cfg_sina")

    # ── 风控参数 ──
    _section_header("风控参数")
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

    if loss_stop >= loss_warn:
        st.markdown('''<div class="alert-banner alert-critical">止损线必须小于警戒线</div>''', unsafe_allow_html=True)

    # ── 回测默认参数 ──
    _section_header("回测默认参数")
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

    # ── UI/运行时设置 ──
    _section_header("运行时设置")
    log_level = st.selectbox("日志级别", ["DEBUG", "INFO", "WARNING", "ERROR"],
                             index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                                 config.get("LOG_LEVEL", "INFO")),
                             key="cfg_log_level")

    # ── 保存/恢复 ──
    _section_header("操作")
    save_col1, save_col2 = st.columns(2)
    with save_col1:
        if st.button("保存配置", key="save_config", type="primary"):
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
                st.success(f"已保存 {len(updates)} 项配置")
            else:
                st.error("配置保存失败")

    with save_col2:
        if st.button("恢复默认", key="restore_defaults"):
            result = _api_post("/product/config/restore-defaults")
            if result and result.get("status") == "ok":
                st.success("配置已恢复默认值")
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

    _section_header("Bug 概览")
    st.markdown(_card_html("Open Bug", str(count), "待处理 Bug 数量", "#f59e0b" if count > 0 else "#10b981"), unsafe_allow_html=True)

    if not bugs:
        st.info("暂无 Open 状态的 Bug")
        return

    # ── Bug 列表 ──
    _section_header("Bug 列表")

    for b in bugs:
        bug_id = b.get("bug_id", "")
        title = b.get("title", "")
        severity = b.get("severity", "")
        component = b.get("component", "")
        status = b.get("status", "")
        occurrence = b.get("occurrence_count", 1)
        summary = b.get("summary", "")

        # 严重程度颜色
        sev_colors = {"critical": "#ef4444", "high": "#f59e0b", "medium": "#3b82f6", "low": "#64748b"}
        sev_color = sev_colors.get(severity.lower(), "#64748b")

        sev_badge_map = {"critical": "badge-error", "high": "badge-warn", "medium": "badge-info", "low": "badge-demo"}
        sev_badge = sev_badge_map.get(severity.lower(), "badge-info")

        with st.expander(f"[{severity.upper()}] {bug_id}: {title}"):
            st.markdown(f'''
            <div style="display:flex;gap:8px;margin-bottom:12px">
                <span class="badge {sev_badge}">{severity.upper()}</span>
                <span class="badge badge-info">{component}</span>
                <span class="badge badge-ok">{status}</span>
            </div>
            <div style="font-size:0.85rem;color:#94a3b8;margin-bottom:8px">{summary}</div>
            <div style="display:flex;gap:16px;font-size:0.8rem;color:#64748b">
                <span>出现次数: {occurrence}</span>
                <span>创建: {b.get('created_at', '')}</span>
                <span>更新: {b.get('updated_at', '')}</span>
            </div>
            ''', unsafe_allow_html=True)

            if b.get("user_action"):
                st.caption(f"用户操作: {b['user_action']}")
            if b.get("endpoint_or_page"):
                st.caption(f"触发端点: {b['endpoint_or_page']}")
            if b.get("exception_type"):
                st.caption(f"异常类型: {b['exception_type']}")
            if b.get("exception_message"):
                st.caption(f"异常消息: {b['exception_message']}")

            # 状态操作按钮
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                if st.button("已分诊", key=f"triage_{bug_id}"):
                    result = _api_post(f"/product/feedback/{bug_id}/status", params={"status": "triaged"})
                    if result and result.get("status") == "ok":
                        st.success("已标记为分诊")
                        st.rerun()
                    else:
                        st.error("操作失败")
            with btn_col2:
                if st.button("已修复", key=f"fix_{bug_id}"):
                    result = _api_post(f"/product/feedback/{bug_id}/status", params={"status": "fixed"})
                    if result and result.get("status") == "ok":
                        st.success("已标记为修复")
                        st.rerun()
                    else:
                        st.error("操作失败")
            with btn_col3:
                if st.button("忽略", key=f"ignore_{bug_id}"):
                    result = _api_post(f"/product/feedback/{bug_id}/status", params={"status": "ignored"})
                    if result and result.get("status") == "ok":
                        st.success("已标记为忽略")
                        st.rerun()
                    else:
                        st.error("操作失败")

    # ── 导出路径 ──
    _section_header("导出路径")
    st.code("feedback/bugs/")


# ============================================================
# 主入口
# ============================================================

def main() -> None:
    st.set_page_config(
        page_title="QuantAgent Pro",
        page_icon="",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # 注入深色主题 CSS
    st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

    # 品牌栏
    st.markdown('''<div class="brand-bar">
        <div>
            <span class="brand-title">QuantAgent Pro</span>
            <span class="brand-sub" style="margin-left:12px">量化交易智能体系统</span>
        </div>
        <div class="brand-sub">A-share / HK Connect</div>
    </div>''', unsafe_allow_html=True)

    tab_labels = [
        "系统状态",
        "实时行情",
        "候选股监控",
        "因子分析",
        "回测实验室",
        "信号中心",
        "人工确认",
        "配置中心",
        "反馈中心",
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
