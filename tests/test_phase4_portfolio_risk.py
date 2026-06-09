"""Phase 4 审计整改 — 交易层风控 (S1) 测试

覆盖 RISK_POLICY.md 2-4 节 HARD 规则：
- 2.1 单票仓位 ≤15%
- 2.2 板块集中度 ≤60%
- 2.2 现金最低比例 ≥20%
- 3.1 单票亏损 -5% warn / -8% stop
- 3.2 日亏损 -2% stop new / -3% reduce only
- 3.3 回撤 -8% defense / -12% halt
"""
from src.risk_engine.models import RiskBlockReason, RiskLevel
from src.risk_engine.runtime import RuntimeRiskEngine


def _make_portfolio(**overrides) -> dict:
    """构造标准持仓信息"""
    portfolio = {
        "total_assets": 1000000.0,
        "cash": 250000.0,
        "daily_pnl_pct": 0.0,
        "drawdown_pct": 0.0,
        "holdings": [],
    }
    portfolio.update(overrides)
    return portfolio


def test_portfolio_risk_passes_healthy_portfolio():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(holdings=[
        {"symbol": "002463.SZ", "sector": "PCB", "position_pct": 0.10, "pnl_pct": 0.02},
    ])

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is True
    assert decision.level == RiskLevel.OK
    assert decision.can_generate_signal is True


def test_portfolio_risk_blocks_single_stock_position_exceeded():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(holdings=[
        {"symbol": "002463.SZ", "sector": "PCB", "position_pct": 0.20, "pnl_pct": 0.01},
    ])

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is False
    assert decision.level == RiskLevel.BLOCK
    assert RiskBlockReason.SINGLE_STOCK_POSITION_EXCEEDED in decision.reasons


def test_portfolio_risk_blocks_sector_concentration():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(holdings=[
        {"symbol": "002463.SZ", "sector": "semiconductor", "position_pct": 0.35, "pnl_pct": 0.01},
        {"symbol": "603501.SH", "sector": "semiconductor", "position_pct": 0.30, "pnl_pct": -0.01},
    ])

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is False
    assert RiskBlockReason.SECTOR_CONCENTRATION_EXCEEDED in decision.reasons


def test_portfolio_risk_blocks_insufficient_cash():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(cash=100000.0, holdings=[
        {"symbol": "002463.SZ", "sector": "PCB", "position_pct": 0.10, "pnl_pct": 0.01},
    ])

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is False
    assert RiskBlockReason.INSUFFICIENT_CASH in decision.reasons


def test_portfolio_risk_warns_single_stock_loss():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(holdings=[
        {"symbol": "002463.SZ", "sector": "PCB", "position_pct": 0.10, "pnl_pct": -0.06},
    ])

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is True
    assert decision.level == RiskLevel.WARN
    assert RiskBlockReason.SINGLE_STOCK_LOSS_WARN in decision.reasons


def test_portfolio_risk_blocks_single_stock_stop_loss():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(holdings=[
        {"symbol": "002463.SZ", "sector": "PCB", "position_pct": 0.10, "pnl_pct": -0.09},
    ])

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is False
    assert RiskBlockReason.SINGLE_STOCK_LOSS_STOP in decision.reasons


def test_portfolio_risk_blocks_daily_loss_stop_new():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(daily_pnl_pct=-0.025)

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is False
    assert RiskBlockReason.DAILY_LOSS_STOP_NEW in decision.reasons


def test_portfolio_risk_blocks_daily_loss_reduce_only():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(daily_pnl_pct=-0.035)

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is False
    assert RiskBlockReason.DAILY_LOSS_REDUCE_ONLY in decision.reasons


def test_portfolio_risk_warns_drawdown_defense():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(drawdown_pct=-0.09)

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is True
    assert decision.level == RiskLevel.WARN
    assert RiskBlockReason.DRAWDOWN_DEFENSE in decision.reasons


def test_portfolio_risk_blocks_drawdown_halt():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(drawdown_pct=-0.13)

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is False
    assert RiskBlockReason.DRAWDOWN_HALT in decision.reasons


def test_portfolio_risk_empty_holdings_passes():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio()

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is True
    assert decision.level == RiskLevel.OK


def test_portfolio_risk_multiple_violations():
    engine = RuntimeRiskEngine()
    portfolio = _make_portfolio(
        cash=100000.0,
        daily_pnl_pct=-0.035,
        drawdown_pct=-0.13,
        holdings=[
            {"symbol": "002463.SZ", "sector": "semiconductor", "position_pct": 0.20, "pnl_pct": -0.09},
            {"symbol": "603501.SH", "sector": "semiconductor", "position_pct": 0.45, "pnl_pct": -0.01},
        ],
    )

    decision = engine.check_portfolio_risk(portfolio)

    assert decision.risk_pass is False
    assert decision.level == RiskLevel.BLOCK
    assert RiskBlockReason.SINGLE_STOCK_POSITION_EXCEEDED in decision.reasons
    assert RiskBlockReason.SECTOR_CONCENTRATION_EXCEEDED in decision.reasons
    assert RiskBlockReason.INSUFFICIENT_CASH in decision.reasons
    assert RiskBlockReason.SINGLE_STOCK_LOSS_STOP in decision.reasons
    assert RiskBlockReason.DAILY_LOSS_REDUCE_ONLY in decision.reasons
    assert RiskBlockReason.DRAWDOWN_HALT in decision.reasons
