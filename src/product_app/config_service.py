"""产品配置服务

从 .env 文件和环境变量加载配置，提供验证、脱敏、持久化能力。
用户配置变更保存到 runtime/user_config.json（不修改 .env）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel, Field

# ============================================================
# 常量定义
# ============================================================

# 需要脱敏的关键字
SENSITIVE_KEYWORDS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "COOKIE", "ACCOUNT", "BROKER")

# 交易模式常量
LEVEL_0 = "LEVEL_0"
LEVEL_1_SIGNAL_ONLY = "LEVEL_1_SIGNAL_ONLY"
LEVEL_2_HUMAN_CONFIRM = "LEVEL_2_HUMAN_CONFIRM"
LEVEL_3_AUTO = "LEVEL_3_AUTO"

VALID_TRADING_LEVELS = {LEVEL_0, LEVEL_1_SIGNAL_ONLY, LEVEL_2_HUMAN_CONFIRM, LEVEL_3_AUTO}

# 安全配置分组：这些分组允许用户在运行时修改
SAFE_CONFIG_GROUPS = {
    "trading_mode": [
        "MAX_TRADING_LEVEL",
        "ENABLE_LIVE_TRADING",
        "REQUIRE_HUMAN_CONFIRMATION",
    ],
    "data_source": [
        "DEFAULT_DATA_PROVIDER",
        "EASTMONEY_ENABLED",
        "SINA_QUOTE_ENABLED",
    ],
    "stock_pool": [],
    "risk_limits": [
        "MAX_SINGLE_STOCK_POSITION",
        "MAX_SECTOR_POSITION",
        "MIN_CASH_RATIO",
        "SINGLE_STOCK_LOSS_WARN",
        "SINGLE_STOCK_LOSS_STOP",
        "DAILY_LOSS_WARN",
        "DAILY_LOSS_STOP",
        "MAX_DRAWDOWN_DEFENSE",
        "MAX_DRAWDOWN_HALT",
    ],
    "backtest": [
        "BACKTEST_COMMISSION_RATE",
        "BACKTEST_STAMP_DUTY",
        "BACKTEST_SLIPPAGE",
    ],
    "ui_runtime": [
        "LOG_LEVEL",
    ],
}

# 所有允许用户修改的键
SAFE_CONFIG_KEYS: set[str] = set()
for _keys in SAFE_CONFIG_GROUPS.values():
    SAFE_CONFIG_KEYS.update(_keys)

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_RUNTIME_DIR = _PROJECT_ROOT / "runtime"
_USER_CONFIG_PATH = _RUNTIME_DIR / "user_config.json"
_ENV_FILE = _PROJECT_ROOT / ".env"
_ENV_EXAMPLE = _PROJECT_ROOT / ".env.example"


# ============================================================
# Pydantic 验证模型
# ============================================================

class ConfigValidationResult(BaseModel):
    """配置验证结果"""
    valid: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TradingModeUpgradeCheck(BaseModel):
    """交易模式升级检查结果"""
    allowed: bool
    requires_confirmation: bool = False
    message: str = ""
    enforced_broker: Optional[str] = None


# ============================================================
# 脱敏工具
# ============================================================

def mask_value(key: str, value: Any) -> Any:
    """对敏感键值进行脱敏处理

    键名包含 TOKEN/KEY/SECRET/PASSWORD/COOKIE/ACCOUNT/BROKER 的值将被掩码。
    非字符串值原样返回。
    """
    if not isinstance(value, str) or not value:
        return value

    key_upper = key.upper()
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in key_upper:
            # 保留前2位和后2位，中间用 **** 替代
            if len(value) <= 4:
                return "****"
            return f"{value[:2]}****{value[-2:]}"

    return value


def mask_config(config: dict[str, Any]) -> dict[str, Any]:
    """对整个配置字典进行脱敏"""
    return {k: mask_value(k, v) for k, v in config.items()}


# ============================================================
# 配置服务主类
# ============================================================

class ConfigService:
    """产品配置服务

    职责：
    - 从 .env 和环境变量加载配置
    - 验证配置值（交易模式、风控参数等）
    - 脱敏敏感键值
    - 持久化用户配置到 runtime/user_config.json
    - 阻止不安全的配置变更
    """

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._loaded = False

    # ----------------------------------------------------------
    # 加载配置
    # ----------------------------------------------------------

    def load_config(self) -> dict[str, Any]:
        """加载配置：.env -> 环境变量 -> user_config.json 覆盖

        返回完整的配置字典。
        """
        # 1. 加载 .env 文件
        if _ENV_FILE.exists():
            load_dotenv(_ENV_FILE, override=False)
            logger.info("已加载 .env 配置文件")
        elif _ENV_EXAMPLE.exists():
            load_dotenv(_ENV_EXAMPLE, override=False)
            logger.warning("未找到 .env，使用 .env.example 默认值")
        else:
            logger.warning("未找到 .env 或 .env.example，仅使用环境变量")

        # 2. 从环境变量读取所有已知配置键
        self._config = self._read_env_defaults()

        # 3. 用 user_config.json 覆盖（用户运行时修改的值优先）
        user_overrides = self._load_user_config()
        if user_overrides:
            for k, v in user_overrides.items():
                if k in self._config:
                    self._config[k] = v
            logger.info(f"已加载用户配置覆盖: {len(user_overrides)} 项")

        # 4. 启动时验证
        result = self.validate_config()
        if not result.valid:
            for err in result.errors:
                logger.error(f"配置验证错误: {err}")
        for warn in result.warnings:
            logger.warning(f"配置验证警告: {warn}")

        self._loaded = True
        return dict(self._config)

    def _read_env_defaults(self) -> dict[str, Any]:
        """从环境变量读取所有已知配置键及其默认值"""
        defaults: dict[str, Any] = {
            # 交易模式
            "MAX_TRADING_LEVEL": "LEVEL_1_SIGNAL_ONLY",
            "ENABLE_LIVE_TRADING": False,
            "REQUIRE_HUMAN_CONFIRMATION": True,
            # 数据源
            "TUSHARE_TOKEN": "",
            "EASTMONEY_ENABLED": True,
            "SINA_QUOTE_ENABLED": True,
            "DEFAULT_DATA_PROVIDER": "akshare",
            # 数据库
            "DATABASE_URL": "sqlite:///data/quant_trading.db",
            # 风控参数
            "MAX_SINGLE_STOCK_POSITION": 0.15,
            "MAX_SECTOR_POSITION": 0.60,
            "MIN_CASH_RATIO": 0.20,
            "SINGLE_STOCK_LOSS_WARN": -0.05,
            "SINGLE_STOCK_LOSS_STOP": -0.08,
            "DAILY_LOSS_WARN": -0.02,
            "DAILY_LOSS_STOP": -0.03,
            "MAX_DRAWDOWN_DEFENSE": -0.08,
            "MAX_DRAWDOWN_HALT": -0.12,
            # 回测参数
            "BACKTEST_COMMISSION_RATE": 0.0003,
            "BACKTEST_STAMP_DUTY": 0.001,
            "BACKTEST_SLIPPAGE": 0.001,
            # 券商
            "BROKER_ADAPTER": "paper",
            "BROKER_API_KEY": "",
            "BROKER_API_SECRET": "",
            "BROKER_ACCOUNT": "",
            # 日志
            "LOG_LEVEL": "INFO",
            "LOG_FILE": "logs/quant_trading.log",
            # 通知
            "NOTIFY_EMAIL": "",
            "NOTIFY_WEBHOOK_URL": "",
        }

        result: dict[str, Any] = {}
        for key, default in defaults.items():
            env_val = os.getenv(key)
            if env_val is not None:
                # 类型转换
                if isinstance(default, bool):
                    result[key] = env_val.lower() in ("true", "1", "yes", "on")
                elif isinstance(default, float):
                    try:
                        result[key] = float(env_val)
                    except ValueError:
                        result[key] = default
                elif isinstance(default, int):
                    try:
                        result[key] = int(env_val)
                    except ValueError:
                        result[key] = default
                else:
                    result[key] = env_val.strip()
            else:
                result[key] = default

        return result

    def _load_user_config(self) -> dict[str, Any]:
        """从 runtime/user_config.json 加载用户覆盖配置"""
        if not _USER_CONFIG_PATH.exists():
            return {}
        try:
            with open(_USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("user_config.json 格式错误，忽略")
                return {}
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取 user_config.json 失败: {e}")
            return {}

    def _save_user_config(self) -> bool:
        """将当前用户覆盖配置保存到 runtime/user_config.json"""
        try:
            _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            # 只保存用户修改过的键（在 SAFE_CONFIG_KEYS 中的键）
            user_overrides = {
                k: v for k, v in self._config.items()
                if k in SAFE_CONFIG_KEYS
            }
            with open(_USER_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(user_overrides, f, indent=2, ensure_ascii=False)
            logger.info(f"用户配置已保存到 {_USER_CONFIG_PATH}")
            return True
        except OSError as e:
            logger.error(f"保存用户配置失败: {e}")
            return False

    # ----------------------------------------------------------
    # 获取配置
    # ----------------------------------------------------------

    def get_config(self, masked: bool = True) -> dict[str, Any]:
        """获取当前配置

        参数:
            masked: 是否对敏感值进行脱敏，默认 True
        """
        if not self._loaded:
            self.load_config()

        config = dict(self._config)
        if masked:
            config = mask_config(config)
        return config

    def get(self, key: str, default: Any = None) -> Any:
        """获取单个配置值"""
        if not self._loaded:
            self.load_config()
        return self._config.get(key, default)

    # ----------------------------------------------------------
    # 更新配置
    # ----------------------------------------------------------

    def update_config(self, key: str, value: Any) -> dict[str, Any]:
        """更新单个配置项

        规则：
        1. 只允许修改 SAFE_CONFIG_KEYS 中的键
        2. 修改前先验证，无效配置不会被持久化
        3. LEVEL_3_AUTO 在 Demo V1 中被阻止
        4. 升级到 LEVEL_2_HUMAN_CONFIRM 需要确认且强制 BROKER_ADAPTER=paper

        返回:
            dict 包含 success, message, requires_confirmation 等信息
        """
        if not self._loaded:
            self.load_config()

        # 检查键是否允许修改
        if key not in SAFE_CONFIG_KEYS:
            msg = f"配置键 '{key}' 不在允许修改的安全列表中"
            logger.warning(msg)
            return {"success": False, "message": msg, "requires_confirmation": False}

        # 类型转换
        coerced_value = self._coerce_value(key, value)
        if coerced_value is None and value is not None:
            msg = f"配置值类型转换失败: {key}={value}"
            logger.warning(msg)
            return {"success": False, "message": msg, "requires_confirmation": False}

        # 交易模式升级检查
        if key == "MAX_TRADING_LEVEL":
            upgrade_check = self._check_trading_mode_upgrade(coerced_value)
            if not upgrade_check.allowed:
                return {
                    "success": False,
                    "message": upgrade_check.message,
                    "requires_confirmation": upgrade_check.requires_confirmation,
                }
            if upgrade_check.requires_confirmation:
                # 需要确认的模式升级：先记录待确认状态，不立即保存
                return {
                    "success": False,
                    "message": upgrade_check.message,
                    "requires_confirmation": True,
                    "pending_key": key,
                    "pending_value": coerced_value,
                    "enforced_broker": upgrade_check.enforced_broker,
                }

        # 临时应用值并验证
        old_value = self._config.get(key)
        self._config[key] = coerced_value

        validation = self.validate_config()
        if not validation.valid:
            # 验证失败，回滚
            self._config[key] = old_value
            msg = f"配置验证失败，未保存: {'; '.join(validation.errors)}"
            logger.warning(msg)
            return {"success": False, "message": msg, "requires_confirmation": False}

        # 验证通过，持久化
        saved = self._save_user_config()
        if not saved:
            # 持久化失败但运行时已生效，发出警告
            logger.warning("配置已在运行时生效但持久化失败，重启后将恢复原值")

        return {
            "success": True,
            "message": f"配置已更新: {key}",
            "requires_confirmation": False,
        }

    def confirm_upgrade(self, key: str, value: Any) -> dict[str, Any]:
        """确认交易模式升级

        用户确认后执行升级，并强制设置 BROKER_ADAPTER=paper。
        """
        if key != "MAX_TRADING_LEVEL":
            return {"success": False, "message": "仅交易模式升级需要确认"}

        if value == LEVEL_2_HUMAN_CONFIRM:
            self._config["MAX_TRADING_LEVEL"] = LEVEL_2_HUMAN_CONFIRM
            self._config["BROKER_ADAPTER"] = "paper"
            self._save_user_config()
            logger.info("交易模式已升级为 LEVEL_2_HUMAN_CONFIRM，BROKER_ADAPTER 强制为 paper")
            return {
                "success": True,
                "message": "已升级为 LEVEL_2_HUMAN_CONFIRM，券商适配器已设为 paper",
            }

        return {"success": False, "message": f"不支持的升级目标: {value}"}

    def _coerce_value(self, key: str, value: Any) -> Any:
        """根据配置键的默认类型强制转换值"""
        defaults = self._read_env_defaults()
        default = defaults.get(key)
        if default is None:
            return value

        try:
            if isinstance(default, bool):
                if isinstance(value, bool):
                    return value
                return str(value).lower() in ("true", "1", "yes", "on")
            elif isinstance(default, float):
                return float(value)
            elif isinstance(default, int):
                return int(value)
            else:
                return str(value).strip()
        except (ValueError, TypeError):
            return None

    def _check_trading_mode_upgrade(self, new_level: str) -> TradingModeUpgradeCheck:
        """检查交易模式升级是否允许

        规则：
        - LEVEL_3_AUTO 在 Demo V1 中被阻止
        - 升级到 LEVEL_2_HUMAN_CONFIRM 需要确认且强制 BROKER_ADAPTER=paper
        """
        if new_level not in VALID_TRADING_LEVELS:
            return TradingModeUpgradeCheck(
                allowed=False,
                message=f"无效的交易模式: {new_level}",
            )

        if new_level == LEVEL_3_AUTO:
            return TradingModeUpgradeCheck(
                allowed=False,
                message="LEVEL_3_AUTO（自动交易）在 Demo V1 中不可用，请联系管理员开通",
            )

        if new_level == LEVEL_2_HUMAN_CONFIRM:
            return TradingModeUpgradeCheck(
                allowed=True,
                requires_confirmation=True,
                message="升级到 LEVEL_2_HUMAN_CONFIRM 需要确认，确认后 BROKER_ADAPTER 将强制为 paper",
                enforced_broker="paper",
            )

        return TradingModeUpgradeCheck(allowed=True, message="交易模式变更允许")

    # ----------------------------------------------------------
    # 验证配置
    # ----------------------------------------------------------

    def validate_config(self) -> ConfigValidationResult:
        """验证当前配置的有效性

        检查项：
        - 交易模式是否合法
        - 风控参数是否在合理范围
        - 不安全的组合是否被标记
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 交易模式验证
        trading_level = self._config.get("MAX_TRADING_LEVEL", "")
        if trading_level not in VALID_TRADING_LEVELS:
            errors.append(f"无效的交易模式: {trading_level}")

        if trading_level == LEVEL_3_AUTO:
            errors.append("LEVEL_3_AUTO 在 Demo V1 中不可用")

        # 风控参数范围验证
        max_single = self._config.get("MAX_SINGLE_STOCK_POSITION", 0)
        if not (0 < max_single <= 1):
            errors.append(f"MAX_SINGLE_STOCK_POSITION 超出范围 (0,1]: {max_single}")

        max_sector = self._config.get("MAX_SECTOR_POSITION", 0)
        if not (0 < max_sector <= 1):
            errors.append(f"MAX_SECTOR_POSITION 超出范围 (0,1]: {max_sector}")

        min_cash = self._config.get("MIN_CASH_RATIO", 0)
        if not (0 <= min_cash <= 1):
            errors.append(f"MIN_CASH_RATIO 超出范围 [0,1]: {min_cash}")

        # 止损参数验证（应为负值）
        for loss_key in ("SINGLE_STOCK_LOSS_WARN", "SINGLE_STOCK_LOSS_STOP",
                         "DAILY_LOSS_WARN", "DAILY_LOSS_STOP",
                         "MAX_DRAWDOWN_DEFENSE", "MAX_DRAWDOWN_HALT"):
            val = self._config.get(loss_key, 0)
            if val >= 0:
                errors.append(f"{loss_key} 应为负值: {val}")

        # 止损层级合理性
        warn_stop = self._config.get("SINGLE_STOCK_LOSS_STOP", 0)
        warn_warn = self._config.get("SINGLE_STOCK_LOSS_WARN", 0)
        if warn_stop >= warn_warn:
            errors.append(f"SINGLE_STOCK_LOSS_STOP({warn_stop}) 应小于 LOSS_WARN({warn_warn})")

        daily_stop = self._config.get("DAILY_LOSS_STOP", 0)
        daily_warn = self._config.get("DAILY_LOSS_WARN", 0)
        if daily_stop >= daily_warn:
            errors.append(f"DAILY_LOSS_STOP({daily_stop}) 应小于 DAILY_LOSS_WARN({daily_warn})")

        drawdown_defense = self._config.get("MAX_DRAWDOWN_DEFENSE", 0)
        drawdown_halt = self._config.get("MAX_DRAWDOWN_HALT", 0)
        if drawdown_halt >= drawdown_defense:
            errors.append(f"MAX_DRAWDOWN_HALT({drawdown_halt}) 应小于 DEFENSE({drawdown_defense})")

        # 回测参数验证
        for bt_key in ("BACKTEST_COMMISSION_RATE", "BACKTEST_STAMP_DUTY", "BACKTEST_SLIPPAGE"):
            val = self._config.get(bt_key, 0)
            if val < 0:
                errors.append(f"{bt_key} 不应为负值: {val}")

        # 安全组合警告
        enable_live = self._config.get("ENABLE_LIVE_TRADING", False)
        require_confirm = self._config.get("REQUIRE_HUMAN_CONFIRMATION", True)

        if enable_live and trading_level == LEVEL_3_AUTO:
            warnings.append("实盘交易 + 自动交易模式：请确保已满足所有安全前提条件")

        if enable_live and not require_confirm:
            warnings.append("实盘交易已启用但未要求人工确认，存在安全风险")

        if trading_level == LEVEL_2_HUMAN_CONFIRM:
            broker = self._config.get("BROKER_ADAPTER", "paper")
            if broker != "paper":
                warnings.append("LEVEL_2_HUMAN_CONFIRM 模式下建议使用 paper 券商适配器")

        return ConfigValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ----------------------------------------------------------
    # 恢复默认
    # ----------------------------------------------------------

    def restore_defaults(self) -> dict[str, Any]:
        """恢复所有用户配置为默认值

        删除 runtime/user_config.json 并重新加载默认配置。
        """
        try:
            if _USER_CONFIG_PATH.exists():
                _USER_CONFIG_PATH.unlink()
                logger.info("已删除用户配置文件，将恢复默认值")
        except OSError as e:
            logger.error(f"删除用户配置文件失败: {e}")

        self._config = self._read_env_defaults()
        self._loaded = True

        validation = self.validate_config()
        if not validation.valid:
            for err in validation.errors:
                logger.error(f"恢复默认后验证错误: {err}")

        return self.get_config(masked=True)


# ============================================================
# 模块级单例
# ============================================================

_config_service: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    """获取全局配置服务单例"""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
        _config_service.load_config()
    return _config_service
