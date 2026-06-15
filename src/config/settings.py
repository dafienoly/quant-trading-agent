"""
配置管理模块

从 .env 文件和环境变量加载系统配置，提供类型安全的访问接口。
所有配置变更需经过本模块，禁止策略/交易模块直接读取 os.environ。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)
else:
    # 尝试加载 .env.example 作为默认值
    _EXAMPLE = Path(__file__).resolve().parent.parent.parent / ".env.example"
    if _EXAMPLE.exists():
        load_dotenv(_EXAMPLE)
        logger.warning("No .env file found, using .env.example defaults")


def _get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _get_bool(key: str, default: bool) -> bool:
    val = _get_env(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")


def _get_float(key: str, default: float) -> float:
    try:
        return float(_get_env(key, str(default)))
    except ValueError:
        return default


def _get_int(key: str, default: int) -> int:
    try:
        return int(_get_env(key, str(default)))
    except ValueError:
        return default


# ============================================================
# 交易模式配置
# ============================================================

MAX_TRADING_LEVEL: str = _get_env("MAX_TRADING_LEVEL", "LEVEL_1_SIGNAL_ONLY")
ENABLE_LIVE_TRADING: bool = _get_bool("ENABLE_LIVE_TRADING", False)
REQUIRE_HUMAN_CONFIRMATION: bool = _get_bool("REQUIRE_HUMAN_CONFIRMATION", True)

# 交易模式常量
LEVEL_0 = "LEVEL_0"
LEVEL_1_SIGNAL_ONLY = "LEVEL_1_SIGNAL_ONLY"
LEVEL_2_HUMAN_CONFIRM = "LEVEL_2_HUMAN_CONFIRM"
LEVEL_3_AUTO = "LEVEL_3_AUTO"


# ============================================================
# 数据源配置
# ============================================================

TUSHARE_TOKEN: str = _get_env("TUSHARE_TOKEN", "")
EASTMONEY_ENABLED: bool = _get_bool("EASTMONEY_ENABLED", True)
SINA_QUOTE_ENABLED: bool = _get_bool("SINA_QUOTE_ENABLED", True)
DEFAULT_DATA_PROVIDER: str = _get_env("DEFAULT_DATA_PROVIDER", "akshare")
REALTIME_REQUEST_INTERVAL_MS: int = _get_int("REALTIME_REQUEST_INTERVAL_MS", 500)


# ============================================================
# 数据库配置
# ============================================================

DATABASE_URL: str = _get_env("DATABASE_URL", "sqlite:///data/quant_trading.db")


# ============================================================
# 风控参数
# ============================================================

MAX_SINGLE_STOCK_POSITION: float = _get_float("MAX_SINGLE_STOCK_POSITION", 0.15)
MAX_SECTOR_POSITION: float = _get_float("MAX_SECTOR_POSITION", 0.60)
MIN_CASH_RATIO: float = _get_float("MIN_CASH_RATIO", 0.20)
SINGLE_STOCK_LOSS_WARN: float = _get_float("SINGLE_STOCK_LOSS_WARN", -0.05)
SINGLE_STOCK_LOSS_STOP: float = _get_float("SINGLE_STOCK_LOSS_STOP", -0.08)
DAILY_LOSS_WARN: float = _get_float("DAILY_LOSS_WARN", -0.02)
DAILY_LOSS_STOP: float = _get_float("DAILY_LOSS_STOP", -0.03)
MAX_DRAWDOWN_DEFENSE: float = _get_float("MAX_DRAWDOWN_DEFENSE", -0.08)
MAX_DRAWDOWN_HALT: float = _get_float("MAX_DRAWDOWN_HALT", -0.12)


# ============================================================
# 回测参数
# ============================================================

BACKTEST_COMMISSION_RATE: float = _get_float("BACKTEST_COMMISSION_RATE", 0.0003)
BACKTEST_STAMP_DUTY: float = _get_float("BACKTEST_STAMP_DUTY", 0.001)
BACKTEST_SLIPPAGE: float = _get_float("BACKTEST_SLIPPAGE", 0.001)


# ============================================================
# 券商接口配置
# ============================================================

BROKER_ADAPTER: str = _get_env("BROKER_ADAPTER", "paper")


# ============================================================
# 日志配置
# ============================================================

LOG_LEVEL: str = _get_env("LOG_LEVEL", "INFO")
LOG_FILE: str = _get_env("LOG_FILE", "logs/quant_trading.log")


# ============================================================
# 通知配置
# ============================================================

NOTIFY_EMAIL: str = _get_env("NOTIFY_EMAIL", "")
NOTIFY_WEBHOOK_URL: str = _get_env("NOTIFY_WEBHOOK_URL", "")


# ============================================================
# 配置验证与导出
# ============================================================

def validate_config() -> list[str]:
    """验证配置有效性，返回问题列表"""
    issues = []

    valid_levels = {LEVEL_0, LEVEL_1_SIGNAL_ONLY, LEVEL_2_HUMAN_CONFIRM, LEVEL_3_AUTO}
    if MAX_TRADING_LEVEL not in valid_levels:
        issues.append(f"Invalid MAX_TRADING_LEVEL: {MAX_TRADING_LEVEL}")

    if MAX_SINGLE_STOCK_POSITION <= 0 or MAX_SINGLE_STOCK_POSITION > 1:
        issues.append(f"Invalid MAX_SINGLE_STOCK_POSITION: {MAX_SINGLE_STOCK_POSITION}")

    if MIN_CASH_RATIO < 0 or MIN_CASH_RATIO > 1:
        issues.append(f"Invalid MIN_CASH_RATIO: {MIN_CASH_RATIO}")

    if ENABLE_LIVE_TRADING and MAX_TRADING_LEVEL == LEVEL_3_AUTO:
        issues.append(
            "WARNING: LIVE_TRADING enabled with AUTO mode. "
            "Ensure Phase 6 preconditions are met."
        )

    if ENABLE_LIVE_TRADING and not REQUIRE_HUMAN_CONFIRMATION:
        issues.append(
            "WARNING: LIVE_TRADING enabled without HUMAN_CONFIRMATION. "
            "This bypasses the safety requirement."
        )

    return issues


def get_config_dict() -> dict:
    """导出所有配置为字典（排除敏感信息）"""
    return {
        "max_trading_level": MAX_TRADING_LEVEL,
        "enable_live_trading": ENABLE_LIVE_TRADING,
        "require_human_confirmation": REQUIRE_HUMAN_CONFIRMATION,
        "default_data_provider": DEFAULT_DATA_PROVIDER,
        "database_url": DATABASE_URL,
        "max_single_stock_position": MAX_SINGLE_STOCK_POSITION,
        "max_sector_position": MAX_SECTOR_POSITION,
        "min_cash_ratio": MIN_CASH_RATIO,
        "single_stock_loss_warn": SINGLE_STOCK_LOSS_WARN,
        "single_stock_loss_stop": SINGLE_STOCK_LOSS_STOP,
        "daily_loss_warn": DAILY_LOSS_WARN,
        "daily_loss_stop": DAILY_LOSS_STOP,
        "max_drawdown_defense": MAX_DRAWDOWN_DEFENSE,
        "max_drawdown_halt": MAX_DRAWDOWN_HALT,
        "backtest_commission_rate": BACKTEST_COMMISSION_RATE,
        "backtest_stamp_duty": BACKTEST_STAMP_DUTY,
        "backtest_slippage": BACKTEST_SLIPPAGE,
        "broker_adapter": BROKER_ADAPTER,
        "log_level": LOG_LEVEL,
    }


# 启动时自动校验
_issues = validate_config()
for _issue in _issues:
    logger.warning(f"Config issue: {_issue}")

logger.info(
    f"Config loaded: trading_level={MAX_TRADING_LEVEL}, "
    f"live_trading={ENABLE_LIVE_TRADING}, "
    f"human_confirm={REQUIRE_HUMAN_CONFIRMATION}"
)