"""Demo 数据夹具模块

当实时数据不可用或市场休市时，提供确定性的演示数据。
用于 Demo V1 产品展示和开发调试。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from src.models.schemas import AccountInfo, Position, RealtimeQuote, Signal

# ============================================================
# 常量定义
# ============================================================

# 半导体 Demo 股票列表（与 stock_pool.yaml 保持一致）
DEMO_STOCKS: list[dict[str, str]] = [
    {"symbol": "002463", "name": "沪电股份", "market": "SZ", "sector": "pcb_ccl"},
    {"symbol": "600584", "name": "长电科技", "market": "SH", "sector": "advanced_packaging"},
    {"symbol": "603228", "name": "景旺电子", "market": "SH", "sector": "pcb_ccl"},
    {"symbol": "002916", "name": "深南电路", "market": "SZ", "sector": "pcb_ccl"},
    {"symbol": "002371", "name": "北方华创", "market": "SZ", "sector": "equipment_material"},
    {"symbol": "002156", "name": "通富微电", "market": "SZ", "sector": "advanced_packaging"},
    {"symbol": "603986", "name": "兆易创新", "market": "SH", "sector": "memory_hbm"},
    {"symbol": "002281", "name": "光迅科技", "market": "SZ", "sector": "optical_module_cpo"},
    {"symbol": "600183", "name": "生益科技", "market": "SH", "sector": "pcb_ccl"},
    {"symbol": "000988", "name": "华工科技", "market": "SZ", "sector": "optical_module_cpo"},
]

# Demo 行情价格表（确定性数据，不依赖实时行情）
_DEMO_PRICES: dict[str, dict[str, Any]] = {
    "002463": {"price": 38.52, "pct_change": 2.35, "volume": 12580000},
    "600584": {"price": 31.78, "pct_change": -0.86, "volume": 9870000},
    "603228": {"price": 26.45, "pct_change": 1.52, "volume": 5620000},
    "002916": {"price": 128.90, "pct_change": 3.12, "volume": 4350000},
    "002371": {"price": 312.50, "pct_change": 1.88, "volume": 8900000},
    "002156": {"price": 22.36, "pct_change": -1.45, "volume": 7230000},
    "603986": {"price": 105.60, "pct_change": 0.75, "volume": 6100000},
    "002281": {"price": 48.92, "pct_change": 4.21, "volume": 11200000},
    "600183": {"price": 19.85, "pct_change": 0.56, "volume": 8450000},
    "000988": {"price": 36.70, "pct_change": -2.10, "volume": 5780000},
}


# ============================================================
# Demo 因子评分数据
# ============================================================

class DemoFactorScore(BaseModel):
    """Demo 因子评分"""
    symbol: str
    name: str
    sector: str
    technical_score: float = Field(default=0.0, description="技术面评分")
    fundamental_score: float = Field(default=0.0, description="基本面评分")
    sentiment_score: float = Field(default=0.0, description="情绪面评分")
    policy_score: float = Field(default=0.0, description="政策面评分")
    total_score: float = Field(default=0.0, description="综合评分")


_DEMO_FACTORS: list[DemoFactorScore] = [
    DemoFactorScore(symbol="002463", name="沪电股份", sector="pcb_ccl",
                    technical_score=85, fundamental_score=78, sentiment_score=72, policy_score=90, total_score=82),
    DemoFactorScore(symbol="600584", name="长电科技", sector="advanced_packaging",
                    technical_score=62, fundamental_score=70, sentiment_score=55, policy_score=95, total_score=68),
    DemoFactorScore(symbol="603228", name="景旺电子", sector="pcb_ccl",
                    technical_score=78, fundamental_score=72, sentiment_score=68, policy_score=88, total_score=76),
    DemoFactorScore(symbol="002916", name="深南电路", sector="pcb_ccl",
                    technical_score=88, fundamental_score=82, sentiment_score=80, policy_score=92, total_score=86),
    DemoFactorScore(symbol="002371", name="北方华创", sector="equipment_material",
                    technical_score=75, fundamental_score=85, sentiment_score=70, policy_score=98, total_score=80),
    DemoFactorScore(symbol="002156", name="通富微电", sector="advanced_packaging",
                    technical_score=55, fundamental_score=60, sentiment_score=45, policy_score=90, total_score=58),
    DemoFactorScore(symbol="603986", name="兆易创新", sector="memory_hbm",
                    technical_score=70, fundamental_score=65, sentiment_score=62, policy_score=85, total_score=70),
    DemoFactorScore(symbol="002281", name="光迅科技", sector="optical_module_cpo",
                    technical_score=92, fundamental_score=80, sentiment_score=88, policy_score=82, total_score=87),
    DemoFactorScore(symbol="600183", name="生益科技", sector="pcb_ccl",
                    technical_score=68, fundamental_score=75, sentiment_score=60, policy_score=88, total_score=72),
    DemoFactorScore(symbol="000988", name="华工科技", sector="optical_module_cpo",
                    technical_score=50, fundamental_score=58, sentiment_score=42, policy_score=80, total_score=55),
]


# ============================================================
# 公开接口
# ============================================================

def is_demo_mode() -> bool:
    """判断当前是否为 Demo 模式

    以下情况进入 Demo 模式：
    1. 环境变量 DEMO_MODE=true
    2. 当前为非交易时段（周末/节假日/非交易时间）
    """
    import os
    demo_env = os.getenv("DEMO_MODE", "").lower()
    if demo_env in ("true", "1", "yes", "on"):
        return True

    # 简单判断：周末为 Demo 模式
    now = datetime.now()
    if now.weekday() >= 5:  # 周六=5, 周日=6
        return True

    # 非交易时段（9:30-15:00 之外）
    if not (9 <= now.hour < 15):
        return True
    if now.hour == 9 and now.minute < 30:
        return True

    return False


def get_demo_quotes() -> list[RealtimeQuote]:
    """获取 Demo 实时行情数据

    返回半导体股票池的确定性行情数据。
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    quotes: list[RealtimeQuote] = []

    for stock in DEMO_STOCKS:
        symbol = stock["symbol"]
        price_data = _DEMO_PRICES.get(symbol, {"price": 10.0, "pct_change": 0.0, "volume": 0})

        price = price_data["price"]
        pct = price_data["pct_change"]
        vol = price_data["volume"]

        # 根据涨跌幅模拟五档行情
        spread = price * 0.001  # 价差约 0.1%
        quotes.append(RealtimeQuote(
            symbol=symbol,
            market=stock["market"],
            datetime=now_str,
            last_price=round(price, 2),
            bid_price_1=round(price - spread, 2),
            bid_price_2=round(price - spread * 2, 2),
            bid_price_3=round(price - spread * 3, 2),
            bid_price_4=round(price - spread * 4, 2),
            bid_price_5=round(price - spread * 5, 2),
            ask_price_1=round(price + spread, 2),
            ask_price_2=round(price + spread * 2, 2),
            ask_price_3=round(price + spread * 3, 2),
            ask_price_4=round(price + spread * 4, 2),
            ask_price_5=round(price + spread * 5, 2),
            bid_volume_1=vol // 10,
            bid_volume_2=vol // 12,
            bid_volume_3=vol // 15,
            bid_volume_4=vol // 20,
            bid_volume_5=vol // 25,
            ask_volume_1=vol // 10,
            ask_volume_2=vol // 12,
            ask_volume_3=vol // 15,
            ask_volume_4=vol // 20,
            ask_volume_5=vol // 25,
            volume=vol,
            amount=round(price * vol, 2),
            pct_change=round(pct, 2),
            status="NORMAL",
        ))

    logger.debug(f"Demo 行情数据: {len(quotes)} 只股票")
    return quotes


