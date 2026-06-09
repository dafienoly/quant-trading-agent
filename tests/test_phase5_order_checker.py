"""Phase 5 测试 — OrderChecker 订单检查器"""
from datetime import datetime, time

from src.execution_engine.order_checker import (
    OrderChecker,
    calculate_buy_quantity,
    is_no_new_buy_period,
    is_trading_hours,
)
from src.models.schemas import AccountInfo, OrderDraft


def _make_draft(side: str = "BUY", symbol: str = "002463.SZ", price: float = 10.0,
                quantity: int = 100, market: str = "SZ") -> OrderDraft:
    return OrderDraft(
        symbol=symbol,
        market=market,
        side=side,
        price_type="LIMIT",
        limit_price=price,
        quantity=quantity,
        strategy_name="test",
        signal_id="SIG_test",
    )


def _make_account(cash: float = 1000000.0) -> AccountInfo:
    return AccountInfo(total_assets=cash, cash=cash, available_cash=cash)


def test_check_order_passes():
    checker = OrderChecker()
    draft = _make_draft()
    account = _make_account()
    # 交易时段内
    now = datetime(2026, 6, 9, 10, 0, 0)
    result = checker.check_order(draft, account, [], now=now)
    assert result.passed is True


def test_check_order_rejects_gem_stock():
    checker = OrderChecker()
    draft = _make_draft(symbol="300750.SZ", side="BUY")
    account = _make_account()
    now = datetime(2026, 6, 9, 10, 0, 0)
    result = checker.check_order(draft, account, [], now=now)
    assert result.passed is False
    assert "创业板" in result.reason or "科创板" in result.reason


def test_check_order_rejects_star_stock():
    checker = OrderChecker()
    draft = _make_draft(symbol="688981.SH", side="BUY")
    account = _make_account()
    now = datetime(2026, 6, 9, 10, 0, 0)
    result = checker.check_order(draft, account, [], now=now)
    assert result.passed is False


def test_check_order_rejects_blacklist():
    checker = OrderChecker(blacklist={"002463"})
    draft = _make_draft()
    account = _make_account()
    now = datetime(2026, 6, 9, 10, 0, 0)
    result = checker.check_order(draft, account, [], now=now)
    assert result.passed is False
    assert "黑名单" in result.reason


def test_check_order_rejects_non_trading_hours():
    checker = OrderChecker()
    draft = _make_draft()
    account = _make_account()
    now = datetime(2026, 6, 9, 8, 0, 0)  # 开盘前
    result = checker.check_order(draft, account, [], now=now)
    assert result.passed is False
    assert "非交易时段" in result.reason


def test_check_order_rejects_zero_price():
    checker = OrderChecker()
    draft = _make_draft(price=0.0)
    account = _make_account()
    now = datetime(2026, 6, 9, 10, 0, 0)
    result = checker.check_order(draft, account, [], now=now)
    assert result.passed is False
    assert "价格" in result.reason


def test_check_order_rejects_odd_lot():
    checker = OrderChecker()
    draft = _make_draft(quantity=150)
    account = _make_account()
    now = datetime(2026, 6, 9, 10, 0, 0)
    result = checker.check_order(draft, account, [], now=now)
    assert result.passed is False
    assert "整数倍" in result.reason


def test_check_order_insufficient_cash_adjusts():
    checker = OrderChecker()
    draft = _make_draft(price=10.0, quantity=10000)
    account = _make_account(cash=5000.0)
    now = datetime(2026, 6, 9, 10, 0, 0)
    result = checker.check_order(draft, account, [], now=now)
    # 应该调整数量而不是直接拒绝
    assert result.passed is True
    assert result.adjusted_quantity is not None
    assert result.adjusted_quantity < 10000


def test_check_order_sell_no_position():
    from src.models.schemas import Position
    checker = OrderChecker()
    draft = _make_draft(side="SELL")
    account = _make_account()
    now = datetime(2026, 6, 9, 10, 0, 0)
    result = checker.check_order(draft, account, [], now=now)
    assert result.passed is False
    assert "无持仓" in result.reason


def test_check_order_sell_exceeds_available():
    from src.models.schemas import Position
    checker = OrderChecker()
    draft = _make_draft(side="SELL", quantity=200)
    account = _make_account()
    positions = [Position(symbol="002463.SZ", quantity=100, available_quantity=100, cost_price=10.0)]
    now = datetime(2026, 6, 9, 10, 0, 0)
    result = checker.check_order(draft, account, positions, now=now)
    assert result.passed is False
    assert "可卖数量不足" in result.reason


def test_calculate_buy_quantity():
    qty = calculate_buy_quantity(available_cash=100000.0, price=10.0, position_pct=0.15)
    assert qty > 0
    assert qty % 100 == 0  # 100的整数倍


def test_calculate_buy_quantity_zero_price():
    qty = calculate_buy_quantity(available_cash=100000.0, price=0.0, position_pct=0.15)
    assert qty == 0


def test_is_trading_hours():
    # 交易时段内
    assert is_trading_hours("SZ", datetime(2026, 6, 9, 10, 0, 0)) is True
    assert is_trading_hours("SZ", datetime(2026, 6, 9, 14, 0, 0)) is True
    # 交易时段外
    assert is_trading_hours("SZ", datetime(2026, 6, 9, 8, 0, 0)) is False
    assert is_trading_hours("SZ", datetime(2026, 6, 9, 12, 0, 0)) is False  # 午休
    assert is_trading_hours("SZ", datetime(2026, 6, 9, 16, 0, 0)) is False


def test_is_no_new_buy_period():
    assert is_no_new_buy_period("SZ", datetime(2026, 6, 9, 14, 56, 0)) is True
    assert is_no_new_buy_period("SZ", datetime(2026, 6, 9, 10, 0, 0)) is False
