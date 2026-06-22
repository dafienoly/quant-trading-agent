"""LiveDataService — 产品闭环唯一真实数据入口。

核心职责：
- 提供实时行情、历史日线、基础财务数据、完整研究上下文
- 调用 DataProviderHub 实现自动降级与熔断
- 调用 DataHealthGate 判断数据健康状态，决定是否允许信号和订单
- 全部真实源失败时写 Feedback Bug 并 fail closed

规则：
- allow_demo=False 是 live closed-loop 默认值
- is_demo 始终为 False
- data_status=FAILED 时 Signal Agent 和订单草稿 API 必须阻断
- 因子、回测、信号不能绕过 LiveDataService 直接读 provider
"""

from __future__ import annotations

REFRESH_IDLE = "IDLE"
REFRESH_QUEUED = "QUEUED"
REFRESH_RUNNING = "RUNNING"
REFRESH_SUCCEEDED = "SUCCEEDED"
REFRESH_FAILED = "FAILED"
REFRESH_CANCELLED = "CANCELLED"




import os
from typing import Any

import pandas as pd
from loguru import logger

from src.data_gateway.provider_contracts import DataCapability, ProviderResult
from src.data_gateway.provider_hub import DataProviderHub, ProviderCircuitBreaker
from src.data_gateway.live_data_mapper import (
    normalize_a_share_symbol,
    normalize_trade_date,
    map_realtime_quotes,
    map_daily_bars,
    map_fundamentals,
    validate_required_fields,
    REALTIME_REQUIRED_FIELDS,
    DAILY_BAR_REQUIRED_FIELDS,
    FUNDAMENTALS_REQUIRED_FIELDS,
)

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

LIVE_DATA_PROVIDER_ORDER = os.getenv(
    "LIVE_DATA_PROVIDER_ORDER", "eastmoney,akshare,aktools"
)
ENABLE_DEMO_FALLBACK_FOR_LIVE_LOOP = os.getenv(
    "ENABLE_DEMO_FALLBACK_FOR_LIVE_LOOP", "false"
).lower() in ("true", "1", "yes")
DATA_FAIL_CLOSED = os.getenv(
    "DATA_FAIL_CLOSED", "true"
).lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# DataFrame → list[dict] 工具
# ---------------------------------------------------------------------------

def _records_from_frame(df: pd.DataFrame) -> list[dict[str, Any]]:
    """将 DataFrame 转为 list[dict]，NaN → None，numpy 类型转 Python 原生类型。"""
    if df is None or df.empty:
        return []
    result = df.where(pd.notna(df), None).to_dict(orient="records")
    converted = []
    for row in result:
        converted_row = {}
        for key, value in row.items():
            if value is None:
                converted_row[str(key)] = None
            elif isinstance(value, (bool, int, float, str)):
                converted_row[str(key)] = value
            elif hasattr(value, "item"):
                # numpy scalar (numpy.bool_, numpy.int64, numpy.float64 等)
                converted_row[str(key)] = value.item()
            else:
                converted_row[str(key)] = value
        converted.append(converted_row)
    return converted


# ---------------------------------------------------------------------------
# LiveDataService
# ---------------------------------------------------------------------------

