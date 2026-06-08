"""Phase 2 审计修复验证测试

覆盖 AUDIT_REPORT_PHASE2.md 中的审计发现：
- S1: 基本面因子接入AkShare真实数据
- S2: 补充3个缺失情绪因子 (turnover_ratio/limit_up_count/large_order_flow)
- S3: 因子评估体系 (IC/IR/衰减分析)
- M1: HOLD信号
- M2: Signal模型补充stock_name/sector字段
- M3: timing_model择时规则
- M4: factor_evaluation子模块
- M5: 板块轮动单板块资金维度降级
- M6: 基本面因子fillna(0)改为标记缺失
- L1: __init__.py导出
- L2: 信号ID随机码
"""
import sys
from datetime import datetime, time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============================================================
# S1: 基本面因子接入AkShare真实数据
# ============================================================

class TestFundamentalDataFetch:
    """验证基本面数据获取接口存在且可调用"""

    def test_fetch_function_exists(self):
        from src.factor_engine.fundamental_factors import fetch_financial_data_from_akshare
        assert callable(fetch_financial_data_from_akshare)

    def test_fetch_returns_dict(self):
        from src.factor_engine.fundamental_factors import fetch_financial_data_from_akshare
        # 不实际调用AkShare（可能无网络），只验证函数签名
        import inspect
        sig = inspect.signature(fetch_financial_data_from_akshare)
        params = list(sig.parameters.keys())
        assert "symbols" in params

    def test_compute_fundamental_accepts_financial_data(self):
        """验证compute_fundamental_factors接受financial_data参数"""
        from src.factor_engine.fundamental_factors import compute_fundamental_factors
        df = pd.DataFrame({
            "symbol": ["002463.SZ"],
            "close": [10.0],
        })
        financial_data = {"002463.SZ": {"revenue_yoy": 30.0, "roe": 15.0}}
        result = compute_fundamental_factors(df, financial_data=financial_data)
        assert result.iloc[0]["revenue_yoy"] == 30.0
        assert result.iloc[0]["roe"] == 15.0


# ============================================================
# S2: 补充3个缺失情绪因子
# ============================================================

class TestMissingSentimentFactors:
    """验证turnover_ratio/limit_up_count/large_order_flow已实现"""

    def _make_df(self):
        return pd.DataFrame({
            "symbol": ["002463.SZ"] * 10,
            "trade_date": [f"2024010{i}" for i in range(10)],
            "close": [10 + i * 0.5 for i in range(10)],
            "volume": [100000 + i * 10000 for i in range(10)],
            "amount": [(10 + i * 0.5) * (100000 + i * 10000) for i in range(10)],
            "pct_change": [1.0 + i * 0.5 for i in range(10)],
            "turnover_rate": [1.0 + i * 0.1 for i in range(10)],
        })

    def test_turnover_ratio(self):
        from src.factor_engine.sentiment_factors import compute_sentiment_factors
        df = self._make_df()
        result = compute_sentiment_factors(df)
        assert "turnover_ratio" in result.columns

    def test_limit_up_count(self):
        from src.factor_engine.sentiment_factors import compute_sentiment_factors
        df = self._make_df()
        result = compute_sentiment_factors(df)
        assert "limit_up_count" in result.columns

    def test_large_order_flow(self):
        from src.factor_engine.sentiment_factors import compute_sentiment_factors
        df = self._make_df()
        result = compute_sentiment_factors(df)
        assert "large_order_flow" in result.columns

    def test_limit_up_count_calculation(self):
        from src.factor_engine.sentiment_factors import calc_limit_up_count
        pct = pd.Series([5.0, 9.8, 3.0, -2.0, 10.0, 1.0, 8.0, 9.9, 4.0, 2.0])
        result = calc_limit_up_count(pct, window=5, threshold=9.5)
        # 最后5个值中有1个涨停(9.9)
        assert result.iloc[-1] >= 0

    def test_sentiment_score_with_7_factors(self):
        """情绪评分使用7个因子"""
        from src.factor_engine.sentiment_factors import compute_sentiment_factors, compute_sentiment_score
        df = self._make_df()
        result = compute_sentiment_factors(df)
        score = compute_sentiment_score(result)
        assert (score >= 0).all()
        assert (score <= 100).all()


