"""Agent runtime abstraction package.

This package is intentionally read-only: it resolves runtime profiles and audit
metadata, but never executes configured Agent commands.
"""

from .contracts import AgentRuntimeProfile, RuntimeMode, RuntimeProvider
from .resolver import resolve_agent_runtime

__all__ = [
    "AgentRuntimeProfile",
    "RuntimeMode",
    "RuntimeProvider",
    "resolve_agent_runtime",
]
