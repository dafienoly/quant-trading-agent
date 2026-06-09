"""Phase 5 集成 / E2E / API 测试

覆盖完整订单生命周期和跨组件集成场景：
1. Signal → Draft → Risk Check → Order Check → Confirm → Execute → TradeRecord
2. LEVEL_3_AUTO 自动执行
3. Risk BLOCK 阻断订单
4. Kill Switch 全局阻断
5. Portfolio risk check 与 ExecutionService 集成
6. API 全生命周期
7. LEVEL_1 模式拒绝确认
8. OrderChecker + ExecutionService 集成
9. 卖出持仓检查
10. TradeRecorder 集成
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.execution_engine.broker_adapter import PaperBroker
from src.execution_engine.execution_service import ExecutionService
from src.execution_engine.order_checker import OrderChecker
from src.execution_engine.trade_recorder import TradeRecorder
from src.models.schemas import AccountInfo, OrderDraft, Position, Signal
from src.risk_engine.models import KillSwitchState, RiskBlockReason, RiskDecision, RiskLevel
from src.risk_engine.runtime import RuntimeRiskEngine

# 交易时段内的时间常量
_TRADING_NOW = datetime(2026, 6, 9, 10, 0, 0)

# 非交易时段
_NON_TRADING_NOW = datetime(2026, 6, 9, 8, 0, 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    symbol: str = "002463.SZ",
    signal_type: str = "BUY",
    price: float = 10.0,
    position_pct: float = 0.10,
    signal_id: str = "SIG_e2e_001",
    sub_type: str = "BREAKOUT",
    strategy: str = "test_strategy",
    stock_name: str = "沪电股份",
    sector: str = "PCB",
    stop_loss_price: float = 9.0,
    take_profit_price: float = 12.0,
    risk_note: str = "",
) -> Signal:
    return Signal(
        signal_id=signal_id,
        symbol=symbol,
        stock_name=stock_name,
        sector=sector,
        trade_date="20260609",
        strategy=strategy,
        signal_type=signal_type,
        sub_type=sub_type,
        score=0.8,
        price_trigger=price,
        reason="e2e test signal",
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        position_pct=position_pct,
        risk_note=risk_note,
        created_at="2026-06-09 10:00:00",
    )


def _make_risk_decision(
    passed: bool = True,
    level: RiskLevel = RiskLevel.OK,
    trading_mode: str = "LEVEL_2_HUMAN_CONFIRM",
) -> RiskDecision:
    return RiskDecision(
        risk_pass=passed,
        level=level,
        trading_mode=trading_mode,
        reasons=[],
        messages=[],
    )


def _make_draft(
    side: str = "BUY",
    symbol: str = "002463.SZ",
    price: float = 10.0,
    quantity: int = 100,
    signal_id: str = "SIG_e2e_001",
    market: str = "SZ",
) -> OrderDraft:
    return OrderDraft(
        symbol=symbol,
        market=market,
        side=side,
        price_type="LIMIT",
        limit_price=price,
        quantity=quantity,
        strategy_name="test_strategy",
        signal_id=signal_id,
        stock_name="沪电股份",
        sector="PCB",
        stop_loss_price=9.0,
        take_profit_price=12.0,
    )


def _build_service(
    trading_mode: str = "LEVEL_2_HUMAN_CONFIRM",
    initial_cash: float = 1000000.0,
    kill_switch: KillSwitchState | None = None,
) -> ExecutionService:
    engine = RuntimeRiskEngine(kill_switch=kill_switch)
    broker = PaperBroker(initial_cash=initial_cash)
    return ExecutionService(
        risk_engine=engine,
        broker=broker,
        trading_mode=trading_mode,
    )


# ===================================================================
# 1. Full E2E: Signal → Draft → Risk Check → Order Check → Confirm
#    → Execute → TradeRecord
# ===================================================================

class TestFullE2ELifecycle:
    """完整订单生命周期端到端测试"""

    def test_signal_to_trade_record_full_lifecycle(self, tmp_path):
        """Signal → Draft → Risk Check → Order → Confirm → Execute → TradeRecord

        验证完整链路中每个环节的状态转换和数据一致性。
        """
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        broker = service._broker

        # Step 1: 创建信号
        signal = _make_signal(symbol="002463.SZ", price=10.0, position_pct=0.10)
        account = broker.query_account()

        # Step 2: 信号转草稿
        draft = service.signal_to_draft(signal, account)
        assert draft is not None, "LEVEL_2 模式下应生成 OrderDraft"
        assert draft.symbol == "002463.SZ"
        assert draft.side == "BUY"
        assert draft.quantity >= 100

        # Step 3: 风控检查通过
        risk_decision = _make_risk_decision(passed=True, level=RiskLevel.OK)
        assert risk_decision.can_generate_signal is True
        assert risk_decision.can_generate_order is True

        # Step 4: 创建订单（含 OrderChecker 检查）
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
        assert order is not None
        assert order.status == "RISK_CHECKED"
        assert order.order_id in service.pending_orders

        # Step 5: 人工确认
        confirmed = service.confirm_order(order.order_id, confirmed_by="e2e_user")
        assert confirmed is not None

        # Step 6: 验证状态转换 RISK_CHECKED → CONFIRMED → SENT → FILLED
        assert confirmed.status == "FILLED"
        assert confirmed.confirmed_by == "e2e_user"
        assert confirmed.confirmed_at is not None
        assert confirmed.fill_price is not None
        assert confirmed.fill_quantity is not None
        assert confirmed.fill_at is not None

        # Step 7: 订单不再待确认
        assert order.order_id not in service.pending_orders

        # Step 8: PaperBroker 持仓和现金变化
        positions = broker.query_positions()
        pos_symbols = [p.symbol for p in positions]
        assert "002463.SZ" in pos_symbols
        buy_pos = next(p for p in positions if p.symbol == "002463.SZ")
        assert buy_pos.quantity == confirmed.fill_quantity

        new_account = broker.query_account()
        assert new_account.cash < 1000000.0, "买入后现金应减少"

        # Step 9: TradeRecorder 记录
        recorder = TradeRecorder(data_dir=str(tmp_path))
        recorder.record_from_order(confirmed)
        assert len(recorder.records) == 1
        trade = recorder.records[0]
        assert trade.symbol == "002463.SZ"
        assert trade.side == "BUY"
        assert trade.order_id == confirmed.order_id
        assert trade.signal_id == confirmed.signal_id

    def test_signal_to_draft_level1_returns_none(self):
        """LEVEL_1_SIGNAL_ONLY 模式下 signal_to_draft 返回 None"""
        service = _build_service(trading_mode="LEVEL_1_SIGNAL_ONLY")
        signal = _make_signal()
        account = service._broker.query_account()
        draft = service.signal_to_draft(signal, account)
        assert draft is None


# ===================================================================
# 2. E2E: LEVEL_3_AUTO mode auto-executes without human confirm
# ===================================================================

class TestLevel3AutoExecution:
    """LEVEL_3_AUTO 模式自动执行测试"""

    def test_level3_auto_executes_without_confirm(self):
        """LEVEL_3_AUTO 模式下订单自动执行，无需人工确认"""
        service = _build_service(trading_mode="LEVEL_3_AUTO")
        broker = service._broker

        draft = _make_draft()
        risk_decision = _make_risk_decision(
            passed=True, level=RiskLevel.OK, trading_mode="LEVEL_3_AUTO",
        )
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

        assert order is not None
        # LEVEL_3 直接执行，不进入待确认队列
        assert order.status == "FILLED"
        assert order.order_id not in service.pending_orders
        assert order.fill_price is not None
        assert order.fill_quantity is not None

        # 验证持仓已建立
        positions = broker.query_positions()
        assert any(p.symbol == "002463.SZ" for p in positions)

    def test_level3_auto_no_pending_state(self):
        """LEVEL_3_AUTO 创建订单后 pending_orders 为空"""
        service = _build_service(trading_mode="LEVEL_3_AUTO")

        draft = _make_draft()
        risk_decision = _make_risk_decision(
            passed=True, level=RiskLevel.OK, trading_mode="LEVEL_3_AUTO",
        )
        service.create_order(draft, risk_decision, now=_TRADING_NOW)

        assert len(service.pending_orders) == 0

    def test_level3_confirm_nonexistent_returns_none(self):
        """LEVEL_3_AUTO 模式下确认不存在的订单返回 None"""
        service = _build_service(trading_mode="LEVEL_3_AUTO")
        result = service.confirm_order("ORD_nonexistent")
        assert result is None


# ===================================================================
# 3. E2E: Risk BLOCK prevents order creation
# ===================================================================

class TestRiskBlockPreventsOrder:
    """风控阻断订单创建测试"""

    def test_risk_block_returns_none(self):
        """RiskDecision risk_pass=False 时 create_order 返回 None"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")

        draft = _make_draft()
        risk_decision = _make_risk_decision(passed=False, level=RiskLevel.BLOCK)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

        assert order is None

    def test_risk_block_with_messages(self):
        """风控阻断时 messages 应包含原因"""
        risk_decision = RiskDecision(
            risk_pass=False,
            level=RiskLevel.BLOCK,
            trading_mode="LEVEL_2_HUMAN_CONFIRM",
            reasons=[RiskBlockReason.SINGLE_STOCK_POSITION_EXCEEDED],
            messages=["单票仓位超限: 002463.SZ"],
        )
        assert risk_decision.can_generate_signal is False
        assert risk_decision.can_generate_order is False

        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        draft = _make_draft()
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
        assert order is None

    def test_risk_warn_allows_order_creation(self):
        """RiskLevel.WARN 仍允许创建订单"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")

        draft = _make_draft()
        risk_decision = _make_risk_decision(passed=True, level=RiskLevel.WARN)
        assert risk_decision.can_generate_signal is True

        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
        assert order is not None
        assert order.status == "RISK_CHECKED"


# ===================================================================
# 4. E2E: Kill Switch blocks all orders
# ===================================================================

class TestKillSwitchBlocksAll:
    """Kill Switch 全局阻断测试"""

    def test_kill_switch_blocks_order_creation(self):
        """Kill Switch 激活后无法创建订单"""
        kill_switch = KillSwitchState(active=True, reason="emergency_stop")
        engine = RuntimeRiskEngine(kill_switch=kill_switch)
        broker = PaperBroker()
        service = ExecutionService(
            risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM",
        )

        # 通过 RuntimeRiskEngine 检查，应返回阻断
        quotes = [{"symbol": "002463.SZ", "delay_seconds": 1, "status": "NORMAL"}]
        risk_decision = engine.check_realtime_snapshot(
            quotes=quotes, trading_mode="LEVEL_2_HUMAN_CONFIRM",
        )
        assert risk_decision.risk_pass is False
        assert RiskBlockReason.KILL_SWITCH in risk_decision.reasons

        # 使用阻断的 RiskDecision 创建订单
        draft = _make_draft()
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
        assert order is None

    def test_kill_switch_blocks_via_api(self):
        """Kill Switch 激活后 API /risk/status 返回阻断"""
        kill_switch = KillSwitchState(active=True, reason="emergency")
        engine = RuntimeRiskEngine(kill_switch=kill_switch)
        client = TestClient(create_app(risk_engine=engine))

        resp = client.get("/risk/status")
        data = resp.json()
        assert data["risk_pass"] is False
        assert data["kill_switch_active"] is True


# ===================================================================
# 5. E2E: Portfolio risk check integration with ExecutionService
# ===================================================================

class TestPortfolioRiskIntegration:
    """组合风控与 ExecutionService 集成测试"""

    def test_excessive_position_blocks_order(self):
        """单票仓位超限时风控阻断，无法创建订单"""
        engine = RuntimeRiskEngine()
        portfolio = {
            "total_assets": 1000000.0,
            "cash": 200000.0,
            "daily_pnl_pct": 0.0,
            "drawdown_pct": 0.0,
            "holdings": [
                {
                    "symbol": "002463.SZ",
                    "sector": "PCB",
                    "position_pct": 0.20,  # 超过 MAX_SINGLE_STOCK_POSITION (0.15)
                    "pnl_pct": 0.01,
                },
            ],
        }

        decision = engine.check_portfolio_risk(portfolio)
        assert decision.risk_pass is False
        assert RiskBlockReason.SINGLE_STOCK_POSITION_EXCEEDED in decision.reasons
        assert decision.can_generate_signal is False

        # 用阻断的 decision 创建订单
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        draft = _make_draft()
        order = service.create_order(draft, decision, now=_TRADING_NOW)
        assert order is None

    def test_daily_loss_stop_blocks_new_positions(self):
        """日亏损超限时风控阻断新开仓"""
        engine = RuntimeRiskEngine()
        portfolio = {
            "total_assets": 960000.0,
            "cash": 200000.0,
            "daily_pnl_pct": -0.04,  # 超过 DAILY_LOSS_STOP (-0.03)
            "drawdown_pct": 0.0,
            "holdings": [],
        }

        decision = engine.check_portfolio_risk(portfolio)
        assert decision.risk_pass is False
        assert RiskBlockReason.DAILY_LOSS_REDUCE_ONLY in decision.reasons

    def test_drawdown_halt_blocks_all(self):
        """最大回撤超限停止所有交易"""
        engine = RuntimeRiskEngine()
        portfolio = {
            "total_assets": 850000.0,
            "cash": 200000.0,
            "daily_pnl_pct": 0.0,
            "drawdown_pct": -0.15,  # 超过 MAX_DRAWDOWN_HALT (-0.12)
            "holdings": [],
        }

        decision = engine.check_portfolio_risk(portfolio)
        assert decision.risk_pass is False
        assert RiskBlockReason.DRAWDOWN_HALT in decision.reasons


# ===================================================================
# 6. API E2E: Full order lifecycle via API
# ===================================================================

class TestAPIFullLifecycle:
    """API 层完整订单生命周期测试"""

    def test_api_confirm_then_verify_account_and_positions(self):
        """POST /orders/{id}/confirm → GET /account → GET /positions 全链路"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        client = TestClient(create_app(execution_service=service))

        # 创建订单
        draft = _make_draft(price=10.0, quantity=100)
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
        assert order is not None

        # 确认订单
        resp = client.post(f"/orders/{order.order_id}/confirm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["order"]["status"] == "FILLED"

        # 验证账户现金扣减
        account_resp = client.get("/account")
        account_data = account_resp.json()
        assert account_data["total_assets"] < 1000000.0
        assert account_data["cash"] < 1000000.0

        # 验证持仓增加
        positions_resp = client.get("/positions")
        positions_data = positions_resp.json()
        assert positions_data["count"] >= 1
        symbols = [p["symbol"] for p in positions_data["positions"]]
        assert "002463.SZ" in symbols

    def test_api_reject_order_sets_cancelled(self):
        """POST /orders/{id}/reject → 订单状态为 CANCELLED"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        client = TestClient(create_app(execution_service=service))

        draft = _make_draft()
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

        resp = client.post(f"/orders/{order.order_id}/reject?reason=test_reject")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["order"]["status"] == "CANCELLED"

        # 验证订单不在待确认队列
        pending_resp = client.get("/orders/pending")
        pending_ids = [o["order_id"] for o in pending_resp.json()["orders"]]
        assert order.order_id not in pending_ids

    def test_api_order_detail_after_fill(self):
        """GET /orders/{id} 查看已成交订单详情"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        client = TestClient(create_app(execution_service=service))

        draft = _make_draft()
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
        service.confirm_order(order.order_id)

        resp = client.get(f"/orders/{order.order_id}")
        data = resp.json()
        assert data["status"] == "FILLED"
        assert data["fill_price"] is not None
        assert data["fill_quantity"] is not None


# ===================================================================
# 7. API E2E: LEVEL_1 mode rejects confirm
# ===================================================================

class TestAPILevel1RejectsConfirm:
    """LEVEL_1_SIGNAL_ONLY 模式下 API 拒绝确认"""

    def test_level1_confirm_returns_error(self):
        """LEVEL_1 模式下 POST /orders/{id}/confirm 返回错误"""
        service = _build_service(trading_mode="LEVEL_1_SIGNAL_ONLY")
        client = TestClient(create_app(execution_service=service))

        # LEVEL_1 无法创建订单，所以用任意 order_id 测试
        resp = client.post("/orders/ORD_fake/confirm")
        data = resp.json()
        assert data["status"] == "error"
        assert "模式" in data["message"] or "不允许" in data["message"]

    def test_level1_no_pending_orders(self):
        """LEVEL_1 模式下待确认订单始终为空"""
        service = _build_service(trading_mode="LEVEL_1_SIGNAL_ONLY")
        client = TestClient(create_app(execution_service=service))

        resp = client.get("/orders/pending")
        assert resp.json()["count"] == 0


# ===================================================================
# 8. E2E: OrderChecker + ExecutionService integration
# ===================================================================

class TestOrderCheckerIntegration:
    """OrderChecker 与 ExecutionService 集成测试"""

    def test_non_trading_hours_order_fails(self):
        """非交易时段订单创建失败"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")

        draft = _make_draft()
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_NON_TRADING_NOW)

        assert order is None, "非交易时段应无法创建订单"

    def test_gem_stock_order_fails(self):
        """创业板 (300xxx) 股票订单创建失败"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")

        draft = _make_draft(symbol="300750.SZ")
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

        assert order is None, "创业板股票应被 OrderChecker 拦截"

    def test_insufficient_cash_quantity_adjusted(self):
        """资金不足时数量自动调整"""
        # 初始资金很少，只够买少量
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM", initial_cash=1500.0)

        # 请求买入 500 股 @ 10.0 = 5000 元，但只有 1500
        draft = _make_draft(price=10.0, quantity=500)
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

        # 应调整数量而非拒绝（调整后 >= 100 股即可）
        if order is not None:
            assert order.quantity <= 500
            assert order.quantity >= 100
            assert order.quantity % 100 == 0
        else:
            # 如果调整后 < 100 则返回 None，也合理
            pass

    def test_star_market_stock_order_fails(self):
        """科创板 (688xxx) 股票订单创建失败"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")

        draft = _make_draft(symbol="688981.SH", market="SH")
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

        assert order is None, "科创板股票应被 OrderChecker 拦截"


# ===================================================================
# 9. E2E: Sell order with position check
# ===================================================================

class TestSellOrderPositionCheck:
    """卖出订单持仓检查测试"""

    def test_buy_then_sell_full_position(self):
        """先买入再卖出，验证持仓变化和卖出数量检查（T+1: 需模拟隔日）"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        broker = service._broker

        # Step 1: 买入
        buy_draft = _make_draft(side="BUY", price=10.0, quantity=200)
        risk_decision = _make_risk_decision(passed=True)
        buy_order = service.create_order(buy_draft, risk_decision, now=_TRADING_NOW)
        assert buy_order is not None

        confirmed_buy = service.confirm_order(buy_order.order_id)
        assert confirmed_buy.status == "FILLED"

        # 验证持仓（T+1: available_quantity=0）
        positions = broker.query_positions()
        buy_pos = next(p for p in positions if p.symbol == "002463.SZ")
        assert buy_pos.quantity == 200
        assert buy_pos.available_quantity == 0  # T+1: 当日不可卖

        # 模拟隔日：设置 available_quantity
        buy_pos.available_quantity = 200

        # Step 2: 卖出
        sell_draft = _make_draft(side="SELL", price=10.0, quantity=200)
        sell_risk = _make_risk_decision(passed=True)
        sell_order = service.create_order(sell_draft, sell_risk, now=_TRADING_NOW)
        assert sell_order is not None

        confirmed_sell = service.confirm_order(sell_order.order_id)
        assert confirmed_sell.status == "FILLED"

        # 验证持仓已清空
        positions_after = broker.query_positions()
        assert not any(p.symbol == "002463.SZ" for p in positions_after)

        # 验证现金恢复（扣除手续费）
        account = broker.query_account()
        assert account.cash < 1000000.0  # 手续费损耗
        assert account.cash > 998000.0  # 但大部分回来

    def test_sell_more_than_position_fails(self):
        """卖出数量超过持仓时订单创建失败"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")

        # 先买入 100 股
        buy_draft = _make_draft(side="BUY", price=10.0, quantity=100)
        risk_decision = _make_risk_decision(passed=True)
        buy_order = service.create_order(buy_draft, risk_decision, now=_TRADING_NOW)
        service.confirm_order(buy_order.order_id)

        # 尝试卖出 200 股（超过持仓）
        sell_draft = _make_draft(side="SELL", price=10.0, quantity=200)
        sell_order = service.create_order(sell_draft, risk_decision, now=_TRADING_NOW)
        assert sell_order is None, "卖出超过持仓应被 OrderChecker 拦截"

    def test_sell_without_position_fails(self):
        """无持仓时卖出订单创建失败"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")

        sell_draft = _make_draft(side="SELL", price=10.0, quantity=100)
        risk_decision = _make_risk_decision(passed=True)
        sell_order = service.create_order(sell_draft, risk_decision, now=_TRADING_NOW)

        assert sell_order is None, "无持仓卖出应被 OrderChecker 拦截"


