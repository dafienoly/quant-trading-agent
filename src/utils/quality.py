from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import pandas as pd
from loguru import logger

from src.models.schemas import DataQualityReport, DataMissingReport, DataDelayReport

KEY_FIELDS = ["open", "high", "low", "close", "volume"]


def check_completeness(df: pd.DataFrame) -> dict:
    result = {}
    for field in KEY_FIELDS:
        if field in df.columns:
            missing = df[field].isna().sum()
            result[f"missing_{field}"] = int(missing)
        else:
            result[f"missing_{field}"] = len(df)
    return result


def check_continuity(df: pd.DataFrame, trade_dates: List[str]) -> int:
    if "trade_date" not in df.columns:
        return len(trade_dates)

    existing = set(df["trade_date"].tolist())
    max_gap = 0
    current_gap = 0

    for d in sorted(trade_dates):
        if d in existing:
            max_gap = max(max_gap, current_gap)
            current_gap = 0
        else:
            current_gap += 1

    max_gap = max(max_gap, current_gap)
    return max_gap


def check_price_validity(df: pd.DataFrame) -> int:
    invalid_count = 0
    if "high" in df.columns and "low" in df.columns:
        invalid_count += int((df["high"] < df["low"]).sum())

    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            invalid_count += int((pd.to_numeric(df[col], errors="coerce") <= 0).sum())

    return invalid_count


def check_limit_status(df: pd.DataFrame) -> tuple[int, int]:
    limit_up = 0
    limit_down = 0

    if "pct_change" in df.columns:
        pct = pd.to_numeric(df["pct_change"], errors="coerce")
        limit_up = int((pct >= 9.9).sum())
        limit_down = int((pct <= -9.9).sum())

    return limit_up, limit_down


def check_suspended(df: pd.DataFrame) -> int:
    if "is_suspended" in df.columns:
        return int(df["is_suspended"].sum())
    if "volume" in df.columns:
        return int((df["volume"] == 0).sum())
    return 0


def generate_quality_report(
    df: pd.DataFrame,
    symbol: str,
    trade_dates: Optional[List[str]] = None,
) -> DataQualityReport:
    total_rows = len(df)
    completeness_info = check_completeness(df)
    invalid_price = check_price_validity(df)
    limit_up, limit_down = check_limit_status(df)
    suspended = check_suspended(df)

    if trade_dates:
        max_consec = check_continuity(df, trade_dates)
        expected = len(trade_dates)
    else:
        max_consec = 0
        expected = total_rows

    if expected > 0:
        filled = expected - completeness_info.get("missing_close", 0)
        completeness_pct = round(filled / expected * 100, 2)
    else:
        completeness_pct = 0.0

    start_date = ""
    end_date = ""
    if "trade_date" in df.columns and not df.empty:
        dates_sorted = sorted(df["trade_date"].tolist())
        start_date = dates_sorted[0]
        end_date = dates_sorted[-1]

    issues = []
    if completeness_pct < 99.0:
        issues.append(f"数据完整率偏低: {completeness_pct}%")
    if invalid_price > 0:
        issues.append(f"存在 {invalid_price} 行价格异常")
    if max_consec > 3:
        issues.append(f"连续缺失最多 {max_consec} 个交易日")
    if suspended > 0:
        issues.append(f"停牌 {suspended} 天")

    report = DataQualityReport(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        total_rows=total_rows,
        missing_open=completeness_info.get("missing_open", 0),
        missing_high=completeness_info.get("missing_high", 0),
        missing_low=completeness_info.get("missing_low", 0),
        missing_close=completeness_info.get("missing_close", 0),
        missing_volume=completeness_info.get("missing_volume", 0),
        max_consecutive_missing=max_consec,
        invalid_price_rows=invalid_price,
        limit_up_days=limit_up,
        limit_down_days=limit_down,
        suspended_days=suspended,
        completeness_pct=completeness_pct,
        issues=issues,
    )

    if issues:
        logger.warning(f"Quality report for {symbol}: {'; '.join(issues)}")
    else:
        logger.info(f"Quality report for {symbol}: OK ({completeness_pct}% complete, {total_rows} rows)")

    return report


def generate_data_missing_report(
    quality_reports: List[DataQualityReport],
) -> DataMissingReport:
    """生成数据缺失报告 (AGENTS.md 3.2 要求)"""
    total = len(quality_reports)
    missing_details = []
    symbols_with_missing = 0

    for report in quality_reports:
        total_missing = (
            report.missing_open
            + report.missing_high
            + report.missing_low
            + report.missing_close
            + report.missing_volume
        )
        if total_missing > 0:
            symbols_with_missing += 1
            missing_details.append({
                "symbol": report.symbol,
                "date_range": f"{report.start_date}~{report.end_date}",
                "total_rows": report.total_rows,
                "missing_open": report.missing_open,
                "missing_high": report.missing_high,
                "missing_low": report.missing_low,
                "missing_close": report.missing_close,
                "missing_volume": report.missing_volume,
                "max_consecutive_missing": report.max_consecutive_missing,
                "completeness_pct": report.completeness_pct,
            })

    summary = (
        f"共检查 {total} 只股票，{symbols_with_missing} 只有数据缺失"
        if symbols_with_missing > 0
        else f"共检查 {total} 只股票，数据完整"
    )

    report = DataMissingReport(
        total_symbols=total,
        symbols_with_missing=symbols_with_missing,
        missing_details=missing_details,
        summary=summary,
    )

    if symbols_with_missing > 0:
        logger.warning(f"Data missing report: {summary}")
    else:
        logger.info(f"Data missing report: {summary}")

    return report


def generate_data_delay_report(
    provider: str,
    symbols: List[str],
    fetch_start_time: datetime,
    fetch_end_time: datetime,
    per_symbol_times: Optional[List[dict]] = None,
) -> DataDelayReport:
    """生成数据延迟报告 (AGENTS.md 3.2 要求)"""
    total_elapsed = (fetch_end_time - fetch_start_time).total_seconds()
    avg_latency = total_elapsed / max(len(symbols), 1)

    delayed_symbols = []
    max_latency = 0.0

    if per_symbol_times:
        for entry in per_symbol_times:
            latency = entry.get("elapsed_seconds", 0)
            max_latency = max(max_latency, latency)
            if latency > avg_latency * 2:  # 超过平均2倍视为延迟
                delayed_symbols.append({
                    "symbol": entry.get("symbol", ""),
                    "elapsed_seconds": latency,
                })

    is_acceptable = avg_latency <= 5.0  # 单只股票平均延迟不超过5秒

    report = DataDelayReport(
        provider=provider,
        total_symbols=len(symbols),
        avg_latency_seconds=round(avg_latency, 2),
        max_latency_seconds=round(max_latency, 2),
        delayed_symbols=delayed_symbols,
        is_acceptable=is_acceptable,
    )

    logger.info(
        f"Data delay report: provider={provider}, "
        f"avg_latency={avg_latency:.2f}s, "
        f"is_acceptable={is_acceptable}"
    )

    return report
