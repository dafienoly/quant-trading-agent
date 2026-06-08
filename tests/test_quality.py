"""测试数据质量检查"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.quality import (
    check_completeness,
    check_price_validity,
    check_limit_status,
    check_continuity,
    generate_quality_report,
)


def _make_daily_df(rows=10, missing=0, invalid=0):
    """生成测试用日线 DataFrame"""
    data = {
        "trade_date": [f"2024010{i+1}" if i < 9 else f"202401{i+1}" for i in range(rows)],
        "open": [10.0] * rows,
        "high": [10.5] * rows,
        "low": [9.5] * rows,
        "close": [10.2] * rows,
        "volume": [100000] * rows,
        "pct_change": [1.5] * rows,
        "is_suspended": [False] * rows,
    }
    df = pd.DataFrame(data)

    for i in range(missing):
        if i < rows:
            df.loc[i, "close"] = None

    for i in range(invalid):
        idx = rows - 1 - i
        if idx >= 0:
            df.loc[idx, "high"] = 9.0
            df.loc[idx, "low"] = 11.0

    return df


class TestCompleteness:
    def test_no_missing(self):
        df = _make_daily_df(rows=10, missing=0)
        result = check_completeness(df)
        assert result["missing_close"] == 0
        assert result["missing_open"] == 0

    def test_with_missing(self):
        df = _make_daily_df(rows=10, missing=3)
        result = check_completeness(df)
        assert result["missing_close"] == 3


class TestPriceValidity:
    def test_valid_prices(self):
        df = _make_daily_df(rows=5, invalid=0)
        assert check_price_validity(df) == 0

    def test_invalid_high_low(self):
        df = _make_daily_df(rows=5, invalid=2)
        assert check_price_validity(df) >= 2


class TestLimitStatus:
    def test_limit_up_detection(self):
        df = _make_daily_df(rows=5)
        df.loc[0, "pct_change"] = 10.0
        df.loc[1, "pct_change"] = 9.9
        up, down = check_limit_status(df)
        assert up == 2

    def test_limit_down_detection(self):
        df = _make_daily_df(rows=5)
        df.loc[0, "pct_change"] = -10.0
        up, down = check_limit_status(df)
        assert down == 1


class TestContinuity:
    def test_no_gaps(self):
        trade_dates = ["20240101", "20240102", "20240103"]
        df = pd.DataFrame({"trade_date": trade_dates})
        assert check_continuity(df, trade_dates) == 0

    def test_with_gaps(self):
        trade_dates = ["20240101", "20240102", "20240103", "20240104", "20240105"]
        df = pd.DataFrame({"trade_date": ["20240101", "20240105"]})
        assert check_continuity(df, trade_dates) == 3


class TestQualityReport:
    def test_acceptable_report(self):
        df = _make_daily_df(rows=50)
        report = generate_quality_report(df, "002463.SZ")
        assert report.is_acceptable
        assert report.symbol == "002463.SZ"
        assert report.total_rows == 50
        assert len(report.issues) == 0

    def test_unacceptable_missing_data(self):
        df = _make_daily_df(rows=50, missing=5)
        trade_dates = [f"2024010{i+1}" if i < 9 else f"202401{i+1}" for i in range(50)]
        report = generate_quality_report(df, "002463.SZ", trade_dates)
        assert report.missing_close == 5
        assert not report.is_acceptable
