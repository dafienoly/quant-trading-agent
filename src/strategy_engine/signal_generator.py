"""信号生成器

实现 ARCHITECTURE.md 6.1~6.2 节定义的买入/卖出/持有信号：

买入信号：
- BUY_BREAKOUT: 趋势突破买入
- BUY_PULLBACK: 回踩低吸买入
- BUY_AMBUSH: 材料设备埋伏买入

卖出信号：
- SELL_STOP_LOSS: 止损卖出
- SELL_HALF_STOP_LOSS: 减半止损
- SELL_TREND_BREAK: 趋势破坏卖出
- SELL_SENTIMENT_FADE: 情绪退潮卖出
- SELL_TAKE_PROFIT_HALF: 半仓止盈
- SELL_TAKE_PROFIT: 全仓止盈

持有信号：
- HOLD_WATCH: 观望持有（不满足买卖条件）

每个信号必须包含解释文本，遵循 AGENTS.md 2.4 节可解释性要求。
"""
from __future__ import annotations

import random
import string
from datetime import datetime
from typing import List, Optional

import pandas as pd
from loguru import logger

from src.models.schemas import Signal


def _make_signal_id(symbol: str, trade_date: str, signal_type: str, sub_type: str) -> str:
    """生成信号ID，含6位随机码避免重复 (DATA_CONTRACTS.md 5节)"""
    rand_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"SIG_{trade_date}_{symbol.replace('.', '')}_{signal_type}_{sub_type}_{rand_code}"


def _safe_get(row: pd.Series, key: str, default=0.0):
    """安全获取行值，NaN返回默认值"""
    val = row.get(key, default)
    if isinstance(val, float) and pd.isna(val):
        return default
    return val


def _get_stock_name(row: pd.Series) -> str:
    """获取股票名称"""
    return str(row.get("name", row.get("stock_name", "")))


def _get_sector(row: pd.Series) -> str:
    """获取所属板块"""
    return str(row.get("sector_key", row.get("sector", "")))


# ============================================================
# 买入信号
# ============================================================

