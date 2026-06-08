from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RAW_DIR = BASE_DIR / "raw"
CLEANED_DIR = BASE_DIR / "cleaned"

DATA_VERSION = "1.0.0"


def _ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)


def _get_data_version() -> str:
    """获取当前数据版本号"""
    return DATA_VERSION


def save_raw_data(df: pd.DataFrame, symbol: str) -> Path:
    """保存原始数据，按日期分区存储"""
    _ensure_dirs()
    code = symbol.split(".")[0] if "." in symbol else symbol
    # 按日期分区存储：raw/{code}/{YYYYMMDD}.csv
    date_dir = RAW_DIR / code
    date_dir.mkdir(parents=True, exist_ok=True)

    if "trade_date" in df.columns:
        for trade_date, group in df.groupby("trade_date"):
            filepath = date_dir / f"{trade_date}.csv"
            group.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.debug(f"Raw data saved: {date_dir}/ (by date, {len(df)} rows)")
        return date_dir
    else:
        # 无日期分区则回退到单文件
        filepath = RAW_DIR / f"{code}_daily_raw.csv"
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.debug(f"Raw data saved: {filepath} ({len(df)} rows)")
        return filepath


def save_cleaned_data(df: pd.DataFrame, symbol: str) -> Path:
    _ensure_dirs()
    code = symbol.split(".")[0] if "." in symbol else symbol
    filepath = CLEANED_DIR / f"{code}_daily_cleaned.csv"

    # 添加 data_version 列
    df_out = df.copy()
    df_out["data_version"] = _get_data_version()

    df_out.to_csv(filepath, index=False)
    logger.debug(f"Cleaned data saved: {filepath} ({len(df_out)} rows, version={_get_data_version()})")
    return filepath


def load_cleaned_data(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    code = symbol.split(".")[0] if "." in symbol else symbol
    filepath = CLEANED_DIR / f"{code}_daily_cleaned.csv"
    if not filepath.exists():
        logger.warning(f"Cleaned data not found: {filepath}")
        return pd.DataFrame()

    df = pd.read_csv(filepath, dtype={"trade_date": str})

    if start_date:
        df = df[df["trade_date"] >= start_date]
    if end_date:
        df = df[df["trade_date"] <= end_date]

    return df


def list_cleaned_symbols() -> list[str]:
    _ensure_dirs()
    return sorted({
        f.stem.replace("_daily_cleaned", "")
        for f in CLEANED_DIR.glob("*_daily_cleaned.csv")
    })


def save_quality_report(report, symbol: str) -> Path:
    _ensure_dirs()
    code = symbol.split(".")[0] if "." in symbol else symbol
    filepath = CLEANED_DIR / f"{code}_quality.json"
    filepath.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return filepath


def save_data_missing_report(report, filename: str = "_data_missing_report.json") -> Path:
    """保存数据缺失报告"""
    _ensure_dirs()
    filepath = CLEANED_DIR / filename
    filepath.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info(f"Data missing report saved: {filepath}")
    return filepath


def save_data_delay_report(report, filename: str = "_data_delay_report.json") -> Path:
    """保存数据延迟报告"""
    _ensure_dirs()
    filepath = CLEANED_DIR / filename
    filepath.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info(f"Data delay report saved: {filepath}")
    return filepath


def save_and_report(
    df: pd.DataFrame,
    symbol: str,
    quality_report,
    trigger_auto_report: bool = True,
) -> dict:
    """统一保存入口：保存原始数据 + 清洗数据 + 自动触发质量报告

    遵循 DATA_CONTRACTS 6 节：数据更新必须触发 data_quality_report 自动生成
    """
    raw_path = save_raw_data(df, symbol)
    cleaned_path = save_cleaned_data(df, symbol)

    if trigger_auto_report and quality_report is not None:
        quality_path = save_quality_report(quality_report, symbol)
        logger.info(
            f"Auto-triggered quality report for {symbol}: "
            f"acceptable={quality_report.is_acceptable}"
        )
    else:
        quality_path = None

    return {
        "symbol": symbol,
        "raw_path": str(raw_path),
        "cleaned_path": str(cleaned_path),
        "quality_path": str(quality_path) if quality_path else None,
        "rows": len(df),
    }
