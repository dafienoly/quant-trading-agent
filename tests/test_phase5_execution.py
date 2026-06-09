"""Phase 5 测试 — ExecutionService + API 订单管理端点"""
from datetime import datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.execution_engine.broker_adapter import PaperBroker
from src.execution_engine.execution_service import ExecutionService
from src.execution_engine.order_checker import OrderChecker
from src.models.schemas import OrderDraft
from src.risk_engine.models import RiskDecision, RiskLevel
from src.risk_engine.runtime import RuntimeRiskEngine

# 交易时段内的时间
_TRADING_NOW = datetime(2026, 6, 9, 10, 0, 0)


def _make_risk_decision(passed: bool = True, level: RiskLevel = RiskLevel.OK) -> RiskDecision:
    return RiskDecision(
        risk_pass=passed,
        level=level,
        trading_mode="LEVEL_2_HUMAN_CONFIRM",
        reasons=[],
        messages=[],
    )


def _make_draft(side: str = "BUY", symbol: str = "002463.SZ", price: float = 10.0,
                quantity: int = 100) -> OrderDraft:
    return OrderDraft(
        symbol=symbol,
        market="SZ",
        side=side,
        price_type="LIMIT",
        limit_price=price,
        quantity=quantity,
        strategy_name="test",
        signal_id="SIG_test",
        stock_name="沪电股份",
        sector="PCB",
        stop_loss_price=9.0,
        take_profit_price=12.0,
    )


def test_execution_service_level1_no_order():
    """LEVEL_1 模式下不生成订单"""
    engine = RuntimeRiskEngine()
    broker = PaperBroker()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_1_SIGNAL_ONLY")

    from src.models.schemas import Signal
    signal = Signal(
        signal_id="SIG_test",
        symbol="002463.SZ",
        stock_name="沪电股份",
        sector="PCB",
        trade_date="20260609",
        strategy="test",
        signal_type="BUY",
        sub_type="BREAKOUT",
        score=0.8,
        price_trigger=10.0,
        reason="test buy",
        stop_loss_price=9.0,
        take_profit_price=12.0,
        position_pct=0.10,
        risk_note="",
        created_at="2026-06-09 10:00:00",
    )
    account = broker.query_account()
    draft = service.signal_to_draft(signal, account)
    assert draft is None


def test_execution_service_create_order_level2():
    """LEVEL_2 模式下创建订单，等待人工确认"""
    engine = RuntimeRiskEngine()
    broker = PaperBroker()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    draft = _make_draft()
    risk_decision = _make_risk_decision(passed=True)
    order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

    assert order is not None
    assert order.status == "RISK_CHECKED"
    assert order.order_id in service.pending_orders


def test_execution_service_risk_blocked():
    """风控未通过不能创建订单"""
    engine = RuntimeRiskEngine()
    broker = PaperBroker()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    draft = _make_draft()
    risk_decision = _make_risk_decision(passed=False, level=RiskLevel.BLOCK)
    order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

    assert order is None


def test_execution_service_confirm_order():
    """确认订单后执行"""
    engine = RuntimeRiskEngine()
    broker = PaperBroker()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    draft = _make_draft()
    risk_decision = _make_risk_decision(passed=True)
    order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
    assert order is not None

    confirmed = service.confirm_order(order.order_id, confirmed_by="test_user")
    assert confirmed is not None
    assert confirmed.status == "FILLED"
    assert confirmed.confirmed_by == "test_user"
    assert order.order_id not in service.pending_orders


def test_execution_service_reject_order():
    """拒绝订单"""
    engine = RuntimeRiskEngine()
    broker = PaperBroker()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    draft = _make_draft()
    risk_decision = _make_risk_decision(passed=True)
    order = service.create_order(draft, risk_decision, now=_TRADING_NOW)
    assert order is not None

    rejected = service.reject_order(order.order_id, reason="test reject")
    assert rejected is not None
    assert rejected.status == "CANCELLED"
    assert order.order_id not in service.pending_orders


def test_execution_service_cancel_order():
    """撤销订单"""
    engine = RuntimeRiskEngine()
    broker = PaperBroker()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    draft = _make_draft()
    risk_decision = _make_risk_decision(passed=True)
    order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

    cancelled = service.cancel_order(order.order_id)
    assert cancelled is not None
    assert cancelled.status == "CANCELLED"


def test_api_orders_pending():
    """API: 查询待确认订单"""
    engine = RuntimeRiskEngine()
    broker = PaperBroker()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    client = TestClient(create_app(execution_service=service))

    # 无订单
    resp = client.get("/orders/pending")
    assert resp.json()["count"] == 0

    # 创建订单
    draft = _make_draft()
    risk_decision = _make_risk_decision(passed=True)
    service.create_order(draft, risk_decision, now=_TRADING_NOW)

    resp = client.get("/orders/pending")
    assert resp.json()["count"] == 1


def test_api_order_confirm():
    """API: 确认订单"""
    engine = RuntimeRiskEngine()
    broker = PaperBroker()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    client = TestClient(create_app(execution_service=service))

    draft = _make_draft()
    risk_decision = _make_risk_decision(passed=True)
    order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

    resp = client.post(f"/orders/{order.order_id}/confirm")
    assert resp.json()["status"] == "ok"
    assert resp.json()["order"]["status"] == "FILLED"


def test_api_order_reject():
    """API: 拒绝订单"""
    engine = RuntimeRiskEngine()
    broker = PaperBroker()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    client = TestClient(create_app(execution_service=service))

    draft = _make_draft()
    risk_decision = _make_risk_decision(passed=True)
    order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

    resp = client.post(f"/orders/{order.order_id}/reject")
    assert resp.json()["status"] == "ok"
    assert resp.json()["order"]["status"] == "CANCELLED"


def test_api_account():
    """API: 查询账户信息"""
    broker = PaperBroker(initial_cash=1000000.0)
    engine = RuntimeRiskEngine()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    client = TestClient(create_app(execution_service=service))
    resp = client.get("/account")
    assert resp.json()["total_assets"] == 1000000.0


def test_api_positions():
    """API: 查询持仓"""
    broker = PaperBroker(initial_cash=1000000.0)
    engine = RuntimeRiskEngine()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    client = TestClient(create_app(execution_service=service))
    resp = client.get("/positions")
    assert resp.json()["count"] == 0


def test_api_order_detail():
    """API: 查询订单详情"""
    broker = PaperBroker()
    engine = RuntimeRiskEngine()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    client = TestClient(create_app(execution_service=service))

    draft = _make_draft()
    risk_decision = _make_risk_decision(passed=True)
    order = service.create_order(draft, risk_decision, now=_TRADING_NOW)

    resp = client.get(f"/orders/{order.order_id}")
    assert resp.json()["order_id"] == order.order_id
    assert resp.json()["symbol"] == "002463.SZ"


def test_api_order_not_found():
    """API: 订单不存在"""
    broker = PaperBroker()
    engine = RuntimeRiskEngine()
    service = ExecutionService(risk_engine=engine, broker=broker, trading_mode="LEVEL_2_HUMAN_CONFIRM")

    client = TestClient(create_app(execution_service=service))
    resp = client.get("/orders/nonexistent")
    assert "error" in resp.json()


def test_api_no_execution_service():
    """API: 无 ExecutionService 时返回提示"""
    client = TestClient(create_app())
    resp = client.get("/orders/pending")
    assert resp.json()["orders"] == []

    resp = client.get("/account")
    assert "error" in resp.json()
