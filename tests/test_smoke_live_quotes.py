"""Architecture Review R2 修复测试：smoke_live_quotes.py

覆盖四种场景，mock 掉外部 provider，不调用真实网络。
"""
from __future__ import annotations

import json
import sys

import pytest


def _fake_service(data_status: str, quote_count: int, is_demo: bool = False):
    """构造一个 FakeService，返回指定数量的行情记录。"""
    class FakeService:
        def get_realtime_quotes(self, symbols, pool_type="watchlist", allow_demo=False):
            quotes = [
                {
                    "symbol": s,
                    "last_price": 10.0 + i,
                    "volume": 100000 * (i + 1),
                    "updated_at": "2026-06-11T10:00:00+08:00",
                    "data_source": "fake",
                }
                for i, s in enumerate(symbols[:quote_count])
            ]
            return {
                "data_status": data_status,
                "chosen_provider": "fake",
                "fallback_chain": ["fake: ok"],
                "data_delay_report": {"elapsed_ms": 15.0},
                "is_demo": is_demo,
                "feedback_bug_id": "BUG_FAKE_001" if data_status == "FAILED" else None,
                "quotes": quotes,
            }
    return FakeService()


class TestSmokeLiveQuotes:
    """smoke_live_quotes.py 的 exit code 和 JSON 输出契约测试"""

    @pytest.fixture(autouse=True)
    def _import_and_clean(self):
        # 清理模块缓存，确保每个测试独立导入
        for mod in list(sys.modules.keys()):
            if "smoke_live_quotes" in mod:
                del sys.modules[mod]
        # 确保脚本目录在 path 中
        if "scripts" not in sys.path:
            sys.path.insert(0, "scripts")

    # ================================================================
    # 1. Full success
    # ================================================================

    def test_full_success(self, tmp_path, monkeypatch):
        """mock 返回 OK，quotes 数量 >= min-success → exit 0, status=passed"""
        from unittest.mock import patch

        output = tmp_path / "smoke-full.json"

        monkeypatch.setattr(sys, "argv", [
            "smoke_live_quotes.py",
            "--symbols", "600000.SH,000001.SZ,600584.SH",
            "--min-success", "2",
            "--output", str(output),
        ])

        with patch(
            "src.product_app.live_data_service.get_live_data_service",
            return_value=_fake_service("OK", 3),
        ):
            import smoke_live_quotes as smoke
            rc = smoke.main()

        assert rc == 0, f"Expected exit 0, got {rc}"

        assert output.exists(), "JSON output not written"
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["status"] == "passed"
        assert report["symbols_requested"] == 3
        assert report["symbols_succeeded"] == 3
        assert report["provider"] == "fake"
        assert report["fallback_chain"] == ["fake: ok"]
        assert report["data_status"] == "OK"
        assert report["is_demo"] is False
        assert report["updated_at_min"] == "2026-06-11T10:00:00+08:00"
        assert report["updated_at_max"] == "2026-06-11T10:00:00+08:00"
        assert len(report["quotes_sample"]) == 3

    # ================================================================
    # 2. Partial success
    # ================================================================

    def test_partial_success(self, tmp_path, monkeypatch):
        """mock 返回 OK，但 quotes 数量 < min-success → exit 3, status=partial"""
        from unittest.mock import patch

        output = tmp_path / "smoke-partial.json"

        monkeypatch.setattr(sys, "argv", [
            "smoke_live_quotes.py",
            "--symbols", "600000.SH,000001.SZ,600584.SH",
            "--min-success", "5",
            "--output", str(output),
        ])

        with patch(
            "src.product_app.live_data_service.get_live_data_service",
            return_value=_fake_service("OK", 2),
        ):
            import smoke_live_quotes as smoke
            rc = smoke.main()

        assert rc == 3, f"Expected exit 3, got {rc}"

        assert output.exists()
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["status"] == "partial"
        assert report["symbols_requested"] == 3
        assert report["symbols_succeeded"] == 2
        assert report["data_status"] == "OK"
        assert report["is_demo"] is False

    # ================================================================
    # 3. All providers failed
    # ================================================================

    def test_all_providers_failed(self, tmp_path, monkeypatch):
        """mock 返回 FAILED，quotes 为空 → exit 2, status=failed, feedback_bug_id 存在"""
        from unittest.mock import patch

        output = tmp_path / "smoke-failed.json"

        monkeypatch.setattr(sys, "argv", [
            "smoke_live_quotes.py",
            "--symbols", "600000.SH,000001.SZ",
            "--min-success", "2",
            "--output", str(output),
        ])

        with patch(
            "src.product_app.live_data_service.get_live_data_service",
            return_value=_fake_service("FAILED", 0),
        ):
            import smoke_live_quotes as smoke
            rc = smoke.main()

        assert rc == 2, f"Expected exit 2, got {rc}"

        assert output.exists()
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["status"] == "failed"
        assert report["data_status"] == "FAILED"
        assert report["symbols_succeeded"] == 0
        assert report["is_demo"] is False
        assert report["feedback_bug_id"] == "BUG_FAKE_001"

    # ================================================================
    # 4. Demo blocked
    # ================================================================

    def test_demo_blocked_without_flag(self, tmp_path, monkeypatch):
        """mock 返回 is_demo=True 且未传 --allow-demo → exit 2, status=failed"""
        from unittest.mock import patch

        output = tmp_path / "smoke-demo-blocked.json"

        monkeypatch.setattr(sys, "argv", [
            "smoke_live_quotes.py",
            "--symbols", "600000.SH,000001.SZ",
            "--min-success", "2",
            "--output", str(output),
        ])

        with patch(
            "src.product_app.live_data_service.get_live_data_service",
            return_value=_fake_service("OK", 2, is_demo=True),
        ):
            import smoke_live_quotes as smoke
            rc = smoke.main()

        assert rc == 2, f"Expected exit 2, got {rc}"

        assert output.exists()
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["status"] == "failed"
        assert report["is_demo"] is True
        assert report["data_status"] == "OK"
        # 即使数据是 OK，因为 is_demo 且未传 --allow-demo，必须拒绝

    def test_demo_allowed_with_flag(self, tmp_path, monkeypatch):
        """mock 返回 is_demo=True 且传 --allow-demo → 可以通过（仅供测试辅助）"""
        from unittest.mock import patch

        output = tmp_path / "smoke-demo-allowed.json"

        monkeypatch.setattr(sys, "argv", [
            "smoke_live_quotes.py",
            "--symbols", "600000.SH,000001.SZ",
            "--min-success", "2",
            "--allow-demo",
            "--output", str(output),
        ])

        with patch(
            "src.product_app.live_data_service.get_live_data_service",
            return_value=_fake_service("OK", 2, is_demo=True),
        ):
            import smoke_live_quotes as smoke
            rc = smoke.main()

        assert rc == 0, f"Expected exit 0 with --allow-demo, got {rc}"
        assert output.exists()
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["status"] == "passed"

    # ================================================================
    # 5. Invalid arguments
    # ================================================================

    def test_empty_symbols(self, monkeypatch):
        """空 symbols → exit 1"""
        monkeypatch.setattr(sys, "argv", [
            "smoke_live_quotes.py",
            "--symbols", "",
            "--min-success", "2",
        ])
        import smoke_live_quotes as smoke
        rc = smoke.main()
        assert rc == 1

    def test_negative_min_success(self, monkeypatch):
        """min-success < 1 → exit 1"""
        monkeypatch.setattr(sys, "argv", [
            "smoke_live_quotes.py",
            "--symbols", "600000.SH",
            "--min-success", "0",
        ])
        import smoke_live_quotes as smoke
        rc = smoke.main()
        assert rc == 1

    # ================================================================
    # 6. Service exception
    # ================================================================

    def test_service_exception(self, tmp_path, monkeypatch):
        """get_live_data_service 抛出异常 → exit 1, fallback_chain 记录"""
        from unittest.mock import patch

        output = tmp_path / "smoke-exception.json"

        monkeypatch.setattr(sys, "argv", [
            "smoke_live_quotes.py",
            "--symbols", "600000.SH",
            "--min-success", "1",
            "--output", str(output),
        ])

        def _raise(*args, **kwargs):
            raise RuntimeError("Service is down")

        with patch(
            "src.product_app.live_data_service.get_live_data_service",
            side_effect=_raise,
        ):
            import smoke_live_quotes as smoke
            rc = smoke.main()

        assert rc == 1, f"Expected exit 1, got {rc}"

        assert output.exists()
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["fallback_chain"] == ["service_error: Service is down"]