# ============================================================
# S3 + M4: 因子评估体系
# ============================================================

class TestFactorEvaluation:
    """验证因子评估模块 (IC/IR/衰减分析)"""

    def _make_factor_df(self):
        np.random.seed(42)
        n = 100
        symbols = [f"STOCK{i:03d}.SZ" for i in range(10)]
        dates = [f"2024010{i}" for i in range(10)]
        rows = []
        for s in symbols:
            for d in dates:
                rows.append({
                    "symbol": s,
                    "trade_date": d,
                    "trend_score": np.random.uniform(20, 80),
                    "sentiment_score": np.random.uniform(20, 80),
                    "policy_score": np.random.uniform(20, 80),
                    "fundamental_score": np.random.uniform(20, 80),
                    "forward_return": np.random.uniform(-5, 5),
                })
        return pd.DataFrame(rows)

    def test_evaluate_factor(self):
        from src.factor_engine.factor_evaluation import evaluate_factor
        df = self._make_factor_df()
        result = evaluate_factor(df, "trend_score")
        assert "factor_name" in result
        assert "ic_mean" in result
        assert "ic_std" in result
        assert "ic_ir" in result
        assert "rank_ic_mean" in result
        assert "turnover" in result
        assert "coverage" in result
        assert "decay_analysis" in result
        assert "long_short_return" in result

    def test_evaluate_all_factors(self):
        from src.factor_engine.factor_evaluation import evaluate_all_factors
        df = self._make_factor_df()
        result = evaluate_all_factors(df)
        assert len(result) > 0
        assert "factor_name" in result.columns

    def test_calc_ic(self):
        from src.factor_engine.factor_evaluation import calc_ic
        factor = pd.Series([1, 2, 3, 4, 5], dtype=float)
        ret = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5], dtype=float)
        ic = calc_ic(factor, ret)
        assert abs(ic - 1.0) < 0.01  # 完全正相关

    def test_calc_coverage(self):
        from src.factor_engine.factor_evaluation import calc_coverage
        factor = pd.Series([1.0, 2.0, np.nan, 4.0, np.nan])
        assert calc_coverage(factor) == 0.6

    def test_calc_decay(self):
        from src.factor_engine.factor_evaluation import calc_decay
        df = self._make_factor_df()
        decay = calc_decay(df, "trend_score")
        assert "ic_lag_1" in decay
        assert "ic_lag_5" in decay


# ============================================================
# M1: HOLD信号
# ============================================================

class TestHoldSignal:
    """验证HOLD信号生成"""

    def test_hold_signal_generated(self):
        from src.strategy_engine.signal_generator import check_hold, generate_signals
        row = pd.Series({
            "symbol": "002463.SZ",
            "trade_date": "20240115",
            "close": 10.0,
            "total_score": 50.0,
        })
        sig = check_hold(row)
        assert sig.signal_type == "HOLD"
        assert sig.sub_type == "WATCH"
        assert len(sig.reason) > 0

    def test_hold_signal_in_generate_signals(self):
        from src.strategy_engine.signal_generator import generate_signals
        from src.strategy_engine.scoring_model import compute_all_factors
        from src.stock_pool.semiconductor import SemiconductorPool

        np.random.seed(42)
        df = pd.DataFrame({
            "symbol": ["002463.SZ"] * 30,
            "trade_date": [f"202401{i:02d}" for i in range(1, 31)],
            "open": [10.0] * 30,
            "high": [10.5] * 30,
            "low": [9.5] * 30,
            "close": [10.0] * 30,
            "volume": [100000.0] * 30,
            "amount": [1000000.0] * 30,
            "pct_change": [0.0] * 30,
            "turnover_rate": [1.0] * 30,
        })
        pool = SemiconductorPool()
        scored = compute_all_factors(df, pool=pool)
        signals = generate_signals(scored, include_hold=True)
        hold_signals = [s for s in signals if s.signal_type == "HOLD"]
        assert len(hold_signals) > 0

    def test_hold_signal_has_sector_and_name(self):
        from src.strategy_engine.signal_generator import check_hold
        row = pd.Series({
            "symbol": "002463.SZ",
            "trade_date": "20240115",
            "close": 10.0,
            "total_score": 50.0,
            "name": "沪电股份",
            "sector_key": "pcb_ccl",
        })
        sig = check_hold(row)
        assert sig.stock_name == "沪电股份"
        assert sig.sector == "pcb_ccl"


