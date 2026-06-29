from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


VALID_DECISIONS = frozenset({
    "ALLOW_AUTO_FIX",
    "BLOCK_RESTRICTED_MODULE",
    "BLOCK_NOT_WHITELISTED",
    "BLOCK_INSUFFICIENT_EVIDENCE",
    "REQUIRE_MANUAL_APPROVAL",
})

SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"\.env"),
    re.compile(r"token=", re.IGNORECASE),
    re.compile(r"api_key=", re.IGNORECASE),
    re.compile(r"(?<![a-zA-Z])secret(?![a-zA-Z])", re.IGNORECASE),
    re.compile(r"password=", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN PRIVATE KEY-----"),
    re.compile(r"broker_credential", re.IGNORECASE),
    re.compile(r"session_cookie", re.IGNORECASE),
    re.compile(r"auth_cookie", re.IGNORECASE),
]

MANUAL_APPROVAL_KEYWORDS: list[re.Pattern] = [
    re.compile(r"live-trading", re.IGNORECASE),
    re.compile(r"risk-policy-change", re.IGNORECASE),
    re.compile(r"execution-policy-change", re.IGNORECASE),
    re.compile(r"LEVEL_3_AUTO", re.IGNORECASE),
    re.compile(r"auto-merge.*override", re.IGNORECASE),
]


@dataclass
class TestEvidence:
    __test__ = False
    command: str = ""
    exit_code: int = -1
    summary: str = ""
    started_at: str | None = None
    completed_at: str | None = None


@dataclass
class BugAutoFixCandidate:
    feature_id: str = ""
    issue_number: int = 0
    issue_url: str | None = None
    run_id: str = ""
    branch: str = ""
    base_branch: str = ""
    stage: str = ""
    candidate_files: list[str] = field(default_factory=list)
    touched_files: list[str] = field(default_factory=list)
    change_summary: str = ""
    change_kind: str | None = None
    diff_stats: dict[str, int] = field(default_factory=dict)
    test_evidence: list[TestEvidence] = field(default_factory=list)
    review_evidence: dict | None = None
    artifact_branch: str | None = None
    artifact_run_id: str | None = None
    test_commands: list[str] = field(default_factory=list)
    test_results: str = ""
    review_status: str = ""
    audit_artifact_path: str = ""

    def __post_init__(self):
        if not self.test_commands and self.test_evidence:
            self.test_commands = [te.command for te in self.test_evidence]
        if not self.test_results and self.test_evidence:
            outcomes = []
            for te in self.test_evidence:
                outcomes.append(
                    f"{te.command}: exit={te.exit_code}"
                )
            self.test_results = "; ".join(outcomes)
        if not self.review_status and self.review_evidence:
            self.review_status = self.review_evidence.get(
                "status", ""
            )

    @classmethod
    def from_dict(cls, data: dict) -> BugAutoFixCandidate:
        te_list = []
        for te_data in data.get("test_evidence", []):
            te_list.append(TestEvidence(**te_data))
        data = dict(data)
        data["test_evidence"] = te_list
        return cls(**data)


@dataclass
class GovernanceDecision:
    feature_id: str = ""
    issue_number: int = 0
    run_id: str = ""
    candidate_files: list[str] = field(default_factory=list)
    change_summary: str = ""
    risk_level: str = "unknown"
    allowed_by_whitelist: bool = False
    restricted_module_touched: bool = False
    restricted_paths: list[str] = field(default_factory=list)
    manual_approval_required: bool = False
    manual_approval_reasons: list[str] = field(default_factory=list)
    auto_fix_decision: str = "BLOCK_INSUFFICIENT_EVIDENCE"
    decision_reason: str = ""
    required_tests: list[str] = field(default_factory=list)
    audit_artifact_path: str = ""
    evidence_status: str = "unknown"
    test_status: str = "unknown"
    secret_scan_status: str = "unknown"
    auto_merge_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm_path(p: str) -> str:
    p = p.replace("\\", "/")
    p = re.sub(r"^\.\/+", "", p)
    if ".." in p.split("/"):
        parts = []
        for part in p.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)
        p = "/".join(parts)
    return p


