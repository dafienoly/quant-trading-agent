"""标准化映射层 — 把不同数据源字段映射为 PRD 定义的标准字段。

核心职责：
- 统一日期格式为 YYYY-MM-DD（存储层）
- 统一 symbol 格式为 CODE.EXCHANGE
- 统一 volume 单位为股（源返回手时乘以100）
- 同时保留 raw price 和 adjusted price
- 财务字段缺失保留 NaN，不得静默填 0
"""
from __future__ import annotations

import re
from datetime import datetime

import pandas as pd


# ============================================================
# Symbol 规范化
# ============================================================

def normalize_a_share_symbol(symbol: str) -> str:
    """将输入 symbol 规范化为 CODE.EXCHANGE 格式。

    支持输入格式：
    - "600000" → "600000.SH"
    - "000001" → "000001.SZ"
    - "600000.SH" → "600000.SH"
    - "sh600000" → "600000.SH"
    - "SH600000" → "600000.SH"
    """
    raw = str(symbol).strip().upper()
    if not raw:
        return raw

    # 已有交易所后缀
    if "." in raw:
        code, suffix = raw.split(".", 1)
        return f"{code}.{suffix}"

    # 去掉前缀如 sh/sz
    cleaned = re.sub(r"^(SH|SZ|BJ)", "", raw)
    if len(cleaned) == 6 and cleaned.isdigit():
        if cleaned.startswith(("5", "6", "9")):
            return f"{cleaned}.SH"
        return f"{cleaned}.SZ"

    return raw


def normalize_trade_date(value: str) -> str:
    """统一日期格式为 YYYY-MM-DD。

    接受 YYYYMMDD 或 YYYY-MM-DD，返回 YYYY-MM-DD。
    """
    if not value or not str(value).strip():
        return ""
    s = str(value).strip().replace("-", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s
    return str(value)


# ============================================================
# 实时行情映射
# ============================================================

# 实时行情标准输出列
REALTIME_QUOTE_COLUMNS = [
    "symbol", "name", "market", "datetime", "last_price",
    "open", "high", "low", "pre_close", "pct_change", "change",
    "volume", "amount", "status", "delay_seconds",
    "currency", "timezone", "data_source", "updated_at",
    "data_version", "source_volume_unit",
]


def map_realtime_quotes(
    raw: pd.DataFrame,
    source: str,
    symbols: list[str],
) -> pd.DataFrame:
    """将原始实时行情映射为 PRD 定义的标准字段。

    输入 raw 应已包含以下列（来自 realtime_provider.py 的映射结果）：
    symbol, name, market, datetime, last_price, open, high, low,
    pre_close, pct_change, change, volume, amount, status,
    delay_seconds, currency, timezone, data_source, updated_at,
    data_version, source_volume_unit

    本函数确保：
    1. 所有标准列都存在
    2. volume 统一为股（source_volume_unit=lot 时已乘以100）
    3. symbol 格式为 CODE.EXCHANGE
    """
    if raw is None or raw.empty:
        return pd.DataFrame(columns=REALTIME_QUOTE_COLUMNS)

    df = raw.copy()

    # 确保 symbol 格式统一
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].apply(normalize_a_share_symbol)

    # 确保 volume 为整数（股）
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")

    # 确保所有标准列存在
    for col in REALTIME_QUOTE_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[REALTIME_QUOTE_COLUMNS]


# ============================================================
# 历史日线映射
# ============================================================

# 日线标准输出列
DAILY_BAR_CONTRACT_COLUMNS = [
    "symbol", "trade_date",
    "open", "high", "low", "close",
    "volume", "amount",
    "raw_open", "raw_high", "raw_low", "raw_close",
    "adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close",
    "adjustment_type",
    "is_suspended", "is_limit_up", "is_limit_down",
    "currency", "timezone", "data_source", "updated_at", "data_version",
]


