"""测试列名映射和数据标准化"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_gateway.column_mapper import (
    symbol_to_market,
    to_standard_symbol,
    map_daily_bars,
    map_stock_list,
    DAILY_BAR_COLUMNS,
)


class TestSymbolMapping:
    def test_sh_symbol(self):
        assert symbol_to_market("600584") == "SH"
        assert symbol_to_market("601398") == "SH"
        assert symbol_to_market("603986") == "SH"

    def test_sz_symbol(self):
        assert symbol_to_market("000001") == "SZ"
        assert symbol_to_market("002463") == "SZ"
        assert symbol_to_market("300001") == "SZ"

    def test_hk_symbol(self):
        assert symbol_to_market("00981") == "HK"

    def test_standard_symbol(self):
        assert to_standard_symbol("600584") == "600584.SH"
        assert to_standard_symbol("002463") == "002463.SZ"
        assert to_standard_symbol("00981") == "00981.HK"


class TestDailyBarMapping:
    def test_basic_mapping(self):
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["002463"],
            "开盘": [10.0],
            "收盘": [10.5],
            "最高": [10.8],
            "最低": [9.9],
            "成交量": [100000],
            "成交额": [1050000.0],
            "振幅": [8.57],
            "涨跌幅": [3.96],
            "涨跌额": [0.4],
            "换手率": [1.2],
        })
        result = map_daily_bars(raw)

        assert not result.empty
        assert result.iloc[0]["symbol"] == "002463.SZ"
        assert result.iloc[0]["market"] == "SZ"
        assert result.iloc[0]["trade_date"] == "20240102"
        assert result.iloc[0]["open"] == 10.0
        assert result.iloc[0]["close"] == 10.5
        assert result.iloc[0]["volume"] == 100000

        for col in DAILY_BAR_COLUMNS:
            assert col in result.columns

    def test_empty_input(self):
        result = map_daily_bars(pd.DataFrame())
        assert result.empty
        for col in DAILY_BAR_COLUMNS:
            assert col in result.columns

    def test_pre_close_calculation(self):
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["600584"],
            "开盘": [30.0],
            "收盘": [31.5],
            "最高": [32.0],
            "最低": [29.5],
            "成交量": [50000],
            "成交额": [1575000.0],
            "振幅": [8.33],
            "涨跌幅": [5.0],
            "涨跌额": [1.5],
            "换手率": [0.8],
        })
        result = map_daily_bars(raw)
        pre_close = result.iloc[0]["pre_close"]
        assert abs(pre_close - 30.0) < 0.1

    def test_suspended_detection(self):
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["002463"],
            "开盘": [10.0],
            "收盘": [10.0],
            "最高": [10.0],
            "最低": [10.0],
            "成交量": [0],
            "成交额": [0],
            "振幅": [0],
            "涨跌幅": [0],
            "涨跌额": [0],
            "换手率": [0],
        })
        result = map_daily_bars(raw)
        assert result.iloc[0]["is_suspended"] is True or result.iloc[0]["is_suspended"] == True


class TestStockListMapping:
    def test_basic_mapping(self):
        raw = pd.DataFrame({
            "code": ["000001", "600584", "300001", "688001"],
            "name": ["平安银行", "长电科技", "特锐德", "华兴源创"],
        })
        result = map_stock_list(raw)

        assert len(result) == 4
        assert result.iloc[0]["board_type"] == "mainboard"
        assert result.iloc[1]["board_type"] == "mainboard"
        assert result.iloc[2]["board_type"] == "chinext"
        assert result.iloc[3]["board_type"] == "star"
        assert result.iloc[0]["market"] == "SZ"
        assert result.iloc[1]["market"] == "SH"
