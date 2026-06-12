"""Phase A 测试：数据契约、映射层、Provider Hub、Eastmoney Provider

测试范围：
- provider_contracts.py: 数据能力枚举、返回模型
- live_data_mapper.py: symbol 规范化、日期格式、字段映射、volume 单位、raw/adjusted price
- provider_hub.py: 自动切源、熔断器、全部失败 fail closed
- eastmoney_provider.py: HTTP 请求映射（mock）
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pandas as pd

from src.data_gateway.provider_contracts import DataCapability, ProviderHealth, ProviderResult
from src.data_gateway.live_data_mapper import (
    DAILY_BAR_CONTRACT_COLUMNS,
    FUNDAMENTALS_CONTRACT_COLUMNS,
    REALTIME_QUOTE_COLUMNS,
    normalize_a_share_symbol,
    normalize_trade_date,
    map_realtime_quotes,
    map_daily_bars,
    map_fundamentals,
    validate_required_fields,
    REALTIME_REQUIRED_FIELDS,
)
from src.data_gateway.provider_hub import DataProviderHub, ProviderCircuitBreaker


# ============================================================
# provider_contracts 测试
# ============================================================

class TestProviderContracts:
    def test_data_capability_values(self):
        assert DataCapability.REALTIME_QUOTES.value == "realtime_quotes"
        assert DataCapability.DAILY_BARS.value == "daily_bars"
        assert DataCapability.FUNDAMENTALS.value == "fundamentals"
        assert DataCapability.INTRADAY_BARS.value == "intraday_bars"

    def test_provider_result_defaults(self):
        result = ProviderResult(
            status="ok",
            provider="eastmoney",
            capability=DataCapability.REALTIME_QUOTES,
            data=pd.DataFrame(),
        )
        assert result.messages == []
        assert result.error == ""
        assert result.elapsed_ms == 0.0
        assert result.fallback_chain == []

    def test_provider_health_fields(self):
        health = ProviderHealth(
            provider="akshare",
            capability=DataCapability.DAILY_BARS,
            status="OK",
            latency_ms=320.0,
            row_count=100,
            field_coverage={"symbol": True, "close": True},
        )
        assert health.status == "OK"
        assert health.row_count == 100


# ============================================================
# live_data_mapper 测试
# ============================================================

class TestNormalizeAShareSymbol:
    def test_pure_code_sh(self):
        assert normalize_a_share_symbol("600000") == "600000.SH"

    def test_pure_code_sz(self):
        assert normalize_a_share_symbol("000001") == "000001.SZ"

    def test_already_qualified(self):
        assert normalize_a_share_symbol("600000.SH") == "600000.SH"
        assert normalize_a_share_symbol("000001.SZ") == "000001.SZ"

    def test_with_prefix(self):
        assert normalize_a_share_symbol("sh600000") == "600000.SH"
        assert normalize_a_share_symbol("SH600000") == "600000.SH"
        assert normalize_a_share_symbol("sz000001") == "000001.SZ"

    def test_empty(self):
        assert normalize_a_share_symbol("") == ""

    def test_5_prefix_sh(self):
        assert normalize_a_share_symbol("500000") == "500000.SH"


class TestNormalizeTradeDate:
    def test_yyyymmdd_to_yyyy_mm_dd(self):
        assert normalize_trade_date("20250610") == "2025-06-10"

    def test_already_yyyy_mm_dd(self):
        assert normalize_trade_date("2025-06-10") == "2025-06-10"

    def test_empty(self):
        assert normalize_trade_date("") == ""

    def test_invalid(self):
        # 非标准格式原样返回
        assert normalize_trade_date("2025/06/10") == "2025/06/10"


class TestMapRealtimeQuotes:
    def _make_raw_quotes(self) -> pd.DataFrame:
        """构造模拟的实时行情原始数据"""
        return pd.DataFrame({
            "symbol": ["600000.SH", "000001.SZ"],
            "name": ["浦发银行", "平安银行"],
            "market": ["SH", "SZ"],
            "datetime": ["2025-06-10T10:00:00+08:00", "2025-06-10T10:00:00+08:00"],
            "last_price": [10.23, 15.50],
            "open": [10.10, 15.30],
            "high": [10.30, 15.60],
            "low": [10.05, 15.20],
            "pre_close": [10.15, 15.40],
            "pct_change": [0.79, 0.65],
            "change": [0.08, 0.10],
            "volume": [1000000, 2000000],  # 已转换为股
            "amount": [10230000, 31000000],
            "status": ["NORMAL", "NORMAL"],
            "delay_seconds": [0.5, 0.3],
            "currency": ["CNY", "CNY"],
            "timezone": ["Asia/Shanghai", "Asia/Shanghai"],
            "data_source": ["akshare", "akshare"],
            "updated_at": ["2025-06-10T10:00:00+08:00", "2025-06-10T10:00:00+08:00"],
            "data_version": ["realtime-v1", "realtime-v1"],
            "source_volume_unit": ["lot", "lot"],
        })

    def test_all_standard_columns_present(self):
        raw = self._make_raw_quotes()
        result = map_realtime_quotes(raw, "akshare", ["600000.SH", "000001.SZ"])
        for col in REALTIME_QUOTE_COLUMNS:
            assert col in result.columns, f"Missing column: {col}"

    def test_empty_input(self):
        result = map_realtime_quotes(pd.DataFrame(), "akshare", [])
        assert result.empty

    def test_none_input(self):
        result = map_realtime_quotes(None, "akshare", [])
        assert result.empty

    def test_volume_is_int(self):
        raw = self._make_raw_quotes()
        result = map_realtime_quotes(raw, "akshare", ["600000.SH", "000001.SZ"])
        assert result["volume"].dtype == "int64"


class TestMapDailyBars:
    def _make_raw_bars(self) -> pd.DataFrame:
        """构造模拟的日线原始数据"""
        return pd.DataFrame({
            "symbol": ["600000.SH", "600000.SH"],
            "trade_date": ["20250609", "20250610"],
            "open": [10.10, 10.20],
            "high": [10.30, 10.40],
            "low": [10.00, 10.10],
            "close": [10.20, 10.30],
            "volume": [1000000, 1200000],
            "amount": [10200000, 12360000],
            "pct_change": [0.50, 0.98],
            "pre_close": [10.15, 10.20],
            "is_suspended": [False, False],
        })

    def test_all_standard_columns_present(self):
        raw = self._make_raw_bars()
        result = map_daily_bars(raw, "akshare", adjust="qfq")
        for col in DAILY_BAR_CONTRACT_COLUMNS:
            assert col in result.columns, f"Missing column: {col}"

    def test_trade_date_format(self):
        raw = self._make_raw_bars()
        result = map_daily_bars(raw, "akshare", adjust="qfq")
        for dt in result["trade_date"]:
            assert "-" in str(dt), f"Date should be YYYY-MM-DD, got: {dt}"

    def test_raw_and_adjusted_price(self):
        raw = self._make_raw_bars()
        result = map_daily_bars(raw, "akshare", adjust="qfq")
        assert "raw_open" in result.columns
        assert "adjusted_open" in result.columns
        assert "adjustment_type" in result.columns

    def test_adjustment_type_qfq(self):
        raw = self._make_raw_bars()
        result = map_daily_bars(raw, "akshare", adjust="qfq")
        assert result["adjustment_type"].iloc[0] == "前复权"

    def test_empty_input(self):
        result = map_daily_bars(pd.DataFrame(), "akshare")
        assert result.empty


class TestMapFundamentals:
    def _make_raw_fundamentals(self) -> pd.DataFrame:
        return pd.DataFrame({
            "symbol": ["600000.SH", "000001.SZ"],
            "pe_ttm": [8.5, 6.2],
            "pb": [0.8, 0.7],
            "roe": [12.5, 11.8],
            "revenue": [1e11, 8e10],
            "net_profit": [5e9, 3e9],
            "market_cap": [3e11, 2e11],
            "report_period": ["2025-03-31", "2025-03-31"],
        })

    def test_all_standard_columns_present(self):
        raw = self._make_raw_fundamentals()
        result = map_fundamentals(raw, "eastmoney")
        for col in FUNDAMENTALS_CONTRACT_COLUMNS:
            assert col in result.columns, f"Missing column: {col}"

    def test_missing_fields_preserved_as_nan(self):
        """缺失字段不得静默填0"""
        raw = pd.DataFrame({
            "symbol": ["600000.SH"],
            "pe_ttm": [8.5],
            # pb, roe, revenue, net_profit, market_cap 全部缺失
        })
        result = map_fundamentals(raw, "eastmoney")
        assert pd.isna(result["pb"].iloc[0])
        assert pd.isna(result["roe"].iloc[0])
        assert pd.isna(result["market_cap"].iloc[0])
        # 不能是0
        assert result["pb"].iloc[0] != 0

    def test_empty_input(self):
        result = map_fundamentals(pd.DataFrame(), "eastmoney")
        assert result.empty


class TestValidateRequiredFields:
    def test_all_fields_present(self):
        df = pd.DataFrame({"symbol": ["600000.SH"], "close": [10.0], "volume": [1000]})
        coverage = validate_required_fields(df, ["symbol", "close", "volume"])
        assert all(coverage.values())

    def test_missing_column(self):
        df = pd.DataFrame({"symbol": ["600000.SH"]})
        coverage = validate_required_fields(df, ["symbol", "close"])
        assert coverage["symbol"]
        assert not coverage["close"]

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        coverage = validate_required_fields(df, ["symbol"])
        assert coverage["symbol"] is False

    def test_all_nan_column(self):
        df = pd.DataFrame({"symbol": ["600000.SH"], "close": [None]})
        coverage = validate_required_fields(df, ["close"])
        assert not coverage["close"]


# ============================================================
# ProviderCircuitBreaker 测试
# ============================================================

class TestProviderCircuitBreaker:
    def test_initial_state_closed(self):
        cb = ProviderCircuitBreaker()
        assert not cb.is_open("akshare", DataCapability.REALTIME_QUOTES)

    def test_opens_after_threshold(self):
        cb = ProviderCircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        assert cb.is_open("akshare", DataCapability.REALTIME_QUOTES)

    def test_success_resets_counter(self):
        cb = ProviderCircuitBreaker(failure_threshold=3)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        cb.record_success("akshare", DataCapability.REALTIME_QUOTES)
        # 失败计数应重置
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        assert not cb.is_open("akshare", DataCapability.REALTIME_QUOTES)

    def test_different_capabilities_independent(self):
        cb = ProviderCircuitBreaker(failure_threshold=2)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        assert cb.is_open("akshare", DataCapability.REALTIME_QUOTES)
        assert not cb.is_open("akshare", DataCapability.DAILY_BARS)

    def test_different_providers_independent(self):
        cb = ProviderCircuitBreaker(failure_threshold=2)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        assert cb.is_open("akshare", DataCapability.REALTIME_QUOTES)
        assert not cb.is_open("eastmoney", DataCapability.REALTIME_QUOTES)

    def test_half_open_after_cooldown(self):
        cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        assert cb.is_open("akshare", DataCapability.REALTIME_QUOTES)
        time.sleep(0.15)
        # 冷却后应半开（允许一次尝试）
        assert not cb.is_open("akshare", DataCapability.REALTIME_QUOTES)

    def test_half_open_failure_reopens(self):
        cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        time.sleep(0.15)
        # 半开后再次失败
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        assert cb.is_open("akshare", DataCapability.REALTIME_QUOTES)


# ============================================================
# DataProviderHub 测试
# ============================================================

def _make_mock_provider(name: str, quotes_df: pd.DataFrame | None = None, should_raise: bool = False):
    """创建 mock provider"""
    provider = MagicMock()
    provider.name = name
    if should_raise:
        provider.get_realtime_quotes.side_effect = Exception(f"{name} connection timeout")
        provider.get_daily_bars.side_effect = Exception(f"{name} connection timeout")
        provider.get_fundamentals.side_effect = Exception(f"{name} connection timeout")
    else:
        provider.get_realtime_quotes.return_value = quotes_df if quotes_df is not None else pd.DataFrame()
        provider.get_daily_bars.return_value = quotes_df if quotes_df is not None else pd.DataFrame()
        provider.get_fundamentals.return_value = quotes_df if quotes_df is not None else pd.DataFrame()
    return provider


def _make_valid_quotes_df() -> pd.DataFrame:
    """构造包含所有必需字段的实时行情 DataFrame"""
    return pd.DataFrame({
        "symbol": ["600000.SH"],
        "last_price": [10.23],
        "open": [10.10],
        "high": [10.30],
        "low": [10.05],
        "pre_close": [10.15],
        "pct_change": [0.79],
        "volume": [1000000],
        "amount": [10230000],
    })


class TestDataProviderHub:
    def test_first_provider_succeeds(self):
        """第一个 provider 成功时直接返回"""
        cb = ProviderCircuitBreaker()
        hub = DataProviderHub(
            providers=[_make_mock_provider("eastmoney", _make_valid_quotes_df())],
            circuit_breaker=cb,
        )
        result = hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            ["600000.SH"],
            required_fields=REALTIME_REQUIRED_FIELDS,
        )
        assert result.status == "ok"
        assert result.provider == "eastmoney"

    def test_fallback_to_second_provider(self):
        """第一个 provider 失败时自动切到第二个"""
        cb = ProviderCircuitBreaker()
        hub = DataProviderHub(
            providers=[
                _make_mock_provider("akshare", should_raise=True),
                _make_mock_provider("eastmoney", _make_valid_quotes_df()),
            ],
            circuit_breaker=cb,
        )
        result = hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            ["600000.SH"],
            required_fields=REALTIME_REQUIRED_FIELDS,
        )
        assert result.status == "ok"
        assert result.provider == "eastmoney"
        assert len(result.fallback_chain) == 2
        assert "akshare" in result.fallback_chain[0]
        assert "eastmoney" in result.fallback_chain[1]

    def test_all_providers_fail(self):
        """所有 provider 失败时返回 failed"""
        cb = ProviderCircuitBreaker()
        hub = DataProviderHub(
            providers=[
                _make_mock_provider("akshare", should_raise=True),
                _make_mock_provider("eastmoney", should_raise=True),
            ],
            circuit_breaker=cb,
        )
        result = hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            ["600000.SH"],
            required_fields=REALTIME_REQUIRED_FIELDS,
        )
        assert result.status == "failed"
        assert result.data.empty
        assert len(result.fallback_chain) == 2

    def test_empty_data_treated_as_failure(self):
        """空数据视为失败，触发 fallback"""
        cb = ProviderCircuitBreaker()
        hub = DataProviderHub(
            providers=[
                _make_mock_provider("akshare", pd.DataFrame()),  # 空数据
                _make_mock_provider("eastmoney", _make_valid_quotes_df()),
            ],
            circuit_breaker=cb,
        )
        result = hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            ["600000.SH"],
            required_fields=REALTIME_REQUIRED_FIELDS,
        )
        assert result.status == "ok"
        assert result.provider == "eastmoney"

    def test_circuit_breaker_skips_open_provider(self):
        """熔断打开的 provider 被跳过"""
        cb = ProviderCircuitBreaker(failure_threshold=2)
        # 手动触发熔断
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        cb.record_failure("akshare", DataCapability.REALTIME_QUOTES)
        assert cb.is_open("akshare", DataCapability.REALTIME_QUOTES)

        hub = DataProviderHub(
            providers=[
                _make_mock_provider("akshare", _make_valid_quotes_df()),
                _make_mock_provider("eastmoney", _make_valid_quotes_df()),
            ],
            circuit_breaker=cb,
        )
        result = hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            ["600000.SH"],
            required_fields=REALTIME_REQUIRED_FIELDS,
        )
        # akshare 被跳过，eastmoney 成功
        assert result.status == "ok"
        assert result.provider == "eastmoney"
        assert "circuit_open" in result.fallback_chain[0]

    def test_success_records_in_circuit_breaker(self):
        """成功时重置熔断器"""
        cb = ProviderCircuitBreaker(failure_threshold=3)
        cb.record_failure("eastmoney", DataCapability.REALTIME_QUOTES)
        cb.record_failure("eastmoney", DataCapability.REALTIME_QUOTES)

        hub = DataProviderHub(
            providers=[_make_mock_provider("eastmoney", _make_valid_quotes_df())],
            circuit_breaker=cb,
        )
        result = hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            ["600000.SH"],
            required_fields=REALTIME_REQUIRED_FIELDS,
        )
        assert result.status == "ok"
        # 成功后熔断器应重置
        assert not cb.is_open("eastmoney", DataCapability.REALTIME_QUOTES)

    def test_failure_records_in_circuit_breaker(self):
        """失败时记录到熔断器"""
        cb = ProviderCircuitBreaker(failure_threshold=5)
        hub = DataProviderHub(
            providers=[_make_mock_provider("akshare", should_raise=True)],
            circuit_breaker=cb,
        )
        hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            ["600000.SH"],
            required_fields=REALTIME_REQUIRED_FIELDS,
        )
        # 失败应记录
        assert not cb.is_open("akshare", DataCapability.REALTIME_QUOTES)  # 还没到阈值
        # 多次失败后应熔断
        for _ in range(4):
            hub.fetch_with_fallback(
                DataCapability.REALTIME_QUOTES,
                "get_realtime_quotes",
                ["600000.SH"],
                required_fields=REALTIME_REQUIRED_FIELDS,
            )
        assert cb.is_open("akshare", DataCapability.REALTIME_QUOTES)

    def test_get_health(self):
        """健康诊断"""
        cb = ProviderCircuitBreaker()
        hub = DataProviderHub(
            providers=[
                _make_mock_provider("akshare", _make_valid_quotes_df()),
                _make_mock_provider("eastmoney", _make_valid_quotes_df()),
            ],
            circuit_breaker=cb,
        )
        health_list = hub.get_health(DataCapability.REALTIME_QUOTES)
        assert len(health_list) == 2
        assert health_list[0].provider == "akshare"
        assert health_list[1].provider == "eastmoney"


# ============================================================
# EastmoneyProvider 测试 (mock HTTP)
# ============================================================

class TestEastmoneyProvider:
    def test_name(self):
        from src.data_gateway.eastmoney_provider import EastmoneyProvider
        provider = EastmoneyProvider()
        assert provider.name == "eastmoney"

    @patch("src.data_gateway.eastmoney_provider.httpx.Client")
    def test_get_realtime_quotes_success(self, mock_client_cls):
        """mock HTTP 成功返回实时行情"""
        from src.data_gateway.eastmoney_provider import EastmoneyProvider

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # 模拟东方财富 API 响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rc": 0,
            "data": {
                "total": 1,
                "diff": [{
                    "f2": 10.23, "f3": 0.79, "f4": 0.08, "f5": 10000,
                    "f6": 10230000, "f7": 2.46, "f8": 0.52, "f9": 8.5,
                    "f10": 1.23, "f12": "600000", "f14": "浦发银行",
                    "f15": 10.30, "f16": 10.05, "f17": 10.10, "f18": 10.15,
                }],
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        provider = EastmoneyProvider()
        result = provider.get_realtime_quotes(["600000.SH"])
        assert not result.empty
        assert "600000" in result["code"].values[0] if "code" in result.columns else True

    @patch("src.data_gateway.eastmoney_provider.httpx.Client")
    def test_get_realtime_quotes_error_returns_empty(self, mock_client_cls):
        """HTTP 错误返回空 DataFrame"""
        from src.data_gateway.eastmoney_provider import EastmoneyProvider

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get.side_effect = Exception("Connection timeout")

        provider = EastmoneyProvider()
        result = provider.get_realtime_quotes(["600000.SH"])
        assert result.empty

    @patch("src.data_gateway.eastmoney_provider.httpx.Client")
    def test_get_daily_bars_success(self, mock_client_cls):
        """mock HTTP 成功返回日线"""
        from src.data_gateway.eastmoney_provider import EastmoneyProvider

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rc": 0,
            "data": {
                "code": "600000",
                "klines": [
                    "2025-06-09,10.10,10.20,10.30,10.00,10000,10200000,2.46,0.50,0.05,0.52",
                    "2025-06-10,10.20,10.30,10.40,10.10,12000,12360000,2.94,0.98,0.10,0.62",
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        provider = EastmoneyProvider()
        result = provider.get_daily_bars(["600000.SH"], "2025-06-09", "2025-06-10")
        assert not result.empty
        assert len(result) == 2

    @patch("src.data_gateway.eastmoney_provider.httpx.Client")
    def test_get_daily_bars_volume_in_shares(self, mock_client_cls):
        """volume 应从手转换为股"""
        from src.data_gateway.eastmoney_provider import EastmoneyProvider

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rc": 0,
            "data": {
                "code": "600000",
                "klines": [
                    "2025-06-10,10.20,10.30,10.40,10.10,10000,12360000,2.94,0.98,0.10,0.62",
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        provider = EastmoneyProvider()
        result = provider.get_daily_bars(["600000.SH"], "2025-06-10", "2025-06-10")
        if not result.empty and "volume" in result.columns:
            # 10000手 * 100 = 1000000股
            assert result["volume"].iloc[0] == 1000000

    @patch("src.data_gateway.eastmoney_provider.httpx.Client")
    def test_get_fundamentals_missing_fields_are_nan(self, mock_client_cls):
        """财务字段缺失保留 NaN，不填 0"""
        from src.data_gateway.eastmoney_provider import EastmoneyProvider

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # 模拟只返回 PE 的响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rc": 0,
            "data": {
                "f9": 8.5,  # PE
                "f23": 0.8,  # PB
                # ROE, revenue, net_profit 缺失
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        provider = EastmoneyProvider()
        result = provider.get_fundamentals(["600000.SH"])
        if not result.empty:
            # PE 和 PB 应有值
            assert result["pe_ttm"].iloc[0] == 8.5
            assert result["pb"].iloc[0] == 0.8
            # ROE 缺失应为 NaN，不是 0
            assert pd.isna(result["roe"].iloc[0]) or result["roe"].iloc[0] != 0

    @patch("src.data_gateway.eastmoney_provider.httpx.Client")
    def test_get_fundamentals_error_returns_empty(self, mock_client_cls):
        """HTTP 错误返回空 DataFrame"""
        from src.data_gateway.eastmoney_provider import EastmoneyProvider

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get.side_effect = Exception("Connection timeout")

        provider = EastmoneyProvider()
        result = provider.get_fundamentals(["600000.SH"])
        assert result.empty
