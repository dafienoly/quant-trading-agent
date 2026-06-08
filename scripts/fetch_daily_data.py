"""
Phase 1 数据获取入口脚本

用法：
  python scripts/fetch_daily_data.py --pool semiconductor --start-date 20240101 --end-date 20250101
  python scripts/fetch_daily_data.py --pool all --start-date 20240101
  python scripts/fetch_daily_data.py --symbols 002463,600584 --start-date 20240101
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from src.data_gateway.akshare_provider import AkShareProvider
from src.stock_pool.mainboard_filter import filter_tradeable
from src.stock_pool.semiconductor import SemiconductorPool
from src.utils.calendar import TradeCalendar
from src.utils.quality import (
    generate_quality_report,
    generate_data_missing_report,
    generate_data_delay_report,
)
from src.utils.storage import (
    save_raw_data,
    save_cleaned_data,
    save_quality_report,
    save_data_missing_report,
    save_data_delay_report,
)


def parse_args():
    parser = argparse.ArgumentParser(description="量化交易系统 - 日线数据获取")
    parser.add_argument(
        "--pool",
        choices=["semiconductor", "all"],
        default="semiconductor",
        help="股票池: semiconductor(半导体主题) 或 all(全市场主板)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="指定股票代码，逗号分隔 (如 002463,600584)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="起始日期 YYYYMMDD",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y%m%d"),
        help="截止日期 YYYYMMDD (默认今天)",
    )
    parser.add_argument(
        "--provider",
        choices=["akshare", "aktools"],
        default="akshare",
        help="数据源: akshare(直接调用) 或 aktools(HTTP API)",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="同时获取关注指数日线数据",
    )
    return parser.parse_args()


def get_provider(name: str):
    if name == "aktools":
        from src.data_gateway.aktools_provider import AkToolsProvider
        return AkToolsProvider()
    return AkShareProvider()


def main():
    args = parse_args()
    logger.info(f"=== Phase 1 数据获取 ===")
    logger.info(f"日期范围: {args.start_date} ~ {args.end_date}")
    logger.info(f"股票池: {args.pool}")
    logger.info(f"数据源: {args.provider}")

    provider = get_provider(args.provider)

    # 1. 加载交易日历
    calendar = TradeCalendar(provider)
    calendar.load()
    trade_dates = calendar.get_trade_dates_between(args.start_date, args.end_date)
    logger.info(f"交易日历: {len(trade_dates)} 个交易日")

    # 2. 确定目标股票列表
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
        logger.info(f"指定股票: {symbols}")
    elif args.pool == "semiconductor":
        pool = SemiconductorPool()
        symbols = pool.get_symbols_with_market()
        logger.info(f"半导体主题池: {len(symbols)} 只股票")
    else:
        stock_list = provider.get_stock_list()
        if stock_list.empty:
            logger.error("获取股票列表失败")
            return
        tradeable = filter_tradeable(stock_list)
        symbols = tradeable["symbol"].tolist()
        logger.info(f"全市场主板可交易: {len(symbols)} 只股票")

    # 3. 获取日线数据
    logger.info(f"开始获取 {len(symbols)} 只股票的日线数据...")
    fetch_start_time = datetime.now()
    start_time = time.time()

    df = provider.get_daily_bars(symbols, args.start_date, args.end_date)

    elapsed = time.time() - start_time
    fetch_end_time = datetime.now()
    logger.info(f"数据获取完成: {len(df)} 行, 耗时 {elapsed:.1f}s")

    if df.empty:
        logger.error("未获取到任何数据")
        return

    # 4. 按股票分组保存 + 质量检查
    quality_reports = []
    grouped = df.groupby("symbol")

    for symbol, group_df in grouped:
        code = symbol.split(".")[0]

        save_raw_data(group_df, symbol)
        save_cleaned_data(group_df, symbol)

        report = generate_quality_report(group_df, symbol, trade_dates)
        save_quality_report(report, symbol)
        quality_reports.append(report)

    # 5. 生成数据缺失报告 (AGENTS.md 3.2)
    missing_report = generate_data_missing_report(quality_reports)
    save_data_missing_report(missing_report)

    # 6. 生成数据延迟报告 (AGENTS.md 3.2)
    delay_report = generate_data_delay_report(
        provider=args.provider,
        symbols=symbols,
        fetch_start_time=fetch_start_time,
        fetch_end_time=fetch_end_time,
    )
    save_data_delay_report(delay_report)

    # 7. 获取指数数据（可选）
    if args.index:
        pool = SemiconductorPool()
        indices = pool.get_watch_indices()
        for idx in indices:
            idx_symbol = idx["symbol"]
            idx_name = idx["name"]
            logger.info(f"获取指数: {idx_name} ({idx_symbol})")
            idx_df = provider.get_index_daily_bars(idx_symbol, args.start_date, args.end_date)
            if not idx_df.empty:
                save_cleaned_data(idx_df, f"IDX_{idx_symbol}")
                logger.info(f"  指数 {idx_name}: {len(idx_df)} 行")

    # 8. 汇总
    acceptable = sum(1 for r in quality_reports if r.is_acceptable)
    logger.info("=" * 60)
    logger.info(f"数据获取汇总:")
    logger.info(f"  股票数: {len(symbols)}")
    logger.info(f"  总数据行: {len(df)}")
    logger.info(f"  质量合格: {acceptable}/{len(quality_reports)}")
    logger.info(f"  耗时: {elapsed:.1f}s")
    logger.info(f"  缺失报告: {missing_report.summary}")
    logger.info(f"  延迟报告: avg={delay_report.avg_latency_seconds}s, "
                f"acceptable={delay_report.is_acceptable}")

    if acceptable < len(quality_reports):
        failed = [r.symbol for r in quality_reports if not r.is_acceptable]
        logger.warning(f"  质量不合格: {failed}")
        for r in quality_reports:
            if not r.is_acceptable:
                logger.warning(f"    {r.symbol}: {r.issues}")


if __name__ == "__main__":
    main()