def map_daily_bars(
    raw: pd.DataFrame,
    source: str,
    adjust: str = "qfq",
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """将原始日线数据映射为 PRD 定义的标准字段。

    同时保留 raw price 和 adjusted price：
    - 当 adjust="qfq"/"hfq" 时，open/high/low/close 为复权价，
      raw_* 为原始价（需要复权因子反算）
    - 当 adjust="" 时，raw 和 adjusted 相同
    - adjustment_type 记录复权方式
    """
    if raw is None or raw.empty:
        return pd.DataFrame(columns=DAILY_BAR_CONTRACT_COLUMNS)

    df = raw.copy()

    # 统一 trade_date 格式为 YYYY-MM-DD
    if "trade_date" in df.columns:
        df["trade_date"] = df["trade_date"].apply(normalize_trade_date)

    # 确保 symbol 格式统一
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].apply(normalize_a_share_symbol)

    # 数值转换
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # volume 统一为股
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0).astype("Int64")

    # raw / adjusted price
    # 如果有 adj_factor，用它反算 raw price
    if "adj_factor" in df.columns and df["adj_factor"].notna().any():
        adj_factor = pd.to_numeric(df["adj_factor"], errors="coerce")
        for price_col in ["open", "high", "low", "close"]:
            if price_col in df.columns:
                df[f"raw_{price_col}"] = df[price_col] / adj_factor * adj_factor.iloc[-1]
                df[f"adjusted_{price_col}"] = df[price_col]
    else:
        # 没有复权因子时，raw 和 adjusted 相同
        for price_col in ["open", "high", "low", "close"]:
            if price_col in df.columns:
                df[f"raw_{price_col}"] = df[price_col]
                df[f"adjusted_{price_col}"] = df[price_col]

    # 复权方式
    adjust_map = {"qfq": "前复权", "hfq": "后复权", "": "不复权"}
    df["adjustment_type"] = adjust_map.get(adjust, adjust)

    # 涨跌停判断
    if "pct_change" in df.columns and "pre_close" in df.columns:
        pct = pd.to_numeric(df["pct_change"], errors="coerce")
        df["is_limit_up"] = pct >= 9.9
        df["is_limit_down"] = pct <= -9.9

        # 创业板/科创板 20% 涨跌停
        if "symbol" in df.columns:
            chinext_star = df["symbol"].str.startswith(("300", "301", "688", "689"), na=False)
            df.loc[chinext_star, "is_limit_up"] = pct >= 19.9
            df.loc[chinext_star, "is_limit_down"] = pct <= -19.9
    else:
        df["is_limit_up"] = False
        df["is_limit_down"] = False

    # 停牌判断
    if "is_suspended" not in df.columns:
        if "volume" in df.columns:
            df["is_suspended"] = df["volume"].fillna(-1) == 0
        else:
            df["is_suspended"] = False

    # 元数据字段
    df["currency"] = "CNY"
    df["timezone"] = "Asia/Shanghai"
    df["data_source"] = source
    df["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["data_version"] = "daily-v1"

    # 确保所有标准列存在
    for col in DAILY_BAR_CONTRACT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[DAILY_BAR_CONTRACT_COLUMNS]


# ============================================================
# 财务数据映射
# ============================================================

# 财务标准输出列
FUNDAMENTALS_CONTRACT_COLUMNS = [
    "symbol", "pe_ttm", "pb", "roe", "revenue", "net_profit",
    "market_cap", "report_period",
    "currency", "data_source", "updated_at", "data_version",
]


def map_fundamentals(
    raw: pd.DataFrame,
    source: str,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """将原始财务数据映射为 PRD 定义的标准字段。

    关键规则：缺失字段保留 NaN，不得静默填 0。
    """
    if raw is None or raw.empty:
        return pd.DataFrame(columns=FUNDAMENTALS_CONTRACT_COLUMNS)

    df = raw.copy()

    # 确保 symbol 格式统一
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].apply(normalize_a_share_symbol)

    # 数值转换 — 缺失保留 NaN
    for col in ["pe_ttm", "pb", "roe", "revenue", "net_profit", "market_cap"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # 不填充 NaN — 缺失就是缺失

    # 元数据
    df["currency"] = "CNY"
    df["data_source"] = source
    df["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["data_version"] = "fundamentals-v1"

    if "report_period" not in df.columns:
        df["report_period"] = None

    # 确保所有标准列存在
    for col in FUNDAMENTALS_CONTRACT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[FUNDAMENTALS_CONTRACT_COLUMNS]


# ============================================================
# 字段覆盖率检查
# ============================================================

def validate_required_fields(
    df: pd.DataFrame,
    required_fields: list[str],
) -> dict[str, bool]:
    """检查 DataFrame 中必需字段的覆盖率。

    返回 {字段名: 是否全覆盖} 的字典。
    """
    if df.empty:
        return {f: False for f in required_fields}

    coverage = {}
    for field_name in required_fields:
        if field_name not in df.columns:
            coverage[field_name] = False
        else:
            # 字段存在且非全 NaN
            coverage[field_name] = df[field_name].notna().any()
    return coverage


# 实时行情必需字段
REALTIME_REQUIRED_FIELDS = [
    "symbol", "last_price", "open", "high", "low",
    "pre_close", "pct_change", "volume", "amount",
]

# 日线必需字段
DAILY_BAR_REQUIRED_FIELDS = [
    "symbol", "trade_date", "open", "high", "low", "close",
    "volume", "amount",
]

# 财务必需字段（允许部分缺失，但需进入 missing report）
FUNDAMENTALS_REQUIRED_FIELDS = [
    "symbol", "pe_ttm", "pb", "roe", "market_cap",
]