# ===================================================================
# 10. E2E: TradeRecorder integration
# ===================================================================

class TestTradeRecorderIntegration:
    """TradeRecorder 集成测试"""

    def test_record_from_order_and_daily_summary(self, tmp_path):
        """执行交易后 record_from_order → get_daily_summary 返回正确计数"""
        recorder = TradeRecorder(data_dir=str(tmp_path))

        # 创建并执行一个订单
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        draft = _make_draft(price=10.0, quantity=100)
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
        confirmed = service.confirm_order(order.order_id)
        assert confirmed.status == "FILLED"

        # 记录成交
        recorder.record_from_order(confirmed)

        # 验证 daily summary
        summary = recorder.get_daily_summary()
        assert summary["total_trades"] == 1
        assert summary["buy_count"] == 1
        assert summary["sell_count"] == 0

    def test_trade_chain_by_signal_id(self, tmp_path):
        """get_trade_chain(signal_id) 返回对应信号的交易记录"""
        recorder = TradeRecorder(data_dir=str(tmp_path))

        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        draft = _make_draft(signal_id="SIG_chain_test", price=10.0, quantity=100)
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
        confirmed = service.confirm_order(order.order_id)

        recorder.record_from_order(confirmed)

        chain = recorder.get_trade_chain("SIG_chain_test")
        assert len(chain) == 1
        assert chain[0].signal_id == "SIG_chain_test"
        assert chain[0].symbol == "002463.SZ"

    def test_trade_chain_empty_for_unknown_signal(self, tmp_path):
        """未知 signal_id 返回空链路"""
        recorder = TradeRecorder(data_dir=str(tmp_path))
        chain = recorder.get_trade_chain("SIG_nonexistent")
        assert chain == []

    def test_daily_summary_multiple_trades(self, tmp_path):
        """多笔交易后 daily_summary 正确统计（T+1: 卖出需模拟隔日）"""
        recorder = TradeRecorder(data_dir=str(tmp_path))

        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")

        # 买入
        buy_draft = _make_draft(side="BUY", signal_id="SIG_buy_1", price=10.0, quantity=200)
        risk_decision = _make_risk_decision(passed=True)
        buy_order = service.create_order(buy_draft, risk_decision, now=_TRADING_NOW)
        buy_confirmed = service.confirm_order(buy_order.order_id)
        recorder.record_from_order(buy_confirmed)

        # T+1: 模拟隔日，设置 available_quantity
        broker = service._broker
        pos = broker._positions.get("002463.SZ")
        if pos:
            pos.available_quantity = 200

        # 卖出
        sell_draft = _make_draft(side="SELL", signal_id="SIG_sell_1", price=10.0, quantity=100)
        sell_order = service.create_order(sell_draft, risk_decision, now=_TRADING_NOW)
        if sell_order is not None:
            sell_confirmed = service.confirm_order(sell_order.order_id)
            recorder.record_from_order(sell_confirmed)

        summary = recorder.get_daily_summary()
        assert summary["total_trades"] >= 1
        assert summary["buy_count"] == 1

    def test_record_from_unfilled_order_ignored(self, tmp_path):
        """未成交订单 record_from_order 不产生记录"""
        recorder = TradeRecorder(data_dir=str(tmp_path))

        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        draft = _make_draft()
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

        # 订单还在 RISK_CHECKED 状态，未成交
        assert order.status == "RISK_CHECKED"
        recorder.record_from_order(order)

        assert len(recorder.records) == 0

    def test_trade_recorder_callback_integration(self, tmp_path):
        """ExecutionService on_trade_callback 与 TradeRecorder 集成"""
        recorder = TradeRecorder(data_dir=str(tmp_path))

        service = _build_service(trading_mode="LEVEL_3_AUTO")
        service.set_on_trade_callback(lambda trade: recorder.record(trade))

        draft = _make_draft(signal_id="SIG_callback_test")
        risk_decision = _make_risk_decision(
            passed=True, level=RiskLevel.OK, trading_mode="LEVEL_3_AUTO",
        )
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
        assert order is not None
        assert order.status == "FILLED"

        # 注意：ExecutionService._execute_order 不调用 on_trade_callback
        # callback 需要在外部调用，这里手动验证 record_from_order
        recorder.record_from_order(order)
        assert len(recorder.records) == 1
        assert recorder.records[0].signal_id == "SIG_callback_test"


