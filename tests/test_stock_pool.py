"""测试股票池过滤"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.stock_pool.mainboard_filter import (
    is_mainboard,
    is_excluded,
    is_st,
    filter_mainboard,
)
from src.stock_pool.semiconductor import SemiconductorPool


class TestMainboardFilter:
    def test_mainboard_symbols(self):
        assert is_mainboard("000001") is True
        assert is_mainboard("001001") is True
        assert is_mainboard("002463") is True
        assert is_mainboard("600584") is True
        assert is_mainboard("601398") is True
        assert is_mainboard("603986") is True
        assert is_mainboard("605001") is True

    def test_excluded_symbols(self):
        assert is_excluded("300001") is True
        assert is_excluded("301001") is True
        assert is_excluded("688001") is True
        assert is_excluded("689001") is True
        assert is_excluded("000001") is False
        assert is_excluded("600584") is False

    def test_hk_symbol(self):
        assert is_mainboard("00981") is True

    def test_st_detection(self):
        assert is_st("*ST长生") is True
        assert is_st("ST康美") is True
        assert is_st("退市海润") is True
        assert is_st("平安银行") is False
        assert is_st("") is False
        assert is_st(None) is False

    def test_filter_mainboard_df(self):
        df = pd.DataFrame({
            "symbol": [
                "000001.SZ", "002463.SZ", "300001.SZ", "688001.SH",
                "600584.SH", "603986.SH", "00981.HK",
            ],
            "name": [
                "平安银行", "沪电股份", "特锐德", "华兴源创",
                "长电科技", "兆易创新", "中芯国际",
            ],
        })
        result = filter_mainboard(df)
        assert len(result) == 5
        assert "300001.SZ" not in result["symbol"].values
        assert "688001.SH" not in result["symbol"].values

    def test_filter_st_stocks(self):
        df = pd.DataFrame({
            "symbol": ["000001.SZ", "000002.SZ"],
            "name": ["*ST测试", "平安银行"],
        })
        result = filter_mainboard(df)
        assert len(result) == 1
        assert result.iloc[0]["name"] == "平安银行"


class TestSemiconductorPool:
    @pytest.fixture
    def pool(self):
        return SemiconductorPool()

    def test_pool_not_empty(self, pool):
        symbols = pool.get_symbols()
        assert len(symbols) > 0

    def test_known_stocks_in_pool(self, pool):
        symbols = pool.get_symbols()
        assert "002463" in symbols  # 沪电股份 PCB
        assert "600584" in symbols  # 长电科技 封测
        assert "002371" in symbols  # 北方华创 设备

    def test_sector_lookup(self, pool):
        assert pool.get_sector("002463") == "pcb_ccl"
        assert pool.get_sector("600584") == "advanced_packaging"
        assert pool.get_sector("002371") == "equipment_material"
        assert pool.get_sector("002281") == "optical_module_cpo"
        assert pool.get_sector("603986") == "memory_hbm"

    def test_sector_name(self, pool):
        name = pool.get_sector_name("002463")
        assert "PCB" in name or "CCL" in name

    def test_hk_stock_in_pool(self, pool):
        symbols = pool.get_symbols()
        assert "00981" in symbols

    def test_to_dataframe(self, pool):
        df = pool.to_dataframe()
        assert not df.empty
        assert "symbol" in df.columns
        assert "sector_key" in df.columns
        assert "sector_name" in df.columns

    def test_policy_weights(self, pool):
        weights = pool.get_policy_weights()
        assert weights["semiconductor_equipment"] == 100
        assert weights["pcb_ccl"] == 90
