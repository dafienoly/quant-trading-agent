"""执行服务 (EXECUTION_POLICY 3)

完整订单生命周期管理：
信号触发 → 生成订单草稿 → 风控检查 → 订单检查 → 人工确认 → 发送交易指令 → 记录成交

核心约束：
- LEVEL_1_SIGNAL_ONLY 模式下不生成订单
- LEVEL_2_HUMAN_CONFIRM 模式下必须人工确认
- 风控不通过不能下单
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Callable

from loguru import logger

from src.config.settings import ENABLE_LIVE_TRADING, MAX_TRADING_LEVEL
from src.execution_engine.broker_adapter import BrokerAdapter, PaperBroker
from src.execution_engine.order_checker import OrderChecker
from src.execution_engine.trade_recorder import TradeRecorder
from src.models.schemas import AccountInfo, Order, OrderDraft, Position, Signal, TradeRecord
from src.risk_engine.models import RiskDecision, RiskLevel
from src.risk_engine.runtime import RuntimeRiskEngine


class ExecutionService:
    """执行服务 (EXECUTION_POLICY 3)

    管理订单从草稿到成交的完整生命周期。
    """

    def __init__(
        self,
        risk_engine: RuntimeRiskEngine,
        broker: BrokerAdapter | None = None,
        order_checker: OrderChecker | None = None,
        trading_mode: str = MAX_TRADING_LEVEL,
        trade_recorder: TradeRecorder | None = None,
    ):
        self._risk_engine = risk_engine
        self._broker = broker or PaperBroker()
        self._order_checker = order_checker or OrderChecker()
        self._trading_mode = trading_mode
        self._pending_orders: dict[str, Order] = {}  # 待确认订单
        self._all_orders: dict[str, Order] = {}  # 所有订单
        self._on_trade_callback: Callable[[TradeRecord], None] | None = None

        # M2 fix: 自动集成 TradeRecorder
        self._trade_recorder = trade_recorder or TradeRecorder()
        self._on_trade_callback = self._trade_recorder.record

    @property
    def trading_mode(self) -> str:
        return self._trading_mode

    @property
    def pending_orders(self) -> dict[str, Order]:
        return self._pending_orders.copy()

    @property
    def all_orders(self) -> dict[str, Order]:
        return self._all_orders.copy()

    @property
    def trade_recorder(self) -> TradeRecorder:
        return self._trade_recorder

    def set_on_trade_callback(self, callback: Callable[[TradeRecord], None]):
        """设置成交回调"""
        self._on_trade_callback = callback

    # M3 fix: 公共方法封装
    def query_account(self) -> AccountInfo:
        """查询账户信息"""
        return self._broker.query_account()

    def query_positions(self) -> list[Position]:
        """查询持仓"""
        return self._broker.query_positions()

    def signal_to_draft(self, signal: Signal, account: AccountInfo) -> OrderDraft | None:
        """将信号转换为订单草稿 (EXECUTION_POLICY 4)

        仅在 LEVEL_2 及以上模式生成订单草稿。
        LEVEL_1 模式下不生成任何订单对象 (EXECUTION_POLICY 10.2)。
        """
        if self._trading_mode not in ("LEVEL_2_HUMAN_CONFIRM", "LEVEL_3_AUTO"):
            logger.info(f"ExecutionService: 当前模式 {self._trading_mode}，不生成订单")
            return None

        if signal.signal_type not in ("BUY", "SELL"):
            return None

        # 确定市场
        code = signal.symbol.split(".")[0] if "." in signal.symbol else signal.symbol
        if len(code) == 5 and code.isdigit():
            market = "HK"
        elif code.startswith(("6",)):
            market = "SH"
        else:
            market = "SZ"

        # 计算数量
        from src.execution_engine.order_checker import calculate_buy_quantity
        if signal.signal_type == "BUY":
            quantity = calculate_buy_quantity(
                account.available_cash, signal.price_trigger, signal.position_pct
            )
            if quantity < 100:
                logger.warning(f"ExecutionService: 买入数量不足100股，跳过 {signal.symbol}")
                return None
        else:
            # 卖出：从持仓获取可卖数量 (EXECUTION_POLICY 4.2)
            positions = self._broker.query_positions()
            pos = next((p for p in positions if p.symbol == signal.symbol), None)
            if pos is None:
                logger.warning(f"ExecutionService: 无持仓可卖 {signal.symbol}")
                return None
            quantity = pos.available_quantity

        side = "BUY" if signal.signal_type == "BUY" else "SELL"
        price_type = "LIMIT"
        limit_price = signal.price_trigger

        # 止损卖出可使用 MARKET 价 (EXECUTION_POLICY 4.2)
        if side == "SELL" and "STOP_LOSS" in signal.sub_type:
            price_type = "MARKET"

        draft = OrderDraft(
            symbol=signal.symbol,
            market=market,
            side=side,
            price_type=price_type,
            limit_price=limit_price,
            quantity=quantity,
            strategy_name=signal.strategy,
            signal_id=signal.signal_id,
            stock_name=signal.stock_name,
            sector=signal.sector,
            stop_loss_price=signal.stop_loss_price,
            take_profit_price=signal.take_profit_price,
            position_pct=signal.position_pct,
            risk_note=signal.risk_note,
        )
        return draft

    def create_order(self, draft: OrderDraft, risk_decision: RiskDecision, now: datetime | None = None) -> Order | None:
        """从草稿创建订单 (EXECUTION_POLICY 3)

        必须先通过风控检查。
        """
        # 风控检查
        if not risk_decision.can_generate_signal:
            logger.warning(f"ExecutionService: 风控未通过，不能创建订单 - {risk_decision.messages}")
            return None

        if self._trading_mode not in ("LEVEL_2_HUMAN_CONFIRM", "LEVEL_3_AUTO"):
            logger.warning("ExecutionService: 当前模式不允许创建订单")
            return None

        # 订单检查
        account = self._broker.query_account()
        positions = self._broker.query_positions()
        check_result = self._order_checker.check_order(draft, account, positions, now=now)

        if not check_result.passed:
            logger.warning(f"ExecutionService: 订单检查未通过 - {check_result.reason}")
            return None

        # 调整数量
        quantity = check_result.adjusted_quantity or draft.quantity

        # 生成订单ID (DATA_CONTRACTS 5)
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"

        order = Order(
            order_id=order_id,
            symbol=draft.symbol,
            market=draft.market,
            side=draft.side,
            price_type=draft.price_type,
            limit_price=draft.limit_price,
            quantity=quantity,
            strategy_name=draft.strategy_name,
            signal_id=draft.signal_id,
            risk_check_id=f"RISK_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
            stock_name=draft.stock_name,
            sector=draft.sector,
            stop_loss_price=draft.stop_loss_price,
            take_profit_price=draft.take_profit_price,
            position_pct=draft.position_pct,
            risk_note=draft.risk_note,
            status="RISK_CHECKED",
        )

        self._all_orders[order_id] = order

        # LEVEL_2 需要人工确认
        if self._trading_mode == "LEVEL_2_HUMAN_CONFIRM":
            self._pending_orders[order_id] = order
            order.status = "RISK_CHECKED"
            logger.info(f"ExecutionService: 订单已创建，等待人工确认 {order_id}")
        elif self._trading_mode == "LEVEL_3_AUTO":
            # LEVEL_3 自动执行
            self._execute_order(order)

        return order

    def confirm_order(self, order_id: str, confirmed_by: str = "user") -> Order | None:
        """人工确认订单 (EXECUTION_POLICY 5)

        禁止提供「全部确认」「一键确认」功能，必须逐笔操作。
        """
        if order_id not in self._pending_orders:
            logger.warning(f"ExecutionService: 订单不在待确认队列 {order_id}")
            return None

        order = self._pending_orders.pop(order_id)
        order.status = "CONFIRMED"
        order.confirmed_by = confirmed_by
        order.confirmed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"ExecutionService: 订单已确认 {order_id} by {confirmed_by}")
        self._execute_order(order)
        return order

    def reject_order(self, order_id: str, reason: str = "") -> Order | None:
        """拒绝订单"""
        if order_id not in self._pending_orders:
            logger.warning(f"ExecutionService: 订单不在待确认队列 {order_id}")
            return None

        order = self._pending_orders.pop(order_id)
        order.status = "CANCELLED"
        order.reject_reason = reason or "用户拒绝"
        order.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"ExecutionService: 订单已拒绝 {order_id} - {order.reject_reason}")
        return order

    def modify_order(self, order_id: str, new_price: float | None = None, new_quantity: int | None = None) -> Order | None:
        """修改订单价格/数量 (EXECUTION_POLICY 5, L3 fix)

        仅允许修改待确认订单的价格和数量。
        """
        if order_id not in self._pending_orders:
            logger.warning(f"ExecutionService: 订单不在待确认队列 {order_id}")
            return None

        order = self._pending_orders[order_id]
        if new_price is not None and new_price > 0:
            order.limit_price = new_price
        if new_quantity is not None and new_quantity > 0:
            order.quantity = new_quantity
        order.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"ExecutionService: 订单已修改 {order_id} price={order.limit_price} qty={order.quantity}")
        return order

    def cancel_expired_orders(self) -> list[Order]:
        """取消当日未确认的过期订单 (EXECUTION_POLICY 5, L4 fix)

        收盘后未确认的订单自动取消。
        """
        now = datetime.now()
        from src.execution_engine.order_checker import A_SHARE_AFTERNOON_CLOSE
        if now.time() <= A_SHARE_AFTERNOON_CLOSE:
            return []  # 交易时段内不取消

        expired = []
        for order_id in list(self._pending_orders.keys()):
            order = self._pending_orders[order_id]
            order_date = order.created_at[:10] if order.created_at else ""
            today = now.strftime("%Y-%m-%d")
            if order_date < today or (order_date == today and now.time() > A_SHARE_AFTERNOON_CLOSE):
                order.status = "CANCELLED"
                order.reject_reason = "收盘后未确认，自动取消"
                order.updated_at = now.strftime("%Y-%m-%d %H:%M:%S")
                del self._pending_orders[order_id]
                expired.append(order)
                logger.info(f"ExecutionService: 过期订单已取消 {order_id}")

        return expired

    def _execute_order(self, order: Order):
        """执行订单"""
        order.status = "SENT"
        order.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result = self._broker.submit_order(order)

        if result.success:
            order.status = "FILLED"
            order.fill_price = result.fill_price
            order.fill_quantity = result.fill_quantity
            order.fill_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"ExecutionService: 订单成交 {order.order_id}")

            # M2 fix: 自动记录成交
            if self._on_trade_callback:
                try:
                    self._trade_recorder.record_from_order(order)
                except Exception as e:
                    logger.error(f"ExecutionService: 成交记录失败 {e}")
        else:
            order.status = "REJECTED"
            order.reject_reason = result.message
            logger.warning(f"ExecutionService: 订单被拒 {order.order_id} - {result.message}")

        order.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def cancel_order(self, order_id: str) -> Order | None:
        """撤销订单"""
        if order_id in self._pending_orders:
            order = self._pending_orders.pop(order_id)
            order.status = "CANCELLED"
            order.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._broker.cancel_order(order_id)
            logger.info(f"ExecutionService: 订单已撤销 {order_id}")
            return order
        return None