class LiveDataService:
    """产品闭环唯一真实数据入口。

    所有因子、回测、信号生成必须通过本服务获取数据，
    不得直接调用 AkShare / AkTools / Eastmoney provider。
    """

    def __init__(self) -> None:
        self._provider_order = [
            name.strip()
            for name in LIVE_DATA_PROVIDER_ORDER.split(",")
            if name.strip()
        ]
        self._realtime_hub = self._build_realtime_hub()
        self._daily_bars_hub = self._build_daily_bars_hub()
        self._fundamentals_hub = self._build_fundamentals_hub()
        self._feedback_service = None  # lazy init

    # ------------------------------------------------------------------
    # Provider Hub 构建
    # ------------------------------------------------------------------

    def _build_provider_hub(self) -> DataProviderHub:
        """按 LIVE_DATA_PROVIDER_ORDER 配置顺序构建通用 provider hub。

        用于 daily_bars 和 fundamentals 能力。
        """
        provider_order = [
            name.strip()
            for name in LIVE_DATA_PROVIDER_ORDER.split(",")
            if name.strip()
        ]

        providers: list[Any] = []
        for name in provider_order:
            try:
                provider = self._create_provider(name)
                if provider is not None:
                    providers.append(provider)
            except Exception as exc:
                logger.warning("Failed to create provider '{}': {}", name, exc)

        if not providers:
            logger.error("No providers available for LiveDataService")

        cb = ProviderCircuitBreaker()
        return DataProviderHub(providers=providers, circuit_breaker=cb)

    def _build_realtime_hub(self) -> DataProviderHub:
        """构建实时行情专用 hub。

        实时行情使用 EastmoneyProvider 和 AkShareRealtimeProvider，
        因为 AkShareProvider.get_realtime_quotes 会抛 NotImplementedError。
        """
        provider_order = [
            name.strip()
            for name in LIVE_DATA_PROVIDER_ORDER.split(",")
            if name.strip()
        ]

        providers: list[Any] = []
        for name in provider_order:
            try:
                if name == "eastmoney":
                    from src.data_gateway.eastmoney_provider import EastmoneyProvider
                    providers.append(EastmoneyProvider())
                elif name == "akshare":
                    from src.data_gateway.realtime_provider import AkShareRealtimeProvider
                    providers.append(AkShareRealtimeProvider())
                elif name == "aktools":
                    from src.data_gateway.aktools_provider import AkToolsProvider
                    providers.append(AkToolsProvider())
                else:
                    logger.warning("Unknown provider in LIVE_DATA_PROVIDER_ORDER: {}", name)
            except Exception as exc:
                logger.warning("Failed to create realtime provider '{}': {}", name, exc)

        if not providers:
            logger.error("No realtime providers available")

        cb = ProviderCircuitBreaker()
        return DataProviderHub(providers=providers, circuit_breaker=cb)

    def _build_daily_bars_hub(self) -> DataProviderHub:
        """构建日线行情专用 hub。"""
        provider_order = [
            name.strip()
            for name in LIVE_DATA_PROVIDER_ORDER.split(",")
            if name.strip()
        ]

        providers: list[Any] = []
        for name in provider_order:
            try:
                provider = self._create_provider(name)
                if provider is not None:
                    providers.append(provider)
            except Exception as exc:
                logger.warning("Failed to create daily_bars provider '{}': {}", name, exc)

        if not providers:
            logger.error("No daily_bars providers available")

        cb = ProviderCircuitBreaker()
        return DataProviderHub(providers=providers, circuit_breaker=cb)

    def _build_fundamentals_hub(self) -> DataProviderHub:
        """构建财务数据专用 hub。"""
        provider_order = [
            name.strip()
            for name in LIVE_DATA_PROVIDER_ORDER.split(",")
            if name.strip()
        ]

        providers: list[Any] = []
        for name in provider_order:
            try:
                provider = self._create_provider(name)
                if provider is not None:
                    providers.append(provider)
            except Exception as exc:
                logger.warning("Failed to create fundamentals provider '{}': {}", name, exc)

        if not providers:
            logger.error("No fundamentals providers available")

        cb = ProviderCircuitBreaker()
        return DataProviderHub(providers=providers, circuit_breaker=cb)

    @staticmethod
    def _create_provider(name: str) -> Any:
        """按名称创建 provider 实例（用于 daily_bars 和 fundamentals）。

        注意：AkShareProvider 的 get_realtime_quotes 会抛 NotImplementedError，
        因此实时行情 hub 不使用此方法。
        """
        if name == "eastmoney":
            from src.data_gateway.eastmoney_provider import EastmoneyProvider
            return EastmoneyProvider()
        elif name == "akshare":
            from src.data_gateway.akshare_provider import AkShareProvider
            return AkShareProvider()
        elif name == "aktools":
            from src.data_gateway.aktools_provider import AkToolsProvider
            return AkToolsProvider()
        else:
            logger.warning("Unknown provider name: {}", name)
            return None

    # ------------------------------------------------------------------
    # FeedbackService（lazy init 避免循环导入）
    # ------------------------------------------------------------------

    def _get_feedback_service(self):
        if self._feedback_service is None:
            from src.product_app.feedback import FeedbackService
            self._feedback_service = FeedbackService()
        return self._feedback_service

    # ------------------------------------------------------------------
    # 核心数据方法
    # ------------------------------------------------------------------

    def get_realtime_quotes(
        self,
        symbols: list[str],
        pool_type: str = "",
        allow_demo: bool = False,
    ) -> dict[str, Any]:
        """获取实时行情快照。

        Args:
            symbols: 股票代码列表，如 ["600000.SH", "000001.SZ"]
            pool_type: 股票池类型（如 "watchlist", "ai_semiconductor"）
            allow_demo: 是否允许 demo fallback（live closed-loop 默认 False）

        Returns:
            标准返回结构，包含 status / data_status / is_demo / quotes 等
        """
        # 规范化 symbol
        normalized = [normalize_a_share_symbol(s) for s in symbols if str(s).strip()]

        # 通过 hub 获取数据
        result: ProviderResult = self._realtime_hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            normalized,
            required_fields=REALTIME_REQUIRED_FIELDS,
        )

        # 标准化映射
        if result.status == "ok" and result.data is not None and not result.data.empty:
            mapped = map_realtime_quotes(result.data, result.provider, normalized)
            quotes = _records_from_frame(mapped)
        else:
            quotes = []

        # 构建返回结构
        data_status = self._compute_data_status(result, quotes)
        provider_health = self._build_provider_health_report(
            DataCapability.REALTIME_QUOTES
        )
        quality_report = self._build_quality_report(
            result, DataCapability.REALTIME_QUOTES, quotes
        )
        missing_report = self._build_missing_report(
            result, REALTIME_REQUIRED_FIELDS
        )
        delay_report = self._build_delay_report(result)

        # 全部失败时写 feedback Bug
        feedback_bug_id = ""
        if data_status == "FAILED":
            feedback_bug_id = self._write_failure_bug(
                capability="realtime_quotes",
                symbols=normalized,
                fallback_chain=result.fallback_chain,
            )

        return {
            "status": "ok" if data_status != "FAILED" else "failed",
            "data_status": data_status,
            "is_demo": False,
            "chosen_provider": result.provider,
            "fallback_chain": result.fallback_chain,
            "quotes": quotes,
            "provider_health_report": provider_health,
            "data_quality_report": quality_report,
            "data_missing_report": missing_report,
            "data_delay_report": delay_report,
            "feedback_bug_id": feedback_bug_id,
        }

    def get_daily_bars(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> dict[str, Any]:
        """获取历史日线数据。

        Args:
            symbols: 股票代码列表
            start_date: 开始日期 (YYYY-MM-DD 或 YYYYMMDD)
            end_date: 结束日期 (YYYY-MM-DD 或 YYYYMMDD)
            adjust: 复权方式 ("qfq" / "hfq" / "")

        Returns:
            标准返回结构，包含 status / data_status / is_demo / daily_bars 等
        """
        normalized = [normalize_a_share_symbol(s) for s in symbols if str(s).strip()]
        start_date = normalize_trade_date(start_date)
        end_date = normalize_trade_date(end_date)

        result: ProviderResult = self._daily_bars_hub.fetch_with_fallback(
            DataCapability.DAILY_BARS,
            "get_daily_bars",
            normalized,
            start_date,
            end_date,
            adjust,
            required_fields=DAILY_BAR_REQUIRED_FIELDS,
        )

        if result.status == "ok" and result.data is not None and not result.data.empty:
            mapped = map_daily_bars(
                result.data, result.provider, adjust, normalized
            )
            daily_bars = _records_from_frame(mapped)
        else:
            daily_bars = []

        data_status = self._compute_data_status(result, daily_bars)
        provider_health = self._build_provider_health_report(
            DataCapability.DAILY_BARS
        )
        quality_report = self._build_quality_report(
            result, DataCapability.DAILY_BARS, daily_bars
        )
        missing_report = self._build_missing_report(
            result, DAILY_BAR_REQUIRED_FIELDS
        )
        delay_report = self._build_delay_report(result)

        feedback_bug_id = ""
        if data_status == "FAILED":
            feedback_bug_id = self._write_failure_bug(
                capability="daily_bars",
                symbols=normalized,
                fallback_chain=result.fallback_chain,
                extra_context={
                    "start_date": start_date,
                    "end_date": end_date,
                    "adjust": adjust,
                },
            )

        return {
            "status": "ok" if data_status != "FAILED" else "failed",
            "data_status": data_status,
            "is_demo": False,
            "chosen_provider": result.provider,
            "fallback_chain": result.fallback_chain,
            "daily_bars": daily_bars,
            "provider_health_report": provider_health,
            "data_quality_report": quality_report,
            "data_missing_report": missing_report,
            "data_delay_report": delay_report,
            "feedback_bug_id": feedback_bug_id,
        }

    def get_fundamentals(self, symbols: list[str]) -> dict[str, Any]:
        """获取基础财务数据。

        Args:
            symbols: 股票代码列表

        Returns:
            标准返回结构，包含 status / data_status / is_demo / fundamentals 等
        """
        normalized = [normalize_a_share_symbol(s) for s in symbols if str(s).strip()]

        result: ProviderResult = self._fundamentals_hub.fetch_with_fallback(
            DataCapability.FUNDAMENTALS,
            "get_fundamentals",
            normalized,
            required_fields=FUNDAMENTALS_REQUIRED_FIELDS,
        )

        if result.status == "ok" and result.data is not None and not result.data.empty:
            mapped = map_fundamentals(result.data, result.provider, normalized)
            fundamentals = _records_from_frame(mapped)
        else:
            fundamentals = []

        data_status = self._compute_data_status(result, fundamentals)
        provider_health = self._build_provider_health_report(
            DataCapability.FUNDAMENTALS
        )
        quality_report = self._build_quality_report(
            result, DataCapability.FUNDAMENTALS, fundamentals
        )
        missing_report = self._build_missing_report(
            result, FUNDAMENTALS_REQUIRED_FIELDS
        )
        delay_report = self._build_delay_report(result)

        feedback_bug_id = ""
        if data_status == "FAILED":
            feedback_bug_id = self._write_failure_bug(
                capability="fundamentals",
                symbols=normalized,
                fallback_chain=result.fallback_chain,
            )

        return {
            "status": "ok" if data_status != "FAILED" else "failed",
            "data_status": data_status,
            "is_demo": False,
            "chosen_provider": result.provider,
            "fallback_chain": result.fallback_chain,
            "fundamentals": fundamentals,
            "provider_health_report": provider_health,
            "data_quality_report": quality_report,
            "data_missing_report": missing_report,
            "data_delay_report": delay_report,
            "feedback_bug_id": feedback_bug_id,
        }

    def build_research_context(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """构建完整研究上下文，供因子计算、回测、信号生成使用。

        汇总日线、财务数据，并通过 DataHealthGate 判断数据健康状态。

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含 daily_bars / fundamentals / health / reports 的完整上下文
        """
        normalized = [normalize_a_share_symbol(s) for s in symbols if str(s).strip()]

        # 获取实时行情、日线和财务数据
        quotes_result = self.get_realtime_quotes(normalized, allow_demo=False)
        daily_result = self.get_daily_bars(normalized, start_date, end_date)
        fundamentals_result = self.get_fundamentals(normalized)

        # 通过 DataHealthGate 判断健康状态
        from src.product_app.data_health_gate import DataHealthGate, DataHealthDecision

        health_gate = DataHealthGate()
        # 从 quotes_result 提取 provider_delay 供 DataHealthGate 使用
        quotes_for_gate = {
            "data_status": quotes_result.get("data_status", "FAILED"),
            "provider_delay": quotes_result.get("data_delay_report", {}).get("max_delay_seconds"),
        }
        health_decision: DataHealthDecision = health_gate.evaluate(
            quotes_result=quotes_for_gate,
            daily_bars_result={"data_status": daily_result["data_status"]},
            fundamentals_result={"data_status": fundamentals_result["data_status"]},
            is_demo=False,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )

        # 综合状态
        overall_data_status = self._merge_data_statuses(
            quotes_result.get("data_status", "FAILED"),
            daily_result["data_status"],
            fundamentals_result["data_status"],
        )

        # 综合状态判断
        if overall_data_status == "FAILED":
            overall_status = "failed"
        elif overall_data_status == "WARN":
            overall_status = "partial"
        else:
            overall_status = "ok"

        # 收集 feedback bug id
        bug_ids = []
        if quotes_result.get("feedback_bug_id"):
            bug_ids.append(quotes_result["feedback_bug_id"])
        if daily_result.get("feedback_bug_id"):
            bug_ids.append(daily_result["feedback_bug_id"])
        if fundamentals_result.get("feedback_bug_id"):
            bug_ids.append(fundamentals_result["feedback_bug_id"])

        return {
            "status": overall_status,
            "data_status": overall_data_status,
            "is_demo": False,
            "symbols": normalized,
            "start_date": normalize_trade_date(start_date),
            "end_date": normalize_trade_date(end_date),
            "quotes": quotes_result.get("quotes", []),
            "daily_bars": daily_result.get("daily_bars", []),
            "fundamentals": fundamentals_result.get("fundamentals", []),
            "health": {
                "data_status": health_decision.data_status,
                "allow_research": health_decision.allow_research,
                "allow_signal": health_decision.allow_signal,
                "allow_order_draft": health_decision.allow_order_draft,
                "risk_level": health_decision.risk_level,
                "messages": health_decision.messages,
            },
            "chosen_provider": {
                "quotes": quotes_result.get("chosen_provider", ""),
                "daily_bars": daily_result.get("chosen_provider", ""),
                "fundamentals": fundamentals_result.get("chosen_provider", ""),
            },
            "fallback_chain": {
                "quotes": quotes_result.get("fallback_chain", []),
                "daily_bars": daily_result.get("fallback_chain", []),
                "fundamentals": fundamentals_result.get("fallback_chain", []),
            },
            "provider_health_report": {
                "quotes": quotes_result.get("provider_health_report", {}),
                "daily_bars": daily_result.get("provider_health_report", {}),
                "fundamentals": fundamentals_result.get("provider_health_report", {}),
            },
            "data_quality_report": {
                "quotes": quotes_result.get("data_quality_report", {}),
                "daily_bars": daily_result.get("data_quality_report", {}),
                "fundamentals": fundamentals_result.get("data_quality_report", {}),
            },
            "data_missing_report": {
                "quotes": quotes_result.get("data_missing_report", {}),
                "daily_bars": daily_result.get("data_missing_report", {}),
                "fundamentals": fundamentals_result.get("data_missing_report", {}),
            },
            "data_delay_report": {
                "quotes": quotes_result.get("data_delay_report", {}),
                "daily_bars": daily_result.get("data_delay_report", {}),
                "fundamentals": fundamentals_result.get("data_delay_report", {}),
            },
            "feedback_bug_id": ", ".join(bug_ids) if bug_ids else "",
        }

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_data_status(
        result: ProviderResult,
        records: list[dict[str, Any]],
    ) -> str:
        """根据 ProviderResult 和实际记录数计算 data_status。

        Returns:
            "OK" | "WARN" | "FAILED"
        """
        if result.status == "failed" or not records:
            return "FAILED"

        # 数据获取成功，检查是否有部分缺失
        if result.data is not None and not result.data.empty:
            # 检查关键字段是否有 NaN
            has_missing = False
            for col in result.data.columns:
                if result.data[col].isna().any():
                    has_missing = True
                    break
            if has_missing:
                return "WARN"

        return "OK"

    @staticmethod
    def _merge_data_statuses(*statuses: str) -> str:
        """合并多个 data_status，取最差状态。"""
        if "FAILED" in statuses:
            return "FAILED"
        if "WARN" in statuses:
            return "WARN"
        return "OK"

    def _build_provider_health_report(
        self, capability: DataCapability
    ) -> dict[str, Any]:
        """构建 provider 健康报告。"""
        # 从对应 hub 获取健康信息
        hub = self._get_hub_for_capability(capability)
        if hub is None:
            return {}

        health_list = hub.get_health(capability)
        report: dict[str, Any] = {}
        for h in health_list:
            report[h.provider] = {
                "status": h.status,
                "latency_ms": h.latency_ms,
            }
        return report

    def _get_hub_for_capability(
        self, capability: DataCapability
    ) -> DataProviderHub | None:
        """根据能力类型返回对应的 hub。"""
        if capability == DataCapability.REALTIME_QUOTES:
            return self._realtime_hub
        elif capability == DataCapability.DAILY_BARS:
            return self._daily_bars_hub
        elif capability == DataCapability.FUNDAMENTALS:
            return self._fundamentals_hub
        return None

    @staticmethod
    def _build_quality_report(
        result: ProviderResult,
        capability: DataCapability,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """构建数据质量报告。"""
        return {
            "capability": capability.value,
            "provider": result.provider,
            "row_count": len(records),
            "elapsed_ms": result.elapsed_ms,
            "critical_fields_ok": bool(result.status == "ok" and len(records) > 0),
        }

    @staticmethod
    def _build_missing_report(
        result: ProviderResult,
        required_fields: list[str],
    ) -> dict[str, Any]:
        """构建字段缺失报告。"""
        if result.status == "failed" or result.data is None or result.data.empty:
            return {
                "missing_fields": list(required_fields),
                "coverage": {f: False for f in required_fields},
            }

        coverage = validate_required_fields(result.data, required_fields)
        missing = [f for f, ok in coverage.items() if not ok]
        return {
            "missing_fields": missing,
            "coverage": {f: bool(ok) for f, ok in coverage.items()},
        }

    @staticmethod
    def _build_delay_report(result: ProviderResult) -> dict[str, Any]:
        """构建延迟报告。"""
        return {
            "provider": result.provider,
            "elapsed_ms": result.elapsed_ms,
            "max_delay_seconds": result.elapsed_ms / 1000.0 if result.elapsed_ms else 0.0,
        }

    def _write_failure_bug(
        self,
        capability: str,
        symbols: list[str],
        fallback_chain: list[str],
        extra_context: dict[str, Any] | None = None,
    ) -> str:
        """当全部真实源失败时写 feedback Bug 报告。

        Returns:
            bug_id，写入失败返回空字符串。
        """
        try:
            feedback = self._get_feedback_service()
            context: dict[str, Any] = {
                "capability": capability,
                "symbols": symbols[:20],  # 限制长度
                "fallback_chain": fallback_chain,
                "DATA_FAIL_CLOSED": DATA_FAIL_CLOSED,
            }
            if extra_context:
                context.update(extra_context)

            bug_id = feedback.write_bug_report(
                component="data_gateway",
                title=f"All providers failed for {capability}",
                summary=(
                    f"All real data providers failed for capability={capability}, "
                    f"symbols={symbols[:5]}{'...' if len(symbols) > 5 else ''}. "
                    f"Fallback chain: {fallback_chain}"
                ),
                severity="high",
                endpoint_or_page=f"/product/live-data/{capability}",
                exception_type="AllProvidersFailed",
                exception_message=f"fallback_chain: {fallback_chain}",
                runtime_context=context,
                reproduction_steps=[
                    "Call LiveDataService method for " + capability,
                    "All providers in LIVE_DATA_PROVIDER_ORDER fail",
                    "DataHealthGate blocks signal and order draft",
                ],
            )
            return bug_id or ""
        except Exception as exc:
            logger.error("Failed to write feedback bug report: {}", exc)
            return ""


# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

_live_data_service: LiveDataService | None = None


def get_live_data_service() -> LiveDataService:
    """获取全局 LiveDataService 单例。"""
    global _live_data_service
    if _live_data_service is None:
        _live_data_service = LiveDataService()
    return _live_data_service