def _match_glob(pattern: str, path: str) -> bool:
    if "**" not in pattern:
        import fnmatch
        return fnmatch.fnmatch(path, pattern)
    parts = pattern.split("**")
    prefix = parts[0]
    if prefix and not path.startswith(prefix):
        return False
    body = path[len(prefix):] if prefix else path
    suffix_glob = parts[-1]
    if suffix_glob:
        if suffix_glob.startswith("/"):
            alt_suffix = suffix_glob[1:]
            import fnmatch
            if fnmatch.fnmatch(body, f"*{alt_suffix}"):
                return True
            return fnmatch.fnmatch(body, f"*{suffix_glob}")
        import fnmatch
        return fnmatch.fnmatch(body, f"*{suffix_glob}")
    if len(parts) > 2:
        for mid in parts[1:-1]:
            mid_stripped = mid.strip("/")
            if mid_stripped and mid_stripped not in body:
                return False
        import fnmatch
        return True
    return True


class BugAutoFixGovernanceEvaluator:
    def __init__(self, policy: dict | None):
        self.policy = policy

    def _check_policy_loaded(self) -> GovernanceDecision | None:
        if self.policy is None:
            return _block_insufficient("policy unavailable")
        return None

    CORE_INPUT_FIELDS = frozenset({
        "feature_id", "issue_number", "run_id", "branch",
        "base_branch", "stage", "candidate_files",
        "change_summary", "touched_files",
    })

    def _validate_required_evidence(
        self, candidate: BugAutoFixCandidate
    ) -> GovernanceDecision | None:
        required = self.policy.get("required_evidence_fields", [])
        cdict = asdict(candidate)
        missing = []
        for field_name in required:
            if field_name in cdict:
                val = cdict[field_name]
            elif hasattr(candidate, field_name):
                val = getattr(candidate, field_name)
            else:
                missing.append(field_name)
                continue

            is_core = field_name in self.CORE_INPUT_FIELDS
            if isinstance(val, (list, str)) and not val:
                if is_core:
                    missing.append(field_name)
            elif isinstance(val, (int, float)) and val == 0:
                if field_name in ("issue_number",):
                    missing.append(field_name)

        if missing:
            return _block_insufficient(
                f"missing required evidence fields: "
                f"{', '.join(missing)}"
            )
        return None

    def _check_stale_artifact(
        self, candidate: BugAutoFixCandidate
    ) -> GovernanceDecision | None:
        if candidate.artifact_branch and candidate.branch:
            if candidate.artifact_branch != candidate.branch:
                return _block_insufficient(
                    f"artifact branch '{candidate.artifact_branch}' "
                    f"does not match current branch '{candidate.branch}'"
                )
        if candidate.artifact_run_id and candidate.run_id:
            if candidate.artifact_run_id != candidate.run_id:
                return _block_insufficient(
                    f"artifact run_id '{candidate.artifact_run_id}' "
                    f"does not match current run_id '{candidate.run_id}'"
                )
        return None

    def _scan_secret_like(
        self, candidate: BugAutoFixCandidate
    ) -> GovernanceDecision | None:
        scan_targets = [
            candidate.change_summary,
            candidate.change_kind or "",
        ] + candidate.touched_files + candidate.candidate_files

        hits = []
        for target in scan_targets:
            for pattern in SECRET_PATTERNS:
                if pattern.search(target):
                    hit_info = _mask_secret(target, pattern)
                    if hit_info not in hits:
                        hits.append(hit_info)

        if candidate.review_evidence:
            for val in candidate.review_evidence.values():
                if isinstance(val, str):
                    for pattern in SECRET_PATTERNS:
                        if pattern.search(val):
                            hits.append(_mask_secret(val, pattern))
                            break

        if hits:
            return _require_manual(
                f"secret-like content detected: {'; '.join(hits[:5])}",
                hits,
            )
        return None

    def _check_restricted_modules(
        self, candidate: BugAutoFixCandidate
    ) -> GovernanceDecision | None:
        restricted = self.policy.get("restricted_paths", [])
        hits = []
        for tf in candidate.touched_files:
            ntf = _norm_path(tf)
            for rp in restricted:
                if _match_glob(rp, ntf):
                    hits.append(rp)
                    break

        if hits:
            return _block_restricted(
                f"restricted module touched: {', '.join(hits)}",
                hits,
            )
        return None

    def _check_manual_approval_triggers(
        self, candidate: BugAutoFixCandidate
    ) -> GovernanceDecision | None:
        reasons = []
        policy_triggers = self.policy.get("manual_approval_required_for", [])

        combined_text = (
            f"{candidate.change_summary} {candidate.change_kind or ''} "
            + " ".join(candidate.touched_files)
        )

        for keyword in MANUAL_APPROVAL_KEYWORDS:
            if keyword.search(combined_text):
                reasons.append(f"keyword matched: {keyword.pattern}")

        for trigger in policy_triggers:
            if trigger in combined_text.lower():
                reason = f"policy trigger matched: {trigger}"
                if reason not in reasons:
                    reasons.append(reason)

        if candidate.review_evidence:
            attempts = candidate.review_evidence.get(
                "codex_review_attempts", 0
            )
            if isinstance(attempts, int) and attempts >= 3:
                reasons.append(
                    f"codex-review-fails-three-times "
                    f"(attempts={attempts})"
                )
            status = candidate.review_evidence.get("status", "")
            if status == "failed" and attempts >= 3:
                if (
                    "codex-review-fails-three-times"
                    not in " ".join(reasons)
                ):
                    reasons.append(
                        f"codex-review-fails-three-times "
                        f"(status={status}, attempts={attempts})"
                    )

        if reasons:
            return _require_manual(
                "; ".join(reasons[:5]), reasons
            )
        return None

    def _match_whitelist(
        self, candidate: BugAutoFixCandidate
    ) -> tuple[bool, str | None, list[str]]:
        allowed = self.policy.get("allowed_fix_types", {})
        if not allowed:
            return False, "no whitelist entries defined", []

        best_match = None
        best_tests = []

        for fix_type, rules in allowed.items():
            path_patterns = rules.get("path_patterns", [])
            allowed_change_kinds = rules.get("allowed_change_kinds", [])

            if not candidate.touched_files:
                continue

            all_files_match = True
            for tf in candidate.touched_files:
                ntf = _norm_path(tf)
                file_match = False
                for pp in path_patterns:
                    if _match_glob(pp, ntf):
                        file_match = True
                        break
                if not file_match:
                    all_files_match = False
                    break

            if not all_files_match:
                continue

            forbidden_paths = rules.get("forbidden_paths", [])
            forbidden_hit = False
            for tf in candidate.touched_files:
                ntf = _norm_path(tf)
                for fp in forbidden_paths:
                    if _match_glob(fp, ntf):
                        forbidden_hit = True
                        break
                if forbidden_hit:
                    break
            if forbidden_hit:
                continue

            if (
                candidate.change_kind
                and allowed_change_kinds
            ):
                if candidate.change_kind not in allowed_change_kinds:
                    continue

            best_match = fix_type
            best_tests = rules.get("required_tests", [])

        if best_match is None:
            return False, "no whitelist entry matched", []
        return True, best_match, best_tests

    def _validate_tests(
        self, candidate: BugAutoFixCandidate
    ) -> GovernanceDecision | None:
        if not candidate.test_evidence:
            return _block_insufficient("no test evidence provided")

        for te in candidate.test_evidence:
            if te.exit_code != 0:
                return _block_insufficient(
                    f"test failed: '{te.command}' "
                    f"exited with code {te.exit_code}"
                )
        return None

    def _check_auto_merge_gate(
        self, candidate: BugAutoFixCandidate
    ) -> GovernanceDecision | None:
        if candidate.review_evidence:
            status = candidate.review_evidence.get("status", "")
            if status == "failed":
                return _require_manual(
                    "review failed, auto-merge not eligible"
                )

        if candidate.stage in ("bugfix",):
            pass
        return None

    def evaluate(
        self, candidate: BugAutoFixCandidate
    ) -> GovernanceDecision:
        dec = GovernanceDecision(
            feature_id=candidate.feature_id,
            issue_number=candidate.issue_number,
            run_id=candidate.run_id,
            candidate_files=list(candidate.candidate_files),
            change_summary=candidate.change_summary,
        )

        result = self._check_policy_loaded()
        if result:
            return self._finalize(dec, result)

        result = self._validate_required_evidence(candidate)
        if result:
            return self._finalize(dec, result)

        result = self._check_stale_artifact(candidate)
        if result:
            return self._finalize(dec, result)

        result = self._scan_secret_like(candidate)
        if result:
            return self._finalize(dec, result)

        result = self._check_restricted_modules(candidate)
        if result:
            return self._finalize(dec, result)

        result = self._check_manual_approval_triggers(candidate)
        if result:
            return self._finalize(dec, result)

        allowed, match_name, required_tests = self._match_whitelist(
            candidate
        )
        if not allowed:
            dec.allowed_by_whitelist = False
            block = _block_not_whitelisted(match_name or "unknown")
            return self._finalize(dec, block)

        result = self._validate_tests(candidate)
        if result:
            return self._finalize(dec, result)

        result = self._check_auto_merge_gate(candidate)
        if result:
            return self._finalize(dec, result)

        risk_level = "low"
        dec.allowed_by_whitelist = True
        dec.risk_level = risk_level
        dec.auto_fix_decision = "ALLOW_AUTO_FIX"
        dec.decision_reason = (
            f"candidate matched whitelist ({match_name}), "
            f"touched no restricted modules, "
            f"evidence complete, tests passed"
        )
        dec.auto_merge_eligible = True
        return dec

    @staticmethod
    def _finalize(
        dec: GovernanceDecision, result: GovernanceDecision
    ) -> GovernanceDecision:
        dec.auto_fix_decision = result.auto_fix_decision
        dec.decision_reason = result.decision_reason
        dec.risk_level = result.risk_level
        dec.restricted_module_touched = result.restricted_module_touched
        dec.restricted_paths = list(result.restricted_paths)
        dec.manual_approval_required = result.manual_approval_required
        dec.manual_approval_reasons = list(
            result.manual_approval_reasons
        )
        dec.allowed_by_whitelist = result.allowed_by_whitelist
        dec.test_status = result.test_status
        dec.secret_scan_status = result.secret_scan_status
        return dec