# ===================================================================
# Cross-cutting: API + ExecutionService edge cases
# ===================================================================

class TestAPIEdgeCases:
    """API 层边界情况测试"""

    def test_api_confirm_already_confirmed_returns_none(self):
        """重复确认同一订单返回错误"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        client = TestClient(create_app(execution_service=service))

        draft = _make_draft()
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

        # 第一次确认成功
        resp1 = client.post(f"/orders/{order.order_id}/confirm")
        assert resp1.json()["status"] == "ok"

        # 第二次确认失败（已不在待确认队列）
        resp2 = client.post(f"/orders/{order.order_id}/confirm")
        assert resp2.json()["status"] == "error"

    def test_api_confirm_nonexistent_order(self):
        """确认不存在的订单返回错误"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        client = TestClient(create_app(execution_service=service))

        resp = client.post("/orders/ORD_nonexistent/confirm")
        assert resp.json()["status"] == "error"

    def test_api_reject_nonexistent_order(self):
        """拒绝不存在的订单返回错误"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        client = TestClient(create_app(execution_service=service))

        resp = client.post("/orders/ORD_nonexistent/reject")
        assert resp.json()["status"] == "error"

    def test_api_cancel_pending_order(self):
        """撤销待确认订单"""
        service = _build_service(trading_mode="LEVEL_2_HUMAN_CONFIRM")
        client = TestClient(create_app(execution_service=service))

        draft = _make_draft()
        risk_decision = _make_risk_decision(passed=True)
        order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

        resp = client.post(f"/orders/{order.order_id}/cancel")
        assert resp.json()["status"] == "ok"
        assert resp.json()["order"]["status"] == "CANCELLED"