def get_demo_signals() -> list[Signal]:
    """获取 Demo 信号数据

    基于因子评分生成确定性信号：
    - 总分 >= 82: BUY
    - 总分 <= 58: SELL
    - 其他: HOLD
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y%m%d")
    signals: list[Signal] = []

    for factor in _DEMO_FACTORS:
        price_data = _DEMO_PRICES.get(factor.symbol, {"price": 10.0})
        price = price_data["price"]

        if factor.total_score >= 82:
            signal_type = "BUY"
            sub_type = "BREAKOUT"
            reason = (
                f"Demo信号-买入: 综合评分{factor.total_score:.0f}, "
                f"技术{factor.technical_score:.0f}/基本面{factor.fundamental_score:.0f}/"
                f"情绪{factor.sentiment_score:.0f}/政策{factor.policy_score:.0f}"
            )
            stop_loss = round(price * 0.92, 2)
            take_profit = round(price * 1.15, 2)
            position_pct = 0.10
            risk_note = "Demo买入信号，注意追高风险"
        elif factor.total_score <= 58:
            signal_type = "SELL"
            sub_type = "TREND_BREAK"
            reason = (
                f"Demo信号-卖出: 综合评分{factor.total_score:.0f}, "
                f"技术{factor.technical_score:.0f}/基本面{factor.fundamental_score:.0f}/"
                f"情绪{factor.sentiment_score:.0f}/政策{factor.policy_score:.0f}"
            )
            stop_loss = round(price * 0.95, 2)
            take_profit = price
            position_pct = 0.5
            risk_note = "Demo卖出信号，趋势走弱"
        else:
            signal_type = "HOLD"
            sub_type = "WATCH"
            reason = (
                f"Demo信号-持有: 综合评分{factor.total_score:.0f}, "
                f"未触发买卖条件"
            )
            stop_loss = round(price * 0.92, 2)
            take_profit = round(price * 1.15, 2)
            position_pct = 0.0
            risk_note = "Demo持有信号，观望等待"

        # 生成确定性 signal_id（基于 symbol 和日期）
        sig_hash = hash(f"{factor.symbol}_{today_str}_{signal_type}") % 1000000
        signal_id = f"SIG_DEMO_{today_str}_{factor.symbol}_{signal_type}_{sig_hash:06d}"

        signals.append(Signal(
            signal_id=signal_id,
            symbol=factor.symbol,
            stock_name=factor.name,
            sector=factor.sector,
            trade_date=today_str,
            strategy="demo_semiconductor_rotation",
            signal_type=signal_type,
            sub_type=sub_type,
            score=factor.total_score,
            price_trigger=price,
            reason=reason,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            position_pct=position_pct,
            risk_note=risk_note,
            created_at=now_str,
        ))

    buy_count = sum(1 for s in signals if s.signal_type == "BUY")
    sell_count = sum(1 for s in signals if s.signal_type == "SELL")
    hold_count = sum(1 for s in signals if s.signal_type == "HOLD")
    logger.debug(f"Demo 信号数据: {buy_count} BUY, {sell_count} SELL, {hold_count} HOLD")
    return signals


def get_demo_factors() -> list[DemoFactorScore]:
    """获取 Demo 因子评分数据"""
    logger.debug(f"Demo 因子数据: {len(_DEMO_FACTORS)} 只股票")
    return list(_DEMO_FACTORS)


def get_demo_account() -> AccountInfo:
    """获取 Demo 账户信息（Paper Broker 模拟账户）

    初始资金 100 万，模拟持仓市值约 30 万。
    """
    # 模拟持仓市值
    positions = get_demo_positions()
    market_value = sum(p.market_value for p in positions)
    cash = 1000000.0 - market_value
    total_assets = cash + market_value
    daily_pnl = 15230.0  # 固定模拟盈亏
    daily_pnl_pct = daily_pnl / 1000000.0

    return AccountInfo(
        total_assets=round(total_assets, 2),
        cash=round(cash, 2),
        market_value=round(market_value, 2),
        available_cash=round(cash, 2),
        daily_pnl=round(daily_pnl, 2),
        daily_pnl_pct=round(daily_pnl_pct, 4),
    )


def get_demo_positions() -> list[Position]:
    """获取 Demo 持仓信息

    模拟持有 3 只股票的持仓。
    """
    return [
        Position(
            symbol="002463",
            market="SZ",
            name="沪电股份",
            quantity=3000,
            available_quantity=3000,
            cost_price=35.80,
            current_price=38.52,
            market_value=round(3000 * 38.52, 2),
            pnl=round(3000 * (38.52 - 35.80), 2),
            pnl_pct=round((38.52 - 35.80) / 35.80, 4),
            sector="pcb_ccl",
        ),
        Position(
            symbol="002916",
            market="SZ",
            name="深南电路",
            quantity=1000,
            available_quantity=1000,
            cost_price=120.50,
            current_price=128.90,
            market_value=round(1000 * 128.90, 2),
            pnl=round(1000 * (128.90 - 120.50), 2),
            pnl_pct=round((128.90 - 120.50) / 120.50, 4),
            sector="pcb_ccl",
        ),
        Position(
            symbol="002371",
            market="SZ",
            name="北方华创",
            quantity=500,
            available_quantity=500,
            cost_price=298.00,
            current_price=312.50,
            market_value=round(500 * 312.50, 2),
            pnl=round(500 * (312.50 - 298.00), 2),
            pnl_pct=round((312.50 - 298.00) / 298.00, 4),
            sector="equipment_material",
        ),
    ]
