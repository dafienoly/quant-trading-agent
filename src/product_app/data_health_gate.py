"""数据健康门控模块

根据数据质量决定是否允许生成信号和订单草稿。
当行情、日线、基本面数据异常时，逐级降级产品能力。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class DataHealthDecision:
    """数据健康决策结果"""

    data_status: str  # "OK" | "WARN" | "FAILED"
    allow_research: bool
    allow_signal: bool
    allow_order_draft: bool
    risk_level: str  # "OK" | "WARN" | "BLOCK"
    messages: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)


class DataHealthGate:
    """数据健康门控

    根据行情、日线、基本面数据质量以及交易模式，决定是否允许
    研究、信号生成、订单草稿等操作。

    门控规则表：
    ┌──────────────────────────────────┬────────────────┬──────────────┬───────────────────┐
    │ 场景                             │ allow_research │ allow_signal │ allow_order_draft │
    ├──────────────────────────────────┼────────────────┼──────────────┼───────────────────┤
    │ 行情正常，日线/基本面正常         │ true           │ true         │ 按交易模式 & 风控  │
    │ 基本面部分缺失                   │ true           │ true(带警告) │ 按风控             │
    │ 行情全部失败                     │ false          │ false        │ false             │
    │ 日线全部失败                     │ false          │ false        │ false             │
    │ 数据为 Demo                     │ true(仅教学)   │ false        │ false             │
    │ 数据延迟超过模式阈值             │ true           │ false        │ false             │
    └──────────────────────────────────┴────────────────┴──────────────┴───────────────────┘
    """

    STALE_THRESHOLD_SECONDS = 30.0

    QUOTE_HEALTHY = "HEALTHY"
    QUOTE_STALE = "STALE"
    QUOTE_UNAVAILABLE = "UNAVAILABLE"
    QUOTE_DEMO = "DEMO"

    DELAY_THRESHOLDS: dict[str, float] = {
        "LEVEL_1_SIGNAL_ONLY": 120.0,
        "LEVEL_2_HUMAN_CONFIRM": 60.0,
        "LEVEL_3_AUTO": 10.0,
    }

    def get_quote_health(self, quote: dict | None, is_demo: bool = False, _now=None) -> str:
        if quote is None:
            return self.QUOTE_UNAVAILABLE
        if is_demo:
            return self.QUOTE_DEMO
        received = quote.get("received_at") or quote.get("timestamp")
        if not received:
            return self.QUOTE_STALE
        import datetime
        try:
            if isinstance(received, str):
                dt = datetime.datetime.fromisoformat(received)
            else:
                dt = datetime.datetime.fromtimestamp(received)
        except (ValueError, TypeError):
            return self.QUOTE_STALE
        now_dt = _now if _now else datetime.datetime.now(dt.tzinfo)
        age = (now_dt - dt).total_seconds()
        if age > self.STALE_THRESHOLD_SECONDS:
            return self.QUOTE_STALE
        return self.QUOTE_HEALTHY

    def evaluate(
        self,
        quotes_result: dict[str, Any],
        daily_bars_result: dict[str, Any] | None = None,
        fundamentals_result: dict[str, Any] | None = None,
        is_demo: bool = False,
        trading_mode: str = "LEVEL_1_SIGNAL_ONLY",
    ) -> DataHealthDecision:
        """评估数据健康状态，返回决策结果

        Args:
            quotes_result: 行情数据结果，包含 data_status / provider_delay 等字段
            daily_bars_result: 日线数据结果，包含 data_status 等字段
            fundamentals_result: 基本面数据结果，包含 data_status 等字段
            is_demo: 是否为 Demo 数据
            trading_mode: 交易模式，用于确定延迟阈值

        Returns:
            DataHealthDecision 决策结果
        """
        messages: list[str] = []
        evidence: dict[str, Any] = {
            "is_demo": is_demo,
            "trading_mode": trading_mode,
            "quotes_status": quotes_result.get("data_status") if quotes_result else None,
            "daily_bars_status": daily_bars_result.get("data_status") if daily_bars_result else None,
            "fundamentals_status": fundamentals_result.get("data_status") if fundamentals_result else None,
        }

        # ── 1. Demo 模式 ──────────────────────────────────────────
        if is_demo:
            messages.append("数据为 Demo 模式，仅允许研究（教学用途），禁止信号和订单")
            logger.info("DataHealthGate: Demo 模式 → allow_research=True, signal/order=False")
            return DataHealthDecision(
                data_status="OK",
                allow_research=True,
                allow_signal=False,
                allow_order_draft=False,
                risk_level="BLOCK",
                messages=messages,
                evidence=evidence,
            )

        # ── 2. 行情全部失败 ──────────────────────────────────────
        quotes_status = (quotes_result or {}).get("data_status", "OK")
        if quotes_status == "FAILED":
            messages.append("实时行情数据全部失败，禁止所有操作")
            logger.warning("DataHealthGate: 行情 FAILED → 全部禁止")
            return DataHealthDecision(
                data_status="FAILED",
                allow_research=False,
                allow_signal=False,
                allow_order_draft=False,
                risk_level="BLOCK",
                messages=messages,
                evidence=evidence,
            )

        # ── 3. 日线全部失败 ──────────────────────────────────────
        daily_status = (daily_bars_result or {}).get("data_status", "OK")
        if daily_status == "FAILED":
            messages.append("日线数据全部失败，禁止所有操作")
            logger.warning("DataHealthGate: 日线 FAILED → 全部禁止")
            return DataHealthDecision(
                data_status="FAILED",
                allow_research=False,
                allow_signal=False,
                allow_order_draft=False,
                risk_level="BLOCK",
                messages=messages,
                evidence=evidence,
            )

        # ── 4. 数据延迟超过模式阈值 ──────────────────────────────
        provider_delay = (quotes_result or {}).get("provider_delay")
        threshold = self.DELAY_THRESHOLDS.get(trading_mode, 120.0)
        evidence["provider_delay"] = provider_delay
        evidence["delay_threshold"] = threshold

        if provider_delay is not None and provider_delay > threshold:
            messages.append(
                f"数据延迟 {provider_delay:.1f}s 超过 {trading_mode} 阈值 {threshold:.0f}s，"
                f"禁止信号和订单"
            )
            logger.warning(
                f"DataHealthGate: 延迟 {provider_delay:.1f}s > {threshold:.0f}s "
                f"→ allow_research=True, signal/order=False"
            )
            return DataHealthDecision(
                data_status="WARN",
                allow_research=True,
                allow_signal=False,
                allow_order_draft=False,
                risk_level="BLOCK",
                messages=messages,
                evidence=evidence,
            )

        # ── 5. 基本面部分缺失 ────────────────────────────────────
        fundamentals_status = (fundamentals_result or {}).get("data_status", "OK")
        if fundamentals_status == "WARN":
            messages.append("基本面数据部分缺失，信号生成将标注缺失项，订单草稿按风控决定")
            logger.info("DataHealthGate: 基本面 WARN → allow_signal=True(带警告)")
            return DataHealthDecision(
                data_status="WARN",
                allow_research=True,
                allow_signal=True,
                allow_order_draft=True,
                risk_level="WARN",
                messages=messages,
                evidence=evidence,
            )

        # ── 6. 全部正常 ──────────────────────────────────────────
        messages.append("数据健康检查通过")
        logger.info("DataHealthGate: 全部正常 → allow_research=True, signal=True, order=True")
        return DataHealthDecision(
            data_status="OK",
            allow_research=True,
            allow_signal=True,
            allow_order_draft=True,
            risk_level="OK",
            messages=messages,
            evidence=evidence,
        )
