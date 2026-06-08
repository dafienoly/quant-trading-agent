"""回测引擎公共接口"""
from src.backtest_engine.commission_model import (
    CommissionModel,
    SlippageModel,
    FixedRateSlippage,
    FixedAmountSlippage,
    NoSlippage,
    FillPriceModel,
)
from src.backtest_engine.portfolio import Portfolio, Position, TradeRecord
from src.backtest_engine.performance import PerformanceAnalyzer
from src.backtest_engine.risk_check import BacktestRiskCheck
from src.backtest_engine.engine import BacktestEngine
from src.backtest_engine.event_backtester import EventBacktester
from src.backtest_engine.report_generator import generate_html_report
from src.backtest_engine.significance_test import significance_test_report
from src.backtest_engine.persistence import save_backtest_result, load_backtest_result
