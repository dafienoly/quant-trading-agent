from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.product_app.market_data.contracts import DataQualityMetadata, QualityStatus
from src.product_app.market_data.quality import CallerContext, QualityGate


class TestCallerContext:
    def test_research_readonly_defaults(self):
        ctx = CallerContext(name="research_readonly")
        assert ctx.name == "research_readonly"
        assert ctx.allow_demo is False
        assert ctx.allow_mock is False

    def test_dashboard_observability_defaults(self):
        ctx = CallerContext(name="dashboard_observability")
        assert ctx.name == "dashboard_observability"

    def test_signal_generation_defaults(self):
        ctx = CallerContext(name="signal_generation")
        assert ctx.name == "signal_generation"
        assert ctx.allow_demo is False
        assert ctx.allow_mock is False

    def test_real_trading_defaults(self):
        ctx = CallerContext(name="real_trading")
        assert ctx.name == "real_trading"

    def test_position_sizing_defaults(self):
        ctx = CallerContext(name="position_sizing")
        assert ctx.name == "position_sizing"

    def test_with_allow_demo(self):
        ctx = CallerContext(name="research_readonly", allow_demo=True)
        assert ctx.allow_demo is True

    def test_with_allow_mock(self):
        ctx = CallerContext(name="research_readonly", allow_mock=True)
        assert ctx.allow_mock is True

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError):
            CallerContext(name="invalid_name")


