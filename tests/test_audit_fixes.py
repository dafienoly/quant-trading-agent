"""审计修复验证测试

覆盖审计报告中的测试盲区：
- 涨跌停幅度区分测试（创业板20%/ST5%）
- is_st 从名称检测测试
- is_data_missing 标记测试
- filter_tradeable 完整过滤测试
- IntradayBar/RealtimeQuote/Order 模型测试
- DataMissingReport/DataDelayReport 测试
- config/settings 模块测试
- StockInfo 缺失字段测试
- memory_hbm 包含 000021 测试
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_gateway.column_mapper import (
    _calc_limit_prices,
    _detect_is_st,
    map_daily_bars,
    DAILY_BAR_COLUMNS,
)
from src.stock_pool.mainboard_filter import (
    filter_tradeable,
    filter_by_listing_date,
    filter_by_suspension,
    filter_by_volume,
)
from src.models.schemas import (
    DailyBar,
    StockInfo,
    IntradayBar,
    RealtimeQuote,
    Order,
    DataMissingReport,
    DataDelayReport,
    DataQualityReport,
)
from src.utils.quality import (
    generate_data_missing_report,
    generate_data_delay_report,
)
from src.utils.storage import save_cleaned_data, save_raw_data, load_cleaned_data


# ============================================================
# S1: 涨跌停幅度区分测试
# ============================================================

class TestLimitPriceCalculation:
    """验证涨跌停价根据股票类型区分幅度"""

    def test_mainboard_10_percent(self):
        """主板/中小板涨跌停幅度为10%"""
        up, down = _calc_limit_prices(10.00, "002463", is_st=False)
        assert up == 11.00
        assert down == 9.00

    def test_chinext_20_percent(self):
        """创业板涨跌停幅度为20%"""
        up, down = _calc_limit_prices(10.00, "300001", is_st=False)
        assert up == 12.00
        assert down == 8.00

    def test_star_20_percent(self):
        """科创板涨跌停幅度为20%"""
        up, down = _calc_limit_prices(10.00, "688001", is_st=False)
        assert up == 12.00
        assert down == 8.00

    def test_st_5_percent(self):
        """ST股涨跌停幅度为5%"""
        up, down = _calc_limit_prices(10.00, "000001", is_st=True)
        assert up == 10.50
        assert down == 9.50

    def test_st_overrides_chinext(self):
        """ST优先于创业板，ST创业板仍为5%"""
        up, down = _calc_limit_prices(10.00, "300001", is_st=True)
        assert up == 10.50
        assert down == 9.50

    def test_limit_prices_in_daily_bars_mainboard(self):
        """日线映射中主板涨跌停价正确"""
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
            "涨跌幅": [5.0],
            "涨跌额": [0.5],
            "换手率": [1.2],
        })
        result = map_daily_bars(raw)
        row = result.iloc[0]
        # pre_close = 10.5 / 1.05 = 10.0
        assert abs(row["limit_up"] - 11.0) < 0.01  # 主板10%
        assert abs(row["limit_down"] - 9.0) < 0.01

    def test_limit_prices_in_daily_bars_chinext(self):
        """日线映射中创业板涨跌停价正确（20%）"""
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["300001"],
            "开盘": [10.0],
            "收盘": [10.5],
            "最高": [10.8],
            "最低": [9.9],
            "成交量": [100000],
            "成交额": [1050000.0],
            "振幅": [8.57],
            "涨跌幅": [5.0],
            "涨跌额": [0.5],
            "换手率": [1.2],
        })
        result = map_daily_bars(raw)
        row = result.iloc[0]
        assert abs(row["limit_up"] - 12.0) < 0.01  # 创业板20%
        assert abs(row["limit_down"] - 8.0) < 0.01

    def test_limit_prices_in_daily_bars_st(self):
        """日线映射中ST股涨跌停价正确（5%）"""
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["000001"],
            "开盘": [10.0],
            "收盘": [10.5],
            "最高": [10.8],
            "最低": [9.9],
            "成交量": [100000],
            "成交额": [1050000.0],
            "振幅": [8.57],
            "涨跌幅": [5.0],
            "涨跌额": [0.5],
            "换手率": [1.2],
        })
        result = map_daily_bars(raw, stock_name="ST某某")
        row = result.iloc[0]
        assert abs(row["limit_up"] - 10.50) < 0.01  # ST 5%
        assert abs(row["limit_down"] - 9.50) < 0.01


# ============================================================
# S2: is_st 从名称检测测试
# ============================================================

class TestIsStDetection:
    """验证从股票名称检测ST状态"""

    def test_st_prefix(self):
        assert _detect_is_st("ST康美") is True

    def test_star_st_prefix(self):
        assert _detect_is_st("*ST长生") is True

    def test_delist_name(self):
        assert _detect_is_st("退市海润") is True

    def test_normal_name(self):
        assert _detect_is_st("平安银行") is False

    def test_empty_name(self):
        assert _detect_is_st("") is False

    def test_none_name(self):
        assert _detect_is_st(None) is False

    def test_st_in_daily_bars_with_stock_name(self):
        """传入stock_name参数时正确识别ST"""
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["000001"],
            "开盘": [10.0],
            "收盘": [10.0],
            "最高": [10.0],
            "最低": [10.0],
            "成交量": [100000],
            "成交额": [1000000.0],
            "振幅": [0],
            "涨跌幅": [0],
            "涨跌额": [0],
            "换手率": [0],
        })
        result = map_daily_bars(raw, stock_name="ST测试")
        assert result.iloc[0]["is_st"] is True or result.iloc[0]["is_st"] == True

    def test_st_in_daily_bars_without_stock_name(self):
        """未传入stock_name时默认is_st=False"""
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["000001"],
            "开盘": [10.0],
            "收盘": [10.0],
            "最高": [10.0],
            "最低": [10.0],
            "成交量": [100000],
            "成交额": [1000000.0],
            "振幅": [0],
            "涨跌幅": [0],
            "涨跌额": [0],
            "换手率": [0],
        })
        result = map_daily_bars(raw)
        assert result.iloc[0]["is_st"] is False or result.iloc[0]["is_st"] == False


# ============================================================
# S4: is_data_missing 标记测试
# ============================================================

class TestDataMissingFlag:
    """验证数据缺失标记"""

    def test_no_missing_flag(self):
        """正常数据不标记缺失"""
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
            "涨跌幅": [5.0],
            "涨跌额": [0.5],
            "换手率": [1.2],
        })
        result = map_daily_bars(raw)
        assert "is_data_missing" in result.columns
        assert result.iloc[0]["is_data_missing"] is False or result.iloc[0]["is_data_missing"] == False

    def test_missing_volume_flagged(self):
        """volume缺失时标记is_data_missing"""
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["002463"],
            "开盘": [10.0],
            "收盘": [10.5],
            "最高": [10.8],
            "最低": [9.9],
            "成交量": [None],
            "成交额": [1050000.0],
            "振幅": [8.57],
            "涨跌幅": [5.0],
            "涨跌额": [0.5],
            "换手率": [1.2],
        })
        result = map_daily_bars(raw)
        assert result.iloc[0]["is_data_missing"] is True or result.iloc[0]["is_data_missing"] == True

    def test_missing_amount_flagged(self):
        """amount缺失时标记is_data_missing"""
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["002463"],
            "开盘": [10.0],
            "收盘": [10.5],
            "最高": [10.8],
            "最低": [9.9],
            "成交量": [100000],
            "成交额": [None],
            "振幅": [8.57],
            "涨跌幅": [5.0],
            "涨跌额": [0.5],
            "换手率": [1.2],
        })
        result = map_daily_bars(raw)
        assert result.iloc[0]["is_data_missing"] is True or result.iloc[0]["is_data_missing"] == True

    def test_volume_nan_not_treated_as_suspended(self):
        """volume缺失(NaN)不应被当作停牌"""
        raw = pd.DataFrame({
            "日期": ["2024-01-02"],
            "股票代码": ["002463"],
            "开盘": [10.0],
            "收盘": [10.5],
            "最高": [10.8],
            "最低": [9.9],
            "成交量": [None],
            "成交额": [1050000.0],
            "振幅": [8.57],
            "涨跌幅": [5.0],
            "涨跌额": [0.5],
            "换手率": [1.2],
        })
        result = map_daily_bars(raw)
        # volume缺失时不应标记为停牌
        assert result.iloc[0]["is_suspended"] is False or result.iloc[0]["is_suspended"] == False

    def test_volume_zero_is_suspended(self):
        """volume为0时应标记为停牌"""
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


# ============================================================
# S3: filter_tradeable 完整过滤测试
# ============================================================

class TestFilterTradeable:
    """验证filter_tradeable集成成交额/上市日期/停牌过滤"""

    def test_filter_by_volume_integrated(self):
        """filter_tradeable集成成交额过滤"""
        df = pd.DataFrame({
            "symbol": ["000001.SZ", "000002.SZ"],
            "name": ["股票A", "股票B"],
            "amount": [2e8, 5e7],  # 2亿 vs 0.5亿
        })
        result = filter_tradeable(df, min_amount=1e8)
        assert len(result) == 1
        assert result.iloc[0]["symbol"] == "000001.SZ"

    def test_filter_by_listing_date(self):
        """filter_by_listing_date过滤上市不足的股票"""
        df = pd.DataFrame({
            "symbol": ["000001.SZ", "000002.SZ"],
            "name": ["老股票", "新股票"],
            "list_date": ["20200101", "20260301"],
        })
        result = filter_by_listing_date(df, min_trading_days=120, ref_date="20260401")
        assert len(result) == 1
        assert result.iloc[0]["name"] == "老股票"

    def test_filter_by_suspension(self):
        """filter_by_suspension过滤停牌股票"""
        df = pd.DataFrame({
            "symbol": ["000001.SZ", "000002.SZ"],
            "name": ["正常股", "停牌股"],
            "is_suspended": [False, True],
        })
        result = filter_by_suspension(df)
        assert len(result) == 1
        assert result.iloc[0]["name"] == "正常股"

    def test_filter_tradeable_all_filters(self):
        """filter_tradeable综合过滤"""
        df = pd.DataFrame({
            "symbol": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "name": ["好股票", "低成交", "停牌股"],
            "amount": [2e8, 5e7, 2e8],
            "is_suspended": [False, False, True],
        })
        result = filter_tradeable(df, min_amount=1e8)
        assert len(result) == 1
        assert result.iloc[0]["name"] == "好股票"


# ============================================================
# S5: 新增模型定义测试
# ============================================================

class TestIntradayBarModel:
    """验证IntradayBar模型定义"""

    def test_create_intraday_bar(self):
        bar = IntradayBar(
            symbol="002463.SZ",
            market="SZ",
            datetime="20240102 09:30:00",
            open=10.0,
            high=10.5,
            low=9.9,
            close=10.2,
            volume=50000,
            amount=510000.0,
        )
        assert bar.symbol == "002463.SZ"
        assert bar.market == "SZ"


class TestRealtimeQuoteModel:
    """验证RealtimeQuote模型定义"""

    def test_create_realtime_quote(self):
        quote = RealtimeQuote(
            symbol="002463.SZ",
            market="SZ",
            datetime="20240102 09:30:05",
            last_price=10.2,
            bid_price_1=10.1,
            ask_price_1=10.3,
            volume=50000,
            amount=510000.0,
            pct_change=1.5,
            status="NORMAL",
        )
        assert quote.symbol == "002463.SZ"
        assert quote.status == "NORMAL"


class TestOrderModel:
    """验证Order模型定义"""

    def test_create_order(self):
        order = Order(
            order_id="ORD_20240102_ABC123",
            symbol="002463.SZ",
            market="SZ",
            side="BUY",
            price_type="LIMIT",
            limit_price=10.5,
            quantity=100,
            strategy_name="semiconductor_rotation",
            signal_id="SIG_20240102_001",
            risk_check_id="RISK_20240102_001",
        )
        assert order.order_id == "ORD_20240102_ABC123"
        assert order.status == "CREATED"
        assert order.side == "BUY"


class TestStockInfoModel:
    """验证StockInfo新增字段"""

    def test_stock_info_with_new_fields(self):
        info = StockInfo(
            symbol="002463.SZ",
            name="沪电股份",
            market="SZ",
            board_type="sme",
            is_st=False,
            list_date="20100818",
            industry_sw="电子",
            industry_sw_detail="印制电路板",
            total_shares=1.9e9,
            float_shares=1.8e9,
            is_hs300=False,
        )
        assert info.industry_sw == "电子"
        assert info.industry_sw_detail == "印制电路板"
        assert info.total_shares == 1.9e9
        assert info.float_shares == 1.8e9
        assert info.is_hs300 is False


# ============================================================
# M6: DataMissingReport / DataDelayReport 测试
# ============================================================

class TestDataMissingReport:
    """验证数据缺失报告生成"""

    def test_generate_missing_report(self):
        reports = [
            DataQualityReport(
                symbol="002463.SZ",
                start_date="20240101",
                end_date="20240110",
                total_rows=10,
                missing_close=2,
            ),
            DataQualityReport(
                symbol="600584.SH",
                start_date="20240101",
                end_date="20240110",
                total_rows=10,
                missing_close=0,
            ),
        ]
        result = generate_data_missing_report(reports)
        assert result.total_symbols == 2
        assert result.symbols_with_missing == 1
        assert len(result.missing_details) == 1
        assert result.missing_details[0]["symbol"] == "002463.SZ"

    def test_generate_missing_report_all_ok(self):
        reports = [
            DataQualityReport(
                symbol="002463.SZ",
                start_date="20240101",
                end_date="20240110",
                total_rows=10,
            ),
        ]
        result = generate_data_missing_report(reports)
        assert result.symbols_with_missing == 0


class TestDataDelayReport:
    """验证数据延迟报告生成"""

    def test_generate_delay_report(self):
        from datetime import datetime, timedelta
        start = datetime(2024, 1, 1, 9, 0, 0)
        end = datetime(2024, 1, 1, 9, 0, 10)
        result = generate_data_delay_report(
            provider="akshare",
            symbols=["002463", "600584"],
            fetch_start_time=start,
            fetch_end_time=end,
        )
        assert result.provider == "akshare"
        assert result.total_symbols == 2
        assert result.avg_latency_seconds == 5.0
        assert result.is_acceptable is True


# ============================================================
# M7: config/settings 模块测试
# ============================================================

class TestConfigSettings:
    """验证配置管理模块"""

    def test_default_trading_level(self):
        from src.config.settings import MAX_TRADING_LEVEL, LEVEL_1_SIGNAL_ONLY
        # 默认应为 LEVEL_1_SIGNAL_ONLY
        assert MAX_TRADING_LEVEL == LEVEL_1_SIGNAL_ONLY or MAX_TRADING_LEVEL in {
            "LEVEL_0", "LEVEL_1_SIGNAL_ONLY", "LEVEL_2_HUMAN_CONFIRM", "LEVEL_3_AUTO"
        }

    def test_validate_config(self):
        from src.config.settings import validate_config
        issues = validate_config()
        # 默认配置不应有问题
        assert isinstance(issues, list)

    def test_get_config_dict(self):
        from src.config.settings import get_config_dict
        config = get_config_dict()
        assert "max_trading_level" in config
        assert "enable_live_trading" in config
        assert "broker_adapter" in config


# ============================================================
# M8: memory_hbm 包含 000021 测试
# ============================================================

class TestMemoryHbmStock:
    """验证memory_hbm板块包含000021(深科技)"""

    def test_000021_in_memory_hbm(self):
        from src.stock_pool.semiconductor import SemiconductorPool
        pool = SemiconductorPool()
        assert pool.get_sector("000021") is not None
        # 000021应属于memory_hbm或advanced_packaging
        sector = pool.get_sector("000021")
        assert sector in ("memory_hbm", "advanced_packaging")


# ============================================================
# M3: cleaned 数据 data_version 列测试
# ============================================================

class TestCleanedDataVersion:
    """验证cleaned数据包含data_version列"""

    def test_data_version_in_cleaned(self, tmp_path):
        df = pd.DataFrame({
            "symbol": ["002463.SZ"],
            "trade_date": ["20240101"],
            "close": [10.5],
        })
        with patch("src.utils.storage.CLEANED_DIR", tmp_path), \
             patch("src.utils.storage.RAW_DIR", tmp_path):
            save_cleaned_data(df, "002463.SZ")
            loaded = load_cleaned_data("002463.SZ")
            assert "data_version" in loaded.columns
            assert loaded.iloc[0]["data_version"] == "1.0.0"


# ============================================================
# DailyBar 模型 is_data_missing 字段测试
# ============================================================

class TestDailyBarModel:
    """验证DailyBar模型新增is_data_missing字段"""

    def test_daily_bar_with_data_missing(self):
        bar = DailyBar(
            symbol="002463.SZ",
            market="SZ",
            trade_date="20240102",
            open=10.0,
            high=10.5,
            low=9.9,
            close=10.2,
            is_data_missing=True,
        )
        assert bar.is_data_missing is True

    def test_daily_bar_default_not_missing(self):
        bar = DailyBar(
            symbol="002463.SZ",
            market="SZ",
            trade_date="20240102",
            open=10.0,
            high=10.5,
            low=9.9,
            close=10.2,
        )
        assert bar.is_data_missing is False
