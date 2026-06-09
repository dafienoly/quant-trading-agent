"""运行时风控引擎

在实盘盯盘阶段执行实时风控检查，包括：
- 数据延迟检测
- 数据空值检测
- Kill Switch 状态
- 股票池范围检查
- 交易模式检查
- 交易层风控（RISK_POLICY.md 2-4 节）

所有检查结果汇聚为 RiskDecision，fail-closed 原则：任何异常默认阻断。
"""
from __future__ import annotations

from src.config.settings import (
    DAILY_LOSS_STOP,
    DAILY_LOSS_WARN,
    LEVEL_1_SIGNAL_ONLY,
    MAX_DRAWDOWN_DEFENSE,
    MAX_DRAWDOWN_HALT,
    MAX_SECTOR_POSITION,
    MAX_SINGLE_STOCK_POSITION,
    MIN_CASH_RATIO,
    SINGLE_STOCK_LOSS_STOP,
    SINGLE_STOCK_LOSS_WARN,
)
from src.risk_engine.models import KillSwitchState, RiskBlockReason, RiskDecision, RiskLevel
from src.stock_pool.mainboard_filter import is_excluded


class RuntimeRiskEngine:
    def __init__(
        self,
        max_quote_delay_seconds: float = 10.0,
        kill_switch: KillSwitchState | None = None,
    ):
        self.max_quote_delay_seconds = max_quote_delay_seconds
        self.kill_switch = kill_switch or KillSwitchState()

    def check_realtime_snapshot(self, quotes: list[dict], trading_mode: str = LEVEL_1_SIGNAL_ONLY) -> RiskDecision:
        reasons: list[RiskBlockReason] = []
        messages: list[str] = []
        evidence = {"quote_count": len(quotes), "max_quote_delay_seconds": self.max_quote_delay_seconds}

        if self.kill_switch.active:
            reasons.append(RiskBlockReason.KILL_SWITCH)
            messages.append(f"Kill Switch active: {self.kill_switch.reason}")

        if not quotes:
            reasons.append(RiskBlockReason.EMPTY_QUOTES)
            messages.append("Realtime quote payload is empty")

        delayed = [
            quote for quote in quotes
            if float(quote.get("delay_seconds", 0.0)) > self.max_quote_delay_seconds
        ]
        if delayed:
            reasons.append(RiskBlockReason.DATA_DELAY)
            messages.append(f"{len(delayed)} quotes exceed delay threshold")
            evidence["delayed_symbols"] = [quote.get("symbol", "") for quote in delayed]

        risk_pass = len(reasons) == 0
        return RiskDecision(
            risk_pass=risk_pass,
            level=RiskLevel.OK if risk_pass else RiskLevel.BLOCK,
            trading_mode=trading_mode,
            reasons=reasons,
            messages=messages,
            evidence=evidence,
        )

    def check_symbol_universe(self, symbols: list[str]) -> RiskDecision:
        reasons: list[RiskBlockReason] = []
        messages: list[str] = []
        disallowed = [symbol for symbol in symbols if is_excluded(symbol)]

        if disallowed:
            reasons.append(RiskBlockReason.DISALLOWED_BOARD)
            messages.append(f"Disallowed board symbols: {','.join(disallowed)}")

        risk_pass = len(reasons) == 0
        return RiskDecision(
            risk_pass=risk_pass,
            level=RiskLevel.OK if risk_pass else RiskLevel.BLOCK,
            reasons=reasons,
            messages=messages,
            evidence={"symbols": symbols, "disallowed": disallowed},
        )

    def check_portfolio_risk(self, portfolio: dict) -> RiskDecision:
        """交易层风控检查 (RISK_POLICY.md 2-4 节)

        Args:
            portfolio: 持仓信息字典，包含：
                - total_assets: float, 账户总资产
                - cash: float, 可用现金
                - daily_pnl_pct: float, 当日盈亏比例 (如 -0.02 表示 -2%)
                - drawdown_pct: float, 从历史最高净值的回撤比例 (如 -0.08 表示 -8%)
                - holdings: list[dict], 持仓列表，每项包含：
                    - symbol: str, 股票代码
                    - sector: str, 所属板块
                    - position_pct: float, 仓位占比 (如 0.15 表示 15%)
                    - pnl_pct: float, 浮动盈亏比例 (如 -0.05 表示 -5%)

        Returns:
            RiskDecision: 风控决策结果
        """
        reasons: list[RiskBlockReason] = []
        messages: list[str] = []
        evidence: dict = {}

        total_assets = portfolio.get("total_assets", 0.0)
        cash = portfolio.get("cash", 0.0)
        daily_pnl_pct = portfolio.get("daily_pnl_pct", 0.0)
        drawdown_pct = portfolio.get("drawdown_pct", 0.0)
        holdings = portfolio.get("holdings", [])

        # --- 2.1 单票仓位检查 [HARD] ---
        for h in holdings:
            symbol = h.get("symbol", "")
            pos_pct = h.get("position_pct", 0.0)
            if pos_pct > MAX_SINGLE_STOCK_POSITION:
                reasons.append(RiskBlockReason.SINGLE_STOCK_POSITION_EXCEEDED)
                messages.append(
                    f"单票仓位超限: {symbol} 仓位 {pos_pct:.1%} > 上限 {MAX_SINGLE_STOCK_POSITION:.1%}"
                )
                evidence.setdefault("position_exceeded", []).append(symbol)

        # --- 2.2 板块集中度检查 [HARD] ---
        sector_positions: dict[str, float] = {}
        for h in holdings:
            sector = h.get("sector", "unknown")
            pos_pct = h.get("position_pct", 0.0)
            sector_positions[sector] = sector_positions.get(sector, 0.0) + pos_pct

        for sector, total_pos in sector_positions.items():
            if total_pos > MAX_SECTOR_POSITION:
                reasons.append(RiskBlockReason.SECTOR_CONCENTRATION_EXCEEDED)
                messages.append(
                    f"板块集中度超限: {sector} 仓位 {total_pos:.1%} > 上限 {MAX_SECTOR_POSITION:.1%}"
                )
                evidence.setdefault("sector_exceeded", []).append(sector)

        # --- 2.2 现金最低比例 [HARD] ---
        if total_assets > 0:
            cash_ratio = cash / total_assets
            evidence["cash_ratio"] = round(cash_ratio, 4)
            if cash_ratio < MIN_CASH_RATIO:
                reasons.append(RiskBlockReason.INSUFFICIENT_CASH)
                messages.append(
                    f"现金比例不足: {cash_ratio:.1%} < 最低 {MIN_CASH_RATIO:.1%}"
                )

        # --- 3.1 单票亏损检查 ---
        for h in holdings:
            symbol = h.get("symbol", "")
            pnl_pct = h.get("pnl_pct", 0.0)
            if pnl_pct <= SINGLE_STOCK_LOSS_STOP:
                reasons.append(RiskBlockReason.SINGLE_STOCK_LOSS_STOP)
                messages.append(
                    f"单票强止损: {symbol} 亏损 {pnl_pct:.1%} <= 止损线 {SINGLE_STOCK_LOSS_STOP:.1%}"
                )
                evidence.setdefault("stop_loss", []).append(symbol)
            elif pnl_pct <= SINGLE_STOCK_LOSS_WARN:
                reasons.append(RiskBlockReason.SINGLE_STOCK_LOSS_WARN)
                messages.append(
                    f"单票减半提醒: {symbol} 亏损 {pnl_pct:.1%} <= 警戒线 {SINGLE_STOCK_LOSS_WARN:.1%}"
                )
                evidence.setdefault("warn_loss", []).append(symbol)

        # --- 3.2 账户日亏损检查 [HARD] ---
        evidence["daily_pnl_pct"] = daily_pnl_pct
        if daily_pnl_pct <= DAILY_LOSS_STOP:
            reasons.append(RiskBlockReason.DAILY_LOSS_REDUCE_ONLY)
            messages.append(
                f"日亏损超限(只允许减仓): {daily_pnl_pct:.1%} <= {DAILY_LOSS_STOP:.1%}"
            )
        elif daily_pnl_pct <= DAILY_LOSS_WARN:
            reasons.append(RiskBlockReason.DAILY_LOSS_STOP_NEW)
            messages.append(
                f"日亏损警戒(停止开新仓): {daily_pnl_pct:.1%} <= {DAILY_LOSS_WARN:.1%}"
            )

        # --- 3.3 账户最大回撤检查 [HARD] ---
        evidence["drawdown_pct"] = drawdown_pct
        if drawdown_pct <= MAX_DRAWDOWN_HALT:
            reasons.append(RiskBlockReason.DRAWDOWN_HALT)
            messages.append(
                f"回撤超限(停止所有交易): {drawdown_pct:.1%} <= {MAX_DRAWDOWN_HALT:.1%}"
            )
        elif drawdown_pct <= MAX_DRAWDOWN_DEFENSE:
            reasons.append(RiskBlockReason.DRAWDOWN_DEFENSE)
            messages.append(
                f"回撤警戒(防守模式): {drawdown_pct:.1%} <= {MAX_DRAWDOWN_DEFENSE:.1%}"
            )

        # 确定风控级别
        has_block = any(
            r in {
                RiskBlockReason.SINGLE_STOCK_POSITION_EXCEEDED,
                RiskBlockReason.SECTOR_CONCENTRATION_EXCEEDED,
                RiskBlockReason.INSUFFICIENT_CASH,
                RiskBlockReason.SINGLE_STOCK_LOSS_STOP,
                RiskBlockReason.DAILY_LOSS_REDUCE_ONLY,
                RiskBlockReason.DAILY_LOSS_STOP_NEW,
                RiskBlockReason.DRAWDOWN_HALT,
            }
            for r in reasons
        )
        has_warn = any(
            r in {
                RiskBlockReason.SINGLE_STOCK_LOSS_WARN,
                RiskBlockReason.DRAWDOWN_DEFENSE,
            }
            for r in reasons
        )

        if has_block:
            level = RiskLevel.BLOCK
            risk_pass = False
        elif has_warn:
            level = RiskLevel.WARN
            risk_pass = True
        else:
            level = RiskLevel.OK
            risk_pass = True

        return RiskDecision(
            risk_pass=risk_pass,
            level=level,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
            reasons=reasons,
            messages=messages,
            evidence=evidence,
        )