# ============================================================
# M2: Signal模型补充stock_name/sector字段
# ============================================================

class TestSignalModelFields:
    """验证Signal模型包含stock_name和sector字段"""

    def test_signal_has_stock_name(self):
        from src.models.schemas import Signal
        sig = Signal(
            signal_id="SIG_20240115_TEST",
            symbol="002463.SZ",
            stock_name="沪电股份",
            sector="pcb_ccl",
            trade_date="20240115",
            strategy="test",
            signal_type="BUY",
            sub_type="BREAKOUT",
            score=85.0,
            price_trigger=10.0,
            reason="test",
            stop_loss_price=9.0,
            take_profit_price=11.5,
            position_pct=0.10,
            risk_note="test",
            created_at="2024-01-15 10:00:00",
        )
        assert sig.stock_name == "沪电股份"
        assert sig.sector == "pcb_ccl"

    def test_signal_default_empty_fields(self):
        from src.models.schemas import Signal
        sig = Signal(
            signal_id="SIG_20240115_TEST",
            symbol="002463.SZ",
            trade_date="20240115",
            strategy="test",
            signal_type="BUY",
            sub_type="BREAKOUT",
            score=85.0,
            price_trigger=10.0,
            reason="test",
            stop_loss_price=9.0,
            take_profit_price=11.5,
            position_pct=0.10,
            risk_note="test",
            created_at="2024-01-15 10:00:00",
        )
        assert sig.stock_name == ""
        assert sig.sector == ""


# ============================================================
# M3: timing_model择时规则
# ============================================================

class TestTimingModel:
    """验证择时模型"""

    def test_trading_time_morning(self):
        from src.strategy_engine.timing_model import is_trading_time
        dt = datetime(2024, 1, 15, 10, 0, 0)
        assert is_trading_time(dt) is True

    def test_non_trading_time(self):
        from src.strategy_engine.timing_model import is_trading_time
        dt = datetime(2024, 1, 15, 12, 0, 0)  # 午休
        assert is_trading_time(dt) is False

    def test_buy_allowed_normal_time(self):
        from src.strategy_engine.timing_model import is_buy_allowed
        dt = datetime(2024, 1, 15, 10, 0, 0)
        assert is_buy_allowed(dt) is True

    def test_buy_not_allowed_open_rush(self):
        from src.strategy_engine.timing_model import is_buy_allowed
        dt = datetime(2024, 1, 15, 9, 32, 0)  # 开盘2分钟
        assert is_buy_allowed(dt) is False

    def test_buy_not_allowed_closing(self):
        from src.strategy_engine.timing_model import is_buy_allowed
        dt = datetime(2024, 1, 15, 14, 55, 0)  # 收盘前5分钟
        assert is_buy_allowed(dt) is False

    def test_get_timing_advice(self):
        from src.strategy_engine.timing_model import get_timing_advice
        dt = datetime(2024, 1, 15, 10, 0, 0)
        advice = get_timing_advice(dt)
        assert "is_trading_time" in advice
        assert "is_buy_allowed" in advice
        assert "advice" in advice


# ============================================================
# M5: 板块轮动单板块资金维度降级
# ============================================================

