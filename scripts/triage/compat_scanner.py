"""Scan changed files against current module structure, detect deleted/renamed files."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Known restricted / safety-sensitive modules from AGENTS.md / architecture
RESTRICTED_MODULES = {
    "src/risk_engine",
    "src/execution_engine",
    "src/data_gateway",
    "src/backtest_engine",
    "src/factor_engine",
    "src/strategy_engine",
    "src/stock_pool",
    "src/api",
    "src/product_app",
    "src/ui_report",
}

SAFETY_SENSITIVE_PATTERNS = [
    re.compile(r"LEVEL_3_AUTO"),
    re.compile(r"allow_demo\s*=\s*True"),
    re.compile(r"bypass.*risk", re.IGNORECASE),
    re.compile(r"bypass.*confirm", re.IGNORECASE),
    re.compile(r"bypass.*veto", re.IGNORECASE),
    re.compile(r"\.env"),
    re.compile(r"api_key"),
    re.compile(r"api_secret"),
    re.compile(r"access_token"),
    re.compile(r"broker.*credential", re.IGNORECASE),
]


@dataclass
class CompatibilityResult:
    """Result of a compatibility scan for a single PR."""

    pr_number: int
    all_changed_files: list[str] = field(default_factory=list)
    existing_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    restricted_hits: list[str] = field(default_factory=list)
    safety_pattern_hits: list[str] = field(default_factory=list)
    obsolete_paths: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    doc_files: list[str] = field(default_factory=list)
    code_files: list[str] = field(default_factory=list)


def scan_changed_files(
    pr_number: int,
    changed_files: list[str],
    repo_root: Optional[str] = None,
) -> CompatibilityResult:
    """Scan a list of changed files against the current repository structure.

    Args:
        pr_number: PR number (for record keeping).
        changed_files: List of file paths from the PR diff.
        repo_root: Repository root directory. Defaults to CWD.

    Returns:
        CompatibilityResult with classification and hit lists.
    """
    if repo_root is None:
        repo_root = os.getcwd()

    result = CompatibilityResult(pr_number=pr_number, all_changed_files=list(changed_files))

    for fpath in changed_files:
        abs_path = os.path.join(repo_root, fpath)
        exists = os.path.exists(abs_path)

        if not exists:
            result.missing_files.append(fpath)

        if exists:
            result.existing_files.append(fpath)

        # Classify file type
        if fpath.startswith("tests/") or "/test_" in fpath or fpath.startswith("test_"):
            result.test_files.append(fpath)
        if fpath.startswith("docs/") or fpath.endswith(".md"):
            result.doc_files.append(fpath)
        if fpath.endswith(".py") and not fpath.startswith("tests/"):
            result.code_files.append(fpath)

        # Check restricted modules
        for module in RESTRICTED_MODULES:
            if fpath.startswith(module):
                result.restricted_hits.append(fpath)

        # Check for obsolete paths (known renamed/deleted dirs)
        if _is_obsolete_path(fpath):
            result.obsolete_paths.append(fpath)

    # Safety pattern scan — read existing files that are being changed
    for fpath in result.existing_files:
        abs_path = os.path.join(repo_root, fpath)
        if not os.path.isfile(abs_path):
            continue
        try:
            content = Path(abs_path).read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in SAFETY_SENSITIVE_PATTERNS:
            if pattern.search(content):
                hit = f"{fpath}: matches {pattern.pattern}"
                if hit not in result.safety_pattern_hits:
                    result.safety_pattern_hits.append(hit)

    return result


def _is_obsolete_path(fpath: str) -> bool:
    """Check if a file path matches known obsolete or renamed paths."""
    obsolete_prefixes = {
        "src/old_",
        "src/legacy_",
        "src/deprecated_",
        "scripts/old_",
        "archive/",
        "src/vendor/",
        "src/third_party/",
        "src/utils/",  # moved to src/helpers or similar
    }
    for prefix in obsolete_prefixes:
        if fpath.startswith(prefix):
            return True
    return False
