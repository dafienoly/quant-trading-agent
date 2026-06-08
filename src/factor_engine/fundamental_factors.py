"""基本面因子计算

实现 ARCHITECTURE.md 5.4 节定义的基本面分：
- revenue_yoy: 营收同比增速
- net_profit_yoy: 净利润同比增速
- gross_margin_change: 毛利率变化
- roe: 净资产收益率
- consensus_profit_growth: 一致预期利润增速
- industry_prosperity: 行业景气度

基本面分公式：
fundamental_score = 0.20*rank(revenue_yoy) + 0.20*rank(net_profit_yoy)
                  + 0.15*rank(gross_margin_change) + 0.15*rank(roe)
                  + 0.15*rank(consensus_profit_growth) + 0.15*rank(industry_prosperity)

缺失数据不静默填充，使用 is_fundamental_missing 标记。
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

FUNDAMENTAL_FIELDS = [
    "revenue_yoy",
    "net_profit_yoy",
    "gross_margin_change",
    "roe",
    "consensus_profit_growth",
    "industry_prosperity",
]


def fetch_financial_data_from_akshare(symbols: List[str]) -> Dict[str, dict]:
    """
    从 AkShare 获取财务指标数据。

    使用 ak.stock_financial_analysis_indicator 获取最新财务分析指标。

    返回: {symbol: {field: value}} 字典
    """
    try:
        import akshare as ak
    except ImportError:
        logger.warning("AkShare not installed, cannot fetch financial data")
        return {}

    result = {}
    for symbol in symbols:
        code = symbol.split(".")[0] if "." in symbol else symbol
        try:
            # 获取财务分析指标
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year="2024")
            if df is not None and not df.empty:
                latest = df.iloc[0]  # 最新一期
                data = {}

                # 营收同比增速
                if "营业收入同比增长率" in df.columns:
                    val = latest.get("营业收入同比增长率")
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        try:
                            data["revenue_yoy"] = float(val)
                        except (ValueError, TypeError):
                            pass

                # 净利润同比增速
                if "净利润同比增长率" in df.columns:
                    val = latest.get("净利润同比增长率")
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        try:
                            data["net_profit_yoy"] = float(val)
                        except (ValueError, TypeError):
                            pass

                # ROE
                if "净资产收益率" in df.columns:
                    val = latest.get("净资产收益率")
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        try:
                            data["roe"] = float(val)
                        except (ValueError, TypeError):
                            pass

                # 毛利率变化（用最新毛利率与上年比较）
                if "销售毛利率" in df.columns and len(df) >= 2:
                    try:
                        current_gm = float(df.iloc[0]["销售毛利率"])
                        prev_gm = float(df.iloc[1]["销售毛利率"])
                        data["gross_margin_change"] = current_gm - prev_gm
                    except (ValueError, TypeError, KeyError):
                        pass

                result[symbol] = data
                logger.debug(f"Financial data fetched for {code}: {list(data.keys())}")
            else:
                logger.debug(f"No financial data for {code}")
        except Exception as e:
            logger.warning(f"Failed to fetch financial data for {code}: {e}")

    return result


def compute_fundamental_factors(
    df: pd.DataFrame,
    financial_data: Optional[Dict[str, dict]] = None,
) -> pd.DataFrame:
    """
    计算基本面因子。

    输入 DataFrame 可包含以下列：
    - revenue_yoy: 营收同比增速 (%)
    - net_profit_yoy: 净利润同比增速 (%)
    - gross_margin_change: 毛利率变化 (百分点)
    - roe: 净资产收益率 (%)
    - consensus_profit_growth: 一致预期利润增速 (%)
    - industry_prosperity: 行业景气度 (0~100)

    若提供 financial_data 字典，则合并到 DataFrame 中。
    缺失字段保留 NaN，不静默填充，新增 is_fundamental_missing 标记。

    输出新增列：所有基本面字段 + is_fundamental_missing
    """
    if df.empty:
        return df

    result = df.copy()

    # 合并外部财务数据
    if financial_data:
        for field in FUNDAMENTAL_FIELDS:
            field_values = []
            for symbol in result["symbol"]:
                val = financial_data.get(symbol, {}).get(field, np.nan)
                field_values.append(val)
            # 外部数据仅在 DataFrame 中该列缺失或全 NaN 时写入
            if field not in result.columns or result[field].isna().all():
                result[field] = field_values
            else:
                # 对已有 NaN 的行用外部数据填充
                for i, (existing, new_val) in enumerate(zip(result[field], field_values)):
                    if pd.isna(existing) and not pd.isna(new_val):
                        result.at[result.index[i], field] = new_val

    # 确保所有基本面字段存在，缺失保留 NaN
    for col in FUNDAMENTAL_FIELDS:
        if col not in result.columns:
            result[col] = np.nan

    # 标记基本面数据缺失（不静默填充）
    result["is_fundamental_missing"] = result[FUNDAMENTAL_FIELDS].isna().all(axis=1)

    missing_count = result["is_fundamental_missing"].sum()
    if missing_count > 0:
        logger.warning(
            f"Fundamental data missing for {missing_count}/{len(result)} stocks"
        )

    return result


def compute_fundamental_score(df: pd.DataFrame) -> pd.Series:
    """
    计算基本面分 (0~100)

    使用绝对评分模式，缺失字段按中性值（中间分）处理：
    - revenue_yoy: -50%~+100% 映射到 0~20
    - net_profit_yoy: -50%~+100% 映射到 0~20
    - gross_margin_change: -10~+10 百分点 映射到 0~15
    - roe: 0~30% 映射到 0~15
    - consensus_profit_growth: -30%~+60% 映射到 0~15
    - industry_prosperity: 0~100 映射到 0~15

    缺失字段给予中间分（满分的一半），而非0分。
    """
    score = pd.Series(0.0, index=df.index)

    if "revenue_yoy" in df.columns:
        valid = df["revenue_yoy"].notna()
        score += np.where(valid, np.clip((df["revenue_yoy"] + 50) / 150 * 20, 0, 20), 10.0)

    if "net_profit_yoy" in df.columns:
        valid = df["net_profit_yoy"].notna()
        score += np.where(valid, np.clip((df["net_profit_yoy"] + 50) / 150 * 20, 0, 20), 10.0)

    if "gross_margin_change" in df.columns:
        valid = df["gross_margin_change"].notna()
        score += np.where(valid, np.clip((df["gross_margin_change"] + 10) / 20 * 15, 0, 15), 7.5)

    if "roe" in df.columns:
        valid = df["roe"].notna()
        score += np.where(valid, np.clip(df["roe"] / 30 * 15, 0, 15), 7.5)

    if "consensus_profit_growth" in df.columns:
        valid = df["consensus_profit_growth"].notna()
        score += np.where(valid, np.clip((df["consensus_profit_growth"] + 30) / 90 * 15, 0, 15), 7.5)

    if "industry_prosperity" in df.columns:
        valid = df["industry_prosperity"].notna()
        score += np.where(valid, np.clip(df["industry_prosperity"] / 100 * 15, 0, 15), 7.5)

    return score
