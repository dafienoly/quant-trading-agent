"""Phase 5 测试 — PaperBroker 模拟交易"""
from src.execution_engine.broker_adapter import PaperBroker
from src.models.schemas import Order


def _make_order(side: str = "BUY", symbol: str = "002463.SZ", price: float = 10.0,
                quantity: int = 100, market_status: str = "NORMAL", **kwargs) -> Order:
    return Order(
        order_id=f"ORD_20260609_test01",
        symbol=symbol,
        market="SZ",
        side=side,
        price_type="LIMIT",
        limit_price=price,
        quantity=quantity,
        strategy_name="test",
        signal_id="SIG_test",
        risk_check_id="RISK_test",
        market_status=market_status,
        **kwargs,
    )


def test_paper_broker_buy():
    broker = PaperBroker(initial_cash=1000000.0)
    order = _make_order(side="BUY", price=10.0, quantity=100)
    result = broker.submit_order(order)

    assert result.success is True
    assert result.fill_price == 10.0
    assert result.fill_quantity == 100

    account = broker.query_account()
    assert account.cash < 1000000.0  # 扣除了资金
    positions = broker.query_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "002463.SZ"
    assert positions[0].quantity == 100


def test_paper_broker_sell():
    """卖出测试：先买入，再卖出（需要 available_quantity > 0）"""
    broker = PaperBroker(initial_cash=1000000.0)
    buy_order = _make_order(side="BUY", price=10.0, quantity=200)
    broker.submit_order(buy_order)

    # T+1: 买入后 available_quantity=0，需要手动设置可卖数量模拟隔日
    pos = broker._positions["002463.SZ"]
    pos.available_quantity = 200

    sell_order = _make_order(side="SELL", price=11.0, quantity=100)
    result = broker.submit_order(sell_order)

    assert result.success is True
    assert result.fill_price == 11.0
    positions = broker.query_positions()
    assert len(positions) == 1
    assert positions[0].quantity == 100


def test_paper_broker_sell_no_position():
    broker = PaperBroker(initial_cash=1000000.0)
    sell_order = _make_order(side="SELL", price=10.0, quantity=100)
    result = broker.submit_order(sell_order)
    assert result.success is False
    assert "无持仓" in result.message


def test_paper_broker_insufficient_cash():
    broker = PaperBroker(initial_cash=500.0)
    order = _make_order(side="BUY", price=10.0, quantity=1000)
    result = broker.submit_order(order)
    assert result.success is False
    assert "资金不足" in result.message


def test_paper_broker_limit_up_no_buy():
    broker = PaperBroker(initial_cash=1000000.0)
    order = _make_order(side="BUY", market_status="LIMIT_UP")
    result = broker.submit_order(order)
    assert result.success is False
    assert "涨停" in result.message


def test_paper_broker_limit_down_no_sell():
    broker = PaperBroker(initial_cash=1000000.0)
    buy_order = _make_order(side="BUY", price=10.0, quantity=100)
    broker.submit_order(buy_order)
    pos = broker._positions["002463.SZ"]
    pos.available_quantity = 100

    sell_order = _make_order(side="SELL", market_status="LIMIT_DOWN")
    result = broker.submit_order(sell_order)
    assert result.success is False
    assert "跌停" in result.message


def test_paper_broker_suspended():
    broker = PaperBroker(initial_cash=1000000.0)
    order = _make_order(side="BUY", market_status="SUSPENDED")
    result = broker.submit_order(order)
    assert result.success is False
    assert "停牌" in result.message


def test_paper_broker_sell_more_than_held():
    broker = PaperBroker(initial_cash=1000000.0)
    buy_order = _make_order(side="BUY", price=10.0, quantity=100)
    broker.submit_order(buy_order)
    pos = broker._positions["002463.SZ"]
    pos.available_quantity = 100

    sell_order = _make_order(side="SELL", quantity=200)
    result = broker.submit_order(sell_order)
    assert result.success is False
    assert "可卖数量不足" in result.message


def test_paper_broker_account_info():
    broker = PaperBroker(initial_cash=1000000.0)
    account = broker.query_account()
    assert account.total_assets == 1000000.0
    assert account.cash == 1000000.0
    assert account.market_value == 0.0


def test_paper_broker_trades_recorded():
    broker = PaperBroker(initial_cash=1000000.0)
    order = _make_order(side="BUY", price=10.0, quantity=100)
    broker.submit_order(order)
    assert len(broker.trades) == 1
    assert broker.trades[0].side == "BUY"
    assert broker.trades[0].price == 10.0


def test_paper_broker_sell_all_position():
    broker = PaperBroker(initial_cash=1000000.0)
    buy_order = _make_order(side="BUY", price=10.0, quantity=100)
    broker.submit_order(buy_order)
    pos = broker._positions["002463.SZ"]
    pos.available_quantity = 100

    sell_order = _make_order(side="SELL", price=10.0, quantity=100)
    broker.submit_order(sell_order)

    positions = broker.query_positions()
    assert len(positions) == 0  # 清仓后持仓为空


def test_paper_broker_t_plus_1():
    """T+1: 当日买入的股票 available_quantity=0，不可当日卖出"""
    broker = PaperBroker(initial_cash=1000000.0)
    buy_order = _make_order(side="BUY", price=10.0, quantity=100)
    broker.submit_order(buy_order)

    positions = broker.query_positions()
    assert positions[0].quantity == 100
    assert positions[0].available_quantity == 0  # T+1: 当日不可卖
