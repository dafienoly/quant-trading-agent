from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yaml
from loguru import logger

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "stock_pool.yaml"


class SemiconductorPool:

    def __init__(self, config_path: Path = CONFIG_PATH):
        self._config_path = config_path
        self._config: dict = {}
        self._stock_sector_map: Dict[str, str] = {}
        self._load()

    def _load(self):
        if not self._config_path.exists():
            logger.error(f"Stock pool config not found: {self._config_path}")
            return
        with open(self._config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        pool = self._config.get("semiconductor_pool", {})
        for sector_key, sector_data in pool.items():
            for stock in sector_data.get("stocks", []):
                symbol = stock["symbol"]
                self._stock_sector_map[symbol] = sector_key

        logger.info(
            f"Semiconductor pool loaded: {len(self._stock_sector_map)} stocks "
            f"across {len(pool)} sectors"
        )

    def get_symbols(self) -> List[str]:
        return list(self._stock_sector_map.keys())

    def get_symbols_with_market(self) -> List[str]:
        result = []
        pool = self._config.get("semiconductor_pool", {})
        for sector_key, sector_data in pool.items():
            for stock in sector_data.get("stocks", []):
                symbol = stock["symbol"]
                market = stock.get("market", "")
                result.append(f"{symbol}.{market}")
        return result

    def get_sector(self, symbol: str) -> Optional[str]:
        code = symbol.split(".")[0] if "." in symbol else symbol
        return self._stock_sector_map.get(code)

    def get_sector_name(self, symbol: str) -> Optional[str]:
        sector_key = self.get_sector(symbol)
        if not sector_key:
            return None
        pool = self._config.get("semiconductor_pool", {})
        sector_data = pool.get(sector_key, {})
        return sector_data.get("name", sector_key)

    def get_stocks_by_sector(self) -> Dict[str, List[dict]]:
        pool = self._config.get("semiconductor_pool", {})
        result = {}
        for sector_key, sector_data in pool.items():
            result[sector_key] = {
                "name": sector_data.get("name", sector_key),
                "stocks": sector_data.get("stocks", []),
            }
        return result

    def get_policy_weights(self) -> Dict[str, int]:
        return self._config.get("sector_policy_weight", {})

    def get_watch_indices(self) -> List[dict]:
        return self._config.get("watch_indices", [])

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        pool = self._config.get("semiconductor_pool", {})
        for sector_key, sector_data in pool.items():
            for stock in sector_data.get("stocks", []):
                rows.append({
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "market": stock.get("market", ""),
                    "sector_key": sector_key,
                    "sector_name": sector_data.get("name", sector_key),
                })
        return pd.DataFrame(rows)
