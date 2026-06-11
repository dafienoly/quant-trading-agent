"""Provider 调度中心 — 管理多数据源并实现自动降级与熔断。

核心组件：
- ProviderCircuitBreaker: 按 (provider, capability) 维度跟踪熔断状态
- DataProviderHub: 统一调度入口，按优先级尝试 provider 并自动降级
"""
from __future__ import annotations

from time import monotonic
from typing import Any

import pandas as pd
from loguru import logger

from src.data_gateway.provider_contracts import DataCapability, ProviderResult, ProviderHealth
from src.data_gateway.live_data_mapper import validate_required_fields


class ProviderCircuitBreaker:
    """按 (provider, capability) 维度跟踪熔断状态。

    熔断逻辑：
    - 连续失败 N 次后熔断打开（blocked）
    - 冷却期后进入半开状态，允许一次尝试
    - 半开状态下成功则关闭熔断，失败则重新打开
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 300.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        # (provider, capability) -> failure_count
        self._failure_counts: dict[tuple[str, DataCapability], int] = {}
        # (provider, capability) -> last_failure_time (monotonic)
        self._last_failure_time: dict[tuple[str, DataCapability], float] = {}

    def is_open(self, provider: str, capability: DataCapability) -> bool:
        """判断熔断器是否打开（即是否应跳过该 provider）。

        返回 True 表示熔断打开，应跳过。
        """
        key = (provider, capability)
        failure_count = self._failure_counts.get(key, 0)

        if failure_count < self._failure_threshold:
            return False

        # 已达阈值，检查冷却期
        last_fail = self._last_failure_time.get(key, 0.0)
        elapsed = monotonic() - last_fail

        if elapsed >= self._cooldown_seconds:
            # 冷却期已过，半开状态 — 允许一次尝试
            logger.debug(
                "Circuit half-open for provider=%s capability=%s, allowing attempt",
                provider,
                capability.value,
            )
            return False

        logger.debug(
            "Circuit open for provider=%s capability=%s, cooldown remaining=%.0fs",
            provider,
            capability.value,
            self._cooldown_seconds - elapsed,
        )
        return True

    def record_success(self, provider: str, capability: DataCapability) -> None:
        """记录成功，重置失败计数（关闭熔断）。"""
        key = (provider, capability)
        prev = self._failure_counts.get(key, 0)
        self._failure_counts[key] = 0
        if prev > 0:
            logger.info(
                "Circuit closed for provider=%s capability=%s (was %d failures)",
                provider,
                capability.value,
                prev,
            )

    def record_failure(self, provider: str, capability: DataCapability) -> None:
        """记录失败，递增失败计数。"""
        key = (provider, capability)
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        self._last_failure_time[key] = monotonic()
        count = self._failure_counts[key]
        if count >= self._failure_threshold:
            logger.warning(
                "Circuit opened for provider=%s capability=%s (%d consecutive failures)",
                provider,
                capability.value,
                count,
            )
        else:
            logger.debug(
                "Failure recorded for provider=%s capability=%s (%d/%d)",
                provider,
                capability.value,
                count,
                self._failure_threshold,
            )

    def get_failure_count(self, provider: str, capability: DataCapability) -> int:
        """获取当前连续失败次数。"""
        return self._failure_counts.get((provider, capability), 0)


class DataProviderHub:
    """Provider 调度中心，管理多数据源并实现自动降级。

    按优先级顺序尝试 provider：
    1. 跳过熔断打开的 provider
    2. 调用 provider 方法并计时
    3. 验证必需字段覆盖率
    4. 成功则记录并返回，失败则降级到下一个 provider
    5. 全部失败则返回 failed 状态的 ProviderResult
    """

    def __init__(
        self,
        providers: list[Any],
        circuit_breaker: ProviderCircuitBreaker | None = None,
    ) -> None:
        self._providers = providers
        self._circuit_breaker = circuit_breaker or ProviderCircuitBreaker()

    @property
    def circuit_breaker(self) -> ProviderCircuitBreaker:
        return self._circuit_breaker

    def fetch_with_fallback(
        self,
        capability: DataCapability,
        fetch_fn_name: str,
        *args: Any,
        required_fields: list[str] | None = None,
    ) -> ProviderResult:
        """按优先级尝试 provider，自动降级。

        Args:
            capability: 数据能力类型
            fetch_fn_name: provider 上的方法名（如 "get_realtime_quotes"）
            *args: 传递给 provider 方法的参数
            required_fields: 必需字段列表，用于验证返回数据

        Returns:
            ProviderResult: 包含数据、状态和降级链信息
        """
        fallback_chain: list[str] = []

        for provider in self._providers:
            provider_name = provider.name

            # 跳过熔断打开的 provider
            if self._circuit_breaker.is_open(provider_name, capability):
                fallback_chain.append(f"{provider_name}: circuit_open")
                logger.info(
                    "Skipping provider=%s capability=%s (circuit open)",
                    provider_name,
                    capability.value,
                )
                continue

            # 调用 provider 方法
            t0 = monotonic()
            try:
                fetch_fn = getattr(provider, fetch_fn_name)
                data = fetch_fn(*args)
                elapsed_ms = (monotonic() - t0) * 1000.0
            except Exception as exc:
                elapsed_ms = (monotonic() - t0) * 1000.0
                error_msg = str(exc) or type(exc).__name__
                fallback_chain.append(f"{provider_name}: {error_msg}")
                self._circuit_breaker.record_failure(provider_name, capability)
                logger.warning(
                    "Provider=%s capability=%s raised %s: %s (%.0fms)",
                    provider_name,
                    capability.value,
                    type(exc).__name__,
                    error_msg,
                    elapsed_ms,
                )
                continue

            # 检查数据是否为空
            if data is None or (isinstance(data, pd.DataFrame) and data.empty):
                fallback_chain.append(f"{provider_name}: empty_data")
                self._circuit_breaker.record_failure(provider_name, capability)
                logger.warning(
                    "Provider=%s capability=%s returned empty data (%.0fms)",
                    provider_name,
                    capability.value,
                    elapsed_ms,
                )
                continue

            # 验证必需字段覆盖率
            if required_fields:
                coverage = validate_required_fields(data, required_fields)
                missing = [f for f, ok in coverage.items() if not ok]
                if missing:
                    fallback_chain.append(
                        f"{provider_name}: missing_fields({','.join(missing)})"
                    )
                    self._circuit_breaker.record_failure(provider_name, capability)
                    logger.warning(
                        "Provider=%s capability=%s missing fields: %s (%.0fms)",
                        provider_name,
                        capability.value,
                        missing,
                        elapsed_ms,
                    )
                    continue

            # 成功
            fallback_chain.append(f"{provider_name}: ok")
            self._circuit_breaker.record_success(provider_name, capability)
            logger.info(
                "Provider=%s capability=%s succeeded (%d rows, %.0fms)",
                provider_name,
                capability.value,
                len(data),
                elapsed_ms,
            )
            return ProviderResult(
                status="ok",
                provider=provider_name,
                capability=capability,
                data=data,
                messages=[],
                error="",
                elapsed_ms=elapsed_ms,
                fallback_chain=fallback_chain,
            )

        # 所有 provider 均失败
        logger.error(
            "All providers failed for capability=%s, fallback_chain=%s",
            capability.value,
            fallback_chain,
        )
        return ProviderResult(
            status="failed",
            provider="",
            capability=capability,
            data=pd.DataFrame(),
            messages=[],
            error="all_providers_failed",
            elapsed_ms=0.0,
            fallback_chain=fallback_chain,
        )

    def get_health(self, capability: DataCapability) -> list[ProviderHealth]:
        """获取所有 provider 对指定能力的健康诊断。"""
        health_list: list[ProviderHealth] = []
        for provider in self._providers:
            provider_name = provider.name
            is_open = self._circuit_breaker.is_open(provider_name, capability)
            failure_count = self._circuit_breaker.get_failure_count(provider_name, capability)

            if is_open:
                status = "CIRCUIT_OPEN"
            elif failure_count > 0:
                status = "ERROR"
            else:
                status = "OK"

            health_list.append(
                ProviderHealth(
                    provider=provider_name,
                    capability=capability,
                    status=status,
                    latency_ms=0.0,
                    row_count=0,
                    field_coverage={},
                    last_success_at="",
                    error="",
                )
            )
        return health_list