def check_buy_breakout(row: pd.Series) -> Optional[Signal]:
    """趋势突破买入信号 (ARCHITECTURE.md 6.1)"""
    total_score = _safe_get(row, "total_score")
    close = _safe_get(row, "close")
    highest_20 = _safe_get(row, "highest_20", close)
    ma5 = _safe_get(row, "ma5", close)
    ma10 = _safe_get(row, "ma10", close)
    volume = _safe_get(row, "volume", 0)
    volume_ma5 = _safe_get(row, "volume_ma5", volume)
    sector_strength = _safe_get(row, "sector_strength", 0)
    pct_change = _safe_get(row, "pct_change", 0)

    if total_score <= 80:
        return None
    if close <= highest_20 * 0.98:
        return None
    if close <= ma5 or close <= ma10:
        return None
    if volume_ma5 > 0 and volume <= volume_ma5 * 1.5:
        return None
    if sector_strength < 0:
        return None
    if pct_change >= 7:
        return None

    symbol = row.get("symbol", "")
    trade_date = row.get("trade_date", "")
    stop_loss = round(close * 0.92, 2)
    take_profit = round(close * 1.15, 2)

    reason = (
        f"趋势突破: 总分{total_score:.0f}, 收盘{close:.2f}接近20日新高{highest_20:.2f}, "
        f"量比{volume/volume_ma5:.1f}倍, 板块强度{sector_strength:.1f}"
    )

    return Signal(
        signal_id=_make_signal_id(symbol, trade_date, "BUY", "BREAKOUT"),
        symbol=symbol,
        stock_name=_get_stock_name(row),
        sector=_get_sector(row),
        trade_date=trade_date,
        strategy="semiconductor_rotation",
        signal_type="BUY",
        sub_type="BREAKOUT",
        score=total_score,
        price_trigger=close,
        reason=reason,
        stop_loss_price=stop_loss,
        take_profit_price=take_profit,
        position_pct=0.10,
        risk_note="趋势突破买入，注意追高风险，严格执行8%止损",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def check_buy_pullback(row: pd.Series) -> Optional[Signal]:
    """回踩低吸买入信号 (ARCHITECTURE.md 6.1)"""
    total_score = _safe_get(row, "total_score")
    close = _safe_get(row, "close")
    low = _safe_get(row, "low", close)
    ma10 = _safe_get(row, "ma10", close)
    ma20 = _safe_get(row, "ma20", close)
    volume = _safe_get(row, "volume", 0)
    volume_ma5 = _safe_get(row, "volume_ma5", volume)
    sector_strength = _safe_get(row, "sector_strength", 0)

    if total_score <= 75:
        return None
    if close <= ma20:
        return None
    if low > ma10 * 1.02:
        return None
    if close <= ma10:
        return None
    if volume_ma5 > 0 and volume >= volume_ma5 * 1.2:
        return None
    if sector_strength < -1:
        return None

    symbol = row.get("symbol", "")
    trade_date = row.get("trade_date", "")
    stop_loss = round(close * 0.92, 2)
    take_profit = round(close * 1.15, 2)

    reason = (
        f"回踩低吸: 总分{total_score:.0f}, 收盘{close:.2f}站稳MA10({ma10:.2f}), "
        f"缩量回踩, 板块强度{sector_strength:.1f}"
    )

    return Signal(
        signal_id=_make_signal_id(symbol, trade_date, "BUY", "PULLBACK"),
        symbol=symbol,
        stock_name=_get_stock_name(row),
        sector=_get_sector(row),
        trade_date=trade_date,
        strategy="semiconductor_rotation",
        signal_type="BUY",
        sub_type="PULLBACK",
        score=total_score,
        price_trigger=close,
        reason=reason,
        stop_loss_price=stop_loss,
        take_profit_price=take_profit,
        position_pct=0.10,
        risk_note="回踩低吸，若跌破MA20需止损",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def check_buy_ambush(row: pd.Series) -> Optional[Signal]:
    """材料设备埋伏买入信号 (ARCHITECTURE.md 6.1)"""
    policy_score = _safe_get(row, "policy_score")
    fundamental_score = _safe_get(row, "fundamental_score")
    total_score = _safe_get(row, "total_score")
    close = _safe_get(row, "close")
    ma20 = _safe_get(row, "ma20", close)
    ma60 = _safe_get(row, "ma60", close)
    volume = _safe_get(row, "volume", 0)
    volume_ma20 = _safe_get(row, "volume_ma20", volume)

    if policy_score < 90:
        return None
    if fundamental_score < 60:
        return None
    if close <= ma20:
        return None
    if close <= ma60:
        return None
    if volume_ma20 > 0 and volume <= volume_ma20 * 1.2:
        return None
    if total_score <= 68:
        return None

    symbol = row.get("symbol", "")
    trade_date = row.get("trade_date", "")
    stop_loss = round(close * 0.92, 2)
    take_profit = round(close * 1.20, 2)

    reason = (
        f"材料设备埋伏: 政策分{policy_score:.0f}, 基本面分{fundamental_score:.0f}, "
        f"总分{total_score:.0f}, 站稳MA20和MA60, 量能放大"
    )

    return Signal(
        signal_id=_make_signal_id(symbol, trade_date, "BUY", "AMBUSH"),
        symbol=symbol,
        stock_name=_get_stock_name(row),
        sector=_get_sector(row),
        trade_date=trade_date,
        strategy="semiconductor_rotation",
        signal_type="BUY",
        sub_type="AMBUSH",
        score=total_score,
        price_trigger=close,
        reason=reason,
        stop_loss_price=stop_loss,
        take_profit_price=take_profit,
        position_pct=0.08,
        risk_note="埋伏买入，仓位较轻，耐心等待催化",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


# ============================================================
# 卖出信号
# ============================================================

def check_sell_stop_loss(row: pd.Series, current_return: float = 0.0) -> Optional[Signal]:
    """止损卖出信号 (ARCHITECTURE.md 6.2)"""
    close = _safe_get(row, "close")
    ma10 = _safe_get(row, "ma10", close)
    symbol = row.get("symbol", "")
    trade_date = row.get("trade_date", "")

    if current_return <= -0.08:
        stop_loss = round(close * 0.95, 2)
        reason = f"强止损: 浮亏{current_return*100:.1f}%, 跌破8%止损线"
        return Signal(
            signal_id=_make_signal_id(symbol, trade_date, "SELL", "STOP_LOSS"),
            symbol=symbol, stock_name=_get_stock_name(row), sector=_get_sector(row),
            trade_date=trade_date, strategy="semiconductor_rotation",
            signal_type="SELL", sub_type="STOP_LOSS",
            score=_safe_get(row, "total_score"),
            price_trigger=close, reason=reason,
            stop_loss_price=stop_loss, take_profit_price=close,
            position_pct=1.0,
            risk_note="触发8%强止损，建议清仓",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    if current_return <= -0.05 and close < ma10:
        stop_loss = round(close * 0.95, 2)
        reason = f"减半止损: 浮亏{current_return*100:.1f}%, 收盘{close:.2f}跌破MA10({ma10:.2f})"
        return Signal(
            signal_id=_make_signal_id(symbol, trade_date, "SELL", "HALF_STOP_LOSS"),
            symbol=symbol, stock_name=_get_stock_name(row), sector=_get_sector(row),
            trade_date=trade_date, strategy="semiconductor_rotation",
            signal_type="SELL", sub_type="HALF_STOP_LOSS",
            score=_safe_get(row, "total_score"),
            price_trigger=close, reason=reason,
            stop_loss_price=stop_loss, take_profit_price=close,
            position_pct=0.5,
            risk_note="触发5%减半止损，若继续跌破8%则清仓",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    return None


def check_sell_trend_break(row: pd.Series) -> Optional[Signal]:
    """趋势破坏卖出信号 (ARCHITECTURE.md 6.2)"""
    close = _safe_get(row, "close")
    ma20 = _safe_get(row, "ma20", close)
    volume = _safe_get(row, "volume", 0)
    volume_ma5 = _safe_get(row, "volume_ma5", volume)

    if close >= ma20:
        return None
    if volume_ma5 > 0 and volume <= volume_ma5 * 1.2:
        return None

    symbol = row.get("symbol", "")
    trade_date = row.get("trade_date", "")

    reason = (
        f"趋势破坏: 收盘{close:.2f}跌破MA20({ma20:.2f}), "
        f"放量破位(量比{volume/volume_ma5:.1f})"
    )

    return Signal(
        signal_id=_make_signal_id(symbol, trade_date, "SELL", "TREND_BREAK"),
        symbol=symbol, stock_name=_get_stock_name(row), sector=_get_sector(row),
        trade_date=trade_date, strategy="semiconductor_rotation",
        signal_type="SELL", sub_type="TREND_BREAK",
        score=_safe_get(row, "total_score"),
        price_trigger=close, reason=reason,
        stop_loss_price=round(close * 0.95, 2),
        take_profit_price=close,
        position_pct=0.5,
        risk_note="趋势破坏，建议减仓观察",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def check_sell_sentiment_fade(row: pd.Series) -> Optional[Signal]:
    """情绪退潮卖出信号 (ARCHITECTURE.md 6.2)"""
    sector_strength = _safe_get(row, "sector_strength", 0)
    pct_change = _safe_get(row, "pct_change", 0)
    volume = _safe_get(row, "volume", 0)
    volume_ma5 = _safe_get(row, "volume_ma5", volume)
    close = _safe_get(row, "close")

    if sector_strength >= -2:
        return None
    if pct_change >= -3:
        return None
    if volume_ma5 > 0 and volume <= volume_ma5:
        return None

    symbol = row.get("symbol", "")
    trade_date = row.get("trade_date", "")

    reason = (
        f"情绪退潮: 板块强度{sector_strength:.1f}, 跌幅{pct_change:.1f}%, "
        f"放量下跌"
    )

    return Signal(
        signal_id=_make_signal_id(symbol, trade_date, "SELL", "SENTIMENT_FADE"),
        symbol=symbol, stock_name=_get_stock_name(row), sector=_get_sector(row),
        trade_date=trade_date, strategy="semiconductor_rotation",
        signal_type="SELL", sub_type="SENTIMENT_FADE",
        score=_safe_get(row, "total_score"),
        price_trigger=close, reason=reason,
        stop_loss_price=round(close * 0.95, 2),
        take_profit_price=close,
        position_pct=0.5,
        risk_note="板块情绪退潮，建议减仓",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def check_sell_take_profit(row: pd.Series, current_return: float = 0.0) -> Optional[Signal]:
    """止盈卖出信号 (ARCHITECTURE.md 6.2)"""
    close = _safe_get(row, "close")
    ma5 = _safe_get(row, "ma5", close)
    symbol = row.get("symbol", "")
    trade_date = row.get("trade_date", "")

    if current_return >= 0.15 and close < ma5:
        reason = f"全仓止盈: 浮盈{current_return*100:.1f}%, 收盘{close:.2f}跌破MA5({ma5:.2f})"
        return Signal(
            signal_id=_make_signal_id(symbol, trade_date, "SELL", "TAKE_PROFIT"),
            symbol=symbol, stock_name=_get_stock_name(row), sector=_get_sector(row),
            trade_date=trade_date, strategy="semiconductor_rotation",
            signal_type="SELL", sub_type="TAKE_PROFIT",
            score=_safe_get(row, "total_score"),
            price_trigger=close, reason=reason,
            stop_loss_price=close, take_profit_price=close,
            position_pct=1.0,
            risk_note="15%以上盈利且跌破MA5，建议全仓止盈",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    if current_return >= 0.10 and close < ma5:
        reason = f"半仓止盈: 浮盈{current_return*100:.1f}%, 收盘{close:.2f}跌破MA5({ma5:.2f})"
        return Signal(
            signal_id=_make_signal_id(symbol, trade_date, "SELL", "TAKE_PROFIT_HALF"),
            symbol=symbol, stock_name=_get_stock_name(row), sector=_get_sector(row),
            trade_date=trade_date, strategy="semiconductor_rotation",
            signal_type="SELL", sub_type="TAKE_PROFIT_HALF",
            score=_safe_get(row, "total_score"),
            price_trigger=close, reason=reason,
            stop_loss_price=close, take_profit_price=close,
            position_pct=0.5,
            risk_note="10%以上盈利且跌破MA5，建议半仓止盈",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    return None


# ============================================================
# 持有信号 (M1 修复)
# ============================================================

def check_hold(row: pd.Series) -> Signal:
    """
    观望持有信号：不满足买卖条件时输出 HOLD。

    ROADMAP Phase 2 验收标准3要求"能输出买入、卖出、持有信号"。
    """
    symbol = row.get("symbol", "")
    trade_date = row.get("trade_date", "")
    close = _safe_get(row, "close")
    total_score = _safe_get(row, "total_score")

    reason = (
        f"观望持有: 总分{total_score:.0f}, 收盘{close:.2f}, "
        f"未触发买入或卖出条件"
    )

    return Signal(
        signal_id=_make_signal_id(symbol, trade_date, "HOLD", "WATCH"),
        symbol=symbol,
        stock_name=_get_stock_name(row),
        sector=_get_sector(row),
        trade_date=trade_date,
        strategy="semiconductor_rotation",
        signal_type="HOLD",
        sub_type="WATCH",
        score=total_score,
        price_trigger=close,
        reason=reason,
        stop_loss_price=round(close * 0.92, 2),
        take_profit_price=round(close * 1.15, 2),
        position_pct=0.0,
        risk_note="观望，等待信号触发",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


# ============================================================
# 统一信号生成入口
# ============================================================

def generate_signals(
    df: pd.DataFrame,
    current_returns: Optional[dict] = None,
    include_hold: bool = True,
) -> List[Signal]:
    """
    为 DataFrame 中的每只股票生成买卖/持有信号。

    参数：
        df: 包含全部因子和评分的 DataFrame
        current_returns: 持仓股票的当前收益率 dict {symbol: return_pct}
        include_hold: 是否对不满足买卖条件的股票输出HOLD信号

    返回：
        信号列表
    """
    if df.empty:
        return []

    if current_returns is None:
        current_returns = {}

    signals = []

    for idx, row in df.iterrows():
        symbol = row.get("symbol", "")

        # 买入信号（优先级：BREAKOUT > PULLBACK > AMBUSH）
        sig = check_buy_breakout(row)
        if sig is None:
            sig = check_buy_pullback(row)
        if sig is None:
            sig = check_buy_ambush(row)
        if sig is not None:
            signals.append(sig)
            continue

        # 卖出信号（仅对持仓股票）
        current_return = current_returns.get(symbol, 0.0)

        sig = check_sell_stop_loss(row, current_return)
        if sig is None:
            sig = check_sell_trend_break(row)
        if sig is None:
            sig = check_sell_sentiment_fade(row)
        if sig is None:
            sig = check_sell_take_profit(row, current_return)
        if sig is not None:
            signals.append(sig)
            continue

        # 持有信号（不满足买卖条件时）
        if include_hold:
            signals.append(check_hold(row))

    buy_count = sum(1 for s in signals if s.signal_type == "BUY")
    sell_count = sum(1 for s in signals if s.signal_type == "SELL")
    hold_count = sum(1 for s in signals if s.signal_type == "HOLD")
    logger.info(
        f"Signal generation: {len(df)} stocks -> "
        f"{buy_count} BUY, {sell_count} SELL, {hold_count} HOLD"
    )
    return signals
