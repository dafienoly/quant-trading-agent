"""Phase D 测试：因子服务、回测服务、信号编排器、Signal API

测试范围：
- live_factor_service.py: 因子计算
- live_backtest_service.py: 快速回测
- live_signal_orchestrator.py: 信号编排
- product_routes.py: /product/signal/* API
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ============================================================
# LiveFactorService 测试
# ============================================================

class TestLiveFactorService:
    def _make_daily_bars_df(self, n=60) -> pd.DataFrame:
        """构造模拟日线数据"""
        dates = pd.date_range("2025-04-01", periods=n, freq="B")
        np.random.seed(42)
        close = 10.0 + np.cumsum(np.random.randn(n) * 0.2)
        return pd.DataFrame({
            "symbol": ["600000.SH"] * n,
            "trade_date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": close + np.random.randn(n) * 0.1,
            "high": close + abs(np.random.randn(n) * 0.2),
            "low": close - abs(np.random.randn(n) * 0.2),
            "close": close,
            "volume": np.random.randint(100000, 1000000, n),
            "amount": close * np.random.randint(100000, 1000000, n),
            "adjusted_close": close,
            "adjusted_open": close + np.random.randn(n) * 0.1,
            "adjusted_high": close + abs(np.random.randn(n) * 0.2),
            "adjusted_low": close - abs(np.random.randn(n) * 0.2),
        })

    def test_compute_factors_basic(self):
        """基础因子计算"""
        from src.product_app.live_factor_service import LiveFactorService
        service = LiveFactorService()
        df = self._make_daily_bars_df()
        result = service.compute_factors(df)
        assert result["status"] == "ok"
        assert len(result["factors"]) > 0
        assert result["is_demo"] is False

    def test_compute_factors_empty_data(self):
        """空数据返回 failed"""
        from src.product_app.live_factor_service import LiveFactorService
        service = LiveFactorService()
        result = service.compute_factors(pd.DataFrame())
        assert result["status"] == "failed"
        assert result["factors"] == []

    def test_compute_factors_with_filter(self):
        """因子名过滤"""
        from src.product_app.live_factor_service import LiveFactorService
        service = LiveFactorService()
        df = self._make_daily_bars_df()
        result = service.compute_factors(df, factor_names=["sma_5", "sma_20"])
        assert result["status"] == "ok"

    def test_is_demo_always_false(self):
        """is_demo 始终为 False"""
        from src.product_app.live_factor_service import LiveFactorService
        service = LiveFactorService()
        df = self._make_daily_bars_df()
        result = service.compute_factors(df)
        assert result["is_demo"] is False


# ============================================================
# LiveBacktestService 测试
# ============================================================

class TestLiveBacktestService:
    def _make_daily_bars_df(self, n=60) -> pd.DataFrame:
        """构造模拟日线数据"""
        dates = pd.date_range("2025-04-01", periods=n, freq="B")
        np.random.seed(42)
        close = 10.0 + np.cumsum(np.random.randn(n) * 0.2)
        return pd.DataFrame({
            "symbol": ["600000.SH"] * n,
            "trade_date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": close + np.random.randn(n) * 0.1,
            "high": close + abs(np.random.randn(n) * 0.2),
            "low": close - abs(np.random.randn(n) * 0.2),
            "close": close,
            "volume": np.random.randint(100000, 1000000, n),
            "amount": close * np.random.randint(100000, 1000000, n),
            "adjusted_close": close,
        })

    def test_run_quick_backtest(self):
        """快速回测"""
        from src.product_app.live_backtest_service import LiveBacktestService
        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds = MagicMock()
            mock_lds_cls.return_value = mock_lds
            mock_lds.get_daily_bars.return_value = {
                "status": "ok",
                "data_status": "OK",
                "is_demo": False,
                "daily_bars": self._make_daily_bars_df().to_dict(orient="records"),
                "chosen_provider": "eastmoney",
                "fallback_chain": ["eastmoney: ok"],
                "provider_health_report": {},
                "data_quality_report": {},
                "data_missing_report": {},
                "data_delay_report": {},
                "feedback_bug_id": "",
            }
            service = LiveBacktestService()
            result = service.run_quick_backtest(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert result["status"] == "ok"
            assert "total_return" in result["results"]
            assert "sharpe_ratio" in result["results"]
            assert result["is_demo"] is False

    def test_run_quick_backtest_insufficient_data(self):
        """数据不足返回 insufficient_data"""
        from src.product_app.live_backtest_service import LiveBacktestService
        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds = MagicMock()
            mock_lds_cls.return_value = mock_lds
            mock_lds.get_daily_bars.return_value = {
                "status": "ok",
                "data_status": "OK",
                "is_demo": False,
                "daily_bars": self._make_daily_bars_df(n=10).to_dict(orient="records"),
                "chosen_provider": "eastmoney",
                "fallback_chain": ["eastmoney: ok"],
                "provider_health_report": {},
                "data_quality_report": {},
                "data_missing_report": {},
                "data_delay_report": {},
                "feedback_bug_id": "",
            }
            service = LiveBacktestService()
            result = service.run_quick_backtest(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert result["status"] == "insufficient_data"

    def test_run_quick_backtest_empty_data(self):
        """空数据返回 failed"""
        from src.product_app.live_backtest_service import LiveBacktestService
        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds = MagicMock()
            mock_lds_cls.return_value = mock_lds
            mock_lds.get_daily_bars.return_value = {
                "status": "failed",
                "data_status": "FAILED",
                "is_demo": False,
                "daily_bars": [],
                "chosen_provider": "",
                "fallback_chain": [],
                "provider_health_report": {},
                "data_quality_report": {},
                "data_missing_report": {},
                "data_delay_report": {},
                "feedback_bug_id": "",
            }
            service = LiveBacktestService()
            result = service.run_quick_backtest(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert result["status"] == "failed"

    def test_is_demo_always_false(self):
        """is_demo 始终为 False"""
        from src.product_app.live_backtest_service import LiveBacktestService
        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds = MagicMock()
            mock_lds_cls.return_value = mock_lds
            mock_lds.get_daily_bars.return_value = {
                "status": "ok",
                "data_status": "OK",
                "is_demo": False,
                "daily_bars": self._make_daily_bars_df().to_dict(orient="records"),
                "chosen_provider": "eastmoney",
                "fallback_chain": ["eastmoney: ok"],
                "provider_health_report": {},
                "data_quality_report": {},
                "data_missing_report": {},
                "data_delay_report": {},
                "feedback_bug_id": "",
            }
            service = LiveBacktestService()
            result = service.run_quick_backtest(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert result["is_demo"] is False


# ============================================================
# LiveSignalOrchestrator 测试
# ============================================================

class TestLiveSignalOrchestrator:
    def _make_mock_lds(self):
        """创建 mock LiveDataService"""
        mock_lds = MagicMock()
        mock_lds.get_realtime_quotes.return_value = {
            "status": "ok",
            "data_status": "OK",
            "is_demo": False,
            "chosen_provider": "eastmoney",
            "fallback_chain": ["eastmoney: ok"],
            "quotes": [],
            "provider_health_report": {},
            "data_quality_report": {},
            "data_missing_report": {},
            "data_delay_report": {"provider": "eastmoney", "elapsed_ms": 100, "max_delay_seconds": 0.1},
            "feedback_bug_id": "",
        }
        mock_lds.get_daily_bars.return_value = {
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
        mock_lds.get_fundamentals.return_value = {
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
        return mock_lds

    def test_generate_signal_draft(self):
        """生成信号草稿"""
        from src.product_app.live_signal_orchestrator import LiveSignalOrchestrator
        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds = self._make_mock_lds()
            mock_lds_cls.return_value = mock_lds
            orchestrator = LiveSignalOrchestrator()

            result = orchestrator.generate_signal_draft(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert "signal_id" in result
            assert result["is_demo"] is False
            assert "evidence" in result

    def test_signal_blocked_when_data_failed(self):
        """数据失败时信号被阻断"""
        from src.product_app.live_signal_orchestrator import LiveSignalOrchestrator
        mock_lds = self._make_mock_lds()
        mock_lds.get_daily_bars.return_value["data_status"] = "FAILED"
        mock_lds.get_daily_bars.return_value["status"] = "failed"

        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds_cls.return_value = mock_lds
            orchestrator = LiveSignalOrchestrator()

            result = orchestrator.generate_signal_draft(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert result.get("status") == "blocked" or result.get("signal_status") == "blocked"

    def test_signal_blocked_when_quotes_failed_daily_ok(self):
        """S1 回归：实时行情 FAILED 但日线/基本面 OK 时信号必须被阻断"""
        from src.product_app.live_signal_orchestrator import LiveSignalOrchestrator
        mock_lds = self._make_mock_lds()
        # 只有 quotes 失败
        mock_lds.get_realtime_quotes.return_value["data_status"] = "FAILED"
        mock_lds.get_realtime_quotes.return_value["status"] = "failed"
        # daily_bars 和 fundamentals 保持 OK

        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds_cls.return_value = mock_lds
            orchestrator = LiveSignalOrchestrator()

            result = orchestrator.generate_signal_draft(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert result.get("status") == "blocked"
            assert result["evidence"]["quotes_status"] == "FAILED"

    def test_signal_blocked_when_quotes_delay_exceeds_threshold(self):
        """S2 回归：行情延迟超过模式阈值时信号被阻断"""
        from src.product_app.live_signal_orchestrator import LiveSignalOrchestrator
        mock_lds = self._make_mock_lds()
        # 延迟 200s 超过 LEVEL_1_SIGNAL_ONLY 的 120s 阈值
        mock_lds.get_realtime_quotes.return_value["data_delay_report"] = {
            "provider": "eastmoney",
            "elapsed_ms": 200000,
            "max_delay_seconds": 200.0,
        }

        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds_cls.return_value = mock_lds
            orchestrator = LiveSignalOrchestrator()

            result = orchestrator.generate_signal_draft(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
                trading_mode="LEVEL_1_SIGNAL_ONLY",
            )
            assert result.get("status") == "blocked"
            assert result["evidence"]["data_health"]["data_status"] == "WARN"

    def test_signal_evidence_includes_quotes_provider_chain(self):
        """信号证据包含 quotes provider chain"""
        from src.product_app.live_signal_orchestrator import LiveSignalOrchestrator
        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds_cls.return_value = self._make_mock_lds()
            orchestrator = LiveSignalOrchestrator()

            result = orchestrator.generate_signal_draft(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert "quotes" in result["evidence"]["provider_chain"]
            assert result["evidence"]["quotes_status"] == "OK"

    def test_signal_id_format(self):
        """信号 ID 格式正确"""
        from src.product_app.live_signal_orchestrator import LiveSignalOrchestrator
        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds_cls.return_value = self._make_mock_lds()
            orchestrator = LiveSignalOrchestrator()

            result = orchestrator.generate_signal_draft(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert result["signal_id"].startswith("SIG_")

    def test_is_demo_always_false(self):
        """is_demo 始终为 False"""
        from src.product_app.live_signal_orchestrator import LiveSignalOrchestrator
        with patch("src.product_app.live_data_service.LiveDataService") as mock_lds_cls:
            mock_lds_cls.return_value = self._make_mock_lds()
            orchestrator = LiveSignalOrchestrator()

            result = orchestrator.generate_signal_draft(
                symbols=["600000.SH"],
                start_date="2025-01-01",
                end_date="2025-06-10",
            )
            assert result["is_demo"] is False


# ============================================================
# Signal API 测试
# ============================================================

class TestSignalAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        return TestClient(app)

    def test_generate_signal_draft_endpoint(self, client):
        """POST /product/signal/draft 返回 200"""
        with patch("src.api.product_routes._get_live_signal_orchestrator") as mock_orch:
            mock_orchestrator = MagicMock()
            mock_orchestrator.generate_signal_draft.return_value = {
                "signal_id": "SIG_20250610_001",
                "status": "draft",
                "signal_status": "draft",
                "symbols": ["600000.SH"],
                "trading_mode": "LEVEL_1_SIGNAL_ONLY",
                "signal_type": "hold",
                "confidence": 0.5,
                "evidence": {},
                "risk_check": {},
                "is_demo": False,
            }
            mock_orch.return_value = mock_orchestrator

            response = client.post("/product/signal/draft?symbols=600000.SH")
            assert response.status_code == 200
            data = response.json()
            assert "signal_id" in data

    def test_get_signal_status_endpoint(self, client):
        """GET /product/signal/{signal_id} 返回 200"""
        with patch("src.api.product_routes._get_live_signal_orchestrator") as mock_orch:
            mock_orchestrator = MagicMock()
            mock_orchestrator.get_signal_status.return_value = {
                "signal_id": "SIG_20250610_001",
                "status": "draft",
            }
            mock_orch.return_value = mock_orchestrator

            response = client.get("/product/signal/SIG_20250610_001")
            assert response.status_code == 200
