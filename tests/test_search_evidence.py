"""搜索增强、主题证据服务 测试

测试范围：
- search_provider_hub.py: Tavily/AnySearch/Firecrawl Provider、搜索预算、缓存、fallback
- theme_evidence_service.py: 主题证据组合
- product_routes.py: /product/search, /product/theme-evidence API
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest


# ============================================================
# TavilyProvider 测试
# ============================================================

class TestTavilyProvider:
    def test_name(self):
        from src.product_app.search_provider_hub import TavilyProvider
        provider = TavilyProvider(api_key="test_key")
        assert provider.name == "tavily"

    def test_not_configured_without_key(self):
        from src.product_app.search_provider_hub import TavilyProvider
        provider = TavilyProvider(api_key="")
        assert not provider.is_configured

    def test_configured_with_key(self):
        from src.product_app.search_provider_hub import TavilyProvider
        provider = TavilyProvider(api_key="tvly-test")
        assert provider.is_configured

    def test_search_raises_without_key(self):
        from src.product_app.search_provider_hub import TavilyProvider
        provider = TavilyProvider(api_key="")
        with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
            provider.search("test query")


# ============================================================
# AnySearchProvider 测试
# ============================================================

class TestAnySearchProvider:
    def test_name(self):
        from src.product_app.search_provider_hub import AnySearchProvider
        provider = AnySearchProvider(api_key="test_key")
        assert provider.name == "anysearch"

    def test_not_configured_without_key(self):
        from src.product_app.search_provider_hub import AnySearchProvider
        provider = AnySearchProvider(api_key="")
        assert not provider.is_configured


# ============================================================
# FirecrawlProvider 测试
# ============================================================

class TestFirecrawlProvider:
    def test_name(self):
        from src.product_app.search_provider_hub import FirecrawlProvider
        provider = FirecrawlProvider(api_key="test_key")
        assert provider.name == "firecrawl"

    def test_not_configured_without_key(self):
        from src.product_app.search_provider_hub import FirecrawlProvider
        provider = FirecrawlProvider(api_key="")
        assert not provider.is_configured


# ============================================================
# SearchProviderHub 测试
# ============================================================

class TestSearchProviderHub:
    def _clear_cache_and_budget(self):
        """清除搜索缓存和预算"""
        from src.product_app.search_provider_hub import SearchProviderHub
        hub = SearchProviderHub()
        hub._save_budget({})
        cache_dir = Path("runtime/cache/search")
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                f.unlink(missing_ok=True)

    def test_search_not_configured(self):
        """未配置任何 API Key 时返回 not_configured"""
        from src.product_app.search_provider_hub import SearchProviderHub
        hub = SearchProviderHub()
        hub._providers = []  # 清空 provider 列表
        result = hub.search("AI算力")
        assert result["status"] == "not_configured"

    def test_search_budget_exceeded(self):
        """搜索预算耗尽时返回 budget_exceeded"""
        from src.product_app.search_provider_hub import SearchProviderHub
        self._clear_cache_and_budget()
        hub = SearchProviderHub()
        # 添加一个 mock provider
        from unittest.mock import MagicMock
        mock_provider = MagicMock()
        mock_provider.name = "tavily"
        hub._providers = [mock_provider]

        # 写入预算文件使预算耗尽
        hub._save_budget({"date": datetime.now().strftime("%Y-%m-%d"), "count": 9999})
        result = hub.search("AI算力")
        assert result["status"] == "budget_exceeded"

    def test_cache_hit(self):
        """缓存命中"""
        from src.product_app.search_provider_hub import SearchProviderHub
        hub = SearchProviderHub()
        # 手动设置缓存
        cache_dir = Path("runtime/cache/search")
        cache_dir.mkdir(parents=True, exist_ok=True)
        import hashlib
        cache_key = hashlib.md5("test_query".encode()).hexdigest()
        cache_file = cache_dir / f"{cache_key}.json"
        cache_data = {
            "query": "test_query",
            "results": [{"title": "test", "url": "http://example.com"}],
            "cached_at": time.time(),
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        result = hub._cache_get("test_query")
        assert result is not None
        cache_file.unlink(missing_ok=True)

    def test_cache_miss(self):
        """缓存未命中"""
        from src.product_app.search_provider_hub import SearchProviderHub
        hub = SearchProviderHub()
        result = hub._cache_get("nonexistent_query_12345")
        assert result is None

    def test_record_usage(self):
        """使用量记录"""
        from src.product_app.search_provider_hub import SearchProviderHub
        hub = SearchProviderHub()
        hub._record_usage(1)
        usage = hub._load_budget()
        assert usage.get("count", 0) >= 1

    def test_search_fallback(self):
        """Provider fallback：第一个失败后尝试第二个"""
        from src.product_app.search_provider_hub import SearchProviderHub
        from unittest.mock import MagicMock
        self._clear_cache_and_budget()
        hub = SearchProviderHub()

        mock_tavily = MagicMock()
        mock_tavily.name = "tavily"
        mock_tavily.search.side_effect = Exception("Tavily timeout")

        mock_anysearch = MagicMock()
        mock_anysearch.name = "anysearch"
        mock_anysearch.search.return_value = [
            {"title": "AI芯片最新消息", "url": "http://example.com", "provider": "anysearch"},
        ]

        hub._providers = [mock_tavily, mock_anysearch]
        result = hub.search("AI算力")
        assert result["status"] == "ok"
        assert result["provider"] == "anysearch"
        assert len(result["fallback_chain"]) == 2
        assert "tavily" in result["fallback_chain"][0]
        assert "anysearch: ok" in result["fallback_chain"][1]

    def test_search_all_failed(self):
        """所有 Provider 失败时返回 all_failed"""
        from src.product_app.search_provider_hub import SearchProviderHub
        from unittest.mock import MagicMock
        self._clear_cache_and_budget()
        hub = SearchProviderHub()

        mock_provider = MagicMock()
        mock_provider.name = "tavily"
        mock_provider.search.side_effect = Exception("API error")

        hub._providers = [mock_provider]
        result = hub.search("AI算力")
        assert result["status"] == "all_failed"
        assert result["results"] == []

    def test_get_provider_status(self):
        """获取 Provider 状态"""
        from src.product_app.search_provider_hub import SearchProviderHub
        hub = SearchProviderHub()
        status = hub.get_provider_status()
        assert len(status) > 0
        for s in status:
            assert "name" in s
            assert "configured" in s


# ============================================================
# ThemeEvidenceService 测试
# ============================================================

class TestThemeEvidenceService:
    def test_get_theme_evidence(self):
        """获取主题证据"""
        from src.product_app.theme_evidence_service import ThemeEvidenceService
        service = ThemeEvidenceService()

        with patch.object(service, "_theme_pool_service") as mock_tps, \
             patch.object(service, "_search_hub") as mock_search:
            mock_tps.get_theme_pool.return_value = {
                "stocks": [
                    {"symbol": "600584.SH", "name": "长电科技", "tags": ["advanced_packaging"]},
                ],
                "tags": [{"id": "advanced_packaging", "name": "先进封装"}],
            }
            mock_search.search.return_value = {
                "status": "not_configured",
                "results": [],
            }

            result = service.get_theme_evidence(["600584.SH"])
            assert "symbols" in result
            assert result["is_demo"] is False

    def test_search_theme_news(self):
        """搜索主题新闻"""
        from src.product_app.theme_evidence_service import ThemeEvidenceService
        service = ThemeEvidenceService()

        with patch.object(service, "_search_hub") as mock_search:
            mock_search.search.return_value = {
                "status": "ok",
                "results": [{"title": "AI芯片最新消息", "url": "http://example.com"}],
            }

            result = service.search_theme_news("ai_chip")
            assert "results" in result

    def test_is_demo_always_false(self):
        """is_demo 始终为 False"""
        from src.product_app.theme_evidence_service import ThemeEvidenceService
        service = ThemeEvidenceService()

        with patch.object(service, "_theme_pool_service") as mock_tps, \
             patch.object(service, "_search_hub") as mock_search:
            mock_tps.get_theme_pool.return_value = {"stocks": [], "tags": []}
            mock_search.search.return_value = {"status": "not_configured", "results": []}

            result = service.get_theme_evidence(["600000.SH"])
            assert result["is_demo"] is False


# ============================================================
# Search & Theme Evidence API 测试
# ============================================================

class TestSearchAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        return TestClient(app)

    def test_search_endpoint(self, client):
        """POST /product/search 返回 200"""
        with patch("src.api.product_routes._get_search_provider_hub") as mock_hub:
            mock_hub.return_value.search.return_value = {
                "status": "not_configured",
                "results": [],
                "provider": "",
                "fallback_chain": [],
            }
            response = client.post("/product/search?query=AI算力")
            assert response.status_code == 200

    def test_theme_evidence_endpoint(self, client):
        """GET /product/theme-evidence 返回 200"""
        with patch("src.api.product_routes._get_theme_evidence_service") as mock_service:
            mock_service.return_value.get_theme_evidence.return_value = {
                "status": "ok",
                "symbols": ["600584.SH"],
                "theme_tags": [],
                "news_results": [],
                "is_demo": False,
            }
            response = client.get("/product/theme-evidence?symbols=600584.SH")
            assert response.status_code == 200