class TestQualityGateBlocks:
    """QualityGate.blocks() must follow architecture §7 pseudocode exactly."""

    def _make_quality(
        self,
        quality_status: QualityStatus,
        is_stale: bool = False,
        is_mock: bool = False,
        is_demo: bool = False,
        is_fallback: bool = False,
    ) -> DataQualityMetadata:
        now = datetime.now(timezone.utc)
        return DataQualityMetadata(
            source_provider="test",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=1.0,
            quality_status=quality_status,
            quality_reason="test",
            request_id="r1",
            is_stale=is_stale,
            is_mock=is_mock,
            is_demo=is_demo,
            is_fallback=is_fallback,
        )

    # ------------------------------------------------------------------ #
    # UNAVAILABLE / INVALID — always block
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("status", [QualityStatus.UNAVAILABLE, QualityStatus.INVALID])
    def test_unavailable_and_invalid_block_research_and_signal(self, status):
        gate = QualityGate()
        quality = self._make_quality(status)
        ctx = CallerContext(name="research_readonly")
        assert gate.blocks(quality, ctx) is True
        ctx2 = CallerContext(name="signal_generation")
        assert gate.blocks(quality, ctx2) is True

    # ------------------------------------------------------------------ #
    # signal_generation — blocks stale / mock / demo / fallback / non-OK
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize(
        "status,is_stale,is_mock,is_demo,is_fallback",
        [
            (QualityStatus.STALE, True, False, False, False),
            (QualityStatus.OK, False, True, False, False),
            (QualityStatus.DEMO, False, False, True, False),
            (QualityStatus.FALLBACK, False, False, False, True),
            (QualityStatus.DEGRADED, False, False, False, False),
            (QualityStatus.MOCK, False, True, False, False),
        ],
    )
    def test_signal_generation_blocks_non_ok(self, status, is_stale, is_mock, is_demo, is_fallback):
        gate = QualityGate()
        quality = self._make_quality(
            quality_status=status,
            is_stale=is_stale,
            is_mock=is_mock,
            is_demo=is_demo,
            is_fallback=is_fallback,
        )
        ctx = CallerContext(name="signal_generation")
        assert gate.blocks(quality, ctx) is True

    def test_signal_generation_allows_ok(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.OK)
        ctx = CallerContext(name="signal_generation")
        assert gate.blocks(quality, ctx) is False

    # ------------------------------------------------------------------ #
    # real_trading — same as signal_generation (blocks non-OK)
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize(
        "status,is_stale,is_mock,is_demo,is_fallback",
        [
            (QualityStatus.STALE, True, False, False, False),
            (QualityStatus.OK, False, True, False, False),
            (QualityStatus.DEMO, False, False, True, False),
            (QualityStatus.FALLBACK, False, False, False, True),
        ],
    )
    def test_real_trading_blocks_non_ok(self, status, is_stale, is_mock, is_demo, is_fallback):
        gate = QualityGate()
        quality = self._make_quality(
            quality_status=status,
            is_stale=is_stale,
            is_mock=is_mock,
            is_demo=is_demo,
            is_fallback=is_fallback,
        )
        ctx = CallerContext(name="real_trading")
        assert gate.blocks(quality, ctx) is True

    def test_real_trading_allows_ok(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.OK)
        ctx = CallerContext(name="real_trading")
        assert gate.blocks(quality, ctx) is False

    # ------------------------------------------------------------------ #
    # position_sizing — same as signal_generation
    # ------------------------------------------------------------------ #

    def test_position_sizing_blocks_stale(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.STALE, is_stale=True)
        ctx = CallerContext(name="position_sizing")
        assert gate.blocks(quality, ctx) is True

    def test_position_sizing_allows_ok(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.OK)
        ctx = CallerContext(name="position_sizing")
        assert gate.blocks(quality, ctx) is False

    # ------------------------------------------------------------------ #
    # research_readonly — allows OK, DEGRADED, FALLBACK
    # but blocks MOCK/DEMO without allow_demo/allow_mock
    # ------------------------------------------------------------------ #

    def test_research_allows_ok(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.OK)
        ctx = CallerContext(name="research_readonly")
        assert gate.blocks(quality, ctx) is False

    def test_research_allows_degraded(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.DEGRADED)
        ctx = CallerContext(name="research_readonly")
        assert gate.blocks(quality, ctx) is False

    def test_research_allows_fallback(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.FALLBACK, is_fallback=True)
        ctx = CallerContext(name="research_readonly")
        assert gate.blocks(quality, ctx) is False

    def test_research_blocks_demo_without_allow(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.DEMO, is_demo=True)
        ctx = CallerContext(name="research_readonly", allow_demo=False)
        assert gate.blocks(quality, ctx) is True

    def test_research_allows_demo_with_allow(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.DEMO, is_demo=True)
        ctx = CallerContext(name="research_readonly", allow_demo=True)
        assert gate.blocks(quality, ctx) is False

    def test_research_blocks_mock_without_allow(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.MOCK, is_mock=True)
        ctx = CallerContext(name="research_readonly", allow_mock=False)
        assert gate.blocks(quality, ctx) is True

    def test_research_allows_mock_with_allow(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.MOCK, is_mock=True)
        ctx = CallerContext(name="research_readonly", allow_mock=True)
        assert gate.blocks(quality, ctx) is False

    # ------------------------------------------------------------------ #
    # dashboard_observability — allows all statuses
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize(
        "status,is_stale,is_mock,is_demo,is_fallback",
        [
            (QualityStatus.OK, False, False, False, False),
            (QualityStatus.STALE, True, False, False, False),
            (QualityStatus.DEGRADED, False, False, False, False),
            (QualityStatus.FALLBACK, False, False, False, True),
            (QualityStatus.UNAVAILABLE, False, False, False, False),
            (QualityStatus.INVALID, False, False, False, False),
            (QualityStatus.MOCK, False, True, False, False),
            (QualityStatus.DEMO, False, False, True, False),
        ],
    )
    def test_dashboard_allows_all(self, status, is_stale, is_mock, is_demo, is_fallback):
        gate = QualityGate()
        quality = self._make_quality(
            quality_status=status,
            is_stale=is_stale,
            is_mock=is_mock,
            is_demo=is_demo,
            is_fallback=is_fallback,
        )
        ctx = CallerContext(name="dashboard_observability")
        assert gate.blocks(quality, ctx) is False

    # ------------------------------------------------------------------ #
    # allow_demo / allow_mock gate
    # ------------------------------------------------------------------ #

    def test_allow_demo_false_blocks_demo(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.DEMO, is_demo=True)
        ctx = CallerContext(name="research_readonly", allow_demo=False)
        assert gate.blocks(quality, ctx) is True

    def test_allow_demo_true_passes_demo(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.DEMO, is_demo=True)
        ctx = CallerContext(name="research_readonly", allow_demo=True)
        assert gate.blocks(quality, ctx) is False

    def test_allow_mock_false_blocks_mock(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.MOCK, is_mock=True)
        ctx = CallerContext(name="research_readonly", allow_mock=False)
        assert gate.blocks(quality, ctx) is True

    def test_allow_mock_true_passes_mock(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.MOCK, is_mock=True)
        ctx = CallerContext(name="research_readonly", allow_mock=True)
        assert gate.blocks(quality, ctx) is False

    # ------------------------------------------------------------------ #
    # signal_generation + allow_demo=True — still blocks DEMO
    # DEMO is never allowed in signal_generation per architecture
    # ------------------------------------------------------------------ #

    def test_signal_generation_blocks_demo_even_with_allow_demo(self):
        gate = QualityGate()
        quality = self._make_quality(QualityStatus.DEMO, is_demo=True)
        ctx = CallerContext(name="signal_generation", allow_demo=True)
        assert gate.blocks(quality, ctx) is True


class TestQualityGateBlocksEdgeCases:
    def test_blocks_called_with_none_quality(self):
        gate = QualityGate()
        ctx = CallerContext(name="research_readonly")
        with pytest.raises(AttributeError):
            gate.blocks(None, ctx)  # type: ignore[arg-type]
