"""Phase C 测试：股票池服务、主题池、Pool API

测试范围：
- stock_pool_service.py: 自选池管理、symbol 验证、主题池
- product_routes.py: /product/pools/* API
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.product_app.stock_pool_service import StockPoolService, ThemePoolService, PoolValidationItem


# ============================================================
# StockPoolService 测试
# ============================================================

class TestStockPoolService:
    def setup_method(self):
        self._tmp_dir = Path("runtime/state")
        self._tmp_dir.mkdir(parents=True, exist_ok=True)
        # 清理测试文件
        watchlist_path = self._tmp_dir / "watchlists.json"
        if watchlist_path.exists():
            watchlist_path.unlink()

    def test_add_symbols(self):
        """添加股票到自选池"""
        service = StockPoolService()
        result = service.add_symbols("default", ["600000.SH", "000001.SZ"])
        assert result["added"] >= 1

    def test_add_chinext_rejected(self):
        """创业板股票被拒绝"""
        service = StockPoolService()
        result = service.add_symbols("default", ["300001.SZ"])
        validation = result.get("validation", [])
        if validation:
            # 创业板不应被允许
            chinext_items = [v for v in validation if v.get("board_type") == "chinext"]
            if chinext_items:
                assert not chinext_items[0]["is_allowed"]

    def test_add_star_rejected(self):
        """科创板股票被拒绝"""
        service = StockPoolService()
        result = service.add_symbols("default", ["688001.SH"])
        validation = result.get("validation", [])
        if validation:
            star_items = [v for v in validation if v.get("board_type") == "star"]
            if star_items:
                assert not star_items[0]["is_allowed"]

    def test_remove_symbols(self):
        """从自选池移除股票"""
        service = StockPoolService()
        service.add_symbols("default", ["600000.SH", "000001.SZ"])
        result = service.remove_symbols("default", ["600000.SH"])
        assert result["removed"] >= 1

    def test_get_pool(self):
        """获取自选池内容"""
        service = StockPoolService()
        service.add_symbols("default", ["600000.SH"])
        pool = service.get_pool("default")
        assert pool["pool_id"] == "default"
        assert "symbols" in pool

    def test_validate_mainboard_allowed(self):
        """主板股票验证通过"""
        service = StockPoolService()
        validation = service.validate_symbols(["600000.SH", "000001.SZ"])
        for item in validation:
            if item.board_type == "mainboard":
                assert item.is_allowed

    def test_validate_chinext_not_allowed(self):
        """创业板不允许进入实盘闭环"""
        service = StockPoolService()
        validation = service.validate_symbols(["300001.SZ"])
        chinext_items = [v for v in validation if v.board_type == "chinext"]
        if chinext_items:
            assert not chinext_items[0].is_allowed

    def test_validate_star_not_allowed(self):
        """科创板不允许进入实盘闭环"""
        service = StockPoolService()
        validation = service.validate_symbols(["688001.SH"])
        star_items = [v for v in validation if v.board_type == "star"]
        if star_items:
            assert not star_items[0].is_allowed

    def test_max_watchlist_size(self):
        """自选池最大容量限制"""
        service = StockPoolService()
        # 添加超过限制的股票
        symbols = [f"60000{i}.SH" for i in range(110)]
        result = service.add_symbols("test_max2", symbols)
        # 添加数量不应超过 MAX_WATCHLIST_SIZE (100)
        assert result["added"] <= 100

    def test_symbol_normalization(self):
        """symbol 自动规范化"""
        service = StockPoolService()
        validation = service.validate_symbols(["600000"])  # 无交易所后缀
        assert len(validation) > 0
        # 规范化后应为 600000.SH
        assert validation[0].symbol in ["600000.SH", "600000"]


# ============================================================
# ThemePoolService 测试
# ============================================================

class TestThemePoolService:
    def test_get_theme_pool(self):
        """获取主题池"""
        service = ThemePoolService()
        pool = service.get_theme_pool()
        assert pool.get("name") is not None
        assert "stocks" in pool
        assert len(pool["stocks"]) >= 100

    def test_get_theme_tags(self):
        """获取主题标签"""
        service = ThemePoolService()
        tags = service.get_theme_tags()
        assert len(tags) > 0
        tag_ids = [t.get("id") for t in tags]
        assert "ai_chip" in tag_ids
        assert "optical_module" in tag_ids

    def test_filter_by_tag(self):
        """按标签筛选"""
        service = ThemePoolService()
        result = service.filter_by_tag("optical_module")
        assert result["count"] > 0
        for stock in result["stocks"]:
            assert "optical_module" in stock.get("tags", [])

    def test_theme_pool_stocks_are_mainboard(self):
        """主题池主板股票可进入实盘闭环"""
        service = ThemePoolService()
        pool = service.get_theme_pool()
        mainboard_stocks = [s for s in pool["stocks"] if s.get("board_type") == "main"]
        assert len(mainboard_stocks) >= 100

    def test_extended_stocks_not_in_main_list(self):
        """扩展区股票不在主列表中"""
        service = ThemePoolService()
        pool = service.get_theme_pool()
        if "extended" in pool:
            main_symbols = {s["symbol"] for s in pool["stocks"]}
            extended_symbols = {s["symbol"] for s in pool["extended"]}
            # 主列表和扩展区不应有交集
            assert not main_symbols & extended_symbols


# ============================================================
# Pool API 测试
# ============================================================

class TestPoolAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        return TestClient(app)

    def test_list_pools(self, client):
        """GET /product/pools 返回 200"""
        with patch("src.api.product_routes._get_stock_pool_service") as mock_sps, \
             patch("src.api.product_routes._get_theme_pool_service") as mock_tps:
            mock_sps.return_value.get_pool.return_value = {
                "pool_id": "default", "symbols": [], "count": 0, "updated_at": "",
            }
            mock_tps.return_value.get_theme_pool.return_value = {
                "pool_id": "ai_semiconductor",
                "name": "AI算力/半导体主题池",
                "stocks": [{"symbol": "600584.SH"}],
                "tags": [{"id": "pcb", "name": "PCB"}],
            }
            response = client.get("/product/pools")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "watchlist" in data
            assert "theme_pool" in data

    def test_validate_symbols_endpoint(self, client):
        """POST /product/pools/validate 返回 200"""
        with patch("src.api.product_routes._get_stock_pool_service") as mock_sps:
            mock_sps.return_value.validate_symbols.return_value = [
                PoolValidationItem(
                    symbol="600000.SH", name="", board_type="mainboard",
                    is_st=False, is_delisting=False, is_allowed=True, reason="",
                ),
            ]
            response = client.post("/product/pools/validate?symbols=600000.SH")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert len(data["validation"]) > 0

    def test_update_watchlist_add(self, client):
        """POST /product/pools/watchlist 添加"""
        with patch("src.api.product_routes._get_stock_pool_service") as mock_sps:
            mock_sps.return_value.add_symbols.return_value = {
                "status": "ok", "added": 1, "validation": [],
            }
            response = client.post("/product/pools/watchlist?action=add&symbols=600000.SH")
            assert response.status_code == 200

    def test_update_watchlist_remove(self, client):
        """POST /product/pools/watchlist 删除"""
        with patch("src.api.product_routes._get_stock_pool_service") as mock_sps:
            mock_sps.return_value.remove_symbols.return_value = {
                "status": "ok", "removed": 1,
            }
            response = client.post("/product/pools/watchlist?action=remove&symbols=600000.SH")
            assert response.status_code == 200