def _block_insufficient(reason: str) -> GovernanceDecision:
    return GovernanceDecision(
        auto_fix_decision="BLOCK_INSUFFICIENT_EVIDENCE",
        decision_reason=reason,
        risk_level="unknown",
    )


def _block_restricted(
    reason: str, paths: list[str]
) -> GovernanceDecision:
    return GovernanceDecision(
        auto_fix_decision="BLOCK_RESTRICTED_MODULE",
        decision_reason=reason,
        risk_level="high",
        restricted_module_touched=True,
        restricted_paths=list(paths),
        manual_approval_required=True,
        manual_approval_reasons=[
            f"restricted module: {p}" for p in paths
        ],
    )


def _block_not_whitelisted(reason: str) -> GovernanceDecision:
    return GovernanceDecision(
        auto_fix_decision="BLOCK_NOT_WHITELISTED",
        decision_reason=reason,
        risk_level="medium",
    )


def _require_manual(
    reason: str, details: list[str] | None = None
) -> GovernanceDecision:
    return GovernanceDecision(
        auto_fix_decision="REQUIRE_MANUAL_APPROVAL",
        decision_reason=reason,
        risk_level="high",
        manual_approval_required=True,
        manual_approval_reasons=list(details or [reason]),
    )


def _mask_secret(text: str, pattern: re.Pattern) -> str:
    match = pattern.search(text)
    if match:
        start = max(0, match.start() - 4)
        end = min(len(text), match.end() + 4)
        snippet = text[start:end]
        return f"...{snippet[:30]}... (hash: {hash(snippet) % 1000000})"
    return text[:30]


