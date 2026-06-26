from __future__ import annotations

from pydantic import BaseModel, field_validator

from src.product_app.market_data.contracts import DataQualityMetadata, QualityStatus

_VALID_CALLER_CONTEXTS = frozenset({
    "research_readonly",
    "dashboard_observability",
    "signal_generation",
    "real_trading",
    "position_sizing",
})


class CallerContext(BaseModel):
    name: str
    allow_demo: bool = False
    allow_mock: bool = False

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if v not in _VALID_CALLER_CONTEXTS:
            raise ValueError(f"Invalid caller_context: {v!r}. Must be one of {sorted(_VALID_CALLER_CONTEXTS)}")
        return v


class QualityGate:
    @staticmethod
    def blocks(quality: DataQualityMetadata, caller_context: CallerContext) -> bool:
        if caller_context.name == "dashboard_observability":
            return False

        if quality.quality_status in (QualityStatus.UNAVAILABLE, QualityStatus.INVALID):
            return True

        if caller_context.name in ("signal_generation", "real_trading", "position_sizing"):
            if quality.is_stale or quality.is_mock or quality.is_demo:
                return True
            if quality.is_fallback:
                return True
            if quality.quality_status != QualityStatus.OK:
                return True

        if not caller_context.allow_demo and quality.is_demo:
            return True

        if not caller_context.allow_mock and quality.is_mock:
            return True

        return False