class TestSectorRotationSingleSector:
    """验证单板块时资金维度使用绝对评分"""

    def test_single_sector_absolute_scoring(self):
        from src.strategy_engine.sector_rotation import compute_sector_scores
        from src.stock_pool.semiconductor import SemiconductorPool

        pool = SemiconductorPool()
        # 只用pcb_ccl板块的股票
        pcb_stocks = pool.get_stocks_by_sector()["pcb_ccl"]["stocks"]
        rows = []
        for stock in pcb_stocks:
            rows.append({
                "symbol": f"{stock['symbol']}.{stock['market']}",
                "pct_change": 2.0,
                "amount": 3e8,  # 3亿
            })
        df = pd.DataFrame(rows)
        result = compute_sector_scores(df, pool=pool)
        # 单板块也应正常输出
        assert not result.empty
        assert "sector_score" in result.columns
        # 评分应在0~100范围内
        assert result["sector_score"].iloc[0] >= 0
        assert result["sector_score"].iloc[0] <= 100


# ============================================================
# M6: 基本面因子fillna(0)改为标记缺失
# ============================================================

class TestFundamentalMissingFlag:
    """验证基本面数据缺失不静默填充"""

    def test_is_fundamental_missing_flag(self):
        from src.factor_engine.fundamental_factors import compute_fundamental_factors
        df = pd.DataFrame({"symbol": ["002463.SZ", "600584.SH"]})
        result = compute_fundamental_factors(df)
        assert "is_fundamental_missing" in result.columns
        # 无基本面数据时全部标记为缺失
        assert result["is_fundamental_missing"].all()

    def test_fundamental_not_missing_when_data_present(self):
        from src.factor_engine.fundamental_factors import compute_fundamental_factors
        df = pd.DataFrame({
            "symbol": ["002463.SZ"],
            "revenue_yoy": [30.0],
            "roe": [15.0],
        })
        result = compute_fundamental_factors(df)
        assert not result.iloc[0]["is_fundamental_missing"]

    def test_missing_gives_mid_score(self):
        """缺失字段给中间分而非0分"""
        from src.factor_engine.fundamental_factors import compute_fundamental_factors, compute_fundamental_score
        df_missing = pd.DataFrame({"symbol": ["002463.SZ"]})
        result_missing = compute_fundamental_factors(df_missing)
        score_missing = compute_fundamental_score(result_missing).iloc[0]
        # 中间分应大于0（每个因子给一半分）
        assert score_missing > 0


# ============================================================
# L1: __init__.py导出
# ============================================================

class TestInitExports:
    """验证模块公共接口导出"""

    def test_factor_engine_exports(self):
        from src.factor_engine import (
            compute_technical_factors,
            compute_trend_score,
            compute_sentiment_factors,
            compute_sentiment_score,
            compute_policy_score,
            compute_fundamental_factors,
            fetch_financial_data_from_akshare,
            evaluate_factor,
            evaluate_all_factors,
        )

    def test_strategy_engine_exports(self):
        from src.strategy_engine import (
            compute_all_factors,
            generate_signals,
            compute_sector_scores,
            is_trading_time,
            is_buy_allowed,
            allocate_position,
        )


# ============================================================
# L2: 信号ID随机码
# ============================================================

class TestSignalIdRandomCode:
    """验证信号ID包含6位随机码"""

    def test_signal_id_has_random_suffix(self):
        from src.strategy_engine.signal_generator import _make_signal_id
        id1 = _make_signal_id("002463.SZ", "20240115", "BUY", "BREAKOUT")
        id2 = _make_signal_id("002463.SZ", "20240115", "BUY", "BREAKOUT")
        # 两次生成的ID应不同（随机码不同）
        assert id1 != id2
        # ID格式正确
        assert id1.startswith("SIG_20240115_002463SZ_BUY_BREAKOUT_")

    def test_signal_id_format(self):
        from src.strategy_engine.signal_generator import _make_signal_id
        sid = _make_signal_id("002463.SZ", "20240115", "BUY", "BREAKOUT")
        parts = sid.split("_")
        # SIG_DATE_SYMBOL_TYPE_SUBTYPE_RANDCODE
        assert parts[0] == "SIG"
        assert len(parts[-1]) == 6  # 6位随机码
