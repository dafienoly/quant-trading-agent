"""LiveSignalOrchestrator — 产品闭环信号生成的唯一入口。

核心职责：
- 协调 LiveDataService、LiveFactorService、LiveBacktestService、DataHealthGate
- 生成带有完整证据链的 SignalDraft
- 强制执行数据健康门控：数据不健康时阻断信号

规则：
- 本模块是 live closed-loop 中唯一生成信号的地方
- is_demo 始终为 False
- 数据健康门控不通过时，返回 status="blocked" 的 SignalDraft
- 信号 ID 格式：SIG_YYYYMMDD_NNN
- 信号当日 15:00 过期
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from src.product_app.data_health_gate import DataHealthGate


# ---------------------------------------------------------------------------
# 信号 ID 计数器（进程内，按日期重置）
# ---------------------------------------------------------------------------

_signal_counter_lock = threading.Lock()
_signal_counter_date: str = ""
_signal_counter_seq: int = 0


def _next_signal_id() -> str:
    """生成唯一信号 ID：SIG_YYYYMMDD_NNN，同一天内递增。"""
    global _signal_counter_date, _signal_counter_seq
    today = datetime.now().strftime("%Y%m%d")
    with _signal_counter_lock:
        if today != _signal_counter_date:
            _signal_counter_date = today
            _signal_counter_seq = 0
        _signal_counter_seq += 1
        return f"SIG_{today}_{_signal_counter_seq:03d}"


# ---------------------------------------------------------------------------
# LiveSignalOrchestrator
# ---------------------------------------------------------------------------

class LiveSignalOrchestrator:
    """产品闭环信号编排器。

    协调数据获取、因子计算、快速回测、数据健康评估，
    生成带有完整证据链的 SignalDraft。
    """

    def __init__(self) -> None:
        self._data_service = None  # lazy init
        self._health_gate = DataHealthGate()
        self._signal_store: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lazy init 避免循环导入
    # ------------------------------------------------------------------

    def _get_data_service(self):
        if self._data_service is None:
            from src.product_app.live_data_service import LiveDataService
            self._data_service = LiveDataService()
        return self._data_service

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    def generate_signal_draft(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        trading_mode: str = "LEVEL_1_SIGNAL_ONLY",
    ) -> dict[str, Any]:
        """生成信号草稿，包含完整证据链。

        流程：
        1. 获取日线数据（LiveDataService）
        2. 获取基本面数据（LiveDataService）
        3. 计算因子（LiveFactorService）
        4. 运行快速回测（LiveBacktestService）
        5. 评估数据健康（DataHealthGate）
        6. 数据不健康 → 返回 blocked 信号
        7. 判定信号类型
        8. 计算置信度
        9. 风控检查
        10. 构建 SignalDraft

        Args:
            symbols: 股票代码列表
            start_date: 开始日期 (YYYY-MM-DD 或 YYYYMMDD)
            end_date: 结束日期 (YYYY-MM-DD 或 YYYYMMDD)
            trading_mode: 交易模式

        Returns:
            SignalDraft 字典
        """
        logger.info(
            "LiveSignalOrchestrator: 开始生成信号草稿, symbols={}, "
            "start_date={}, end_date={}, trading_mode={}",
            symbols, start_date, end_date, trading_mode,
        )

        # LEVEL_3_AUTO 在当前阶段被禁止
        if trading_mode == "LEVEL_3_AUTO":
            logger.warning("LiveSignalOrchestrator: LEVEL_3_AUTO 被拒绝")
            return {
                "signal_id": _next_signal_id(),
                "status": "rejected",
                "message": "LEVEL_3_AUTO is not available in the current phase. Automated trading is not enabled.",
                "trading_mode": trading_mode,
                "symbols": symbols,
            }

        now = datetime.now()
        created_at = now.strftime("%Y-%m-%d %H:%M:%S")
        expires_at = now.replace(hour=15, minute=0, second=0, microsecond=0)
        if now >= expires_at:
            # 已过收盘时间，次日收盘过期
            expires_at = (now + timedelta(days=1)).replace(
                hour=15, minute=0, second=0, microsecond=0
            )
        expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")

        # ── 1. 获取实时行情 ──────────────────────────────────────
        data_service = self._get_data_service()
        quotes_result = data_service.get_realtime_quotes(symbols, allow_demo=False)

        # ── 2. 获取日线数据 ──────────────────────────────────────
        daily_result = data_service.get_daily_bars(symbols, start_date, end_date)

        # ── 3. 获取基本面数据 ────────────────────────────────────
        fundamentals_result = data_service.get_fundamentals(symbols)

        # ── 4. 计算因子 ──────────────────────────────────────────
        factor_result = self._compute_factors(
            daily_result, fundamentals_result, symbols
        )

        # ── 5. 运行快速回测 ──────────────────────────────────────
        backtest_result = self._run_quick_backtest(
            daily_result, symbols, start_date, end_date
        )

        # ── 6. 评估数据健康（使用真实行情结果）────────────────────
        # 从 quotes_result 提取 provider_delay 供 DataHealthGate 使用
        quotes_for_gate = {
            "data_status": quotes_result.get("data_status", "FAILED"),
            "provider_delay": quotes_result.get("data_delay_report", {}).get("max_delay_seconds"),
        }
        health_decision = self._health_gate.evaluate(
            quotes_result=quotes_for_gate,
            daily_bars_result={"data_status": daily_result.get("data_status", "FAILED")},
            fundamentals_result={"data_status": fundamentals_result.get("data_status", "FAILED")},
            is_demo=False,
            trading_mode=trading_mode,
        )

        # ── 7. 数据不健康 → 返回 blocked 信号 ────────────────────
        if not health_decision.allow_signal:
            logger.warning(
                "LiveSignalOrchestrator: 数据健康门控阻断信号, "
                "data_status={}, messages={}",
                health_decision.data_status,
                health_decision.messages,
            )
            signal_id = _next_signal_id()
            blocked_draft = {
                "signal_id": signal_id,
                "status": "blocked",
                "symbols": symbols,
                "trading_mode": trading_mode,
                "signal_type": "hold",
                "confidence": 0.0,
                "evidence": {
                    "data_health": {
                        "data_status": health_decision.data_status,
                        "allow_signal": health_decision.allow_signal,
                        "risk_level": health_decision.risk_level,
                        "messages": health_decision.messages,
                        "delay_evidence": health_decision.evidence,
                    },
                    "factor_summary": factor_result.get("summary", {}),
                    "backtest_summary": backtest_result.get("summary", {}),
                    "provider_chain": {
                        "quotes": quotes_result.get("fallback_chain", []),
                        "daily_bars": daily_result.get("fallback_chain", []),
                        "fundamentals": fundamentals_result.get("fallback_chain", []),
                    },
                    "quotes_status": quotes_result.get("data_status", "UNKNOWN"),
                    "feedback_bug_id": quotes_result.get("feedback_bug_id", ""),
                },
                "risk_check": {
                    "position_limit_ok": False,
                    "drawdown_limit_ok": False,
                    "concentration_ok": False,
                },
                "created_at": created_at,
                "expires_at": expires_at_str,
                "is_demo": False,
            }
            self._signal_store[signal_id] = blocked_draft
            return blocked_draft

        # ── 7. 判定信号类型 ──────────────────────────────────────
        signal_type = self._determine_signal_type(factor_result, backtest_result)

        # ── 8. 计算置信度 ────────────────────────────────────────
        confidence = self._calculate_confidence(
            health_decision, factor_result, backtest_result
        )

        # ── 9. 风控检查 ──────────────────────────────────────────
        risk_check = self._check_risk(symbols, backtest_result)

        # ── 10. 构建 SignalDraft ─────────────────────────────────
        signal_id = _next_signal_id()
        signal_draft = {
            "signal_id": signal_id,
            "status": "draft",
            "symbols": symbols,
            "trading_mode": trading_mode,
            "signal_type": signal_type,
            "confidence": round(confidence, 4),
            "evidence": {
                "data_health": {
                    "data_status": health_decision.data_status,
                    "allow_signal": health_decision.allow_signal,
                    "risk_level": health_decision.risk_level,
                    "messages": health_decision.messages,
                    "delay_evidence": health_decision.evidence,
                },
                "factor_summary": factor_result.get("summary", {}),
                "backtest_summary": backtest_result.get("summary", {}),
                "provider_chain": {
                    "quotes": quotes_result.get("fallback_chain", []),
                    "daily_bars": daily_result.get("fallback_chain", []),
                    "fundamentals": fundamentals_result.get("fallback_chain", []),
                },
                "quotes_status": quotes_result.get("data_status", "UNKNOWN"),
            },
            "risk_check": risk_check,
            "created_at": created_at,
            "expires_at": expires_at_str,
            "is_demo": False,
        }

        self._signal_store[signal_id] = signal_draft
        logger.info(
            "LiveSignalOrchestrator: 信号草稿生成完成, signal_id={}, "
            "signal_type={}, confidence={:.4f}",
            signal_id, signal_type, confidence,
        )
        return signal_draft

    def get_signal_status(self, signal_id: str) -> dict[str, Any]:
        """获取信号状态。

        Args:
            signal_id: 信号 ID

        Returns:
            信号状态字典，不存在时返回 not_found
        """
        if signal_id in self._signal_store:
            return {
                "status": "ok",
                "signal": self._signal_store[signal_id],
            }
        return {
            "status": "not_found",
            "signal": None,
            "message": f"Signal {signal_id} not found",
        }

    # ------------------------------------------------------------------
    # 因子计算（内部方法）
    # ------------------------------------------------------------------

    def _compute_factors(
        self,
        daily_result: dict[str, Any],
        fundamentals_result: dict[str, Any],
        symbols: list[str],
    ) -> dict[str, Any]:
        """基于日线和基本面数据计算因子。

        当前为简化实现，基于已有数据提取关键指标。
        后续可接入 LiveFactorService 进行完整因子计算。
        """
        daily_bars = daily_result.get("daily_bars", [])
        fundamentals = fundamentals_result.get("fundamentals", [])

        # 提取因子指标
        factor_values: dict[str, Any] = {}
        factor_warnings: list[str] = []

        if not daily_bars:
            factor_warnings.append("日线数据为空，因子计算受限")
            factor_values["momentum"] = 0.0
            factor_values["volatility"] = 0.0
            factor_values["volume_ratio"] = 0.0
        else:
            # 动量因子：最近收盘价相对期初的涨跌幅
            closes = [
                bar.get("close", 0) for bar in daily_bars
                if bar.get("close") is not None
            ]
            if len(closes) >= 2:
                factor_values["momentum"] = (closes[-1] - closes[0]) / closes[0] if closes[0] != 0 else 0.0
            else:
                factor_values["momentum"] = 0.0

            # 波动率因子：收益率标准差
            if len(closes) >= 2:
                returns = [
                    (closes[i] - closes[i - 1]) / closes[i - 1]
                    for i in range(1, len(closes))
                    if closes[i - 1] != 0
                ]
                if returns:
                    mean_ret = sum(returns) / len(returns)
                    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
                    factor_values["volatility"] = variance ** 0.5
                else:
                    factor_values["volatility"] = 0.0
            else:
                factor_values["volatility"] = 0.0

            # 成交量比率
            volumes = [
                bar.get("volume", 0) for bar in daily_bars
                if bar.get("volume") is not None
            ]
            if len(volumes) >= 2 and volumes[0] != 0:
                factor_values["volume_ratio"] = volumes[-1] / volumes[0]
            else:
                factor_values["volume_ratio"] = 0.0

        # 基本面因子
        if not fundamentals:
            factor_warnings.append("基本面数据为空，基本面因子不可用")
            factor_values["pe_ratio"] = None
            factor_values["pb_ratio"] = None
        else:
            pe_values = [
                f.get("pe_ratio") for f in fundamentals
                if f.get("pe_ratio") is not None
            ]
            pb_values = [
                f.get("pb_ratio") for f in fundamentals
                if f.get("pb_ratio") is not None
            ]
            factor_values["pe_ratio"] = sum(pe_values) / len(pe_values) if pe_values else None
            factor_values["pb_ratio"] = sum(pb_values) / len(pb_values) if pb_values else None

        # 因子强度评分 (0-1)
        momentum = factor_values.get("momentum", 0.0) or 0.0
        volatility = factor_values.get("volatility", 0.0) or 0.0
        # 动量绝对值越大、波动率适中 → 因子越强
        factor_strength = min(abs(momentum) * 5, 1.0) * max(0.2, 1.0 - volatility * 10)
        factor_strength = max(0.0, min(1.0, factor_strength))

        return {
            "factors": factor_values,
            "warnings": factor_warnings,
            "summary": {
                "factor_strength": round(factor_strength, 4),
                "momentum": round(momentum, 4),
                "volatility": round(volatility, 4),
                "symbols_count": len(symbols),
                "has_fundamentals": bool(fundamentals),
            },
        }

    # ------------------------------------------------------------------
    # 快速回测（内部方法）
    # ------------------------------------------------------------------

    def _run_quick_backtest(
        self,
        daily_result: dict[str, Any],
        symbols: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """基于日线数据运行快速回测。

        当前为简化实现，基于已有数据计算回测指标。
        后续可接入 LiveBacktestService 进行完整回测。
        """
        daily_bars = daily_result.get("daily_bars", [])

        if not daily_bars:
            return {
                "status": "no_data",
                "summary": {
                    "total_return": 0.0,
                    "sharpe": 0.0,
                    "max_drawdown": 0.0,
                    "win_rate": 0.0,
                },
                "warnings": ["日线数据为空，无法运行回测"],
            }

        # 计算简单回测指标
        closes = [
            bar.get("close", 0) for bar in daily_bars
            if bar.get("close") is not None
        ]

        if len(closes) < 2:
            return {
                "status": "insufficient_data",
                "summary": {
                    "total_return": 0.0,
                    "sharpe": 0.0,
                    "max_drawdown": 0.0,
                    "win_rate": 0.0,
                },
                "warnings": ["数据点不足，无法运行回测"],
            }

        # 总收益率
        total_return = (closes[-1] - closes[0]) / closes[0] if closes[0] != 0 else 0.0

        # 日收益率
        daily_returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1] != 0
        ]

        # Sharpe 比率（年化，假设 252 个交易日）
        if daily_returns:
            mean_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
            std_return = variance ** 0.5 if variance > 0 else 0.0
            sharpe = (mean_return / std_return) * (252 ** 0.5) if std_return > 0 else 0.0
        else:
            sharpe = 0.0

        # 最大回撤
        max_drawdown = 0.0
        peak = closes[0]
        for close in closes:
            if close > peak:
                peak = close
            if peak != 0:
                drawdown = (peak - close) / peak
                max_drawdown = max(max_drawdown, drawdown)

        # 胜率
        win_count = sum(1 for r in daily_returns if r > 0)
        win_rate = win_count / len(daily_returns) if daily_returns else 0.0

        return {
            "status": "ok",
            "summary": {
                "total_return": round(total_return, 4),
                "sharpe": round(sharpe, 4),
                "max_drawdown": round(max_drawdown, 4),
                "win_rate": round(win_rate, 4),
                "symbols_count": len(symbols),
                "bars_count": len(daily_bars),
            },
            "warnings": [],
        }

    # ------------------------------------------------------------------
    # 信号类型判定
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_signal_type(
        factor_result: dict[str, Any],
        backtest_result: dict[str, Any],
    ) -> str:
        """根据因子和回测结果判定信号类型。

        规则：
        - backtest total_return > 0.05 且 sharpe > 0.5 → "buy"
        - backtest total_return < -0.05 或 sharpe < -0.5 → "sell"
        - 其他 → "hold"
        """
        bt_summary = backtest_result.get("summary", {})
        total_return = bt_summary.get("total_return", 0.0) or 0.0
        sharpe = bt_summary.get("sharpe", 0.0) or 0.0

        if total_return > 0.05 and sharpe > 0.5:
            return "buy"
        if total_return < -0.05 or sharpe < -0.5:
            return "sell"
        return "hold"

    # ------------------------------------------------------------------
    # 置信度计算
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_confidence(
        health_decision: Any,
        factor_result: dict[str, Any],
        backtest_result: dict[str, Any],
    ) -> float:
        """计算信号置信度。

        confidence = data_health_score * 0.3 + factor_score * 0.3 + backtest_score * 0.4

        - data_health_score: OK=1.0, WARN=0.5, FAILED=0.0
        - factor_score: factor_strength (0-1)
        - backtest_score: sharpe 归一化到 0-1
        """
        # 数据健康评分
        data_status = health_decision.data_status
        if data_status == "OK":
            data_health_score = 1.0
        elif data_status == "WARN":
            data_health_score = 0.5
        else:
            data_health_score = 0.0

        # 因子评分
        factor_score = factor_result.get("summary", {}).get("factor_strength", 0.0) or 0.0

        # 回测评分（sharpe 归一化：sharpe 2.0 → 1.0）
        sharpe = backtest_result.get("summary", {}).get("sharpe", 0.0) or 0.0
        backtest_score = min(abs(sharpe) / 2.0, 1.0)

        confidence = (
            data_health_score * 0.3
            + factor_score * 0.3
            + backtest_score * 0.4
        )
        return max(0.0, min(1.0, confidence))

    # ------------------------------------------------------------------
    # 风控检查
    # ------------------------------------------------------------------

    @staticmethod
    def _check_risk(
        symbols: list[str],
        backtest_result: dict[str, Any],
    ) -> dict[str, bool]:
        """风控检查。

        - position_limit_ok: True（占位，实际检查在 risk_engine）
        - drawdown_limit_ok: max_drawdown < 0.15
        - concentration_ok: len(symbols) >= 3 或单标的权重 < 0.3
        """
        bt_summary = backtest_result.get("summary", {})
        max_drawdown = bt_summary.get("max_drawdown", 0.0) or 0.0

        # 仓位限制（占位）
        position_limit_ok = True

        # 回撤限制
        drawdown_limit_ok = max_drawdown < 0.15

        # 集中度限制：标的数 >= 3 或单标的权重 < 0.3
        # 当只有 1-2 个标的时，单标的权重必然 >= 0.5，不满足
        concentration_ok = len(symbols) >= 3

        return {
            "position_limit_ok": position_limit_ok,
            "drawdown_limit_ok": drawdown_limit_ok,
            "concentration_ok": concentration_ok,
        }


# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

_live_signal_orchestrator: LiveSignalOrchestrator | None = None


def get_live_signal_orchestrator() -> LiveSignalOrchestrator:
    """获取全局 LiveSignalOrchestrator 单例。"""
    global _live_signal_orchestrator
    if _live_signal_orchestrator is None:
        _live_signal_orchestrator = LiveSignalOrchestrator()
    return _live_signal_orchestrator
