"""Bug feedback indexing package.

This package is intentionally read-only. It scans repository-local feedback
artifacts and returns secret-safe summary models for AgentOps and diagnostics.
"""

from .contracts import BugFeedbackItem, BugFeedbackSeverity, BugFeedbackStatus, BugFeedbackSummary
from .indexer import build_bug_feedback_summary

__all__ = [
    "BugFeedbackItem",
    "BugFeedbackSeverity",
    "BugFeedbackStatus",
    "BugFeedbackSummary",
    "build_bug_feedback_summary",
]
