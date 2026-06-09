"""运行时风控决策模型

定义风控级别、阻断原因、Kill Switch 状态和风控决策模型。
Phase 4 核心约束：LEVEL_1_SIGNAL_ONLY 模式下 can_generate_order 永远为 False。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    OK = "OK"
    WARN = "WARN"
    BLOCK = "BLOCK"


class RiskBlockReason(str, Enum):
    DATA_DELAY = "DATA_DELAY"
    EMPTY_QUOTES = "EMPTY_QUOTES"
    UNKNOWN_SYMBOL = "UNKNOWN_SYMBOL"
    DISALLOWED_BOARD = "DISALLOWED_BOARD"
    KILL_SWITCH = "KILL_SWITCH"
    INVALID_TRADING_MODE = "INVALID_TRADING_MODE"
    LIVE_TRADING_DISABLED = "LIVE_TRADING_DISABLED"
    # 交易层风控 (RISK_POLICY.md 2-4)
    SINGLE_STOCK_POSITION_EXCEEDED = "SINGLE_STOCK_POSITION_EXCEEDED"
    SECTOR_CONCENTRATION_EXCEEDED = "SECTOR_CONCENTRATION_EXCEEDED"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    SINGLE_STOCK_LOSS_WARN = "SINGLE_STOCK_LOSS_WARN"
    SINGLE_STOCK_LOSS_STOP = "SINGLE_STOCK_LOSS_STOP"
    DAILY_LOSS_STOP_NEW = "DAILY_LOSS_STOP_NEW"
    DAILY_LOSS_REDUCE_ONLY = "DAILY_LOSS_REDUCE_ONLY"
    DRAWDOWN_DEFENSE = "DRAWDOWN_DEFENSE"
    DRAWDOWN_HALT = "DRAWDOWN_HALT"


class KillSwitchState(BaseModel):
    active: bool = False
    reason: str = ""
    activated_at: str = ""


class RiskDecision(BaseModel):
    risk_pass: bool
    level: RiskLevel
    trading_mode: str = "LEVEL_1_SIGNAL_ONLY"
    reasons: list[RiskBlockReason] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    checked_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def can_generate_signal(self) -> bool:
        return self.risk_pass and self.level in {RiskLevel.OK, RiskLevel.WARN}

    @property
    def can_generate_order(self) -> bool:
        return self.can_generate_signal and self.trading_mode in {
            "LEVEL_2_HUMAN_CONFIRM",
            "LEVEL_3_AUTO",
        }
