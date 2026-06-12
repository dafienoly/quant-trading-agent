"""BugFixBranchManager — isolated Git worktree management for automated fixes.

Creates a temporary Git worktree for each bugfix, runs the fix there,
commits it, and optionally merges back after human approval.

Safety invariants:
- Never modifies the active development branch or workspace.
- All git operations run non-interactively.
- Paths are validated before any deletion.
- Merge is disabled by default.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BugFixWorktree:
    """Describes an isolated bugfix worktree and its metadata."""
    bug_id: str
    base_branch: str
    branch_name: str
    path: Path
    base_sha: str


class BugFixBranchManager:
    """Manages isolated Git worktrees for automated bugfix execution.

    Args:
        project_root: Root of the Git repository.
        worktree_root: Where to create bugfix worktrees.
            Defaults to ``<project_root>/runtime/bugfix_worktrees``.
        base_branch: Git branch to fork bugfix branches from.
            Configurable via env var ``BUGFIX_BASE_BRANCH`` (default ``main``).
    """

    def __init__(
        self,
        project_root: Path,
        worktree_root: Path | None = None,
        base_branch: str = "main",
    ) -> None:
        self._project_root = project_root.resolve()
        self._base_branch = os.getenv("BUGFIX_BASE_BRANCH", base_branch)
        self._worktree_root = (
            worktree_root
            if worktree_root is not None
            else (self._project_root / "runtime" / "bugfix_worktrees")
        )
        self._worktree_root = self._worktree_root.resolve()
        self._auto_merge = os.getenv("BUGFIX_AUTO_MERGE", "false").strip().lower() in ("1", "true", "yes")
        self._keep_on_failure = os.getenv("BUGFIX_KEEP_WORKTREE_ON_FAILURE", "true").strip().lower() in ("1", "true", "yes")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    _BUG_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

    @staticmethod
    def _sanitize_bug_id(bug_id: str) -> str:
        """Validate and sanitize bug_id for use in branch names and paths.

        Raises:
            ValueError: If bug_id contains dangerous characters like ``..``,
                ``/``, or shell metacharacters.
        """
        if not bug_id:
            raise ValueError("bug_id must not be empty")
        if ".." in bug_id:
            raise ValueError(f"bug_id must not contain '..' (got: {bug_id!r})")
        if bug_id.startswith("/") or bug_id.startswith("-"):
            raise ValueError(f"bug_id must not start with '/' or '-' (got: {bug_id!r})")
        if not BugFixBranchManager._BUG_ID_RE.match(bug_id):
            raise ValueError(
                f"bug_id must match {BugFixBranchManager._BUG_ID_RE.pattern!r} "
                f"(got: {bug_id!r})"
            )
        return bug_id

    def _make_worktree_info(self, bug_id: str) -> tuple[str, Path]:
        """Compute branch name and worktree path without running git.

        Returns ``(branch_name, worktree_path)``.
        """
        sanitized = self._sanitize_bug_id(bug_id)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"bugfix/{sanitized}-{timestamp}"
        worktree_path = self._worktree_root / f"{sanitized}-{timestamp}"
        return branch_name, worktree_path

    def prepare_worktree(self, bug_id: str) -> BugFixWorktree:
        """Create an isolated worktree and bugfix branch.

        Steps:
        1. Fetch base branch from remote if available.
        2. Create a ``bugfix/<bug_id>-<timestamp>`` branch.
        3. Create a Git worktree at ``<worktree_root>/<bug_id>-<timestamp>/``.
        4. Return a ``BugFixWorktree`` descriptor.

        Args:
            bug_id: Unique bug identifier (e.g. ``BUG_20260612_ABC123``).

        Returns:
            A ``BugFixWorktree`` with path, branch name, and base SHA.

        Raises:
            RuntimeError: If git operations fail.
        """
        branch_name, worktree_path = self._make_worktree_info(bug_id)

        # Ensure worktree root exists
        self._worktree_root.mkdir(parents=True, exist_ok=True)

        # Fetch base branch (best-effort — local only fallback)
        base_ref = self._base_branch
        try:
            self._git(["fetch", "origin", self._base_branch], check=False)
        except Exception:
            pass

        # After fetch, prefer origin/<base_branch> for base SHA
        # to avoid using stale local branch state
        try:
            origin_ref = f"origin/{self._base_branch}"
            self._git(["rev-parse", "--verify", origin_ref], check=True)
            base_ref = origin_ref
        except RuntimeError:
            # origin/<base_branch> not available; fall back to local
            pass

        # Record the actual base SHA (resolves the chosen ref)
        base_sha = self._git(["rev-parse", base_ref]).strip()

        # Create worktree from the resolved ref
        self._git([
            "worktree", "add", "-b", branch_name,
            str(worktree_path), base_ref,
        ])

        return BugFixWorktree(
            bug_id=bug_id,
            base_branch=self._base_branch,
            branch_name=branch_name,
            path=worktree_path.resolve(),
            base_sha=base_sha,
        )

    def commit_fix(
        self,
        worktree: BugFixWorktree,
        files: list[str],
        message: str,
    ) -> str:
        """Stage and commit the fix files inside the isolated worktree.

        Args:
            worktree: Target worktree descriptor.
            files: Relative file paths to stage and commit.
            message: Commit message.

        Returns:
            The commit hash.

        Raises:
            RuntimeError: If git add or git commit fails.
        """
        for file_path in files:
            result = subprocess.run(
                ["git", "add", file_path],
                cwd=str(worktree.path),
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"git add failed for {file_path}: {result.stderr.strip()}"
                )

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(worktree.path),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            error = (result.stderr or result.stdout or "git commit failed").strip()
            raise RuntimeError(error)

        sha = self._git(["rev-parse", "HEAD"], cwd=str(worktree.path)).strip()
        return sha

    def merge_fix(
        self,
        worktree: BugFixWorktree,
        force: bool = False,
    ) -> dict[str, Any]:
        """Merge the bugfix branch into the base branch.

        By default, merge is disabled unless ``force=True`` (explicit user
        approval) or ``BUGFIX_AUTO_MERGE=true``.

        Args:
            worktree: Target worktree descriptor.
            force: If True, bypass the auto-merge guard.

        Returns:
            A dict with ``merged`` (bool), ``merge_commit`` (str), and
            ``reason`` (str if blocked).
        """
        if not self._auto_merge and not force:
            return {
                "merged": False,
                "reason": "auto_merge_disabled",
                "message": (
                    "Merge requires explicit user approval. "
                    "Set BUGFIX_AUTO_MERGE=true or call with force=True."
                ),
            }

        # Switch to base branch and merge
        self._git(["switch", self._base_branch])
        result = subprocess.run(
            ["git", "merge", "--no-ff", worktree.branch_name, "-m",
             f"fix(auto): merge {worktree.bug_id} from {worktree.branch_name}"],
            cwd=str(self._project_root),
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            error = (result.stderr or result.stdout or "git merge failed").strip()
            return {
                "merged": False,
                "reason": "merge_failed",
                "message": error,
            }

        merge_sha = self._git(["rev-parse", "HEAD"]).strip()
        return {
            "merged": True,
            "merge_commit": merge_sha,
        }

    def cleanup_worktree(
        self,
        worktree: BugFixWorktree,
        *,
        keep_on_failure: bool | None = None,
    ) -> dict[str, Any]:
        """Remove a bugfix worktree and its branch.

        Args:
            worktree: Target worktree descriptor.
            keep_on_failure: Override env ``BUGFIX_KEEP_WORKTREE_ON_FAILURE``.

        Returns:
            A dict with ``removed`` (bool) and optionally ``reason``.

        Raises:
            ValueError: If ``worktree.path`` is outside the configured root,
                indicating a path traversal attempt.
        """
        resolved_path = worktree.path.resolve()
        allowed_root = self._worktree_root.resolve()
        try:
            is_safe = resolved_path.is_relative_to(allowed_root)
        except (ValueError, AttributeError):
            # Python <3.9 fallback: check via prefix with trailing separator
            root_str = str(allowed_root)
            path_str = str(resolved_path)
            is_safe = path_str.startswith(root_str) and (
                len(path_str) == len(root_str) or path_str[len(root_str)] == "/"
            )
        if not is_safe:
            raise ValueError(
                f"Worktree path {resolved_path} is outside allowed root "
                f"{allowed_root}. Refusing to delete."
            )

        if not resolved_path.exists():
            return {"removed": False, "reason": "worktree_path_does_not_exist"}

        try:
            self._git(["worktree", "remove", str(resolved_path)])
            self._git(["branch", "-D", worktree.branch_name], check=False)
            return {"removed": True}
        except RuntimeError as e:
            return {"removed": False, "reason": str(e)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _git(
        self,
        args: list[str],
        cwd: str | None = None,
        check: bool = True,
    ) -> str:
        """Run a git command and return stdout.

        Raises RuntimeError on failure (unless check=False).
        """
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or str(self._project_root),
            capture_output=True, text=True, timeout=60,
        )
        if check and result.returncode != 0:
            error = (result.stderr or result.stdout or "git failed").strip()
            raise RuntimeError(f"git {' '.join(args)} failed: {error}")
        return result.stdout or ""
