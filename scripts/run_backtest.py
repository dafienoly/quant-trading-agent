"""
Phase 3 回测入口脚本

用法：
  python scripts/run_backtest.py --start-date 20240101 --end-date 20241231 --capital 1000000
  python scripts/run_backtest.py --start-date 20240101 --end-date 20241231 --in-sample-end 20240630
  python scripts/run_backtest.py --start-date 20240101 --end-date 20241231 --symbols 002463,600584
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from src.backtest_engine.engine import BacktestEngine
from src.backtest_engine.commission_model import CommissionModel
from src.backtest_engine.risk_check import BacktestRiskCheck
from src.data_gateway.akshare_provider import AkShareProvider
from src.stock_pool.semiconductor import SemiconductorPool
from src.utils.storage import save_cleaned_data


def parse_args():
    parser = argparse.ArgumentParser(description="量化交易系统 - 策略回测")
    parser.add_argument("--start-date", type=str, required=True, help="回测起始日期 YYYYMMDD")
    parser.add_argument("--end-date", type=str, required=True, help="回测截止日期 YYYYMMDD")
    parser.add_argument("--capital", type=float, default=1000000.0, help="初始资金（默认100万）")
    parser.add_argument("--in-sample-end", type=str, default=None, help="样本内截止日期（用于样本外测试）")
    parser.add_argument("--symbols", type=str, default=None, help="指定股票代码，逗号分隔")
    parser.add_argument("--commission-rate", type=float, default=0.0003, help="佣金费率（默认万3）")
    parser.add_argument("--stamp-duty-rate", type=float, default=0.001, help="印花税费率（默认千1）")
    parser.add_argument("--slippage-rate", type=float, default=0.001, help="滑点费率（默认千1）")
    parser.add_argument("--output-dir", type=str, default="data/backtest_results", help="输出目录")
    return parser.parse_args()


def main():
    args = parse_args()
    logger.info("=" * 60)
    logger.info("Phase 3 策略回测")
    logger.info("=" * 60)
    logger.info(f"回测区间: {args.start_date} ~ {args.end_date}")
    logger.info(f"初始资金: {args.capital:,.0f}")

    # 1. 加载股票池
    pool = SemiconductorPool()
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        symbols = pool.get_symbols_with_market()
    logger.info(f"股票池: {len(symbols)} 只")

    # 2. 获取历史数据
    provider = AkShareProvider()
    logger.info("获取历史数据...")
    data = provider.get_daily_bars(symbols, args.start_date, args.end_date)

    if data.empty:
        logger.error("未获取到数据")
        return

    logger.info(f"数据加载完成: {len(data)} 行")

    # 3. 获取基准数据
    benchmark_data = None
    try:
        benchmark_data = provider.get_index_daily_bars("000001", args.start_date, args.end_date)
        logger.info(f"基准数据: {len(benchmark_data)} 行")
    except Exception as e:
        logger.warning(f"获取基准数据失败: {e}")

    # 4. 配置回测引擎
    commission = CommissionModel(
        commission_rate=args.commission_rate,
        stamp_duty_rate=args.stamp_duty_rate,
        slippage_rate=args.slippage_rate,
    )
    risk_check = BacktestRiskCheck()
    engine = BacktestEngine(
        initial_capital=args.capital,
        commission_model=commission,
        risk_check=risk_check,
        pool=pool,
    )

    # 5. 执行回测
    logger.info("开始回测...")
    result = engine.run(data, benchmark_data=benchmark_data)

    if not result:
        logger.error("回测失败")
        return

    # 6. 输出报告
    print(result["report_text"])

    # 7. 保存结果
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 保存报告文本
    report_path = output_dir / f"backtest_report_{timestamp}.txt"
    report_path.write_text(result["report_text"], encoding="utf-8")
    logger.info(f"报告已保存: {report_path}")

    # 保存每日资产
    if not result["daily_values"].empty:
        daily_path = output_dir / f"daily_values_{timestamp}.csv"
        result["daily_values"].to_csv(daily_path, index=False, encoding="utf-8-sig")
        logger.info(f"每日资产已保存: {daily_path}")

    # 保存交易记录
    if not result["trade_records"].empty:
        trades_path = output_dir / f"trade_records_{timestamp}.csv"
        result["trade_records"].to_csv(trades_path, index=False, encoding="utf-8-sig")
        logger.info(f"交易记录已保存: {trades_path}")

    # 8. 样本外测试（如果指定了样本内截止日期）
    if args.in_sample_end:
        logger.info("=" * 60)
        logger.info("样本外测试")
        logger.info(f"样本内: {args.start_date} ~ {args.in_sample_end}")
        logger.info(f"样本外: {args.in_sample_end} ~ {args.end_date}")

        in_sample_data = data[data["trade_date"] <= args.in_sample_end]
        out_sample_data = data[data["trade_date"] > args.in_sample_end]

        if not out_sample_data.empty:
            out_risk = BacktestRiskCheck()
            out_engine = BacktestEngine(
                initial_capital=args.capital,
                commission_model=commission,
                risk_check=out_risk,
                pool=pool,
            )
            out_result = out_engine.run(out_sample_data, benchmark_data=benchmark_data)

            if out_result:
                logger.info("-" * 60)
                logger.info("样本外结果:")
                print(out_result["report_text"])

                # 比较样本内外
                in_annual = result.get("annual_return", 0)
                out_annual = out_result.get("annual_return", 0)
                degradation = in_annual - out_annual

                if degradation > 0.10:
                    logger.warning(f"样本外年化收益劣化{degradation:.2%}，可能存在过拟合")
                else:
                    logger.info(f"样本外劣化{degradation:.2%}，在可接受范围内")


if __name__ == "__main__":
    main()
