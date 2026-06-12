"""Provider 诊断服务 — 对每个 provider 执行真实连接测试并输出诊断结果。

职责：
- 按 provider 和 capability 执行诊断
- 输出 provider 级健康报告
- 记录最近成功时间
- 诊断失败时写入 feedback Bug

BUG-002 修复：接收多个 hub（realtime/daily_bars/fundamentals），
每个 capability 使用对应的 hub 进行诊断。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from src.data_gateway.provider_contracts import DataCapability
from src.data_gateway.live_data_mapper import (
    REALTIME_REQUIRED_FIELDS,
    DAILY_BAR_REQUIRED_FIELDS,
    FUNDAMENTALS_REQUIRED_FIELDS,
)
from src.data_gateway.provider_hub import DataProviderHub


# 诊断用的测试 symbol
_DIAG_SYMBOLS = ["600000.SH", "000001.SZ"]
_DIAG_START_DATE = "20250101"
_DIAG_END_DATE = "20251231"

# 每个 capability 对应的必需字段
_CAPABILITY_REQUIRED_FIELDS = {
    DataCapability.REALTIME_QUOTES: REALTIME_REQUIRED_FIELDS,
    DataCapability.DAILY_BARS: DAILY_BAR_REQUIRED_FIELDS,
    DataCapability.FUNDAMENTALS: FUNDAMENTALS_REQUIRED_FIELDS,
}

# capability → hub 属性名的映射
_CAPABILITY_HUB_MAP = {
    DataCapability.REALTIME_QUOTES: "realtime",
    DataCapability.DAILY_BARS: "daily_bars",
    DataCapability.FUNDAMENTALS: "fundamentals",
}


class ProviderDiagnosticsService:
    """Provider 诊断服务

    接收多个 hub（按 capability 区分），对每个 provider 执行诊断。
    """

    def __init__(
        self,
        realtime_hub: DataProviderHub,
        daily_bars_hub: DataProviderHub,
        fundamentals_hub: DataProviderHub,
    ):
        self._hubs: dict[str, DataProviderHub] = {
            "realtime": realtime_hub,
            "daily_bars": daily_bars_hub,
            "fundamentals": fundamentals_hub,
        }

    def _get_hub(self, capability: DataCapability) -> DataProviderHub:
        """根据 capability 获取对应的 hub"""
        hub_key = _CAPABILITY_HUB_MAP.get(capability, "realtime")
        return self._hubs[hub_key]

    def diagnose(
        self,
        symbols: list[str] | None = None,
        capabilities: list[DataCapability] | None = None,
    ) -> dict[str, Any]:
        """执行 provider 诊断

        Args:
            symbols: 诊断用的股票代码，默认使用内置测试代码
            capabilities: 要诊断的能力列表，默认诊断全部

        Returns:
            诊断结果字典，包含 provider_health_report 和 chosen_provider
        """
        if symbols is None:
            symbols = _DIAG_SYMBOLS
        if capabilities is None:
            capabilities = [
                DataCapability.REALTIME_QUOTES,
                DataCapability.DAILY_BARS,
                DataCapability.FUNDAMENTALS,
            ]

        provider_health_report: dict[str, dict[str, dict[str, Any]]] = {}
        chosen_provider: dict[str, str] = {}

        for capability in capabilities:
            fetch_fn_name = self._capability_to_fetch_fn(capability)
            if not fetch_fn_name:
                continue

            required_fields = _CAPABILITY_REQUIRED_FIELDS.get(capability, [])
            fetch_args = self._build_fetch_args(capability, symbols)
            hub = self._get_hub(capability)

            result = hub.fetch_with_fallback(
                capability,
                fetch_fn_name,
                *fetch_args,
                required_fields=required_fields,
            )

            # 记录每个 provider 的健康状态
            for chain_entry in result.fallback_chain:
                provider_name = chain_entry.split(":")[0].strip()
                status_detail = ":".join(chain_entry.split(":")[1:]).strip()

                if provider_name not in provider_health_report:
                    provider_health_report[provider_name] = {}

                is_ok = "ok" in status_detail.lower()
                provider_health_report[provider_name][capability.value] = {
                    "status": "OK" if is_ok else "ERROR",
                    "error": "" if is_ok else status_detail,
                    "latency_ms": result.elapsed_ms if is_ok and result.provider == provider_name else 0,
                }

            # 记录选中的 provider
            if result.status == "ok":
                chosen_provider[capability.value] = result.provider

        # 获取每个 hub 的健康诊断
        for capability in capabilities:
            hub = self._get_hub(capability)
            health_list = hub.get_health(capability)
            for health in health_list:
                if health.provider not in provider_health_report:
                    provider_health_report[health.provider] = {}
                if capability.value not in provider_health_report[health.provider]:
                    provider_health_report[health.provider][capability.value] = {
                        "status": health.status,
                        "latency_ms": health.latency_ms,
                        "row_count": health.row_count,
                        "error": health.error,
                    }

        return {
            "status": "ok",
            "provider_health_report": provider_health_report,
            "chosen_provider": chosen_provider,
            "diagnosed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "feedback_bug_id": "",
        }

    def _capability_to_fetch_fn(self, capability: DataCapability) -> str | None:
        """将能力映射为 provider 方法名"""
        mapping = {
            DataCapability.REALTIME_QUOTES: "get_realtime_quotes",
            DataCapability.DAILY_BARS: "get_daily_bars",
            DataCapability.FUNDAMENTALS: "get_fundamentals",
        }
        return mapping.get(capability)

    def _build_fetch_args(self, capability: DataCapability, symbols: list[str]) -> tuple:
        """构建 fetch_with_fallback 的位置参数"""
        if capability == DataCapability.REALTIME_QUOTES:
            return (symbols,)
        if capability == DataCapability.DAILY_BARS:
            return (symbols, _DIAG_START_DATE, _DIAG_END_DATE)
        if capability == DataCapability.FUNDAMENTALS:
            return (symbols,)
        return ()
