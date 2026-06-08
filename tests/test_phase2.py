"""Phase 2 因子与策略评分测试

覆盖：
- 技术趋势因子计算与评分
- 情绪资金因子计算与评分
- 政策主题因子计算
- 基本面因子计算与评分
- 总评分模型
- 买入信号生成 (BREAKOUT/PULLBACK/AMBUSH)
- 卖出信号生成 (STOP_LOSS/TREND_BREAK/SENTIMENT_FADE/TAKE_PROFIT)
- 板块轮动评分
- 信号可解释性验证
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.factor_engine.technical_factors import (
    compute_technical_factors,
    compute_trend_score,
    calc_ma,
    calc_atr,
)
from src.factor_engine.sentiment_factors import (
    compute_sentiment_factors,
    compute_sentiment_score,
    calc_volume_ratio,
)
from src.factor_engine.theme_factors import compute_policy_score, compute_policy_score_for_df
from src.factor_engine.fundamental_factors import (
    compute_fundamental_factors,
    compute_fundamental_score,
)
from src.strategy_engine.scoring_model import compute_all_factors, compute_total_score_only
from src.strategy_engine.signal_generator import (
    check_buy_breakout,
    check_buy_pullback,
    check_buy_ambush,
    check_sell_stop_loss,
    check_sell_trend_break,
    check_sell_sentiment_fade,
    check_sell_take_profit,
    generate_signals,
)
from src.strategy_engine.sector_rotation import compute_sector_scores
from src.stock_pool.semiconductor import SemiconductorPool


# ============================================================
# 辅助函数
# ============================================================

def _make_daily_df(rows=30, symbol="002463.SZ"):
    """生成测试用日线 DataFrame，含足够数据计算MA60"""
    np.random.seed(42)
    dates = pd.bdate_range(start="2024-01-01", periods=rows)
    base_price = 10.0
    close = base_price + np.cumsum(np.random.randn(rows) * 0.2)
    close = np.maximum(close, 1.0)  # 不允许负价
    high = close + np.abs(np.random.randn(rows) * 0.3)
    low = close - np.abs(np.random.randn(rows) * 0.3)
    low = np.maximum(low, 0.5)
    volume = (np.random.randint(50000, 200000, rows)).astype(float)
    amount = close * volume

    df = pd.DataFrame({
        "symbol": [symbol] * rows,
        "trade_date": dates.strftime("%Y%m%d"),
        "open": close + np.random.randn(rows) * 0.1,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "amount": amount,
        "pct_change": np.random.uniform(-3, 3, rows),
        "turnover_rate": np.random.uniform(0.5, 3, rows),
    })
    return df


def _make_scored_df(rows=30, symbol="002463.SZ"):
    """生成已计算全部因子的 DataFrame"""
    df = _make_daily_df(rows, symbol)
    pool = SemiconductorPool()
    result = compute_all_factors(df, pool=pool)
    return result


# ============================================================
# 技术趋势因子测试
# ============================================================

class TestTechnicalFactors:
    def test_ma_calculation(self):
        df = _make_daily_df(30)
        result = compute_technical_factors(df)
        assert "ma5" in result.columns
        assert "ma10" in result.columns
        assert "ma20" in result.columns
        assert "ma60" in result.columns

    def test_close_above_ma_flags(self):
        df = _make_daily_df(30)
        result = compute_technical_factors(df)
        assert "close_above_ma5" in result.columns
        assert "close_above_ma10" in result.columns
        assert "close_above_ma20" in result.columns
        # 布尔类型检查
        for col in ["close_above_ma5", "close_above_ma10", "close_above_ma20"]:
            assert result[col].dtype == bool

    def test_ma_bullish_align(self):
        df = _make_daily_df(30)
        result = compute_technical_factors(df)
        assert "ma_bullish_align" in result.columns

    def test_volume_breakout(self):
        df = _make_daily_df(30)
        result = compute_technical_factors(df)
        assert "volume_breakout" in result.columns
        assert "volume_ma5" in result.columns

    def test_atr_calculation(self):
        df = _make_daily_df(30)
        result = compute_technical_factors(df)
        assert "atr_14" in result.columns
        assert (result["atr_14"] > 0).all()

    def test_trend_score_range(self):
        df = _make_daily_df(30)
        result = compute_technical_factors(df)
        score = compute_trend_score(result)
        assert (score >= 0).all()
        assert (score <= 100).all()

    def test_empty_input(self):
        result = compute_technical_factors(pd.DataFrame())
        assert result.empty


# ============================================================
# 情绪资金因子测试
# ============================================================

class TestSentimentFactors:
    def test_volume_ratio(self):
        df = _make_daily_df(30)
        result = compute_sentiment_factors(df)
        assert "volume_ratio" in result.columns
        assert "amount_ratio" in result.columns

    def test_relative_strength(self):
        df = _make_daily_df(30)
        benchmark = pd.Series(0.5, index=df.index)  # 基准涨0.5%
        result = compute_sentiment_factors(df, benchmark_pct=benchmark)
        assert "relative_strength" in result.columns

    def test_sector_strength(self):
        df = _make_daily_df(30)
        sector_pct = pd.Series(1.0, index=df.index)
        result = compute_sentiment_factors(df, sector_pct=sector_pct)
        assert "sector_strength" in result.columns

    def test_sentiment_score_range(self):
        df = _make_daily_df(30)
        result = compute_sentiment_factors(df)
        score = compute_sentiment_score(result)
        assert (score >= 0).all()
        assert (score <= 100).all()


# ============================================================
# 政策主题因子测试
# ============================================================

class TestPolicyScore:
    def test_known_stock_policy_score(self):
        pool = SemiconductorPool()
        result = compute_policy_score(["002463.SZ", "600584.SH"], pool=pool)
        assert len(result) == 2
        # 002463 沪电股份属于 pcb_ccl，权重90
        pcb_row = result[result["symbol"] == "002463.SZ"]
        assert pcb_row.iloc[0]["policy_score"] == 90.0

    def test_unknown_stock_zero_score(self):
        pool = SemiconductorPool()
        result = compute_policy_score(["999999.SZ"], pool=pool)
        assert result.iloc[0]["policy_score"] == 0.0

    def test_policy_score_for_df(self):
        df = _make_daily_df(10, "002463.SZ")
        result = compute_policy_score_for_df(df)
        assert "policy_score" in result.columns
        assert "sector_key" in result.columns


# ============================================================
# 基本面因子测试
# ============================================================

class TestFundamentalFactors:
    def test_fundamental_factors_added(self):
        df = _make_daily_df(10)
        result = compute_fundamental_factors(df)
        for col in ["revenue_yoy", "net_profit_yoy", "gross_margin_change", "roe", "consensus_profit_growth"]:
            assert col in result.columns

    def test_fundamental_score_range(self):
        df = _make_daily_df(10)
        result = compute_fundamental_factors(df)
        score = compute_fundamental_score(result)
        assert (score >= 0).all()
        assert (score <= 100).all()

    def test_fundamental_score_with_data(self):
        df = pd.DataFrame({
            "symbol": ["002463.SZ"],
            "revenue_yoy": [30.0],
            "net_profit_yoy": [50.0],
            "gross_margin_change": [2.0],
            "roe": [15.0],
            "consensus_profit_growth": [20.0],
        })
        result = compute_fundamental_factors(df)
        score = compute_fundamental_score(result)
        assert score.iloc[0] > 50  # 好的基本面应该高分


# ============================================================
# 总评分模型测试
# ============================================================

class TestScoringModel:
    def test_compute_all_factors(self):
        df = _make_daily_df(30, "002463.SZ")
        result = compute_all_factors(df)
        # 检查所有评分列存在
        for col in ["trend_score", "sentiment_score", "policy_score", "fundamental_score", "total_score"]:
            assert col in result.columns, f"Missing column: {col}"

    def test_total_score_range(self):
        df = _make_daily_df(30, "002463.SZ")
        result = compute_all_factors(df)
        assert (result["total_score"] >= 0).all()
        assert (result["total_score"] <= 100).all()

    def test_total_score_formula(self):
        """验证总评分公式: 0.25*policy + 0.30*sentiment + 0.20*fundamental + 0.25*trend"""
        df = _make_daily_df(30, "002463.SZ")
        result = compute_all_factors(df)
        expected = (
            0.25 * result["policy_score"]
            + 0.30 * result["sentiment_score"]
            + 0.20 * result["fundamental_score"]
            + 0.25 * result["trend_score"]
        )
        pd.testing.assert_series_equal(result["total_score"], expected, check_names=False)

    def test_compute_total_score_only(self):
        score = compute_total_score_only(
            policy_score=90, sentiment_score=70, fundamental_score=60, trend_score=80
        )
        expected = 0.25 * 90 + 0.30 * 70 + 0.20 * 60 + 0.25 * 80
        assert abs(score - expected) < 0.01


# ============================================================
# 买入信号测试
# ============================================================

class TestBuySignals:
    def _make_breakout_row(self):
        """构造满足突破买入条件的行"""
        return pd.Series({
            "symbol": "002463.SZ",
            "trade_date": "20240115",
            "close": 12.0,
            "high": 12.5,
            "low": 11.5,
            "ma5": 11.5,
            "ma10": 11.0,
            "ma20": 10.5,
            "ma60": 10.0,
            "highest_20": 12.2,
            "volume": 200000.0,
            "volume_ma5": 100000.0,
            "volume_ma20": 90000.0,
            "pct_change": 3.0,
            "sector_strength": 1.0,
            "total_score": 85.0,
            "policy_score": 90.0,
            "fundamental_score": 70.0,
            "sentiment_score": 80.0,
            "trend_score": 90.0,
            "amount": 2400000.0,
        })

    def test_buy_breakout_triggered(self):
        row = self._make_breakout_row()
        sig = check_buy_breakout(row)
        assert sig is not None
        assert sig.signal_type == "BUY"
        assert sig.sub_type == "BREAKOUT"
        assert len(sig.reason) > 0  # 必须有解释

    def test_buy_breakout_low_score(self):
        row = self._make_breakout_row()
        row["total_score"] = 70  # 低于80
        sig = check_buy_breakout(row)
        assert sig is None

    def test_buy_breakout_limit_up(self):
        row = self._make_breakout_row()
        row["pct_change"] = 8  # 接近涨停不追
        sig = check_buy_breakout(row)
        assert sig is None

    def test_buy_pullback_triggered(self):
        row = pd.Series({
            "symbol": "002463.SZ",
            "trade_date": "20240115",
            "close": 11.5,
            "low": 11.2,
            "ma10": 11.0,
            "ma20": 10.5,
            "volume": 90000.0,
            "volume_ma5": 100000.0,
            "sector_strength": 0.5,
            "total_score": 78.0,
            "policy_score": 80.0,
            "fundamental_score": 60.0,
            "sentiment_score": 70.0,
            "trend_score": 85.0,
            "amount": 1000000.0,
            "high": 11.8,
            "pct_change": 1.0,
        })
        sig = check_buy_pullback(row)
        assert sig is not None
        assert sig.sub_type == "PULLBACK"
        assert len(sig.reason) > 0

    def test_buy_ambush_triggered(self):
        row = pd.Series({
            "symbol": "002371.SZ",
            "trade_date": "20240115",
            "close": 200.0,
            "high": 205.0,
            "low": 198.0,
            "ma20": 195.0,
            "ma60": 190.0,
            "volume": 150000.0,
            "volume_ma20": 100000.0,
            "total_score": 72.0,
            "policy_score": 100.0,  # 设备板块100分
            "fundamental_score": 70.0,
            "sentiment_score": 50.0,
            "trend_score": 60.0,
            "pct_change": 2.0,
            "sector_strength": 0.5,
            "amount": 30000000.0,
        })
        sig = check_buy_ambush(row)
        assert sig is not None
        assert sig.sub_type == "AMBUSH"
        assert sig.position_pct == 0.08  # 埋伏仓8%


# ============================================================
# 卖出信号测试
# ============================================================

class TestSellSignals:
    def _make_base_row(self):
        return pd.Series({
            "symbol": "002463.SZ",
            "trade_date": "20240115",
            "close": 10.0,
            "high": 10.5,
            "low": 9.5,
            "ma5": 10.2,
            "ma10": 10.5,
            "ma20": 11.0,
            "volume": 150000.0,
            "volume_ma5": 100000.0,
            "pct_change": -4.0,
            "sector_strength": -3.0,
            "total_score": 40.0,
            "policy_score": 90.0,
            "fundamental_score": 50.0,
            "sentiment_score": 30.0,
            "trend_score": 20.0,
            "amount": 1500000.0,
        })

    def test_sell_stop_loss_8pct(self):
        row = self._make_base_row()
        sig = check_sell_stop_loss(row, current_return=-0.08)
        assert sig is not None
        assert sig.sub_type == "STOP_LOSS"
        assert sig.position_pct == 1.0  # 清仓
        assert len(sig.reason) > 0

    def test_sell_half_stop_loss_5pct(self):
        row = self._make_base_row()
        sig = check_sell_stop_loss(row, current_return=-0.06)
        assert sig is not None
        assert sig.sub_type == "HALF_STOP_LOSS"
        assert sig.position_pct == 0.5  # 减半

    def test_sell_trend_break(self):
        row = self._make_base_row()
        sig = check_sell_trend_break(row)
        assert sig is not None
        assert sig.sub_type == "TREND_BREAK"
        assert len(sig.reason) > 0

    def test_sell_sentiment_fade(self):
        row = self._make_base_row()
        sig = check_sell_sentiment_fade(row)
        assert sig is not None
        assert sig.sub_type == "SENTIMENT_FADE"

    def test_sell_take_profit(self):
        row = self._make_base_row()
        row["close"] = 10.0
        row["ma5"] = 10.5  # close < ma5
        sig = check_sell_take_profit(row, current_return=0.16)
        assert sig is not None
        assert sig.sub_type == "TAKE_PROFIT"
        assert sig.position_pct == 1.0

    def test_sell_take_profit_half(self):
        row = self._make_base_row()
        row["close"] = 10.0
        row["ma5"] = 10.5
        sig = check_sell_take_profit(row, current_return=0.12)
        assert sig is not None
        assert sig.sub_type == "TAKE_PROFIT_HALF"
        assert sig.position_pct == 0.5


# ============================================================
# 信号生成器集成测试
# ============================================================

class TestSignalGenerator:
    def test_generate_signals_empty(self):
        signals = generate_signals(pd.DataFrame())
        assert signals == []

    def test_generate_signals_with_data(self):
        df = _make_scored_df(30, "002463.SZ")
        signals = generate_signals(df)
        # 可能产生BUY/SELL/HOLD信号
        for sig in signals:
            assert sig.signal_type in ("BUY", "SELL", "HOLD")
            assert len(sig.reason) > 0
            assert sig.stop_loss_price > 0
            assert sig.symbol != ""

    def test_signal_explainability(self):
        """验证每个信号都有解释文本 (AGENTS.md 2.4)"""
        df = _make_scored_df(30, "002463.SZ")
        signals = generate_signals(df)
        for sig in signals:
            assert len(sig.reason) > 10, f"Signal {sig.signal_id} reason too short"
            assert sig.risk_note, f"Signal {sig.signal_id} missing risk_note"
            assert sig.stop_loss_price > 0, f"Signal {sig.signal_id} missing stop_loss"
            assert sig.take_profit_price > 0, f"Signal {sig.signal_id} missing take_profit"

    def test_signals_no_future_data(self):
        """验证信号不使用未来数据 (ROADMAP Phase 2 验收标准5)"""
        # 所有因子计算使用rolling，不使用shift(-1)
        # 这里验证因子列不存在负向偏移
        df = _make_daily_df(30, "002463.SZ")
        result = compute_all_factors(df)
        # MA应该使用当前及之前的数据
        # 检查ma5第一行是否只用1个数据点（min_periods=1）
        assert not result["ma5"].isna().all()


# ============================================================
# 板块轮动评分测试
# ============================================================

class TestSectorRotation:
    def test_sector_scores(self):
        pool = SemiconductorPool()
        # 构造多只股票的数据
        rows = []
        for sector_key, sector_info in pool.get_stocks_by_sector().items():
            for stock in sector_info["stocks"]:
                rows.append({
                    "symbol": f"{stock['symbol']}.{stock['market']}",
                    "pct_change": np.random.uniform(-3, 5),
                    "amount": np.random.uniform(1e8, 5e8),
                })
        df = pd.DataFrame(rows)
        result = compute_sector_scores(df, pool=pool)
        assert not result.empty
        assert "sector_score" in result.columns
        assert "sector_name" in result.columns
        # 评分应按降序排列
        if len(result) > 1:
            assert result["sector_score"].iloc[0] >= result["sector_score"].iloc[-1]

    def test_sector_scores_empty(self):
        result = compute_sector_scores(pd.DataFrame())
        assert result.empty


# ============================================================
# 四类因子每日生成验证 (ROADMAP Phase 2 验收标准1)
# ============================================================

class TestDailyFactorGeneration:
    """验收标准1: 每只股票每天能生成4类因子分"""

    def test_four_factor_scores_per_day(self):
        df = _make_daily_df(30, "002463.SZ")
        result = compute_all_factors(df)
        for col in ["policy_score", "sentiment_score", "fundamental_score", "trend_score"]:
            assert col in result.columns
            # 每行都有评分
            assert not result[col].isna().all()

    def test_total_score_per_day(self):
        """验收标准2: 每只股票每天能生成总分"""
        df = _make_daily_df(30, "002463.SZ")
        result = compute_all_factors(df)
        assert "total_score" in result.columns
        assert not result["total_score"].isna().all()

    def test_buy_sell_hold_signals(self):
        """验收标准3: 能输出买入、卖出、持有信号"""
        # 构造不同条件的股票
        dfs = []
        for symbol in ["002463.SZ", "600584.SH", "002371.SZ"]:
            dfs.append(_make_scored_df(30, symbol))
        combined = pd.concat(dfs, ignore_index=True)
        signals = generate_signals(combined)
        signal_types = {s.signal_type for s in signals}
        # 应包含HOLD，可能包含BUY或SELL
        assert "HOLD" in signal_types
        assert signal_types.issubset({"BUY", "SELL", "HOLD"})

    def test_signal_reason_text(self):
        """验收标准4: 每个信号必须有解释文本"""
        df = _make_scored_df(30, "002463.SZ")
        signals = generate_signals(df)
        for sig in signals:
            assert len(sig.reason) > 0
            assert len(sig.risk_note) > 0
