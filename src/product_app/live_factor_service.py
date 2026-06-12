"""LiveFactorService — 从实时日线数据计算技术因子，供闭环信号生成使用。

核心职责：
- 封装 FactorEngine 的技术因子计算能力，适配 live 数据流
- 接收 LiveDataService 输出的日线 DataFrame，计算因子
- 优先使用 FactorEngine，不可用时降级为基础因子计算（SMA/EMA/RSI/MACD/BOLL）
- 因子值基于复权价（adjusted_close）计算

规则：
- is_demo 始终为 False
- data_status 为 FAILED 时返回空因子，status="failed"
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger


# ---------------------------------------------------------------------------
# 基础因子计算（降级方案）
# ---------------------------------------------------------------------------

def _calc_sma(series: pd.Series, window: int) -> pd.Series:
    """简单移动平均"""
    return series.rolling(window=window, min_periods=1).mean()


def _calc_ema(series: pd.Series, window: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=window, adjust=False).mean()


def _calc_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """相对强弱指标"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _calc_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD 指标，返回 (macd_line, signal_line, histogram)"""
    ema_fast = _calc_ema(series, fast)
    ema_slow = _calc_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _calc_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _calc_boll(
    series: pd.Series,
    window: int = 20,
    num_std: int = 2,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """布林带，返回 (upper, middle, lower)"""
    middle = _calc_sma(series, window)
    std = series.rolling(window=window, min_periods=1).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower


def _compute_basic_factors(df: pd.DataFrame) -> pd.DataFrame:
    """基础因子计算降级方案：SMA / EMA / RSI / MACD / BOLL。

    基于 adjusted_close 计算；若不存在则回退到 close。
    """
    result = df.copy()

    price_col = "adjusted_close" if "adjusted_close" in result.columns else "close"
    price = pd.to_numeric(result[price_col], errors="coerce")

    # SMA
    for w in (5, 10, 20, 60):
        result[f"sma_{w}"] = _calc_sma(price, w)

    # EMA
    for w in (12, 26):
        result[f"ema_{w}"] = _calc_ema(price, w)

    # RSI
    result["rsi_14"] = _calc_rsi(price, 14)

    # MACD
    macd_line, signal_line, histogram = _calc_macd(price, 12, 26, 9)
    result["macd_line"] = macd_line
    result["macd_signal"] = signal_line
    result["macd_hist"] = histogram

    # BOLL
    boll_upper, boll_middle, boll_lower = _calc_boll(price, 20, 2)
    result["boll_upper"] = boll_upper
    result["boll_middle"] = boll_middle
    result["boll_lower"] = boll_lower

    return result


# ---------------------------------------------------------------------------
# DataFrame → list[dict] 工具
# ---------------------------------------------------------------------------

def _records_from_frame(df: pd.DataFrame) -> list[dict[str, Any]]:
    """将 DataFrame 转为 list[dict]，NaN → None。"""
    if df is None or df.empty:
        return []
    result = df.where(pd.notna(df), None).to_dict(orient="records")
    return [{str(key): value for key, value in row.items()} for row in result]


# ---------------------------------------------------------------------------
# LiveFactorService
# ---------------------------------------------------------------------------

class LiveFactorService:
    """从实时日线数据计算技术因子，供闭环信号生成使用。

    优先使用 FactorEngine 的 compute_technical_factors，
    不可用时降级到基础因子计算（SMA/EMA/RSI/MACD/BOLL）。
    """

    # 尝试导入 FactorEngine 的标记
    _factor_engine_available: bool | None = None

    def __init__(self) -> None:
        self._check_factor_engine()

    def _check_factor_engine(self) -> None:
        """检测 FactorEngine 是否可用。"""
        if LiveFactorService._factor_engine_available is None:
            try:
                from src.factor_engine.technical_factors import compute_technical_factors  # noqa: F401
                LiveFactorService._factor_engine_available = True
            except Exception:
                LiveFactorService._factor_engine_available = False
                logger.warning(
                    "FactorEngine not available, falling back to basic factor computation"
                )

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    def compute_factors(
        self,
        daily_bars_df: pd.DataFrame,
        factor_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """从日线 DataFrame 计算技术因子。

        Args:
            daily_bars_df: 日线数据 DataFrame，应包含 live_data_mapper 定义的
                           DAILY_BAR_CONTRACT_COLUMNS 字段
            factor_names: 需要计算的因子名称列表，None 表示计算全部

        Returns:
            dict 包含:
            - status: "ok" | "failed"
            - factors: list[dict] 因子计算结果
            - factor_names: list[str] 实际计算的因子名
            - data_status: "OK" | "WARN" | "FAILED"
            - is_demo: 始终 False
        """
        # 空数据检查
        if daily_bars_df is None or daily_bars_df.empty:
            return {
                "status": "failed",
                "factors": [],
                "factor_names": [],
                "data_status": "FAILED",
                "is_demo": False,
            }

        # data_status 判断
        data_status = self._assess_data_status(daily_bars_df)
        if data_status == "FAILED":
            return {
                "status": "failed",
                "factors": [],
                "factor_names": [],
                "data_status": "FAILED",
                "is_demo": False,
            }

        # 计算因子
        try:
            result_df = self._do_compute(daily_bars_df)
        except Exception as exc:
            logger.error("Factor computation failed: {}", exc)
            return {
                "status": "failed",
                "factors": [],
                "factor_names": [],
                "data_status": "FAILED",
                "is_demo": False,
            }

        # 提取因子列名
        computed_factor_names = self._extract_factor_names(result_df, daily_bars_df)

        # 按 factor_names 过滤
        if factor_names is not None:
            # 保留标识列 + 指定因子列
            id_cols = [c for c in ["symbol", "trade_date"] if c in result_df.columns]
            keep_cols = id_cols + [c for c in factor_names if c in result_df.columns]
            # 也保留未在 factor_names 中但已计算的关键因子列（宽松匹配）
            result_df = result_df[keep_cols] if keep_cols else result_df
            computed_factor_names = [
                c for c in computed_factor_names if c in factor_names
            ]

        factors = _records_from_frame(result_df)

        return {
            "status": "ok" if data_status != "FAILED" else "failed",
            "factors": factors,
            "factor_names": computed_factor_names,
            "data_status": data_status,
            "is_demo": False,
        }

    def get_factor_summary(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """获取因子值及数据健康信息。

        通过 LiveDataService 获取日线数据，然后计算因子，
        返回合并结果。

        Args:
            symbols: 股票代码列表
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            dict 包含因子计算结果和数据健康信息
        """
        from src.product_app.live_data_service import get_live_data_service

        live_svc = get_live_data_service()
        bars_result = live_svc.get_daily_bars(symbols, start_date, end_date)

        # 如果日线数据获取失败，直接返回失败
        if bars_result.get("data_status") == "FAILED" or not bars_result.get("daily_bars"):
            return {
                "status": "failed",
                "factors": [],
                "factor_names": [],
                "data_status": "FAILED",
                "is_demo": False,
                "data_health": {
                    "data_status": bars_result.get("data_status", "FAILED"),
                    "chosen_provider": bars_result.get("chosen_provider", ""),
                    "fallback_chain": bars_result.get("fallback_chain", []),
                    "provider_health_report": bars_result.get("provider_health_report", {}),
                    "data_quality_report": bars_result.get("data_quality_report", {}),
                    "data_missing_report": bars_result.get("data_missing_report", {}),
                    "data_delay_report": bars_result.get("data_delay_report", {}),
                },
            }

        # 将 daily_bars list[dict] 转回 DataFrame
        daily_bars_df = pd.DataFrame(bars_result["daily_bars"])

        # 计算因子
        factor_result = self.compute_factors(daily_bars_df)

        # 合并数据健康信息
        factor_result["data_health"] = {
            "data_status": bars_result.get("data_status", "OK"),
            "chosen_provider": bars_result.get("chosen_provider", ""),
            "fallback_chain": bars_result.get("fallback_chain", []),
            "provider_health_report": bars_result.get("provider_health_report", {}),
            "data_quality_report": bars_result.get("data_quality_report", {}),
            "data_missing_report": bars_result.get("data_missing_report", {}),
            "data_delay_report": bars_result.get("data_delay_report", {}),
        }

        return factor_result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _do_compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行因子计算，优先使用 FactorEngine，降级到基础因子。"""
        if LiveFactorService._factor_engine_available:
            try:
                return self._compute_with_factor_engine(df)
            except Exception as exc:
                logger.warning(
                    "FactorEngine computation failed, falling back to basic: {}", exc
                )
                LiveFactorService._factor_engine_available = False

        return _compute_basic_factors(df)

    def _compute_with_factor_engine(self, df: pd.DataFrame) -> pd.DataFrame:
        """使用 FactorEngine 的 compute_technical_factors 计算。

        FactorEngine 需要 close/high/low/volume 列。
        优先使用 adjusted_close 作为 close 输入。
        """
        from src.factor_engine.technical_factors import compute_technical_factors

        work = df.copy()

        # FactorEngine 需要 close/high/low/volume
        # 优先使用复权价
        if "adjusted_close" in work.columns:
            work["close"] = pd.to_numeric(work["adjusted_close"], errors="coerce")
        if "adjusted_high" in work.columns:
            work["high"] = pd.to_numeric(work["adjusted_high"], errors="coerce")
        if "adjusted_low" in work.columns:
            work["low"] = pd.to_numeric(work["adjusted_low"], errors="coerce")
        if "adjusted_open" in work.columns:
            work["open"] = pd.to_numeric(work["adjusted_open"], errors="coerce")

        # 确保必要列存在且为数值
        for col in ["close", "high", "low", "volume"]:
            if col in work.columns:
                work[col] = pd.to_numeric(work[col], errors="coerce")

        result = compute_technical_factors(work)

        # 同时计算基础因子作为补充（RSI/MACD/BOLL 不在 FactorEngine 中）
        price_col = "close"
        price = pd.to_numeric(result[price_col], errors="coerce")

        # RSI
        result["rsi_14"] = _calc_rsi(price, 14)

        # MACD
        macd_line, signal_line, histogram = _calc_macd(price, 12, 26, 9)
        result["macd_line"] = macd_line
        result["macd_signal"] = signal_line
        result["macd_hist"] = histogram

        # BOLL
        boll_upper, boll_middle, boll_lower = _calc_boll(price, 20, 2)
        result["boll_upper"] = boll_upper
        result["boll_middle"] = boll_middle
        result["boll_lower"] = boll_lower

        # SMA/EMA 别名（FactorEngine 用 ma5/ma10/ma20/ma60，补充 sma_ 前缀别名）
        for alias, src in [
            ("sma_5", "ma5"),
            ("sma_10", "ma10"),
            ("sma_20", "ma20"),
            ("sma_60", "ma60"),
        ]:
            if src in result.columns and alias not in result.columns:
                result[alias] = result[src]

        # EMA
        for w in (12, 26):
            col_name = f"ema_{w}"
            if col_name not in result.columns:
                result[col_name] = _calc_ema(price, w)

        return result

    @staticmethod
    def _assess_data_status(df: pd.DataFrame) -> str:
        """评估输入数据的健康状态。

        Returns:
            "OK" | "WARN" | "FAILED"
        """
        if df is None or df.empty:
            return "FAILED"

        # 检查关键价格列是否存在
        price_col = "adjusted_close" if "adjusted_close" in df.columns else "close"
        if price_col not in df.columns:
            return "FAILED"

        # 检查关键列是否全为 NaN
        if df[price_col].isna().all():
            return "FAILED"

        # 有部分 NaN 则 WARN
        if df[price_col].isna().any():
            return "WARN"

        return "OK"

    @staticmethod
    def _extract_factor_names(
        result_df: pd.DataFrame,
        input_df: pd.DataFrame,
    ) -> list[str]:
        """从计算结果中提取因子列名（排除输入列和标识列）。"""
        id_cols = {"symbol", "trade_date", "currency", "timezone",
                    "data_source", "updated_at", "data_version"}
        input_cols = set(input_df.columns)
        factor_cols = [
            col for col in result_df.columns
            if col not in id_cols and col not in input_cols
        ]
        return factor_cols


# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

_live_factor_service: LiveFactorService | None = None


def get_live_factor_service() -> LiveFactorService:
    """获取全局 LiveFactorService 单例。"""
    global _live_factor_service
    if _live_factor_service is None:
        _live_factor_service = LiveFactorService()
    return _live_factor_service
