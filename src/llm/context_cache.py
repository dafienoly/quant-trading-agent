"""Context Prefix Cache — local stable prefix management for KV cache optimization.

DeepSeek service-side KV cache is enabled by default; its hit rate depends on
stable prompt prefixes. This module generates and caches those prefixes so that
repeated calls from the same task profile reuse the same prefix text, improving
cache hit probability.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

_SYSTEM_INVARIANTS = (
    "## Safety Invariants\n"
    "- Default: no real automatic trading.\n"
    "- Risk Agent has one-veto power.\n"
    "- All real orders must be traceable.\n"
    "- Data source failure blocks trading by default.\n"
    "- LLM must not directly decide buy or sell.\n"
    "- All secrets from environment variables only.\n"
)

_AGENT_PIPELINE_SUMMARY = (
    "## Development Pipeline\n"
    "User -> PM requirements -> Architect design -> Developer TDD -> "
    "Tester verification -> Code review -> PM acceptance -> Merge.\n"
)

_SAFETY_CONSTRAINTS = (
    "## LLM Constraints\n"
    "- Output structured JSON only.\n"
    "- Do not output trading decisions.\n"
    "- Do not bypass risk checks or human confirmation.\n"
    "- Do not reveal API keys, tokens, or credentials.\n"
)


@dataclass
class PrefixEntry:
    """A cached prefix entry persisted as JSON."""

    prefix_id: str
    profile: str
    fingerprint: str
    created_at: str
    source_files: list[str] = field(default_factory=list)
    prefix: str = ""


class ContextPrefixCache:
    """Builds, caches, and fingerprints stable system-prompt prefixes.

    Each profile gets one cache file. The cache is keyed by ``(profile, fingerprint)``,
    where fingerprint is SHA-256 of the assembled prefix text.
    """

    def __init__(self, cache_dir: str | None = None) -> None:
        self._cache_dir = Path(
            cache_dir or os.getenv("LLM_CONTEXT_CACHE_DIR", "runtime/llm_context_cache")
        )

    def build_prefix(
        self,
        profile: str,
        system_prompt: str,
        json_schema_prompt: str = "",
    ) -> PrefixEntry:
        """Assemble a stable prefix from invariants, pipeline summary, and profile content."""
        parts = [
            _SYSTEM_INVARIANTS,
            _AGENT_PIPELINE_SUMMARY,
            _SAFETY_CONSTRAINTS,
            f"## Task Profile: {profile}\n",
            system_prompt,
        ]
        if json_schema_prompt:
            parts.append(f"## JSON Schema\n{json_schema_prompt}\n")

        prefix_text = "\n\n".join(parts)
        fingerprint = hashlib.sha256(prefix_text.encode("utf-8")).hexdigest()[:32]
        prefix_id = f"{profile}:v1:{fingerprint}"

        entry = PrefixEntry(
            prefix_id=prefix_id,
            profile=profile,
            fingerprint=fingerprint,
            created_at=_now_iso(),
            source_files=[
                "SYSTEM_INVARIANTS",
                "docs/process/AGENT_DEVELOPMENT_PIPELINE.md",
            ],
            prefix=prefix_text,
        )
        self._save(entry)
        return entry

    def load(self, profile: str, fingerprint: str) -> PrefixEntry | None:
        """Load a previously cached prefix entry."""
        path = self._cache_path(profile, fingerprint)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return PrefixEntry(**data)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to load cache entry {}: {}", path, exc)
            return None

    def fingerprint(self, system_prompt: str) -> str:
        """Return SHA-256 fingerprint of the system prompt alone."""
        return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:32]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self, entry: PrefixEntry) -> None:
        path = self._cache_path(entry.profile, entry.fingerprint)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "prefix_id": entry.prefix_id,
                    "profile": entry.profile,
                    "fingerprint": entry.fingerprint,
                    "created_at": entry.created_at,
                    "source_files": entry.source_files,
                    "prefix": entry.prefix,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _cache_path(self, profile: str, fingerprint: str) -> Path:
        return self._cache_dir / profile / f"{fingerprint}.json"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
