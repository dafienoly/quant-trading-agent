"""测试数据存储"""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.storage import save_raw_data, save_cleaned_data, load_cleaned_data


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "symbol": ["002463.SZ"] * 3,
        "trade_date": ["20240101", "20240102", "20240103"],
        "open": [10.0, 10.5, 11.0],
        "close": [10.5, 11.0, 10.8],
        "high": [10.8, 11.2, 11.5],
        "low": [9.9, 10.3, 10.5],
        "volume": [100000, 120000, 90000],
    })


class TestStorage:
    def test_save_and_load(self, sample_df, tmp_path):
        with patch("src.utils.storage.CLEANED_DIR", tmp_path), \
             patch("src.utils.storage.RAW_DIR", tmp_path):
            save_cleaned_data(sample_df, "002463.SZ")
            loaded = load_cleaned_data("002463.SZ")
            assert not loaded.empty
            assert len(loaded) == 3
            assert loaded.iloc[0]["symbol"] == "002463.SZ"

    def test_load_nonexistent(self):
        result = load_cleaned_data("999999.XX")
        assert result.empty

    def test_date_filter(self, sample_df, tmp_path):
        with patch("src.utils.storage.CLEANED_DIR", tmp_path), \
             patch("src.utils.storage.RAW_DIR", tmp_path):
            save_cleaned_data(sample_df, "002463.SZ")
            loaded = load_cleaned_data("002463.SZ", start_date="20240102")
            assert len(loaded) == 2