def _generate_summary_md(
    decision: GovernanceDecision, candidate: BugAutoFixCandidate
) -> str:
    lines = [
        "# Bug Auto-Fix Governance Summary",
        "",
        f"- **Feature:** {decision.feature_id}",
        f"- **Issue:** #{decision.issue_number}",
        f"- **Run ID:** {decision.run_id}",
        f"- **Branch:** {candidate.branch}",
        f"- **Base Branch:** {candidate.base_branch}",
        f"- **Stage:** {candidate.stage}",
        "",
        "## Decision",
        "",
        f"- **auto_fix_decision:** {decision.auto_fix_decision}",
        f"- **risk_level:** {decision.risk_level}",
        f"- **reason:** {decision.decision_reason}",
        "",
        "## Details",
        "",
        f"- **allowed_by_whitelist:** {decision.allowed_by_whitelist}",
        f"- **restricted_module_touched:** "
        f"{decision.restricted_module_touched}",
        f"- **manual_approval_required:** "
        f"{decision.manual_approval_required}",
        f"- **auto_merge_eligible:** "
        f"{decision.auto_merge_eligible}",
        "",
    ]

    if decision.restricted_paths:
        lines.append("### Restricted Paths Hit")
        lines.append("")
        for rp in decision.restricted_paths:
            lines.append(f"- `{rp}`")
        lines.append("")

    if decision.manual_approval_reasons:
        lines.append("### Manual Approval Reasons")
        lines.append("")
        for r in decision.manual_approval_reasons:
            lines.append(f"- {r}")
        lines.append("")

    lines.append("### Candidate Files")
    lines.append("")
    for cf in candidate.candidate_files:
        lines.append(f"- `{cf}`")
    lines.append("")

    lines.append("### Touched Files")
    lines.append("")
    for tf in candidate.touched_files:
        lines.append(f"- `{tf}`")
    lines.append("")

    if candidate.test_evidence:
        lines.append("### Test Evidence")
        lines.append("")
        lines.append(
            "| Command | Exit Code | Summary |"
        )
        lines.append(
            "|---------|-----------|---------|"
        )
        for te in candidate.test_evidence:
            lines.append(
                f"| `{te.command}` | {te.exit_code} "
                f"| {te.summary} |"
            )
        lines.append("")

    lines.append(
        "---\n*Generated by Bug Auto-Fix Governance Evaluator*"
    )
    return "\n".join(lines)


