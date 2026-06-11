"""Phase B 测试：LiveDataService、DataHealthGate、ProviderDiagnosticsService、Live Data API

测试范围：
- data_health_gate.py: 健康门禁决策
- live_data_service.py: 产品闭环数据入口
- provider_diagnostics_service.py: Provider 诊断
- product_routes.py: /product/live-data/* API
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data_gateway.provider_contracts import DataCapability, ProviderResult
from src.product_app.data_health_gate import DataHealthGate


# ============================================================
# DataHealthGate 测试
# ============================================================

class TestDataHealthGate:
    def setup_method(self):
        self.gate = DataHealthGate()

    def test_all_ok(self):
        """行情和日线都正常"""
        decision = self.gate.evaluate(
            quotes_result={"data_status": "OK", "max_delay_seconds": 0.5},
            daily_bars_result={"data_status": "OK"},
            fundamentals_result={"data_status": "OK"},
            is_demo=False,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert decision.data_status == "OK"
        assert decision.allow_research
        assert decision.allow_signal
        assert decision.allow_order_draft
        assert decision.risk_level == "OK"

    def test_demo_mode_blocks_signal(self):
        """Demo 模式下禁止信号和订单"""
        decision = self.gate.evaluate(
            quotes_result={"data_status": "OK"},
            daily_bars_result={"data_status": "OK"},
            fundamentals_result={"data_status": "OK"},
            is_demo=True,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert decision.allow_research  # 教学允许
        assert not decision.allow_signal  # 信号禁止
        assert not decision.allow_order_draft  # 订单禁止

    def test_quotes_failed_blocks_all(self):
        """行情全部失败时全部阻断"""
        decision = self.gate.evaluate(
            quotes_result={"data_status": "FAILED"},
            daily_bars_result={"data_status": "OK"},
            fundamentals_result={"data_status": "OK"},
            is_demo=False,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert decision.data_status == "FAILED"
        assert not decision.allow_research
        assert not decision.allow_signal
        assert not decision.allow_order_draft
        assert decision.risk_level == "BLOCK"

    def test_daily_bars_failed_blocks_all(self):
        """日线全部失败时全部阻断"""
        decision = self.gate.evaluate(
            quotes_result={"data_status": "OK"},
            daily_bars_result={"data_status": "FAILED"},
            fundamentals_result={"data_status": "OK"},
            is_demo=False,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert decision.data_status == "FAILED"
        assert not decision.allow_signal

    def test_fundamentals_warn_allows_signal(self):
        """财务部分缺失允许信号但标注警告"""
        decision = self.gate.evaluate(
            quotes_result={"data_status": "OK"},
            daily_bars_result={"data_status": "OK"},
            fundamentals_result={"data_status": "WARN"},
            is_demo=False,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert decision.data_status == "WARN"
        assert decision.allow_research
        assert decision.allow_signal  # 允许但带警告
        assert decision.risk_level == "WARN"

    def test_delay_exceeds_level1_threshold(self):
        """LEVEL_1 延迟超过 120 秒阻断信号"""
        decision = self.gate.evaluate(
            quotes_result={"data_status": "OK", "provider_delay": 150.0},
            daily_bars_result={"data_status": "OK"},
            fundamentals_result={"data_status": "OK"},
            is_demo=False,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert decision.allow_research
        assert not decision.allow_signal
        assert not decision.allow_order_draft

    def test_delay_within_level1_threshold(self):
        """LEVEL_1 延迟在阈值内允许信号"""
        decision = self.gate.evaluate(
            quotes_result={"data_status": "OK", "provider_delay": 60.0},
            daily_bars_result={"data_status": "OK"},
            fundamentals_result={"data_status": "OK"},
            is_demo=False,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert decision.allow_signal

    def test_delay_exceeds_level2_threshold(self):
        """LEVEL_2 延迟超过 60 秒阻断信号"""
        decision = self.gate.evaluate(
            quotes_result={"data_status": "OK", "provider_delay": 80.0},
            daily_bars_result={"data_status": "OK"},
            fundamentals_result={"data_status": "OK"},
            is_demo=False,
            trading_mode="LEVEL_2_HUMAN_CONFIRM",
        )
        assert not decision.allow_signal

    def test_messages_populated(self):
        """决策消息非空"""
        decision = self.gate.evaluate(
            quotes_result={"data_status": "FAILED"},
            daily_bars_result={"data_status": "OK"},
            fundamentals_result={"data_status": "OK"},
            is_demo=False,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert len(decision.messages) > 0


# ============================================================
# LiveDataService 测试 (mock provider hub)
# ============================================================

class TestLiveDataService:
    def _make_service(self):
        """创建 mock hub 的 LiveDataService"""
        from src.product_app.live_data_service import LiveDataService

        with patch("src.product_app.live_data_service.DataProviderHub") as mock_hub_cls, \
             patch("src.product_app.live_data_service.ProviderCircuitBreaker") as mock_cb_cls:
            mock_hub = MagicMock()
            mock_hub_cls.return_value = mock_hub
            mock_cb = MagicMock()
            mock_cb_cls.return_value = mock_cb

            # 模拟成功的 fetch_with_fallback
            valid_df = pd.DataFrame({
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
            mock_result = ProviderResult(
                status="ok",
                provider="eastmoney",
                capability=DataCapability.REALTIME_QUOTES,
                data=valid_df,
                fallback_chain=["eastmoney: ok"],
            )
            mock_hub.fetch_with_fallback.return_value = mock_result
            mock_hub.get_health.return_value = []

            service = LiveDataService()
            # 替换 hub 为 mock
            service._realtime_hub = mock_hub
            service._daily_hub = mock_hub
            service._fundamentals_hub = mock_hub
            return service

    def test_get_realtime_quotes_ok(self):
        """实时行情成功返回"""
        service = self._make_service()
        result = service.get_realtime_quotes(["600000.SH"])
        assert result["status"] == "ok"
        assert result["is_demo"] is False
        assert result["chosen_provider"] == "eastmoney"
        assert "quotes" in result

    def test_get_realtime_quotes_failed(self):
        """所有 provider 失败时返回 failed"""
        service = self._make_service()
        failed_result = ProviderResult(
            status="failed",
            provider="",
            capability=DataCapability.REALTIME_QUOTES,
            data=pd.DataFrame(),
            messages=["akshare: timeout", "eastmoney: timeout"],
            fallback_chain=["akshare: timeout", "eastmoney: timeout"],
        )
        service._realtime_hub.fetch_with_fallback.return_value = failed_result

        with patch.object(service, "_get_feedback_service") as mock_fs:
            mock_fb = MagicMock()
            mock_fb.write_bug_report.return_value = "BUG_001"
            mock_fs.return_value = mock_fb
            result = service.get_realtime_quotes(["600000.SH"])

        assert result["data_status"] == "FAILED"
        assert result["is_demo"] is False
        assert result["quotes"] == []

    def test_get_daily_bars_ok(self):
        """日线成功返回"""
        service = self._make_service()
        valid_df = pd.DataFrame({
            "symbol": ["600000.SH", "600000.SH"],
            "trade_date": ["2025-06-09", "2025-06-10"],
            "open": [10.10, 10.20],
            "high": [10.30, 10.40],
            "low": [10.00, 10.10],
            "close": [10.20, 10.30],
            "volume": [1000000, 1200000],
            "amount": [10200000, 12360000],
            "raw_open": [10.10, 10.20],
            "raw_high": [10.30, 10.40],
            "raw_low": [10.00, 10.10],
            "raw_close": [10.20, 10.30],
            "adjusted_open": [10.10, 10.20],
            "adjusted_high": [10.30, 10.40],
            "adjusted_low": [10.00, 10.10],
            "adjusted_close": [10.20, 10.30],
            "adjustment_type": ["前复权", "前复权"],
            "is_suspended": [False, False],
            "is_limit_up": [False, False],
            "is_limit_down": [False, False],
            "currency": ["CNY", "CNY"],
            "timezone": ["Asia/Shanghai", "Asia/Shanghai"],
            "data_source": ["eastmoney", "eastmoney"],
            "updated_at": ["2025-06-10 10:00:00", "2025-06-10 10:00:00"],
            "data_version": ["daily-v1", "daily-v1"],
        })
        daily_result = ProviderResult(
            status="ok",
            provider="eastmoney",
            capability=DataCapability.DAILY_BARS,
            data=valid_df,
            fallback_chain=["eastmoney: ok"],
        )
        service._daily_hub.fetch_with_fallback.return_value = daily_result

        result = service.get_daily_bars(["600000.SH"], "2025-06-09", "2025-06-10")
        assert result["status"] == "ok"
        assert result["is_demo"] is False
        assert "daily_bars" in result

    def test_get_fundamentals_missing_fields_not_zero(self):
        """财务缺失字段不填0"""
        service = self._make_service()
        fund_df = pd.DataFrame({
            "symbol": ["600000.SH"],
            "pe_ttm": [8.5],
            "pb": [pd.NA],
            "roe": [pd.NA],
            "revenue": [pd.NA],
            "net_profit": [pd.NA],
            "market_cap": [3e11],
            "report_period": [None],
            "currency": ["CNY"],
            "data_source": ["eastmoney"],
            "updated_at": ["2025-06-10 10:00:00"],
            "data_version": ["fundamentals-v1"],
        })
        fund_result = ProviderResult(
            status="ok",
            provider="eastmoney",
            capability=DataCapability.FUNDAMENTALS,
            data=fund_df,
            fallback_chain=["eastmoney: ok"],
        )
        service._fundamentals_hub.fetch_with_fallback.return_value = fund_result

        result = service.get_fundamentals(["600000.SH"])
        assert result["status"] == "ok"
        # 缺失字段应在 missing_report 中
        assert "data_missing_report" in result

    def test_build_research_context(self):
        """研究上下文包含健康决策"""
        service = self._make_service()
        result = service.build_research_context(["600000.SH"], "2025-06-09", "2025-06-10")
        assert "health" in result
        assert "daily_bars" in result
        assert "fundamentals" in result


# ============================================================
# ProviderDiagnosticsService 测试
# ============================================================

class TestProviderDiagnosticsService:
    def test_diagnose_returns_structure(self):
        """诊断返回标准结构"""
        from src.product_app.provider_diagnostics_service import ProviderDiagnosticsService

        mock_hub = MagicMock()
        valid_df = pd.DataFrame({
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
        mock_result = ProviderResult(
            status="ok",
            provider="eastmoney",
            capability=DataCapability.REALTIME_QUOTES,
            data=valid_df,
            fallback_chain=["eastmoney: ok"],
        )
        mock_hub.fetch_with_fallback.return_value = mock_result
        mock_hub.get_health.return_value = []

        service = ProviderDiagnosticsService(
            realtime_hub=mock_hub,
            daily_bars_hub=mock_hub,
            fundamentals_hub=mock_hub,
        )
        result = service.diagnose(
            symbols=["600000.SH"],
            capabilities=[DataCapability.REALTIME_QUOTES],
        )
        assert "provider_health_report" in result
        assert "chosen_provider" in result
        assert "diagnosed_at" in result


# ============================================================
# Live Data API 测试 (FastAPI TestClient)
# ============================================================

class TestLiveDataAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        return TestClient(app)

    def test_live_data_providers_endpoint(self, client):
        """GET /product/live-data/providers 返回 200"""
        with patch("src.api.product_routes._get_live_data_service") as mock_lds:
            mock_service = MagicMock()
            mock_service._provider_order = ["eastmoney", "akshare", "aktools"]
            mock_service._realtime_hub.get_health.return_value = []
            mock_service._daily_hub.get_health.return_value = []
            mock_service._fundamentals_hub.get_health.return_value = []
            mock_lds.return_value = mock_service

            response = client.get("/product/live-data/providers")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "provider_order" in data

    def test_live_data_quotes_endpoint(self, client):
        """GET /product/live-data/quotes 返回 200"""
        with patch("src.api.product_routes._get_live_data_service") as mock_lds:
            mock_service = MagicMock()
            mock_service.get_realtime_quotes.return_value = {
                "status": "ok",
                "data_status": "OK",
                "is_demo": False,
                "chosen_provider": "eastmoney",
                "fallback_chain": ["eastmoney: ok"],
                "quotes": [],
                "provider_health_report": {},
                "data_quality_report": {},
                "data_missing_report": {},
                "data_delay_report": {},
                "feedback_bug_id": "",
            }
            mock_lds.return_value = mock_service

            response = client.get("/product/live-data/quotes?symbols=600000.SH")
            assert response.status_code == 200
            data = response.json()
            assert data["is_demo"] is False

    def test_live_data_daily_bars_endpoint(self, client):
        """GET /product/live-data/daily-bars 返回 200"""
        with patch("src.api.product_routes._get_live_data_service") as mock_lds:
            mock_service = MagicMock()
            mock_service.get_daily_bars.return_value = {
                "status": "ok",
                "data_status": "OK",
                "is_demo": False,
                "chosen_provider": "eastmoney",
                "fallback_chain": ["eastmoney: ok"],
                "daily_bars": [],
                "provider_health_report": {},
                "data_quality_report": {},
                "data_missing_report": {},
                "data_delay_report": {},
                "feedback_bug_id": "",
            }
            mock_lds.return_value = mock_service

            response = client.get("/product/live-data/daily-bars?symbols=600000.SH&start_date=20250101&end_date=20251231")
            assert response.status_code == 200

    def test_live_data_fundamentals_endpoint(self, client):
        """GET /product/live-data/fundamentals 返回 200"""
        with patch("src.api.product_routes._get_live_data_service") as mock_lds:
            mock_service = MagicMock()
            mock_service.get_fundamentals.return_value = {
                "status": "ok",
                "data_status": "OK",
                "is_demo": False,
                "chosen_provider": "eastmoney",
                "fallback_chain": ["eastmoney: ok"],
                "fundamentals": [],
                "provider_health_report": {},
                "data_quality_report": {},
                "data_missing_report": {},
                "data_delay_report": {},
                "feedback_bug_id": "",
            }
            mock_lds.return_value = mock_service

            response = client.get("/product/live-data/fundamentals?symbols=600000.SH")
            assert response.status_code == 200

    def test_live_data_diagnose_endpoint(self, client):
        """POST /product/live-data/diagnose 返回 200"""
        with patch("src.api.product_routes._get_diagnostics_service") as mock_diag:
            mock_service = MagicMock()
            mock_service.diagnose.return_value = {
                "status": "ok",
                "provider_health_report": {},
                "chosen_provider": {},
                "diagnosed_at": "2025-06-10 10:00:00",
                "feedback_bug_id": "",
            }
            mock_diag.return_value = mock_service

            response = client.post("/product/live-data/diagnose?symbols=600000.SH&capabilities=realtime_quotes")
            assert response.status_code == 200

    def test_research_context_endpoint(self, client):
        """POST /product/live-data/research-context 返回 200"""
        with patch("src.api.product_routes._get_live_data_service") as mock_lds:
            mock_service = MagicMock()
            mock_service.build_research_context.return_value = {
                "status": "ok",
                "data_status": "OK",
                "is_demo": False,
                "daily_bars": [],
                "fundamentals": [],
                "health": {
                    "data_status": "OK",
                    "allow_research": True,
                    "allow_signal": True,
                    "allow_order_draft": True,
                    "risk_level": "OK",
                    "messages": [],
                    "evidence": {},
                },
                "provider_health_report": {},
                "data_quality_report": {},
                "data_missing_report": {},
                "data_delay_report": {},
                "feedback_bug_id": "",
            }
            mock_lds.return_value = mock_service

            response = client.post("/product/live-data/research-context?symbols=600000.SH")
            assert response.status_code == 200
