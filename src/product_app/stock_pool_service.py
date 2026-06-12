"""股票池服务

提供用户自选股池（Watchlist）和主题股票池（Theme Pool）的管理能力。
自选股池支持添加/删除/验证，主题池提供 AI 算力/半导体等内置主题。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.stock_pool.mainboard_filter import is_mainboard, is_excluded, is_st
from src.data_gateway.live_data_mapper import normalize_a_share_symbol

# ============================================================
# 路径常量
# ============================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_WATCHLIST_PATH = _PROJECT_ROOT / "runtime" / "state" / "watchlists.json"
_THEME_POOL_DIR = _PROJECT_ROOT / "data" / "reference" / "theme_pools"
_AI_SEMICONDUCTOR_PATH = _THEME_POOL_DIR / "ai_semiconductor.json"

# ============================================================
# 环境配置
# ============================================================

MAX_WATCHLIST_SIZE = int(os.getenv("MAX_WATCHLIST_SIZE", "100"))
MAX_THEME_POOL_SIZE = int(os.getenv("MAX_THEME_POOL_SIZE", "300"))

# ============================================================
# 板块分类映射
# ============================================================

_BOARD_TYPE_MAP: dict[str, str] = {
    "000": "mainboard",
    "001": "mainboard",
    "002": "sme",
    "300": "chinext",
    "301": "chinext",
    "600": "mainboard",
    "601": "mainboard",
    "603": "mainboard",
    "605": "mainboard",
    "688": "star",
    "689": "star",
}


def _get_board_type(symbol: str) -> str:
    """根据代码前缀判断板块类型"""
    code = symbol.split(".")[0] if "." in symbol else symbol
    for prefix, board in _BOARD_TYPE_MAP.items():
        if code.startswith(prefix):
            return board
    return "unknown"


# ============================================================
# 数据模型
# ============================================================

@dataclass
class PoolValidationItem:
    """股票池验证项

    对每只股票进行合规性校验，判断是否允许加入自选股池。
    """
    symbol: str
    name: str
    board_type: str  # "mainboard" | "chinext" | "star" | "sme"
    is_st: bool
    is_delisting: bool
    is_allowed: bool
    reason: str


@dataclass
class WatchlistPool:
    """自选股池数据结构"""
    pool_id: str
    symbols: list[str] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "symbols": self.symbols,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WatchlistPool:
        return cls(
            pool_id=data.get("pool_id", ""),
            symbols=data.get("symbols", []),
            updated_at=data.get("updated_at", ""),
        )


# ============================================================
# StockPoolService — 用户自选股池管理
# ============================================================

class StockPoolService:
    """用户自选股池服务

    职责：
    - 添加/删除自选股（上限 MAX_WATCHLIST_SIZE）
    - 获取自选股池内容
    - 验证股票是否符合 A 股主板交易规则
    """

    def __init__(self) -> None:
        self._pools: dict[str, WatchlistPool] = {}
        self._loaded = False

    # ----------------------------------------------------------
    # 持久化
    # ----------------------------------------------------------

    def _load(self) -> None:
        """从 watchlists.json 加载自选股池"""
        if self._loaded:
            return
        if _WATCHLIST_PATH.exists():
            try:
                with open(_WATCHLIST_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for pool_id, pool_data in data.items():
                        if isinstance(pool_data, dict):
                            pool_data.setdefault("pool_id", pool_id)
                            self._pools[pool_id] = WatchlistPool.from_dict(pool_data)
                logger.info(f"已加载自选股池: {len(self._pools)} 个")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"加载自选股池失败: {e}")
        self._loaded = True

    def _save(self) -> None:
        """保存自选股池到 watchlists.json"""
        try:
            _WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {pid: pool.to_dict() for pid, pool in self._pools.items()}
            with open(_WATCHLIST_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"自选股池已保存到 {_WATCHLIST_PATH}")
        except OSError as e:
            logger.error(f"保存自选股池失败: {e}")

    def _ensure_pool(self, pool_id: str) -> WatchlistPool:
        """确保池存在，不存在则创建"""
        if pool_id not in self._pools:
            self._pools[pool_id] = WatchlistPool(pool_id=pool_id)
        return self._pools[pool_id]

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------

    def add_symbols(self, pool_id: str, symbols: list[str]) -> dict[str, Any]:
        """向自选股池添加股票

        规则：
        - 先验证所有股票，仅添加 is_allowed=True 的股票
        - 池容量上限 MAX_WATCHLIST_SIZE
        - 自动去重
        - symbol 会被规范化为 CODE.EXCHANGE 格式

        返回:
            dict 包含 added, skipped, validation, message
        """
        self._load()
        pool = self._ensure_pool(pool_id)

        # 规范化 symbol
        normalized = []
        for s in symbols:
            ns = normalize_a_share_symbol(s)
            if ns:
                normalized.append(ns)

        # 验证
        validation_items = self.validate_symbols(normalized)

        # 筛选允许的股票
        allowed_symbols = [v.symbol for v in validation_items if v.is_allowed]

        # 去重：排除已在池中的
        existing_set = set(pool.symbols)
        new_symbols = [s for s in allowed_symbols if s not in existing_set]

        # 容量检查
        remaining = MAX_WATCHLIST_SIZE - len(pool.symbols)
        if remaining <= 0:
            return {
                "added": 0,
                "skipped": len(normalized),
                "validation": [self._item_to_dict(v) for v in validation_items],
                "message": f"自选股池已满（上限 {MAX_WATCHLIST_SIZE}）",
            }

        to_add = new_symbols[:remaining]
        skipped_count = len(normalized) - len(to_add)

        pool.symbols.extend(to_add)
        pool.updated_at = datetime.now().isoformat()
        self._save()

        msg = f"已添加 {len(to_add)} 只股票到自选股池 '{pool_id}'"
        if skipped_count > 0:
            msg += f"，跳过 {skipped_count} 只（验证不通过或超出容量）"
        logger.info(msg)

        return {
            "added": len(to_add),
            "skipped": skipped_count,
            "validation": [self._item_to_dict(v) for v in validation_items],
            "message": msg,
        }

    def remove_symbols(self, pool_id: str, symbols: list[str]) -> dict[str, Any]:
        """从自选股池移除股票

        返回:
            dict 包含 removed, message
        """
        self._load()

        if pool_id not in self._pools:
            return {"removed": 0, "message": f"自选股池 '{pool_id}' 不存在"}

        pool = self._pools[pool_id]

        # 规范化待移除的 symbol
        normalized_remove = set()
        for s in symbols:
            ns = normalize_a_share_symbol(s)
            if ns:
                normalized_remove.add(ns)

        before = len(pool.symbols)
        pool.symbols = [s for s in pool.symbols if s not in normalized_remove]
        removed = before - len(pool.symbols)

        if removed > 0:
            pool.updated_at = datetime.now().isoformat()
            self._save()

        msg = f"已从自选股池 '{pool_id}' 移除 {removed} 只股票"
        logger.info(msg)

        return {"removed": removed, "message": msg}

    def get_pool(self, pool_id: str) -> dict[str, Any]:
        """获取自选股池内容

        返回:
            dict 包含 pool_id, symbols, updated_at, count
        """
        self._load()

        if pool_id not in self._pools:
            return {
                "pool_id": pool_id,
                "symbols": [],
                "updated_at": "",
                "count": 0,
            }

        pool = self._pools[pool_id]
        return {
            "pool_id": pool.pool_id,
            "symbols": list(pool.symbols),
            "updated_at": pool.updated_at,
            "count": len(pool.symbols),
        }

    def validate_symbols(self, symbols: list[str]) -> list[PoolValidationItem]:
        """验证股票列表是否符合 A 股主板交易规则

        规则：
        - 创业板 (300xxx, 301xxx): 不允许
        - 科创板 (688xxx, 689xxx): 不允许
        - ST 股票: 不允许
        - 退市整理股: 不允许
        - 仅 A 股主板 (000xxx, 001xxx, 002xxx, 600xxx, 601xxx, 603xxx, 605xxx) 允许
        """
        results: list[PoolValidationItem] = []

        for symbol in symbols:
            board_type = _get_board_type(symbol)

            # 判断是否 ST（基于 symbol 无法直接获取名称，暂用代码判断）
            # is_st 需要名称，此处先标记为 False，后续可扩展
            symbol_is_st = False
            symbol_is_delisting = False

            # 判断是否被排除（创业板/科创板）
            excluded = is_excluded(symbol)

            # 判断是否主板
            mainboard = is_mainboard(symbol)

            # 退市整理股判断：代码中包含退市标识
            # 退市股通常在名称中带"退"，此处基于代码无法判断，预留字段
            symbol_is_delisting = False

            # 综合判断是否允许
            is_allowed = True
            reason = ""

            if excluded:
                is_allowed = False
                if board_type == "chinext":
                    reason = "创业板股票不允许加入实盘闭环自选股池"
                elif board_type == "star":
                    reason = "科创板股票不允许加入实盘闭环自选股池"
                else:
                    reason = "非主板股票不允许加入自选股池"
            elif not mainboard:
                is_allowed = False
                reason = f"非 A 股主板股票（板块: {board_type}），不允许加入自选股池"

            if symbol_is_st:
                is_allowed = False
                reason = "ST 股票不允许加入自选股池"

            if symbol_is_delisting:
                is_allowed = False
                reason = "退市整理股不允许加入自选股池"

            results.append(PoolValidationItem(
                symbol=symbol,
                name="",  # 名称需要从行情数据获取，此处留空
                board_type=board_type,
                is_st=symbol_is_st,
                is_delisting=symbol_is_delisting,
                is_allowed=is_allowed,
                reason=reason,
            ))

        return results

    def validate_symbols_with_names(
        self, symbols: list[dict[str, str]]
    ) -> list[PoolValidationItem]:
        """验证股票列表（带名称），用于有名称数据的场景

        参数:
            symbols: [{"symbol": "600000.SH", "name": "浦发银行"}, ...]
        """
        results: list[PoolValidationItem] = []

        for item in symbols:
            symbol = item.get("symbol", "")
            name = item.get("name", "")
            board_type = _get_board_type(symbol)

            # 使用 is_st 判断 ST 和退市
            symbol_is_st = is_st(name)
            symbol_is_delisting = "退" in name if name else False

            # 判断是否被排除（创业板/科创板）
            excluded = is_excluded(symbol)

            # 判断是否主板
            mainboard = is_mainboard(symbol)

            # 综合判断是否允许
            is_allowed = True
            reason = ""

            if excluded:
                is_allowed = False
                if board_type == "chinext":
                    reason = "创业板股票不允许加入实盘闭环自选股池"
                elif board_type == "star":
                    reason = "科创板股票不允许加入实盘闭环自选股池"
                else:
                    reason = "非主板股票不允许加入自选股池"
            elif not mainboard:
                is_allowed = False
                reason = f"非 A 股主板股票（板块: {board_type}），不允许加入自选股池"

            if symbol_is_st:
                is_allowed = False
                reason = "ST 股票不允许加入自选股池"

            if symbol_is_delisting:
                is_allowed = False
                reason = "退市整理股不允许加入自选股池"

            results.append(PoolValidationItem(
                symbol=symbol,
                name=name,
                board_type=board_type,
                is_st=symbol_is_st,
                is_delisting=symbol_is_delisting,
                is_allowed=is_allowed,
                reason=reason,
            ))

        return results

    @staticmethod
    def _item_to_dict(item: PoolValidationItem) -> dict[str, Any]:
        return {
            "symbol": item.symbol,
            "name": item.name,
            "board_type": item.board_type,
            "is_st": item.is_st,
            "is_delisting": item.is_delisting,
            "is_allowed": item.is_allowed,
            "reason": item.reason,
        }


# ============================================================
# ThemePoolService — 主题股票池管理
# ============================================================

class ThemePoolService:
    """主题股票池服务

    职责：
    - 提供内置 AI 算力/半导体主题池
    - 按主题标签筛选股票
    - 主题池上限 MAX_THEME_POOL_SIZE
    """

    def __init__(self) -> None:
        self._theme_data: dict[str, Any] = {}
        self._loaded = False

    # ----------------------------------------------------------
    # 持久化
    # ----------------------------------------------------------

    def _load(self) -> None:
        """加载 AI 半导体主题池数据"""
        if self._loaded:
            return
        if _AI_SEMICONDUCTOR_PATH.exists():
            try:
                with open(_AI_SEMICONDUCTOR_PATH, "r", encoding="utf-8") as f:
                    self._theme_data = json.load(f)
                logger.info(f"已加载 AI 半导体主题池: {len(self._theme_data.get('stocks', []))} 只股票")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"加载 AI 半导体主题池失败: {e}")
                self._theme_data = {"name": "AI算力/半导体", "stocks": [], "tags": []}
        else:
            logger.info("AI 半导体主题池数据文件不存在，使用空数据")
            self._theme_data = {"name": "AI算力/半导体", "stocks": [], "tags": []}
        self._loaded = True

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------

    def get_theme_pool(self) -> dict[str, Any]:
        """获取 AI 算力/半导体主题池

        返回:
            dict 包含 name, stocks, count, tags
        """
        self._load()

        stocks = self._theme_data.get("stocks", [])
        # 上限截断
        stocks = stocks[:MAX_THEME_POOL_SIZE]

        return {
            "pool_id": self._theme_data.get("pool_id", "ai_semiconductor"),
            "name": self._theme_data.get("name", "AI算力/半导体"),
            "stocks": stocks,
            "count": len(stocks),
            "tags": self._theme_data.get("tags", []),
        }

    def get_theme_tags(self) -> list[str]:
        """获取可用的主题标签列表

        返回:
            标签名称列表，如 ["AI芯片", "GPU", "光模块", "半导体设备", ...]
        """
        self._load()
        return list(self._theme_data.get("tags", []))

    def filter_by_tag(self, tag: str) -> dict[str, Any]:
        """按主题标签筛选股票

        参数:
            tag: 主题标签名称

        返回:
            dict 包含 tag, stocks, count
        """
        self._load()

        all_stocks = self._theme_data.get("stocks", [])
        filtered = [
            s for s in all_stocks
            if isinstance(s, dict) and tag in s.get("tags", [])
        ]

        # 上限截断
        filtered = filtered[:MAX_THEME_POOL_SIZE]

        return {
            "tag": tag,
            "stocks": filtered,
            "count": len(filtered),
        }


# ============================================================
# 模块级单例
# ============================================================

_stock_pool_service: StockPoolService | None = None
_theme_pool_service: ThemePoolService | None = None


def get_stock_pool_service() -> StockPoolService:
    """获取全局自选股池服务单例"""
    global _stock_pool_service
    if _stock_pool_service is None:
        _stock_pool_service = StockPoolService()
    return _stock_pool_service


def get_theme_pool_service() -> ThemePoolService:
    """获取全局主题股票池服务单例"""
    global _theme_pool_service
    if _theme_pool_service is None:
        _theme_pool_service = ThemePoolService()
    return _theme_pool_service
