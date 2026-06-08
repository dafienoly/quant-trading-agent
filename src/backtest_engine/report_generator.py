"""回测报告生成器

实现 M3 审计修复：HTML 可视化回测报告输出。
包含：
- 策略概览（年化收益/最大回撤/夏普等）
- 净值曲线图
- 回撤曲线图
- 月度收益热力图
- 交易统计
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger


def generate_html_report(
    result: dict,
    output_path: str = "data/backtest_results/report.html",
    title: str = "回测报告",
) -> Path:
    """生成 HTML 格式回测报告"""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    daily_df = result.get("daily_values", pd.DataFrame())
    trades_df = result.get("trade_records", pd.DataFrame())

    # 构建净值曲线 JS 数据
    nav_data = ""
    drawdown_data = ""
    if not daily_df.empty and "trade_date" in daily_df.columns:
        nav_points = []
        dd_points = []
        cummax = daily_df["total_value"].cummax()
        drawdown = ((daily_df["total_value"] - cummax) / cummax * 100).round(2)

        for _, row in daily_df.iterrows():
            nav_points.append(f'["{row["trade_date"]}",{row["total_value"]:.2f}]')
            dd_points.append(f'["{row["trade_date"]}",{drawdown.get(_, 0):.2f}]')

        nav_data = ",\n".join(nav_points)
        drawdown_data = ",\n".join(dd_points)

    # 月度收益表格
    monthly_html = ""
    monthly = result.get("monthly_return", {})
    if monthly:
        rows = []
        for month, ret in sorted(monthly.items()):
            color = "#c6efce" if ret > 0 else "#ffc7ce" if ret < 0 else "#ffffff"
            rows.append(f'<tr><td>{month}</td><td style="background:{color}">{ret:.2%}</td></tr>')
        monthly_html = f'<table class="table"><tr><th>月份</th><th>收益率</th></tr>{"".join(rows)}</table>'

    # 交易统计
    trades_html = ""
    if not trades_df.empty:
        buy_count = len(trades_df[trades_df["side"] == "BUY"])
        sell_count = len(trades_df[trades_df["side"] == "SELL"])
        trades_html = f"""
        <div class="row">
            <div class="col">买入次数: {buy_count}</div>
            <div class="col">卖出次数: {sell_count}</div>
            <div class="col">总交易次数: {result.get('total_trades', 0)}</div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric {{ display: inline-block; margin: 10px 20px; text-align: center; }}
        .metric .value {{ font-size: 24px; font-weight: bold; }}
        .metric .label {{ font-size: 12px; color: #666; }}
        .positive {{ color: #e74c3c; }}
        .negative {{ color: #27ae60; }}
        .table {{ width: 100%; border-collapse: collapse; }}
        .table th, .table td {{ padding: 8px 12px; border: 1px solid #ddd; text-align: center; }}
        .table th {{ background: #f8f9fa; }}
        .row {{ display: flex; gap: 20px; }}
        .col {{ flex: 1; }}
        canvas {{ max-height: 400px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>{title}</h1>

    <div class="card">
        <h2>策略概览</h2>
        <div class="metric"><div class="value {'positive' if result.get('annual_return', 0) > 0 else 'negative'}">{result.get('annual_return', 0):.2%}</div><div class="label">年化收益</div></div>
        <div class="metric"><div class="value negative">{result.get('max_drawdown', 0):.2%}</div><div class="label">最大回撤</div></div>
        <div class="metric"><div class="value">{result.get('sharpe_ratio', 0):.2f}</div><div class="label">夏普比率</div></div>
        <div class="metric"><div class="value">{result.get('calmar_ratio', 0):.2f}</div><div class="label">Calmar比率</div></div>
        <div class="metric"><div class="value">{result.get('win_rate', 0):.2%}</div><div class="label">胜率</div></div>
        <div class="metric"><div class="value">{result.get('profit_loss_ratio', 0):.2f}</div><div class="label">盈亏比</div></div>
    </div>

    <div class="card">
        <h2>收益详情</h2>
        <div class="metric"><div class="value">{result.get('total_return', 0):.2%}</div><div class="label">总收益</div></div>
        <div class="metric"><div class="value">{result.get('cost_adjusted_return', 0):.2%}</div><div class="label">扣费后收益</div></div>
        <div class="metric"><div class="value">{result.get('benchmark_return', 0):.2%}</div><div class="label">基准收益</div></div>
        <div class="metric"><div class="value {'positive' if result.get('excess_return', 0) > 0 else 'negative'}">{result.get('excess_return', 0):.2%}</div><div class="label">超额收益</div></div>
        <div class="metric"><div class="value">{result.get('turnover', 0):.2%}</div><div class="label">换手率</div></div>
    </div>

    <div class="card">
        <h2>交易成本</h2>
        <div class="metric"><div class="value">{result.get('total_commission', 0):,.2f}</div><div class="label">总佣金</div></div>
        <div class="metric"><div class="value">{result.get('total_stamp_duty', 0):,.2f}</div><div class="label">总印花税</div></div>
        <div class="metric"><div class="value">{result.get('total_slippage', 0):,.2f}</div><div class="label">总滑点</div></div>
        <div class="metric"><div class="value">{result.get('total_cost', 0):,.2f}</div><div class="label">总成本</div></div>
    </div>

    <div class="card">
        <h2>净值曲线</h2>
        <canvas id="navChart"></canvas>
    </div>

    <div class="card">
        <h2>回撤曲线</h2>
        <canvas id="drawdownChart"></canvas>
    </div>

    {"<div class='card'><h2>月度收益</h2>" + monthly_html + "</div>" if monthly_html else ""}

    {"<div class='card'><h2>交易统计</h2>" + trades_html + "</div>" if trades_html else ""}
</div>

<script>
new Chart(document.getElementById('navChart'), {{
    type: 'line',
    data: {{
        labels: [{nav_data}].map(d => d[0]),
        datasets: [{{
            label: '总资产',
            data: [{nav_data}].map(d => d[1]),
            borderColor: '#3498db',
            fill: false,
            pointRadius: 0,
        }}]
    }},
    options: {{ responsive: true, scales: {{ x: {{ display: true, ticks: {{ maxTicksLimit: 12 }} }} }} }}
}});

new Chart(document.getElementById('drawdownChart'), {{
    type: 'line',
    data: {{
        labels: [{drawdown_data}].map(d => d[0]),
        datasets: [{{
            label: '回撤(%)',
            data: [{drawdown_data}].map(d => d[1]),
            borderColor: '#e74c3c',
            backgroundColor: 'rgba(231,76,60,0.1)',
            fill: true,
            pointRadius: 0,
        }}]
    }},
    options: {{ responsive: true, scales: {{ x: {{ display: true, ticks: {{ maxTicksLimit: 12 }} }} }} }}
}});
</script>
</body>
</html>"""

    output.write_text(html, encoding="utf-8")
    logger.info(f"HTML报告已保存: {output}")
    return output