def load_candidate(path: str) -> BugAutoFixCandidate:
    with open(path) as f:
        data = json.load(f)
    return BugAutoFixCandidate.from_dict(data)


def load_policy(path: str) -> dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bug Auto-Fix Governance Evaluator"
    )
    parser.add_argument(
        "--candidate",
        required=False,
        help="Path to candidate JSON file",
    )
    parser.add_argument(
        "--policy",
        default="docs/pipeline/bug_auto_fix_governance_policy.yaml",
        help="Path to policy YAML file",
    )
    parser.add_argument(
        "--out",
        help="Path to write governance decision JSON",
    )
    parser.add_argument(
        "--summary",
        help="Path to write governance summary markdown",
    )
    args = parser.parse_args(argv)

    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        parser.print_help()
        return 0

    try:
        if args.candidate:
            candidate = load_candidate(args.candidate)
        else:
            candidate = None

        try:
            policy = load_policy(args.policy)
        except Exception:
            policy = None
            if candidate is None:
                candidate = BugAutoFixCandidate()

        if candidate is None:
            candidate = BugAutoFixCandidate()

        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)

        summary_md = _generate_summary_md(decision, candidate)

        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(decision.to_dict(), ensure_ascii=False, indent=2)
            )

        if args.summary:
            summary_path = Path(args.summary)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(summary_md)

        print(f"Decision: {decision.auto_fix_decision}")
        print(f"Reason: {decision.decision_reason}")

        dec = decision.auto_fix_decision
        if dec == "ALLOW_AUTO_FIX":
            return 0
        elif dec in (
            "BLOCK_RESTRICTED_MODULE",
            "BLOCK_NOT_WHITELISTED",
            "REQUIRE_MANUAL_APPROVAL",
        ):
            return 2
        elif dec == "BLOCK_INSUFFICIENT_EVIDENCE":
            return 3
        else:
            return 4

    except Exception as exc:
        print(
            f"Fatal error: {exc}",
            file=sys.stderr,
        )
        return 4


if __name__ == "__main__":
    sys.exit(main())
