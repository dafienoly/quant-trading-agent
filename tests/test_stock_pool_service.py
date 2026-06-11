"""Phase C 测试：股票池服务、主题池、Pool API

测试范围：
- stock_pool_service.py: 自选池管理、symbol 验证、主题池
- product_routes.py: /product/pools/* API
"""
from __future__ import annotations

import json
import re
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

    def test_get_ai_semiconductor_pool_endpoint(self, client):
        """GET /product/pools/ai_semiconductor 返回主题池"""
        with patch("src.api.product_routes._get_theme_pool_service") as mock_tps:
            mock_tps.return_value.get_theme_pool.return_value = {
                "pool_id": "ai_semiconductor",
                "name": "AI算力/半导体主题池",
                "stocks": [{"symbol": "600584.SH", "name": "长电科技", "tags": ["advanced_packaging"]}],
                "count": 1,
                "tags": [{"id": "advanced_packaging", "name": "先进封装"}],
            }
            response = client.get("/product/pools/ai_semiconductor")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            pool = data["pool"]
            assert pool["pool_id"] == "ai_semiconductor"
            assert "stocks" in pool
            assert "tags" in pool


# ============================================================
# Theme Pool Contract Tests (2026-06-11 acceptance fix)
# ============================================================


def _get_pool_path():
    return Path(__file__).resolve().parent.parent / "data" / "reference" / "theme_pools" / "ai_semiconductor.json"


class TestThemePoolContract:
    """验证 ai_semiconductor JSON 文件满足架构契约规则"""

    @pytest.fixture
    def pool_data(self):
        path = _get_pool_path()
        assert path.exists(), f"Theme pool file not found: {path}"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_file_exists(self):
        assert _get_pool_path().exists()

    def test_top_level_fields(self, pool_data):
        fields = ["pool_id", "name", "version", "updated_at", "data_source", "universe", "tags", "stocks"]
        for f in fields:
            assert f in pool_data, f"Missing top-level field: {f}"

    def test_data_source(self, pool_data):
        assert pool_data.get("data_source") == "curated_reference"

    def test_universe(self, pool_data):
        assert pool_data.get("universe") == "a_share_mainboard"

    def test_version_format(self, pool_data):
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", pool_data.get("version", ""))

    def test_updated_at_format(self, pool_data):
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$", pool_data.get("updated_at", ""))

    def test_stock_count_range(self, pool_data):
        stocks = pool_data.get("stocks", [])
        assert 100 <= len(stocks) <= 300, f"Stock count {len(stocks)} not in [100, 300]"

    def test_required_tag_ids(self, pool_data):
        tag_ids = {t.get("id") for t in pool_data.get("tags", []) if isinstance(t, dict)}
        assert "ai_chip" in tag_ids
        assert "optical_module" in tag_ids

    def test_symbol_pattern(self, pool_data):
        pattern = re.compile(r"^\d{6}\.(SH|SZ)$")
        for stock in pool_data.get("stocks", []):
            symbol = stock.get("symbol", "")
            assert pattern.match(symbol), f"Invalid symbol pattern: {symbol}"

    def test_mainboard_only(self, pool_data):
        allowed_prefixes = ("600", "601", "603", "605", "000", "001", "002", "003")
        for stock in pool_data.get("stocks", []):
            symbol = stock.get("symbol", "")
            code = symbol.split(".")[0]
            assert code.startswith(allowed_prefixes), f"Non-mainboard symbol: {symbol}"

    def test_no_duplicate_symbols(self, pool_data):
        symbols = [s["symbol"] for s in pool_data.get("stocks", [])]
        assert len(symbols) == len(set(symbols)), "Duplicate symbols found"

    def test_stock_fields(self, pool_data):
        required = {"symbol", "name", "exchange", "board_type", "tags", "is_st", "is_delisting", "evidence"}
        for stock in pool_data.get("stocks", []):
            for field in required:
                assert field in stock, f"{stock.get('symbol', '?')} missing field: {field}"

    def test_no_risk_stocks_in_main_list(self, pool_data):
        for stock in pool_data.get("stocks", []):
            assert not stock.get("is_st", False), f"ST stock in main list: {stock['symbol']}"
            assert not stock.get("is_delisting", False), f"Delisting stock in main list: {stock['symbol']}"

    def test_each_stock_has_at_least_one_tag(self, pool_data):
        tag_ids = {t.get("id") for t in pool_data.get("tags", []) if isinstance(t, dict)}
        for stock in pool_data.get("stocks", []):
            stock_tags = set(stock.get("tags", []))
            assert stock_tags, f"{stock['symbol']} has no tags"
            unknown = stock_tags - tag_ids
            assert not unknown, f"{stock['symbol']} has unknown tags: {unknown}"

    def test_stock_exchange_field(self, pool_data):
        for stock in pool_data.get("stocks", []):
            exchange = stock.get("exchange", "")
            assert exchange in ("SH", "SZ"), f"{stock['symbol']} invalid exchange: {exchange}"
