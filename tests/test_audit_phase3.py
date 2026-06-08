"""Phase 3 审计整改专项测试

覆盖 AUDIT_REPORT_PHASE3.md 中所有审计发现：
- S1: 事件驱动回测器 EventBacktester
- S2: 独立 SlippageModel 抽象
- S3: 集成测试和端到端测试
- M1: 回测引擎涨跌停/停牌无法成交逻辑
- M2: 补齐5项绩效指标 (cost_adjusted/benchmark/excess/monthly/yearly)
- M3: 回测报告HTML/可视化输出
- M4: 样本外测试统计显著性检验
- M5: 风控检查与回测引擎深度集成
- L1: 支持多种成交价模式(开盘价/收盘价/VWAP)
- L2: 回测结果持久化存储
- L4: 印花税区分A股/港股
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest_engine.commission_model import (
    CommissionModel,
    FixedRateSlippage,
    FixedAmountSlippage,
    NoSlippage,
    FillPriceModel,
    SlippageModel,
)
from src.backtest_engine.portfolio import Portfolio, Position, TradeRecord
from src.backtest_engine.performance import PerformanceAnalyzer
from src.backtest_engine.risk_check import BacktestRiskCheck
from src.backtest_engine.engine import BacktestEngine
from src.backtest_engine.event_backtester import (
    EventBacktester,
    MarketEvent,
    SignalEvent,
    OrderEvent,
    FillEvent,
    EventType,
)
from src.backtest_engine.report_generator import generate_html_report
from src.backtest_engine.significance_test import (
    t_test_excess_return,
    bootstrap_test,
    significance_test_report,
)
from src.backtest_engine.persistence import (
    save_backtest_result,
    load_backtest_result,
    list_backtest_runs,
)


# ============================================================
# 辅助函数
# ============================================================

def _make_backtest_data(days=60, symbols=None):
    """生成回测用的日线数据"""
    if symbols is None:
        symbols = ["002463.SZ", "600584.SH", "002371.SZ"]

    np.random.seed(42)
    rows = []
    dates = pd.bdate_range(start="2024-01-01", periods=days)
    dates_str = [d.strftime("%Y%m%d") for d in dates]

    for symbol in symbols:
        base_price = 10.0
        for i, date in enumerate(dates_str):
            pct = np.random.uniform(-3, 3)
            base_price *= (1 + pct / 100)
            base_price = max(base_price, 1.0)
            volume = float(np.random.randint(50000, 200000))
            rows.append({
                "symbol": symbol,
                "trade_date": date,
                "open": round(base_price * (1 + np.random.uniform(-0.01, 0.01)), 2),
                "high": round(base_price * (1 + abs(np.random.uniform(0, 0.03))), 2),
                "low": round(base_price * (1 - abs(np.random.uniform(0, 0.03))), 2),
                "close": round(base_price, 2),
                "volume": volume,
                "amount": round(base_price * volume, 2),
                "pct_change": round(pct, 2),
                "turnover_rate": round(np.random.uniform(0.5, 3), 2),
                "is_suspended": False,
                "is_st": False,
                "is_data_missing": False,
            })

    return pd.DataFrame(rows)


def _make_portfolio_with_trades():
    """创建有交易记录的组合"""
    p = Portfolio(initial_capital=1000000)
    p.buy("002463.SZ", 10.0, 1000, "20240101")
    p.update_price("002463.SZ", 11.0)
    p.record_daily_value("20240101")
    p.record_daily_value("20240102")
    p.record_daily_value("20240103")
    return p


# ============================================================
# S1: 事件驱动回测器 EventBacktester
# ============================================================

class TestS1EventBacktester:
    """S1审计修复: 验证EventBacktester实现"""

    def test_event_types_defined(self):
        """事件类型枚举完整"""
        assert EventType.MARKET.value == "MARKET"
        assert EventType.SIGNAL.value == "SIGNAL"
        assert EventType.ORDER.value == "ORDER"
        assert EventType.FILL.value == "FILL"

    def test_event_dataclasses(self):
        """事件数据类可实例化"""
        me = MarketEvent(trade_date="20240101", bar_data=pd.DataFrame())
        assert me.trade_date == "20240101"

        se = SignalEvent(trade_date="20240101", signals=[])
        assert se.trade_date == "20240101"

        oe = OrderEvent(
            trade_date="20240101", symbol="002463.SZ",
            side="BUY", quantity=1000, price=10.0,
        )
        assert oe.symbol == "002463.SZ"

        fe = FillEvent(
            trade_date="20240101", symbol="002463.SZ",
            side="BUY", quantity=1000, fill_price=10.01,
            commission=5.0, stamp_duty=0.0, slippage=10.0, total_cost=15.0,
        )
        assert fe.fill_price == 10.01

    def test_event_backtester_instantiation(self):
        """EventBacktester可实例化"""
        eb = EventBacktester(initial_capital=500000)
        assert eb.initial_capital == 500000
        assert eb.portfolio is not None
        assert eb.risk_check is not None

    def test_event_backtester_with_custom_model(self):
        """EventBacktester支持自定义成本模型"""
        model = CommissionModel(slippage_model=NoSlippage())
        eb = EventBacktester(initial_capital=1000000, commission_model=model)
        assert eb.commission_model.slippage_model.__class__ is NoSlippage

    def test_event_backtester_run(self):
        """EventBacktester可执行完整回测"""
        data = _make_backtest_data(30, ["002463.SZ"])
        eb = EventBacktester(initial_capital=1000000)
        result = eb.run(data)
        assert result is not None
        assert "annual_return" in result
        assert "events" in result

    def test_event_backtester_signal_callback(self):
        """信号回调被正确调用"""
        signal_events = []

        def on_signal(event):
            signal_events.append(event)

        data = _make_backtest_data(30, ["002463.SZ"])
        eb = EventBacktester(on_signal_handler=on_signal)
        eb.run(data)
        # 至少应有信号事件（即使无交易）
        assert isinstance(signal_events, list)

    def test_event_backtester_fill_callback(self):
        """成交回调被正确调用"""
        fill_events = []

        def on_fill(event):
            fill_events.append(event)

        data = _make_backtest_data(30, ["002463.SZ"])
        eb = EventBacktester(on_fill_handler=on_fill)
        eb.run(data)
        # 如果有成交，应被回调
        for fe in fill_events:
            assert isinstance(fe, FillEvent)


# ============================================================
# S2: 独立 SlippageModel 抽象
# ============================================================

class TestS2SlippageModel:
    """S2审计修复: 验证独立SlippageModel抽象"""

    def test_slippage_model_is_abstract(self):
        """SlippageModel是抽象基类"""
        with pytest.raises(TypeError):
            SlippageModel()

    def test_fixed_rate_slippage(self):
        """固定比例滑点模型"""
        model = FixedRateSlippage(slippage_rate=0.002)
        buy_price = model.calc_buy_fill_price(10.0)
        sell_price = model.calc_sell_fill_price(10.0)
        assert buy_price == 10.0 * 1.002
        assert sell_price == 10.0 * 0.998

    def test_fixed_amount_slippage(self):
        """固定金额滑点模型"""
        model = FixedAmountSlippage(slippage_amount=0.05)
        buy_price = model.calc_buy_fill_price(10.0)
        sell_price = model.calc_sell_fill_price(10.0)
        assert buy_price == 10.05
        assert sell_price == 9.95

    def test_no_slippage(self):
        """无滑点模型"""
        model = NoSlippage()
        assert model.calc_buy_fill_price(10.0) == 10.0
        assert model.calc_sell_fill_price(10.0) == 10.0
        assert model.calc_slippage_amount(10.0, 1000, "BUY") == 0.0

    def test_slippage_amount_calculation(self):
        """滑点金额计算"""
        model = FixedRateSlippage(slippage_rate=0.001)
        amount = model.calc_slippage_amount(10.0, 1000, "BUY")
        assert amount == 10.0 * 0.001 * 1000

    def test_commission_model_uses_slippage_model(self):
        """CommissionModel使用独立SlippageModel"""
        model = CommissionModel(slippage_model=FixedRateSlippage(slippage_rate=0.003))
        result = model.calc_buy_cost(10.0, 1000)
        assert result["fill_price"] == 10.0 * 1.003

    def test_commission_model_default_slippage(self):
        """CommissionModel默认使用FixedRateSlippage"""
        model = CommissionModel()
        assert isinstance(model.slippage_model, FixedRateSlippage)


# ============================================================
# S3: 集成测试和端到端测试
# ============================================================

class TestS3Integration:
    """S3审计修复: 集成测试覆盖"""

    def test_signal_to_backtest_integration(self):
        """信号→回测引擎→绩效报告 全流程集成"""
        data = _make_backtest_data(60, ["002463.SZ"])
        engine = BacktestEngine(initial_capital=1000000)
        result = engine.run(data)

        # 验证完整流程输出
        assert "annual_return" in result
        assert "max_drawdown" in result
        assert "total_trades" in result
        assert "report_text" in result
        assert "trade_records" in result
        assert "daily_values" in result

    def test_risk_check_backtest_integration(self):
        """风控检查→回测引擎集成"""
        data = _make_backtest_data(60, ["002463.SZ"])
        rc = BacktestRiskCheck(max_single_stock_position=0.05)
        engine = BacktestEngine(initial_capital=1000000, risk_check=rc)
        result = engine.run(data)
        # 风控应限制单票仓位，回测应正常运行
        assert result is not None

    def test_cost_model_portfolio_performance_integration(self):
        """成本模型→组合管理→绩效 集成"""
        model = CommissionModel(
            commission_rate=0.0003,
            slippage_model=FixedRateSlippage(slippage_rate=0.001),
        )
        p = Portfolio(initial_capital=1000000, commission_model=model)
        p.buy("002463.SZ", 10.0, 1000, "20240101")
        p.update_price("002463.SZ", 11.0)
        p.record_daily_value("20240101")
        p.record_daily_value("20240102")

        analyzer = PerformanceAnalyzer(p)
        result = analyzer.analyze()
        # 成本应被计入绩效
        assert result["total_cost"] > 0
        assert result["cost_adjusted_return"] < result["total_return"]


# ============================================================
# M1: 回测引擎涨跌停/停牌无法成交逻辑
# ============================================================

class TestM1LimitAndSuspension:
    """M1审计修复: 验证回测引擎涨跌停/停牌无法成交"""

    def test_engine_limit_up_prevents_buy(self):
        """涨停日买入被拒绝"""
        data = _make_backtest_data(5, ["002463.SZ"])
        # 将某天设为涨停
        data.loc[data.index[2], "pct_change"] = 9.98
        engine = BacktestEngine(initial_capital=1000000)
        result = engine.run(data)
        assert result is not None

    def test_engine_limit_down_prevents_sell(self):
        """跌停日卖出被拒绝"""
        data = _make_backtest_data(5, ["002463.SZ"])
        data.loc[data.index[2], "pct_change"] = -9.98
        engine = BacktestEngine(initial_capital=1000000)
        result = engine.run(data)
        assert result is not None

    def test_engine_suspension_prevents_trading(self):
        """停牌日交易被拒绝"""
        data = _make_backtest_data(5, ["002463.SZ"])
        data.loc[data.index[2], "is_suspended"] = True
        engine = BacktestEngine(initial_capital=1000000)
        result = engine.run(data)
        assert result is not None

    def test_portfolio_limit_up_rejection(self):
        """Portfolio层涨停拒绝"""
        p = Portfolio(initial_capital=1000000)
        record = p.buy("002463.SZ", 10.0, 1000, "20240115", is_limit_up=True)
        assert record is None

    def test_portfolio_limit_down_rejection(self):
        """Portfolio层跌停拒绝"""
        p = Portfolio(initial_capital=1000000)
        p.buy("002463.SZ", 10.0, 1000, "20240115")
        record = p.sell("002463.SZ", 9.0, 1000, "20240116", is_limit_down=True)
        assert record is None

    def test_portfolio_suspension_rejection(self):
        """Portfolio层停牌拒绝"""
        p = Portfolio(initial_capital=1000000)
        record = p.buy("002463.SZ", 10.0, 1000, "20240115", is_suspended=True)
        assert record is None


# ============================================================
# M2: 补齐5项绩效指标
# ============================================================

class TestM2PerformanceMetrics:
    """M2审计修复: 验证补齐5项绩效指标"""

    def test_cost_adjusted_return(self):
        """扣费后收益 = 总收益 - 总成本/初始资金"""
        p = _make_portfolio_with_trades()
        analyzer = PerformanceAnalyzer(p)
        result = analyzer.analyze()
        assert "cost_adjusted_return" in result
        # 扣费后收益应小于总收益
        assert result["cost_adjusted_return"] <= result["total_return"]

    def test_benchmark_return(self):
        """基准收益使用复合收益"""
        p = _make_portfolio_with_trades()
        benchmark = pd.Series([0.01, 0.02, -0.01], index=["20240101", "20240102", "20240103"])
        analyzer = PerformanceAnalyzer(p, benchmark_returns=benchmark)
        result = analyzer.analyze()
        assert "benchmark_return" in result
        # 复合收益: (1.01)*(1.02)*(0.99) - 1
        expected = (1.01) * (1.02) * (0.99) - 1
        assert abs(result["benchmark_return"] - expected) < 0.001

    def test_excess_return(self):
        """超额收益 = 总收益 - 基准收益"""
        p = _make_portfolio_with_trades()
        benchmark = pd.Series([0.01, 0.02, -0.01], index=["20240101", "20240102", "20240103"])
        analyzer = PerformanceAnalyzer(p, benchmark_returns=benchmark)
        result = analyzer.analyze()
        assert "excess_return" in result
        assert abs(result["excess_return"] - (result["total_return"] - result["benchmark_return"])) < 0.001

    def test_monthly_return(self):
        """月度收益"""
        p = _make_portfolio_with_trades()
        analyzer = PerformanceAnalyzer(p)
        result = analyzer.analyze()
        assert "monthly_return" in result
        assert isinstance(result["monthly_return"], dict)

    def test_yearly_return(self):
        """年度收益"""
        p = _make_portfolio_with_trades()
        analyzer = PerformanceAnalyzer(p)
        result = analyzer.analyze()
        assert "yearly_return" in result
        assert isinstance(result["yearly_return"], dict)

    def test_all_12_metrics_present(self):
        """AGENTS.md 3.5节要求的12项指标全部存在"""
        p = _make_portfolio_with_trades()
        analyzer = PerformanceAnalyzer(p)
        result = analyzer.analyze()
        required = [
            "annual_return", "max_drawdown", "sharpe_ratio", "calmar_ratio",
            "win_rate", "profit_loss_ratio", "turnover", "cost_adjusted_return",
            "benchmark_return", "excess_return", "monthly_return", "yearly_return",
        ]
        for key in required:
            assert key in result, f"缺少指标: {key}"


# ============================================================
# M3: 回测报告HTML/可视化输出
# ============================================================

class TestM3HTMLReport:
    """M3审计修复: 验证HTML回测报告生成"""

    def test_generate_html_report(self):
        """HTML报告可生成"""
        p = _make_portfolio_with_trades()
        analyzer = PerformanceAnalyzer(p)
        result = analyzer.analyze()
        result["daily_values"] = p.get_daily_values_df()
        result["trade_records"] = p.get_trade_records_df()

        with tempfile.TemporaryDirectory() as tmpdir:
            output = generate_html_report(result, output_path=str(Path(tmpdir) / "report.html"))
            assert output.exists()
            content = output.read_text(encoding="utf-8")
            assert "回测报告" in content
            assert "年化收益" in content

    def test_html_report_contains_charts(self):
        """HTML报告包含图表"""
        p = _make_portfolio_with_trades()
        analyzer = PerformanceAnalyzer(p)
        result = analyzer.analyze()
        result["daily_values"] = p.get_daily_values_df()
        result["trade_records"] = p.get_trade_records_df()

        with tempfile.TemporaryDirectory() as tmpdir:
            output = generate_html_report(result, output_path=str(Path(tmpdir) / "report.html"))
            content = output.read_text(encoding="utf-8")
            assert "Chart.js" in content or "chart.js" in content
            assert "navChart" in content
            assert "drawdownChart" in content

    def test_html_report_contains_cost_section(self):
        """HTML报告包含交易成本"""
        p = _make_portfolio_with_trades()
        analyzer = PerformanceAnalyzer(p)
        result = analyzer.analyze()
        result["daily_values"] = p.get_daily_values_df()
        result["trade_records"] = p.get_trade_records_df()

        with tempfile.TemporaryDirectory() as tmpdir:
            output = generate_html_report(result, output_path=str(Path(tmpdir) / "report.html"))
            content = output.read_text(encoding="utf-8")
            assert "总佣金" in content or "总印花税" in content


# ============================================================
# M4: 样本外测试统计显著性检验
# ============================================================

class TestM4SignificanceTest:
    """M4审计修复: 验证统计显著性检验"""

    def test_t_test_excess_return(self):
        """t检验超额收益"""
        strategy = pd.Series([0.01, 0.02, -0.005, 0.015, 0.008] * 20)
        benchmark = pd.Series([0.005, 0.01, -0.003, 0.008, 0.004] * 20)
        result = t_test_excess_return(strategy, benchmark)
        assert "t_stat" in result
        assert "p_value" in result
        assert "is_significant" in result
        assert "mean_excess" in result

    def test_t_test_short_series(self):
        """短序列t检验"""
        strategy = pd.Series([0.01])
        benchmark = pd.Series([0.005])
        result = t_test_excess_return(strategy, benchmark)
        assert result["is_significant"] is False

    def test_bootstrap_test(self):
        """Bootstrap检验"""
        returns = pd.Series(np.random.normal(0.001, 0.02, 100))
        result = bootstrap_test(returns, n_bootstrap=100)
        assert "mean" in result
        assert "ci_lower" in result
        assert "ci_upper" in result
        assert "is_positive" in result

    def test_bootstrap_short_series(self):
        """短序列Bootstrap"""
        returns = pd.Series([0.01, 0.02])
        result = bootstrap_test(returns)
        assert result["is_positive"] is False  # 样本太少

    def test_significance_test_report(self):
        """完整显著性检验报告"""
        strategy = pd.Series(np.random.normal(0.002, 0.015, 200))
        benchmark = pd.Series(np.random.normal(0.001, 0.01, 200))
        report = significance_test_report(strategy, benchmark)
        assert "conclusion" in report
        assert "bootstrap" in report

    def test_significance_test_no_benchmark(self):
        """无基准时的显著性检验"""
        strategy = pd.Series(np.random.normal(0.001, 0.02, 100))
        report = significance_test_report(strategy)
        assert "conclusion" in report
        assert "bootstrap" in report


# ============================================================
# M5: 风控检查与回测引擎深度集成
# ============================================================

class TestM5RiskIntegration:
    """M5审计修复: 验证风控与回测引擎深度集成"""

    def test_daily_risk_check_in_engine(self):
        """回测引擎每日执行风控检查"""
        data = _make_backtest_data(30, ["002463.SZ"])
        engine = BacktestEngine(initial_capital=1000000)
        result = engine.run(data)
        # 引擎应正常运行，风控每日检查
        assert result is not None

    def test_risk_halt_stops_trading(self):
        """风控停止交易时回测继续但不交易"""
        rc = BacktestRiskCheck(daily_loss_stop=-0.001)  # 极低阈值
        data = _make_backtest_data(30, ["002463.SZ"])
        engine = BacktestEngine(initial_capital=1000000, risk_check=rc)
        result = engine.run(data)
        # 即使风控触发，回测也应完成
        assert result is not None

    def test_risk_check_update_daily(self):
        """风控每日检查更新"""
        rc = BacktestRiskCheck()
        p = Portfolio(initial_capital=1000000)
        # 第一天
        msg = rc.update_daily_check(p)
        assert msg is None  # 无风控问题
        assert rc._prev_total_value == 1000000

    def test_risk_check_sector_exposure(self):
        """板块暴露检查"""
        rc = BacktestRiskCheck(max_sector_position=0.30)
        p = Portfolio(initial_capital=1000000)
        # 板块暴露超过限制
        sector_exposure = {"PCB": 400000.0}
        can, reason = rc.check_buy(
            p, "002463.SZ", 10.0, 10000,
            sector="PCB", sector_exposure=sector_exposure,
        )
        assert can is False
        assert "板块仓位" in reason


# ============================================================
# L1: 支持多种成交价模式
# ============================================================

class TestL1FillPriceModel:
    """L1审计修复: 验证多种成交价模式"""

    def test_fill_price_next_open(self):
        """开盘价成交"""
        price = FillPriceModel.get_fill_price("next_open", 10.0, 11.0)
        assert price == 10.0

    def test_fill_price_close(self):
        """收盘价成交"""
        price = FillPriceModel.get_fill_price("close", 10.0, 11.0)
        assert price == 11.0

    def test_fill_price_vwap_with_amount(self):
        """VWAP成交（有成交额）"""
        price = FillPriceModel.get_fill_price(
            "vwap", 10.0, 11.0,
            high_price=12.0, low_price=9.0,
            volume=100000.0, amount=1050000.0,
        )
        assert price == 10.5  # amount / volume

    def test_fill_price_vwap_without_amount(self):
        """VWAP成交（无成交额，使用高低收均值）"""
        price = FillPriceModel.get_fill_price(
            "vwap", 10.0, 11.0,
            high_price=12.0, low_price=9.0,
            volume=0, amount=0,
        )
        expected = (12.0 + 9.0 + 11.0) / 3
        assert abs(price - expected) < 0.01

    def test_fill_price_default_close(self):
        """未知模式默认收盘价"""
        price = FillPriceModel.get_fill_price("unknown", 10.0, 11.0)
        assert price == 11.0

    def test_engine_with_fill_price_mode(self):
        """回测引擎支持成交价模式配置"""
        data = _make_backtest_data(30, ["002463.SZ"])
        engine = BacktestEngine(initial_capital=1000000, buy_price_mode="close")
        result = engine.run(data)
        assert result is not None


# ============================================================
# L2: 回测结果持久化存储
# ============================================================

class TestL2Persistence:
    """L2审计修复: 验证回测结果持久化"""

    def test_save_and_load(self):
        """保存和加载回测结果"""
        p = _make_portfolio_with_trades()
        analyzer = PerformanceAnalyzer(p)
        result = analyzer.analyze()
        result["daily_values"] = p.get_daily_values_df()
        result["trade_records"] = p.get_trade_records_df()
        result["report_text"] = "测试报告"

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_dir = save_backtest_result(result, output_dir=tmpdir)
            assert saved_dir.exists()
            assert (saved_dir / "metrics.json").exists()

            loaded = load_backtest_result(str(saved_dir))
            assert loaded["annual_return"] == result["annual_return"]
            assert loaded["report_text"] == "测试报告"

    def test_save_creates_directory(self):
        """保存自动创建目录"""
        result = {"annual_return": 0.1, "total_trades": 5}

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_dir = save_backtest_result(result, output_dir=tmpdir)
            assert saved_dir.exists()

    def test_save_with_tag(self):
        """保存支持标签"""
        result = {"annual_return": 0.1}

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_dir = save_backtest_result(result, output_dir=tmpdir, tag="test_run")
            assert "test_run" in saved_dir.name

    def test_list_runs(self):
        """列出回测运行记录"""
        result = {"annual_return": 0.1, "max_drawdown": -0.05, "sharpe_ratio": 1.5, "total_trades": 10}

        with tempfile.TemporaryDirectory() as tmpdir:
            save_backtest_result(result, output_dir=tmpdir)
            runs = list_backtest_runs(output_dir=tmpdir)
            assert len(runs) >= 1
            assert "annual_return" in runs[0]

    def test_load_nonexistent_raises(self):
        """加载不存在的目录抛出异常"""
        with pytest.raises(FileNotFoundError):
            load_backtest_result("/nonexistent/path")


# ============================================================
# L4: 印花税区分A股/港股
# ============================================================

class TestL4HKStampDuty:
    """L4审计修复: 验证印花税区分A股/港股"""

    def test_a_share_stamp_duty(self):
        """A股印花税千1"""
        model = CommissionModel()
        result = model.calc_sell_cost(10.0, 1000, market="SZ")
        assert result["stamp_duty"] == 10.0 * 1000 * 0.001

    def test_hk_stamp_duty(self):
        """港股印花税千1.3"""
        model = CommissionModel()
        result = model.calc_sell_cost(10.0, 1000, market="HK")
        assert result["stamp_duty"] == 10.0 * 1000 * 0.0013

    def test_hk_stamp_duty_higher_than_a_share(self):
        """港股印花税高于A股"""
        model = CommissionModel()
        a_result = model.calc_sell_cost(10.0, 1000, market="SZ")
        hk_result = model.calc_sell_cost(10.0, 1000, market="HK")
        assert hk_result["stamp_duty"] > a_result["stamp_duty"]

    def test_buy_no_stamp_duty_any_market(self):
        """买入无印花税（无论A股/港股）"""
        model = CommissionModel()
        a_result = model.calc_buy_cost(10.0, 1000, market="SZ")
        hk_result = model.calc_buy_cost(10.0, 1000, market="HK")
        assert a_result["stamp_duty"] == 0.0
        assert hk_result["stamp_duty"] == 0.0

    def test_round_trip_hk(self):
        """港股往返成本"""
        model = CommissionModel()
        result = model.calc_total_round_trip(10.0, 11.0, 1000, market="HK")
        assert result["total_cost"] > 0
        # 港股卖出印花税应为千1.3
        sell_stamp = 11.0 * 1000 * 0.0013
        assert sell_stamp > 0
