"""搜索提供者中心

按架构文档 §5.8 / §8 要求，支持 Tavily / AnySearch / Firecrawl 三个独立搜索 Provider：
- 每个 Provider 有独立的 API Key 和 Endpoint
- SEARCH_PROVIDER_ORDER 控制 fallback 顺序
- SEARCH_DAILY_CALL_BUDGET 统一预算控制
- 查询结果缓存 4 小时

关键规则：
- 搜索失败不阻断实时行情
- 搜索结果不直接决定买卖
- API Key 只读环境变量，不写入仓库
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from loguru import logger

# ============================================================
# 路径常量
# ============================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BUDGET_FILE = _PROJECT_ROOT / "runtime" / "state" / "search_budget.json"
_CACHE_DIR = _PROJECT_ROOT / "runtime" / "cache" / "search"

# ============================================================
# 环境配置
# ============================================================

SEARCH_PROVIDER_ORDER = [
    s.strip()
    for s in os.getenv("SEARCH_PROVIDER_ORDER", "tavily,anysearch,firecrawl").split(",")
    if s.strip()
]
SEARCH_DAILY_CALL_BUDGET = int(os.getenv("SEARCH_DAILY_CALL_BUDGET", "2500"))
CACHE_TTL_SECONDS = 4 * 3600  # 4 小时

# 各 Provider 独立 API Key
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
ANYSEARCH_API_KEY = os.getenv("ANYSEARCH_API_KEY", "")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")


# ============================================================
# SearchProvider 协议
# ============================================================

class SearchProvider(Protocol):
    """搜索 Provider 协议"""
    name: str

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """执行搜索，返回结果列表"""
        ...


# ============================================================
# Tavily Provider
# ============================================================

class TavilyProvider:
    """Tavily 搜索 Provider — 专为 AI 应用设计的搜索 API

    API 文档: https://tavily.com
    Endpoint: https://api.tavily.com/search
    """

    name = "tavily"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else TAVILY_API_KEY
        self._base_url = "https://api.tavily.com/search"

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        if not self._api_key:
            raise RuntimeError("TAVILY_API_KEY 未配置")

        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }

        with httpx.Client(timeout=15.0) as client:
            response = client.post(self._base_url, json=payload)
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "date": item.get("published_date", ""),
                "provider": "tavily",
            })

        return results


# ============================================================
# AnySearch Provider
# ============================================================

class AnySearchProvider:
    """AnySearch 搜索 Provider — 统一搜索入口

    API 文档: https://anysearch.com
    Endpoint: https://api.anysearch.com/mcp
    """

    name = "anysearch"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else ANYSEARCH_API_KEY
        self._base_url = "https://api.anysearch.com/mcp"

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        if not self._api_key:
            raise RuntimeError("ANYSEARCH_API_KEY 未配置")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "max_results": max_results,
        }

        with httpx.Client(timeout=15.0) as client:
            response = client.post(self._base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", item.get("content", "")),
                "date": item.get("date", ""),
                "provider": "anysearch",
            })

        return results


# ============================================================
# Firecrawl Provider
# ============================================================

class FirecrawlProvider:
    """Firecrawl 搜索 Provider — 网页抓取和搜索

    API 文档: https://firecrawl.dev
    Endpoint: https://api.firecrawl.dev/v1/search
    """

    name = "firecrawl"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else FIRECRAWL_API_KEY
        self._base_url = "https://api.firecrawl.dev/v1/search"

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        if not self._api_key:
            raise RuntimeError("FIRECRAWL_API_KEY 未配置")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "limit": max_results,
        }

        with httpx.Client(timeout=15.0) as client:
            response = client.post(self._base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("data", data.get("results", []))[:max_results]:
            results.append({
                "title": item.get("metadata", {}).get("title", item.get("title", "")),
                "url": item.get("metadata", {}).get("sourceURL", item.get("url", "")),
                "snippet": item.get("markdown", item.get("content", ""))[:500],
                "date": item.get("metadata", {}).get("publishedTime", ""),
                "provider": "firecrawl",
            })

        return results


# ============================================================
# Provider 注册表
# ============================================================

_PROVIDER_CLASSES: dict[str, type] = {
    "tavily": TavilyProvider,
    "anysearch": AnySearchProvider,
    "firecrawl": FirecrawlProvider,
}


# ============================================================
# SearchProviderHub
# ============================================================

class SearchProviderHub:
    """搜索提供者中心

    职责：
    - 按 SEARCH_PROVIDER_ORDER 依次尝试搜索 Provider
    - 每日预算控制（SEARCH_DAILY_CALL_BUDGET）
    - 查询结果缓存，减少 API 调用
    - 所有 Provider 失败时返回 not_configured 或 all_failed
    """

    def __init__(self) -> None:
        self._budget_file = _BUDGET_FILE
        self._cache_dir = _CACHE_DIR
        self._providers = self._build_providers()

    def _build_providers(self) -> list[SearchProvider]:
        """按 SEARCH_PROVIDER_ORDER 构建已配置的 provider 列表"""
        providers = []
        for name in SEARCH_PROVIDER_ORDER:
            cls = _PROVIDER_CLASSES.get(name)
            if cls is None:
                logger.warning(f"未知搜索 Provider: {name}")
                continue
            try:
                provider = cls()
                if provider.is_configured:
                    providers.append(provider)
                    logger.info(f"搜索 Provider 已就绪: {name}")
                else:
                    logger.debug(f"搜索 Provider 未配置 API Key: {name}")
            except Exception as e:
                logger.warning(f"初始化搜索 Provider 失败: {name} - {e}")
        return providers

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------

    def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """执行搜索，带预算检查、缓存和 Provider fallback

        参数:
            query: 搜索关键词
            max_results: 最大返回结果数

        返回:
            dict 包含 status, source, results, provider, fallback_chain 等字段
        """
        # 1. 检查是否有可用 Provider
        if not self._providers:
            logger.warning("无可用搜索 Provider（未配置任何 API Key）")
            return {
                "status": "not_configured",
                "results": [],
                "provider": "",
                "fallback_chain": [],
            }

        # 2. 检查缓存
        cached = self._cache_get(query)
        if cached is not None:
            logger.debug(f"搜索缓存命中: {query}")
            return {
                "status": "ok",
                "source": "cache",
                "results": cached[:max_results],
                "provider": "cache",
                "fallback_chain": ["cache: hit"],
            }

        # 3. 检查预算
        if not self._check_budget():
            logger.warning(f"搜索预算已耗尽 (上限 {SEARCH_DAILY_CALL_BUDGET})")
            return {
                "status": "budget_exceeded",
                "results": [],
                "provider": "",
                "fallback_chain": [],
            }

        # 4. 按 Provider 顺序尝试搜索
        fallback_chain: list[str] = []
        for provider in self._providers:
            try:
                results = provider.search(query, max_results)
                if results:
                    self._record_usage(cost=1)
                    self._cache_set(query, results)
                    fallback_chain.append(f"{provider.name}: ok")
                    logger.info(f"搜索完成: '{query}' via {provider.name} -> {len(results)} 条结果")
                    return {
                        "status": "ok",
                        "source": "api",
                        "results": results,
                        "provider": provider.name,
                        "fallback_chain": fallback_chain,
                    }
                fallback_chain.append(f"{provider.name}: empty_results")
            except Exception as e:
                fallback_chain.append(f"{provider.name}: {e}")
                logger.warning(f"搜索 Provider {provider.name} 失败: {e}")
                continue

        # 所有 Provider 都失败
        logger.error(f"所有搜索 Provider 均失败: {fallback_chain}")
        return {
            "status": "all_failed",
            "results": [],
            "provider": "",
            "fallback_chain": fallback_chain,
        }

    def get_provider_status(self) -> list[dict[str, Any]]:
        """获取所有搜索 Provider 的状态"""
        status = []
        for name in SEARCH_PROVIDER_ORDER:
            cls = _PROVIDER_CLASSES.get(name)
            if cls is None:
                continue
            try:
                provider = cls()
                status.append({
                    "name": name,
                    "configured": provider.is_configured,
                })
            except Exception:
                status.append({"name": name, "configured": False})
        return status

    # ----------------------------------------------------------
    # 预算控制
    # ----------------------------------------------------------

    def _check_budget(self) -> bool:
        """检查当前预算是否允许搜索"""
        usage = self._load_budget()
        today = datetime.now().strftime("%Y-%m-%d")

        if usage.get("date") != today:
            return True

        return usage.get("count", 0) < SEARCH_DAILY_CALL_BUDGET

    def _record_usage(self, cost: int = 1) -> None:
        """记录使用量"""
        usage = self._load_budget()
        today = datetime.now().strftime("%Y-%m-%d")

        if usage.get("date") != today:
            usage = {"date": today, "count": cost}
        else:
            usage["count"] = usage.get("count", 0) + cost

        self._save_budget(usage)
        logger.debug(f"搜索预算已记录: 今日已用 {usage['count']}/{SEARCH_DAILY_CALL_BUDGET}")

    # ----------------------------------------------------------
    # 缓存
    # ----------------------------------------------------------

    def _cache_get(self, query: str) -> list[dict[str, Any]] | None:
        """从缓存获取搜索结果"""
        cache_key = self._make_cache_key(query)
        cache_file = self._cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            cached_at = data.get("cached_at", 0)
            if time.time() - cached_at > CACHE_TTL_SECONDS:
                return None

            return data.get("results", [])
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取搜索缓存失败: {e}")
            return None

    def _cache_set(self, query: str, result: list[dict[str, Any]]) -> None:
        """将搜索结果写入缓存"""
        cache_key = self._make_cache_key(query)
        cache_file = self._cache_dir / f"{cache_key}.json"

        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "query": query,
                "cached_at": time.time(),
                "results": result,
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.warning(f"写入搜索缓存失败: {e}")

    # ----------------------------------------------------------
    # 内部工具
    # ----------------------------------------------------------

    @staticmethod
    def _make_cache_key(query: str) -> str:
        """生成缓存键（query 的 MD5）"""
        return hashlib.md5(query.encode("utf-8")).hexdigest()

    def _load_budget(self) -> dict[str, Any]:
        """加载预算使用记录"""
        if not self._budget_file.exists():
            return {}
        try:
            with open(self._budget_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"加载搜索预算文件失败: {e}")
            return {}

    def _save_budget(self, usage: dict[str, Any]) -> None:
        """保存预算使用记录"""
        try:
            self._budget_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._budget_file, "w", encoding="utf-8") as f:
                json.dump(usage, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"保存搜索预算文件失败: {e}")


# ============================================================
# 模块级单例
# ============================================================

_search_provider_hub: SearchProviderHub | None = None


def get_search_provider_hub() -> SearchProviderHub:
    """获取全局搜索提供者中心单例"""
    global _search_provider_hub
    if _search_provider_hub is None:
        _search_provider_hub = SearchProviderHub()
    return _search_provider_hub
