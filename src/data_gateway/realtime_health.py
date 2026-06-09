"""实时行情数据健康门禁

将实时行情获取元数据转换为 DataDelayReport 和风控快照，
用于 Phase 4 盯盘前的数据可用性检查。
"""
from __future__ import annotations

from datetime import datetime

from src.models.schemas import DataDelayReport


def _parse_quote_time(value: str) -> datetime | None:
    if not value or not value.strip():
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def build_realtime_health_report(
    provider: str,
    quotes: list[dict],
    now: datetime,
    max_delay_seconds: float = 10.0,
) -> DataDelayReport:
    delayed_symbols = []
    max_latency = 0.0
    total_latency = 0.0
    valid_count = 0

    for quote in quotes:
        # 优先使用 delay_seconds 字段（RuntimeRiskEngine 格式）
        delay_seconds = quote.get("delay_seconds")
        if delay_seconds is not None:
            latency = float(delay_seconds)
        else:
            # 使用 datetime 字段计算延迟
            quote_time = _parse_quote_time(str(quote.get("datetime", "")))
            if quote_time is None:
                continue
            latency = max((now - quote_time).total_seconds(), 0.0)

        total_latency += latency
        max_latency = max(max_latency, latency)
        valid_count += 1
        if latency > max_delay_seconds:
            delayed_symbols.append({
                "symbol": quote.get("symbol", ""),
                "elapsed_seconds": latency,
            })

    avg_latency = total_latency / max(valid_count, 1)
    return DataDelayReport(
        provider=provider,
        total_symbols=len(quotes),
        avg_latency_seconds=round(avg_latency, 2),
        max_latency_seconds=round(max_latency, 2),
        delayed_symbols=delayed_symbols,
        is_acceptable=len(quotes) > 0 and len(delayed_symbols) == 0,
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
