"""回测结果持久化存储

实现 L2 审计修复：回测结果保存到本地文件，支持加载和比较。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from loguru import logger


DEFAULT_OUTPUT_DIR = Path("data/backtest_results")


def save_backtest_result(
    result: dict,
    output_dir: Optional[str] = None,
    tag: str = "",
) -> Path:
    """保存回测结果到本地文件"""
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag_suffix = f"_{tag}" if tag else ""
    run_dir = out_dir / f"run_{timestamp}{tag_suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # 保存绩效指标（排除 DataFrame）
    metrics = {k: v for k, v in result.items() if not isinstance(v, pd.DataFrame)}
    # 排除不可序列化的字段
    for key in ["events", "trade_records", "daily_values"]:
        metrics.pop(key, None)
    # monthly_return/yearly_return 是 dict，需要转换
    for key in ["monthly_return", "yearly_return"]:
        if key in metrics and isinstance(metrics[key], dict):
            metrics[key] = {str(k): v for k, v in metrics[key].items()}

    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # 保存交易记录
    if "trade_records" in result and isinstance(result["trade_records"], pd.DataFrame) and not result["trade_records"].empty:
        result["trade_records"].to_csv(run_dir / "trade_records.csv", index=False, encoding="utf-8-sig")

    # 保存每日资产
    if "daily_values" in result and isinstance(result["daily_values"], pd.DataFrame) and not result["daily_values"].empty:
        result["daily_values"].to_csv(run_dir / "daily_values.csv", index=False, encoding="utf-8-sig")

    # 保存报告文本
    if "report_text" in result:
        (run_dir / "report.txt").write_text(result["report_text"], encoding="utf-8")

    logger.info(f"回测结果已保存: {run_dir}")
    return run_dir


def load_backtest_result(run_dir: str) -> dict:
    """加载回测结果"""
    run_path = Path(run_dir)
    if not run_path.exists():
        raise FileNotFoundError(f"回测结果目录不存在: {run_dir}")

    result = {}

    # 加载指标
    metrics_path = run_path / "metrics.json"
    if metrics_path.exists():
        result.update(json.loads(metrics_path.read_text(encoding="utf-8")))

    # 加载交易记录
    trades_path = run_path / "trade_records.csv"
    if trades_path.exists():
        result["trade_records"] = pd.read_csv(trades_path, encoding="utf-8-sig")

    # 加载每日资产
    daily_path = run_path / "daily_values.csv"
    if daily_path.exists():
        result["daily_values"] = pd.read_csv(daily_path, encoding="utf-8-sig")

    # 加载报告
    report_path = run_path / "report.txt"
    if report_path.exists():
        result["report_text"] = report_path.read_text(encoding="utf-8")

    return result


def list_backtest_runs(output_dir: Optional[str] = None) -> list:
    """列出所有回测运行记录"""
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not out_dir.exists():
        return []

    runs = []
    for d in sorted(out_dir.iterdir()):
        if d.is_dir() and d.name.startswith("run_"):
            metrics_path = d / "metrics.json"
            if metrics_path.exists():
                try:
                    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                    runs.append({
                        "dir": str(d),
                        "name": d.name,
                        "annual_return": metrics.get("annual_return", 0),
                        "max_drawdown": metrics.get("max_drawdown", 0),
                        "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                        "total_trades": metrics.get("total_trades", 0),
                    })
                except Exception:
                    runs.append({"dir": str(d), "name": d.name})

    return runs
