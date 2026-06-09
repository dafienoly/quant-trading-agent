"""成交记录与交易复盘 (EXECUTION_POLICY 1.5)

可追溯：每一笔订单必须有完整的日志链路，从信号 ID -> 风控 ID -> 订单 ID -> 成交记录。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.models.schemas import Order, TradeRecord


class TradeRecorder:
    """成交记录器 (EXECUTION_POLICY 1.5)"""

    def __init__(self, data_dir: str = "data/trade_records"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[TradeRecord] = []
        self._load_today_records()

    def _load_today_records(self):
        """加载当日记录"""
        today = datetime.now().strftime("%Y%m%d")
        filepath = self._data_dir / f"trades_{today}.json"
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._records = [TradeRecord(**r) for r in data]
                logger.info(f"TradeRecorder: 加载 {len(self._records)} 条当日记录")
            except Exception as e:
                logger.warning(f"TradeRecorder: 加载记录失败 {e}")
                self._records = []

    def record(self, trade: TradeRecord):
        """记录成交"""
        self._records.append(trade)
        self._save()
        logger.info(f"TradeRecorder: 记录成交 {trade.trade_id} {trade.side} {trade.symbol} x{trade.quantity}@{trade.price}")

    def record_from_order(self, order: Order, env: str = "paper"):
        """从订单生成成交记录"""
        if order.status != "FILLED" or order.fill_price is None:
            return
        trade = TradeRecord(
            trade_id=f"TRD_{datetime.now().strftime('%Y%m%d')}_{order.order_id.split('_')[-1]}",
            order_id=order.order_id,
            symbol=order.symbol,
            market=order.market,
            side=order.side,
            price=order.fill_price,
            quantity=order.fill_quantity or order.quantity,
            amount=order.fill_price * (order.fill_quantity or order.quantity),
            signal_id=order.signal_id,
            risk_check_id=order.risk_check_id,
            strategy_name=order.strategy_name,
            env=env,
        )
        self.record(trade)

    def _save(self):
        """保存当日记录"""
        today = datetime.now().strftime("%Y%m%d")
        filepath = self._data_dir / f"trades_{today}.json"
        try:
            data = [r.model_dump() for r in self._records]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"TradeRecorder: 保存记录失败 {e}")

    @property
    def records(self) -> list[TradeRecord]:
        return self._records.copy()

    def get_daily_summary(self) -> dict:
        """生成当日交易复盘摘要"""
        if not self._records:
            return {"total_trades": 0, "buy_count": 0, "sell_count": 0, "total_commission": 0.0, "total_stamp_duty": 0.0}

        buy_count = sum(1 for r in self._records if r.side == "BUY")
        sell_count = sum(1 for r in self._records if r.side == "SELL")
        total_commission = sum(r.commission for r in self._records)
        total_stamp_duty = sum(r.stamp_duty for r in self._records)
        total_amount = sum(r.amount for r in self._records)
        symbols = list(set(r.symbol for r in self._records))

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_trades": len(self._records),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "total_amount": round(total_amount, 2),
            "total_commission": round(total_commission, 2),
            "total_stamp_duty": round(total_stamp_duty, 2),
            "symbols": symbols,
            "env": self._records[0].env if self._records else "paper",
        }

    def get_trade_chain(self, signal_id: str) -> list[TradeRecord]:
        """根据信号ID追溯完整交易链路"""
        return [r for r in self._records if r.signal_id == signal_id]
