"""主题证据服务

组合 ThemePoolService 与 SearchProviderHub，为股票收集主题证据。
根据股票所属主题标签搜索最新新闻，形成完整的主题证据链。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from src.product_app.stock_pool_service import get_theme_pool_service
from src.product_app.search_provider_hub import get_search_provider_hub


# ============================================================
# ThemeEvidenceService
# ============================================================

class ThemeEvidenceService:
    """主题证据服务

    职责：
    - 获取股票所属的主题标签
    - 按主题标签搜索最新新闻
    - 组合返回主题证据
    """

    def __init__(self) -> None:
        self._theme_pool_service = get_theme_pool_service()
        self._search_hub = get_search_provider_hub()

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------

    def get_theme_evidence(
        self,
        symbols: list[str],
        theme_tag: str | None = None,
    ) -> dict[str, Any]:
        """获取股票的主题证据

        参数:
            symbols: 股票代码列表，如 ["600000.SH", "000001.SZ"]
            theme_tag: 可选，指定只搜索某个主题标签

        返回:
            dict 包含 symbols, theme_tags, news_results, data_status, is_demo
        """
        # 1. 获取主题池数据
        theme_pool = self._theme_pool_service.get_theme_pool()
        all_stocks = theme_pool.get("stocks", [])

        if not all_stocks:
            logger.info("主题池为空，返回空证据")
            return {
                "symbols": symbols,
                "theme_tags": [],
                "news_results": [],
                "data_status": "theme_pool_empty",
                "is_demo": False,
            }

        # 2. 找出每个 symbol 所属的主题标签
        symbol_tag_map: dict[str, list[str]] = {}
        relevant_tags: set[str] = set()

        for symbol in symbols:
            matched_tags = []
            for stock in all_stocks:
                if not isinstance(stock, dict):
                    continue
                stock_symbol = stock.get("symbol", "")
                # 兼容带/不带交易所后缀的匹配
                if stock_symbol == symbol or stock_symbol.split(".")[0] == symbol.split(".")[0]:
                    stock_tags = stock.get("tags", [])
                    matched_tags.extend(stock_tags)
            # 去重
            matched_tags = list(dict.fromkeys(matched_tags))
            symbol_tag_map[symbol] = matched_tags
            relevant_tags.update(matched_tags)

        # 如果指定了 theme_tag，只搜索该标签
        if theme_tag:
            relevant_tags = {theme_tag} & relevant_tags
            if not relevant_tags:
                relevant_tags = {theme_tag}

        # 3. 按主题标签搜索新闻
        news_results: list[dict[str, Any]] = []
        budget_exceeded = False

        for tag in relevant_tags:
            search_result = self.search_theme_news(tag)
            status = search_result.get("status", "")

            if status == "budget_exceeded":
                budget_exceeded = True
                # 预算耗尽时返回已收集的部分结果
                logger.warning(f"搜索预算耗尽，标签 '{tag}' 搜索被跳过")
                continue

            if status == "not_configured":
                logger.warning("搜索 API 未配置，跳过新闻搜索")
                continue

            tag_news = search_result.get("results", [])
            for news_item in tag_news:
                news_results.append({
                    "theme_tag": tag,
                    **news_item,
                })

        # 4. 组装返回
        collected_tags = list(relevant_tags)
        data_status = "ok"
        if budget_exceeded:
            data_status = "partial_budget_exceeded"
        elif not news_results and relevant_tags:
            data_status = "no_news_found"

        return {
            "symbols": symbols,
            "theme_tags": collected_tags,
            "news_results": news_results,
            "data_status": data_status,
            "is_demo": False,
        }

    def search_theme_news(
        self,
        theme_tag: str,
        max_results: int = 5,
    ) -> dict[str, Any]:
        """搜索主题相关新闻

        参数:
            theme_tag: 主题标签名称，如 "AI芯片"
            max_results: 最大返回结果数

        返回:
            dict 包含 status, source, timestamp, results
        """
        # 构建搜索查询
        query = f"{theme_tag} 最新消息"
        logger.info(f"搜索主题新闻: '{query}'")

        search_result = self._search_hub.search(query, max_results=max_results)

        return {
            "status": search_result.get("status", "unknown"),
            "source": search_result.get("source", ""),
            "timestamp": datetime.now().isoformat(),
            "results": search_result.get("results", []),
        }


# ============================================================
# 模块级单例
# ============================================================

_theme_evidence_service: ThemeEvidenceService | None = None


def get_theme_evidence_service() -> ThemeEvidenceService:
    """获取全局主题证据服务单例"""
    global _theme_evidence_service
    if _theme_evidence_service is None:
        _theme_evidence_service = ThemeEvidenceService()
    return _theme_evidence_service
