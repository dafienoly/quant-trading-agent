"""Tests for /product/market/** API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.product_app.market_data.contracts import (
    DataQualityMetadata,
    ItemError,
    MarketBar,
    MarketQuote,
    MultiSymbolQuoteResult,
    ProviderAttempt,
    ProviderErrorCategory,
    QualityStatus,
)
from src.product_app.market_data.errors import MarketDataUnavailableError


def _make_quality(overrides: dict | None = None) -> DataQualityMetadata:
    fields = {
        "source_provider": "test_provider",
        "source_priority": 1,
        "as_of": datetime.now(timezone.utc),
        "received_at": datetime.now(timezone.utc),
        "freshness_seconds": 1.0,
        "is_stale": False,
        "is_realtime": True,
        "is_demo": False,
        "is_mock": False,
        "is_fallback": False,
        "quality_status": QualityStatus.OK,
        "quality_reason": "",
        "provider_latency_ms": 50.0,
        "request_id": "test-request-1",
    }
    if overrides:
        fields.update(overrides)
    return DataQualityMetadata(**fields)


def _make_quote(symbol: str = "000001.SZ", overrides: dict | None = None) -> MarketQuote:
    fields = {
        "symbol": symbol,
        "market": "cn_stock_a",
        "asset_type": "equity",
        "price": Decimal("10.50"),
        "open": Decimal("10.00"),
        "high": Decimal("10.80"),
        "low": Decimal("10.20"),
        "previous_close": Decimal("10.00"),
        "volume": 1000000,
        "currency": "CNY",
        "quality": _make_quality(),
    }
    if overrides:
        fields.update(overrides)
    return MarketQuote(**fields)


def _make_bar(symbol: str = "000001.SZ") -> MarketBar:
    return MarketBar(
        symbol=symbol,
        market="cn_stock_a",
        granularity="1d",
        timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
        open=Decimal("10.00"),
        high=Decimal("10.80"),
        low=Decimal("10.20"),
        close=Decimal("10.50"),
        volume=2000000,
        quality=_make_quality(),
    )


class TestMarketDataRoutes:
    """Tests for /product/market/ endpoints."""

    ROUTE_PREFIX = "/product/market"

    # ── GET /product/market/latest/{symbol} ────────────────────

    def test_get_latest_quote_success(self):
        """GET latest/{symbol} returns 200 with MarketQuote."""
        mock_relay = MagicMock()
        mock_relay.get_latest_quote.return_value = _make_quote("600000.SH")

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.get(f"{self.ROUTE_PREFIX}/latest/600000.SH")
            assert response.status_code == 200
            body = response.json()
            assert body["symbol"] == "600000.SH"
            assert float(body["price"]) == 10.50
            assert "quality" in body
            assert body["quality"]["source_provider"] == "test_provider"

    def test_get_latest_quote_with_market_param(self):
        """GET latest/{symbol} accepts custom market query param."""
        mock_relay = MagicMock()
        mock_relay.get_latest_quote.return_value = _make_quote("00700.HK")

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.get(f"{self.ROUTE_PREFIX}/latest/00700.HK?market=hk_equity")
            assert response.status_code == 200
            body = response.json()
            assert body["symbol"] == "00700.HK"

    def test_get_latest_quote_provider_fail_closed(self):
        """All providers fail returns 503 with structured error."""
        mock_relay = MagicMock()
        err = MarketDataUnavailableError(
            request_id="err-001",
            safe_reason="All providers failed to return acceptable quote",
            provider_attempts=[
                ProviderAttempt(
                    provider_id="p1", priority=1,
                    error_category=ProviderErrorCategory.TIMEOUT,
                    quality_status=QualityStatus.UNAVAILABLE,
                    latency_ms=5000.0, safe_reason="timeout",
                ),
            ],
            fallback_used=False,
            quality_status=QualityStatus.UNAVAILABLE,
        )
        mock_relay.get_latest_quote.side_effect = err

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.get(f"{self.ROUTE_PREFIX}/latest/000001.SZ")
            assert response.status_code == 503
            body = response.json()
            assert "error" in body
            assert body["error"]["request_id"] == "err-001"
            assert body["error"]["quality_status"] == "UNAVAILABLE"
            assert "secret" not in str(body).lower()
            assert "/home" not in str(body)
            assert "traceback" not in str(body).lower()

    def test_get_latest_quote_internal_error(self):
        """Unexpected exception returns 500 without traceback/secret."""
        mock_relay = MagicMock()
        mock_relay.get_latest_quote.side_effect = RuntimeError("internal oops")

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.get(f"{self.ROUTE_PREFIX}/latest/000001.SZ")
            assert response.status_code == 500
            body = response.json()
            assert "error" in body
            assert "traceback" not in str(body).lower()
            assert "/home" not in str(body)
            assert "secret" not in str(body).lower()
            assert body["error"]["request_id"]

    # ── POST /product/market/latest ────────────────────────────

    def test_post_latest_quotes_success(self):
        """POST latest returns 200 with MultiSymbolQuoteResult."""
        mock_relay = MagicMock()
        result = MultiSymbolQuoteResult(
            results=[_make_quote("000001.SZ"), _make_quote("600000.SH")],
            item_errors=[],
            summary={"total": 2, "ok_count": 2, "failed_count": 0, "degraded_count": 0, "fallback_count": 0},
            request_quality=QualityStatus.OK,
            request_id="multi-001",
        )
        mock_relay.get_latest_quotes.return_value = result

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.post(
                f"{self.ROUTE_PREFIX}/latest",
                json={"symbols": ["000001.SZ", "600000.SH"], "market": "cn_stock_a"},
            )
            assert response.status_code == 200
            body = response.json()
            assert len(body["results"]) == 2
            assert body["summary"]["total"] == 2
            assert body["request_id"] == "multi-001"
            assert body["request_quality"] == "OK"

    def test_post_latest_quotes_partial_failure(self):
        """Partial failures appear in item_errors."""
        mock_relay = MagicMock()
        result = MultiSymbolQuoteResult(
            results=[_make_quote("000001.SZ")],
            item_errors=[
                ItemError(symbol="BADSYM", error_category=ProviderErrorCategory.EMPTY_RESPONSE, safe_reason="not found"),
            ],
            summary={"total": 2, "ok_count": 1, "failed_count": 1, "degraded_count": 0, "fallback_count": 0},
            request_quality=QualityStatus.DEGRADED,
            request_id="multi-002",
        )
        mock_relay.get_latest_quotes.return_value = result

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.post(
                f"{self.ROUTE_PREFIX}/latest",
                json={"symbols": ["000001.SZ", "BADSYM"], "market": "cn_stock_a"},
            )
            assert response.status_code == 200
            body = response.json()
            assert len(body["item_errors"]) == 1
            assert body["item_errors"][0]["symbol"] == "BADSYM"
            assert body["summary"]["failed_count"] == 1

    def test_post_latest_quotes_all_failed(self):
        """All providers fail returns 503."""
        mock_relay = MagicMock()
        err = MarketDataUnavailableError(
            request_id="err-002",
            safe_reason="All providers failed",
            provider_attempts=[ProviderAttempt(provider_id="p1", priority=1)],
            fallback_used=False,
            quality_status=QualityStatus.UNAVAILABLE,
        )
        mock_relay.get_latest_quotes.side_effect = err

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.post(
                f"{self.ROUTE_PREFIX}/latest",
                json={"symbols": ["000001.SZ"], "market": "cn_stock_a"},
            )
            assert response.status_code == 503
            body = response.json()
            assert body["error"]["request_id"] == "err-002"

    def test_post_latest_quotes_invalid_body(self):
        """Missing required body fields returns 422."""
        client = TestClient(app)
        response = client.post(
            f"{self.ROUTE_PREFIX}/latest",
            json={},
        )
        assert response.status_code == 422

    # ── GET /product/market/bars/{symbol} ──────────────────────

    def test_get_bars_success(self):
        """GET bars/{symbol} returns 200 with list of MarketBar."""
        mock_relay = MagicMock()
        mock_relay.get_bars.return_value = [_make_bar("000001.SZ"), _make_bar("000001.SZ")]

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.get(
                f"{self.ROUTE_PREFIX}/bars/000001.SZ",
                params={"granularity": "1d", "start": "2025-01-01", "end": "2025-01-31"},
            )
            assert response.status_code == 200
            body = response.json()
            assert len(body) == 2
            assert body[0]["symbol"] == "000001.SZ"
            assert body[0]["granularity"] == "1d"

    def test_get_bars_missing_params(self):
        """Missing granularity/start/end returns 422."""
        client = TestClient(app)
        response = client.get(f"{self.ROUTE_PREFIX}/bars/000001.SZ")
        assert response.status_code == 422

    def test_get_bars_provider_fail_closed(self):
        """Provider failure for bars returns 503."""
        mock_relay = MagicMock()
        err = MarketDataUnavailableError(
            request_id="err-bars",
            safe_reason="All providers failed",
            provider_attempts=[],
            fallback_used=False,
            quality_status=QualityStatus.UNAVAILABLE,
        )
        mock_relay.get_bars.side_effect = err

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.get(
                f"{self.ROUTE_PREFIX}/bars/000001.SZ",
                params={"granularity": "1d", "start": "2025-01-01", "end": "2025-01-31"},
            )
            assert response.status_code == 503

    # ── GET /product/market/providers/health ───────────────────

    def test_get_providers_health_success(self):
        """GET providers/health returns 200 with health snapshot."""
        mock_relay = MagicMock()
        mock_relay._health.snapshot.return_value = {
            "p1": {
                "availability": 0.95,
                "last_success_at": "2025-06-26T00:00:00Z",
                "last_failure_at": None,
                "consecutive_failures": 0,
                "latency_p50_ms": 45.0,
                "latency_p95_ms": 120.0,
                "latency_last_ms": 50.0,
                "error_category_summary": {},
                "circuit_breaker_status": "closed",
                "fallback_activation_count": 0,
                "freshness_summary": {},
                "updated_at": "2025-06-26T00:00:00Z",
                "total_success": 100,
                "total_failures": 5,
            }
        }

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.get(f"{self.ROUTE_PREFIX}/providers/health")
            assert response.status_code == 200
            body = response.json()
            assert "p1" in body
            assert body["p1"]["availability"] == 0.95
            assert body["p1"]["circuit_breaker_status"] == "closed"

    # ── GET /product/market/providers/quality ──────────────────

    def test_get_providers_quality_success(self):
        """GET providers/quality returns 200 with quality info."""
        client = TestClient(app)
        response = client.get(f"{self.ROUTE_PREFIX}/providers/quality")
        assert response.status_code == 200

    # ── GET /product/market/providers/fallback ──────────────────

    def test_get_providers_fallback_success(self):
        """GET providers/fallback returns 200 with fallback info."""
        client = TestClient(app)
        response = client.get(f"{self.ROUTE_PREFIX}/providers/fallback")
        assert response.status_code == 200

    # ── Route prefix and security assertions ───────────────────

    def test_routes_under_product_prefix(self):
        """All market routes are under /product/market, not /api/market or bare /market."""
        all_paths = [getattr(r, "path", "") for r in app.routes]
        market_paths = [p for p in all_paths if "market" in p.lower() and p]
        for path in market_paths:
            assert path.startswith("/product/market"), f"Route {path} not under /product/market"
        assert not any(p == "/market" or p.startswith("/api/market") for p in all_paths)

    def test_error_response_no_secrets(self):
        """Error responses must not contain secret, traceback, or absolute paths."""
        mock_relay = MagicMock()
        err = MarketDataUnavailableError(
            request_id="sec-001",
            safe_reason="Provider auth failure",
            provider_attempts=[
                ProviderAttempt(
                    provider_id="p1", priority=1,
                    error_category=ProviderErrorCategory.AUTH_FAILED,
                    safe_reason="api_key expired",
                ),
            ],
            fallback_used=False,
            quality_status=QualityStatus.UNAVAILABLE,
        )
        mock_relay.get_latest_quote.side_effect = err

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.get(f"{self.ROUTE_PREFIX}/latest/000001.SZ")
            assert response.status_code == 503
            text = str(response.json()).lower()
            assert "/home" not in text
            assert "traceback" not in text
            assert "api_key" not in text

    def test_no_raw_provider_import_in_routes(self):
        """Routes file should not import raw provider modules."""
        import ast
        with open("src/api/market_data_routes.py") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if any(x in module for x in ["data_gateway", "akshare", "eastmoney", "aktools"]):
                    raise AssertionError(f"Routes should not import raw provider: {module}")

    # ── CallerContext parameter ────────────────────────────────

    def test_post_latest_with_caller_context(self):
        """POST latest accepts caller_context in body."""
        mock_relay = MagicMock()
        result = MultiSymbolQuoteResult(
            results=[_make_quote("000001.SZ")],
            item_errors=[],
            summary={"total": 1, "ok_count": 1, "failed_count": 0, "degraded_count": 0, "fallback_count": 0},
            request_quality=QualityStatus.OK,
            request_id="ctx-001",
        )
        mock_relay.get_latest_quotes.return_value = result

        with patch("src.api.market_data_routes._get_market_data_relay", return_value=mock_relay):
            client = TestClient(app)
            response = client.post(
                f"{self.ROUTE_PREFIX}/latest",
                json={
                    "symbols": ["000001.SZ"],
                    "market": "cn_stock_a",
                    "caller_context": "dashboard_observability",
                    "allow_demo": False,
                },
            )
            assert response.status_code == 200
