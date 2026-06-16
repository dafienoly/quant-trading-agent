# Team Plan: v12-real-codex-pm-architect-smoke

## Objective

Validate that the V12 automation pipeline can execute a real Codex PM stage and hand off cleanly to a real Codex Architect stage for a docs-only smoke feature. Prove that Codex A (PM) produces a complete requirements document and Codex B (Architect) produces a matching architecture document, and that downstream planning, development, testing, review, and acceptance stages can consume both without changing product code or trading behavior.

## Inputs Reviewed

| Document | Path | Status |
|---|---|---|
| AGENTS.md | `AGENTS.md` | Reviewed |
| Agent Development Pipeline | `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` | Reviewed |
| Branch Workflow | `docs/process/BRANCH_WORKFLOW.md` | Reviewed |
| Team Pipeline V2 | `docs/pipeline/TEAM_PIPELINE_V2.md` | Reviewed |
| Agent Handoff Contract | `docs/pipeline/AGENT_HANDOFF_CONTRACT.md` | Reviewed |
| Self-Test Checklist | `docs/policy/SELF_TEST_CHECKLIST.md` | Reviewed |
| Requirements | `docs/requirements/2026-06-16-v12-real-codex-pm-architect-smoke-requirements.md` | Reviewed |
| Architecture | `docs/design/2026-06-16-v12-real-codex-pm-architect-smoke-architecture.md` | Reviewed |
| Architecture Dev Guide | Embedded in architecture doc | Reviewed |
| Phase 1 Dev Report | `docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-1-dev-report.md` | Reviewed |
| Phase 1 Test Report | `docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-1-test-report.md` | Reviewed |
| Claude Lead Review (Phase 1) | `docs/review/2026-06-16-v12-real-codex-pm-architect-smoke-claude-lead-review.md` | Reviewed |
| Codex Review R1 | `docs/review/2026-06-16-v12-real-codex-pm-architect-smoke-codex-review-r1.md` | Reviewed |
| Acceptance Report | `docs/acceptance/2026-06-16-v12-real-codex-pm-architect-smoke-acceptance.md` | Reviewed |

## Scope

- Produce a multi-phase team development plan for the remaining smoke validation work after Phase 1 (infrastructure validated).
- Phase 2: Documentation evidence generation — git evidence, path-consistency checks, stage-status validation for the codex_pm and codex_architect real outputs.
- Phase 3: Review and acceptance evidence — confirm all required docs exist, path mismatches are documented, no trading-sensitive code changed, and acceptance correctly scopes to pipeline validation only.
- All work is documentation-only. No production code changes, no trading module changes, no runtime config changes, no secret introduction.

## Non-Goals

- No production code implementation.
- No API, UI, strategy, risk, execution, broker, or order module changes.
- No live trading, demo trading, or paper trading behavior introduction.
- No stock-pool filter changes.
- No LLM decision-boundary changes.
- No auto-merge to main.
- No weakening of manual approval gates.

## Safety Constraints

1. Feature risk level is `docs-only`. No production code changes are permitted.
2. Do NOT modify trading-sensitive modules: `src/broker`, `src/execution`, `src/order`, `src/account`, `src/risk`, `src/miniQMT`, `src/risk_engine`, `src/execution_engine`, `src/data_gateway`, `src/backtest_engine`, `src/factor_engine`, `src/strategy_engine`, `src/stock_pool`, `src/agent_orchestrator`, `src/ui_report`, `src/config`, `src/models`, `main.py`, runtime startup scripts.
3. Do NOT weaken the Merge Gate or bypass manual approval. The `manual_approval_required_for` list in pipeline state must remain intact.
4. Do NOT write API keys, tokens, secrets, credentials, or `.env` content into the repository.
5. Do NOT auto-merge to main. Only merge after full acceptance and manual approval.
6. Do NOT modify policy enforcement or risk controls in `docs/policy/`.
7. If any downstream stage determines that code changes are required, the stage must stop and return to Claude Code A (Lead) for scope revision — not expand this docs-only plan silently.
8. Path-format mismatches between hyphenated date paths (`2026-06-16`) and no-hyphen metadata paths (`20260616`) must be recorded as pipeline consistency evidence, not silently normalized.
9. No stage may claim live trading, real market-data validation, execution readiness, or production release readiness from this smoke feature.

## Proposed Phases

### Phase 1: Pipeline Infrastructure and Stage Execution Validation

**Status: ✅ COMPLETED** (see Phase 1 dev report, test report, Claude lead review, Codex review, and acceptance report)

Phase 1 validated the pipeline scaffolding, branch creation, label routing, stage execution ordering, handoff artifact completeness, and safety isolation for a docs-only smoke feature. All 14 test cases passed, all gates passed, and the acceptance result was `ACCEPTED_WITH_NOTES`. The phase established that the epic branch exists, stage commits execute in order (codex_pm → codex_architect → claude_lead_plan → claude_developer → claude_tester), and no restricted modules were modified.

**Key findings carried forward into Phase 2 planning:**
- Gate JSON files listed upstream artifacts as "found" when files did not exist — gate checker validates report existence but not upstream artifact existence. Phase 2 must verify actual file presence.
- Label name `codex_pm` initially mismatched repo label `pm` — fixed in commit `6101c7f`.
- Dev report omitted later-stage references — acceptable for Phase 1 but Phase 2 reports should include full stage context.

### Phase 2: Documentation Evidence Generation and Path Validation

**Scope:**
- Verify the real Codex PM requirements document and Codex Architect architecture document exist at the required hyphenated target paths.
- Record the path-format inconsistency between the hyphenated PM/Architect target paths and the no-hyphen automation metadata paths as pipeline consistency evidence.
- Run lightweight git evidence commands to confirm no production or trading-sensitive files were modified.
- Produce a Phase 2 development report and Phase 2 test report documenting the evidence.
- Do NOT run product smoke tests, linters, or Python checks unless touched files include Python source (only documentation files are expected).

**Owner:** Claude Code B (Developer), Claude Code C (Tester)

**Branch:**
- Dev branch: `feat/v12-real-codex-pm-architect-smoke/phase-2-evidence` (created from epic branch)
- Test branch: `test/v12-real-codex-pm-architect-smoke/phase-2-evidence-<tester>-<timestamp>` (local temporary branch)

**Files/directories in scope:**
- `docs/requirements/2026-06-16-v12-real-codex-pm-architect-smoke-requirements.md` — read-only verification
- `docs/design/2026-06-16-v12-real-codex-pm-architect-smoke-architecture.md` — read-only verification
- `docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-2-dev-report.md` — to be created by Claude B
- `docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-2-test-report.md` — to be created by Claude C

**Explicit out-of-scope for Phase 2:**
- No edits to requirements or architecture documents.
- No production code creation or modification.
- No runtime testing or UI verification.
- No changes to `.agent/` pipeline automation files.
- No changes to `.github/` workflows.

**Self-test commands (Claude B):**

```powershell
# 1. Workspace check
git status --short --branch
git diff --stat

# 2. Verify PM requirements doc exists at hyphenated path (authoritative PM target)
$reqPath = "docs/requirements/2026-06-16-v12-real-codex-pm-architect-smoke-requirements.md"
Test-Path $reqPath

# 3. Verify architecture doc exists at hyphenated path (authoritative architecture target)
$archPath = "docs/design/2026-06-16-v12-real-codex-pm-architect-smoke-architecture.md"
Test-Path $archPath

# 4. Verify no-hyphen metadata path variant for requirements
$reqMetaPath = "docs/requirements/20260616-v12-real-codex-pm-architect-smoke-requirements.md"
Test-Path $reqMetaPath

# 5. Verify no-hyphen metadata path variant for architecture
$archMetaPath = "docs/design/20260616-v12-real-codex-pm-architect-smoke-architecture.md"
Test-Path $archMetaPath

# 6. Check restricted modules unchanged
git diff origin/main --name-only | Where-Object { $_ -match '^(src/broker|src/execution|src/order|src/account|src/risk|src/miniQMT|src/risk_engine|src/execution_engine|src/data_gateway|src/backtest_engine|src/factor_engine|src/strategy_engine|src/stock_pool)' }

# 7. Check diff is docs-only
git diff origin/main --name-only | Where-Object { $_ -notmatch '^docs/' -and $_ -notmatch '^\.agent/' -and $_ -notmatch '^\.github/' }

# 8. Record path-format mismatch evidence
$hyphenReq = "docs/requirements/2026-06-16-v12-real-codex-pm-architect-smoke-requirements.md"
$noHyphenReq = "docs/requirements/20260616-v12-real-codex-pm-architect-smoke-requirements.md"
if ((Test-Path $hyphenReq) -and -not (Test-Path $noHyphenReq)) {
    Write-Output "PATH_MISMATCH_NOTE: Hyphenated PM target exists at $hyphenReq but no-hyphen metadata path $noHyphenReq does not exist — expected per requirements doc instruction."
}

$hyphenArch = "docs/design/2026-06-16-v12-real-codex-pm-architect-smoke-architecture.md"
$noHyphenArch = "docs/design/20260616-v12-real-codex-pm-architect-smoke-architecture.md"
if ((Test-Path $hyphenArch) -and -not (Test-Path $noHyphenArch)) {
    Write-Output "PATH_MISMATCH_NOTE: Hyphenated architecture target exists at $hyphenArch but no-hyphen metadata path $noHyphenArch does not exist — expected per architecture doc instruction."
}

# 9. Check no TODO/TBD/placeholder markers in evidence files
rg -n "TODO|TBD|待补充" docs/dev_reports/*phase-2* docs/test_reports/*phase-2* 2>$null

# 10. Verify requirements doc has required sections
$reqContent = Get-Content $reqPath -Raw
$reqContent -match "# v12-real-codex-pm-architect-smoke Requirements"
$reqContent -match "## User Goal"
$reqContent -match "## Functional Requirements"
$reqContent -match "## Non-functional Requirements"
$reqContent -match "## Acceptance Criteria"
$reqContent -match "## Safety Constraints"

# 11. Verify architecture doc has required sections
$archContent = Get-Content $archPath -Raw
$archContent -match "## Architecture Summary"
$archContent -match "## Module Plan"
$archContent -match "## Technical Decisions"
$archContent -match "## Safety Impact"
$archContent -match "## Development Guidance"
```

**Self-test pass criteria:**
- PM requirements doc exists at hyphenated target path.
- Architecture doc exists at hyphenated target path.
- All required sections present in both docs.
- No restricted module files changed in `git diff origin/main`.
- Any non-documentation file change is explicitly explained and justified.
- Path-format mismatch is recorded as a consistency note, not silently ignored.
- No TODO/TBD markers in new evidence files.

**Tester verification commands (Claude C):**

```powershell
# 1. Verify dev report exists
Test-Path "docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-2-dev-report.md"

# 2. Verify test report will be generated at expected path
Write-Output "Test report target: docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-2-test-report.md"

# 3. Cross-validate path-consistency note
$devReport = Get-Content "docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-2-dev-report.md" -Raw
if ($devReport -match "PATH_MISMATCH_NOTE|path-format|path consistency") {
    Write-Output "PATH_MISMATCH_DOCUMENTED — PASS"
} else {
    Write-Output "PATH_MISMATCH_NOT_DOCUMENTED — WARN"
}

# 4. Confirm no restricted module changes in actual diff
git diff origin/main --name-only | Where-Object { $_ -match '^(src/broker|src/execution|src/order|src/account|src/risk)' }

# 5. Confirm diff is docs-only (with explicit exceptions list)
$nonDocFiles = git diff origin/main --name-only | Where-Object {
    $_ -notmatch '^docs/' -and
    $_ -notmatch '^\.agent/' -and
    $_ -notmatch '^\.github/' -and
    $_ -notmatch '^\.vscode/' -and
    $_ -notmatch '\.md$'
}
if ($nonDocFiles) {
    Write-Output "NON_DOC_FILES: $nonDocFiles — requires explanation"
} else {
    Write-Output "DOCS_ONLY_CONFIRMED"
}

# 6. Verify requirements doc section completeness
$reqContent = Get-Content "docs/requirements/2026-06-16-v12-real-codex-pm-architect-smoke-requirements.md" -Raw
$requiredReqSections = @(
    "# v12-real-codex-pm-architect-smoke Requirements",
    "## User Goal",
    "## Functional Requirements",
    "## Non-functional Requirements",
    "## Acceptance Criteria",
    "## Safety Constraints"
)
foreach ($section in $requiredReqSections) {
    if ($reqContent -match [regex]::Escape($section)) {
        Write-Output "REQ_SECTION_FOUND: $section"
    } else {
        Write-Output "REQ_SECTION_MISSING: $section"
    }
}

# 7. Verify architecture doc section completeness
$archContent = Get-Content "docs/design/2026-06-16-v12-real-codex-pm-architect-smoke-architecture.md" -Raw
$requiredArchSections = @(
    "## Architecture Summary",
    "## Module Plan",
    "## Technical Decisions",
    "## Safety Impact",
    "## Development Guidance"
)
foreach ($section in $requiredArchSections) {
    if ($archContent -match [regex]::Escape($section)) {
        Write-Output "ARCH_SECTION_FOUND: $section"
    } else {
        Write-Output "ARCH_SECTION_MISSING: $section"
    }
}

# 8. Feature ID traceability check
$reqContent -match "v12-real-codex-pm-architect-smoke"
$archContent -match "v12-real-codex-pm-architect-smoke"
```

**Tester pass criteria:**
- Dev report exists and documents all self-test commands and results.
- Path-format mismatch is documented in dev report or test report as a note.
- No restricted module files modified.
- All non-documentation file changes (if any) are explicitly explained and justified.
- PM requirements doc has all 6 required sections.
- Architecture doc has all 5 required sections (Architecture Summary, Module Plan, Technical Decisions, Safety Impact, Development Guidance).
- Feature ID `v12-real-codex-pm-architect-smoke` is traceable in both docs.

**Pass/fail routing:**
- If Phase 2 tests **PASS**: Route to Phase 3.
- If Phase 2 tests **PASS_WITH_NOTES** (e.g., path-mismatch documented): Route to Phase 3 with notes.
- If Phase 2 tests **REJECTED** (e.g., restricted module changed, docs corrupted): Return to Claude Code B for fix, then re-test.

**Restricted modules touched:** No.

### Phase 3: Review and Acceptance Evidence

**Scope:**
- Claude Code A reviews all Phase 2 evidence plus the upstream requirements and architecture documents.
- Confirm all required docs are present or missing docs are explicitly explained by stage scope.
- Confirm no trading-sensitive code path was modified across the entire feature.
- Produce the Claude lead review report.
- Hand off to Codex B for final architecture review.
- Codex A performs PM acceptance confirming the smoke validates pipeline handoff, not product delivery.

**Owner:** Claude Code A (Lead Review), Codex B (Final Review), Codex A (Acceptance)

**Branch:**
- Review work committed directly to epic branch (documentation-only review reports).
- Fix branch if needed: `fix/v12-real-codex-pm-architect-smoke/review-r1`.

**Files/directories in scope:**
- `docs/review/20260616-v12-real-codex-pm-architect-smoke-claude-lead-review.md` — to be created/updated by Claude A
- `docs/review/20260616-v12-real-codex-pm-architect-smoke-codex-review-r1.md` — to be created/updated by Codex B
- `docs/acceptance/20260616-v12-real-codex-pm-architect-smoke-acceptance.md` — to be created/updated by Codex A
- Read-only verification of all upstream docs.

**Explicit out-of-scope for Phase 3:**
- No production code changes.
- No architecture or requirements document edits.
- No pipeline automation changes.

**Self-test commands (Claude A):**

```powershell
# 1. Verify all required docs are present
$requiredDocs = @(
    "docs/requirements/2026-06-16-v12-real-codex-pm-architect-smoke-requirements.md",
    "docs/design/2026-06-16-v12-real-codex-pm-architect-smoke-architecture.md",
    "docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-1-dev-report.md",
    "docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-1-test-report.md",
    "docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-2-dev-report.md",
    "docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-2-test-report.md"
)
foreach ($doc in $requiredDocs) {
    if (Test-Path $doc) {
        Write-Output "FOUND: $doc"
    } else {
        Write-Output "MISSING: $doc"
    }
}

# 2. Verify trading-sensitive code unchanged across entire feature
git diff origin/main --name-only | Where-Object { $_ -match '^(src/broker|src/execution|src/order|src/account|src/risk|src/miniQMT|src/risk_engine|src/execution_engine)' }

# 3. Verify no product-readiness claims in any report
$reports = @(
    "docs/dev_reports/*phase-2*",
    "docs/test_reports/*phase-2*",
    "docs/review/*claude-lead-review*"
)
foreach ($pattern in $reports) {
    Get-ChildItem -Path $pattern | ForEach-Object {
        $content = Get-Content $_.FullName -Raw
        if ($content -match "live trading ready|production release|real market-data validation|execution readiness") {
            Write-Output "PRODUCT_CLAIM_FOUND in $($_.Name)"
        }
    }
}

# 4. Verify path-format mismatch is documented
$allReports = Get-ChildItem -Recurse -Path "docs/dev_reports/*.md", "docs/test_reports/*.md", "docs/review/*.md", "docs/acceptance/*.md"
$mismatchFound = $false
foreach ($report in $allReports) {
    $content = Get-Content $report.FullName -Raw
    if ($content -match "path-format|path consistency|PATH_MISMATCH|date format|20260616.*2026-06-16") {
        $mismatchFound = $true
        Write-Output "MISMATCH_DOCUMENTED_IN: $($report.Name)"
    }
}
if (-not $mismatchFound) {
    Write-Output "MISMATCH_NOT_DOCUMENTED_ANYWHERE — DEFECT"
}
```

**Self-test pass criteria:**
- All 6 required documentation artifacts for Phase 1 and Phase 2 are present.
- Zero trading-sensitive module files changed in `git diff origin/main`.
- No product-readiness claims (live trading, production release, execution readiness) appear in any report.
- Path-format mismatch is documented in at least one downstream report.

**Tester verification commands (Claude C / Codex B):**

Same as Claude A self-test commands plus:
- Cross-reference that all prior gate files (`.agent/gates/*.json`) report `passed: true`.
- Verify that no acceptance report claims product delivery.
- Verify acceptance conclusion correctly identifies as `ACCEPTED`, `ACCEPTED_WITH_NOTES`, or `REJECTED` — not `APPROVED` (which is a review term, not an acceptance term).

**Pass/fail routing:**
- If Claude lead review **APPROVED/APPROVED_WITH_NOTES**: Route to Codex B for final architecture review.
- If Claude lead review **CHANGES_REQUESTED**: Return to appropriate prior phase for fix.
- If Codex B review passes (≤3 attempts): Route to Codex A for PM acceptance.
- If Codex B review fails 3 times: Trigger `stage:postmortem-pending` and stop automation (per TEAM_PIPELINE_V2.md).
- If PM acceptance is **ACCEPTED/ACCEPTED_WITH_NOTES**: Feature complete, proceed to merge gate.
- If PM acceptance is **REJECTED**: Return to appropriate upstream stage.

**Restricted modules touched:** No.

## Agent Assignments

| Phase | Role | Agent | Owner | Deliverables |
|---|---|---|---|---|
| Phase 1 | Infrastructure + Pipeline Validation | Claude A/B/C | ✅ Complete | Dev report, test report, lead review, codex review, acceptance |
| Phase 2 | Documentation Evidence Generation | Claude B (Dev) | Claude B | `docs/dev_reports/*phase-2-dev-report.md` |
| Phase 2 | Documentation Evidence Testing | Claude C (Test) | Claude C | `docs/test_reports/*phase-2-test-report.md` |
| Phase 3 | Lead Review | Claude A (Lead) | Claude A | `docs/review/*claude-lead-review.md` |
| Phase 3 | Final Architecture Review | Codex B | Codex B | `docs/review/*codex-review-r*.md` |
| Phase 3 | PM Acceptance | Codex A | Codex A | `docs/acceptance/*acceptance.md` |

## Validation Plan

### Per-Phase Validation

| Phase | Validation Method | Success Criteria |
|---|---|---|
| Phase 2 | Git evidence + doc inspection | PM requirements and architecture docs exist at hyphenated paths; all required sections present; no restricted modules changed; path-format mismatch recorded |
| Phase 3 | Cross-document review | All required docs present; no product-readiness claims; path mismatch documented in ≥1 report; acceptance does not claim product delivery |

### Pipeline Routing

```text
Phase 2 Dev (Claude B)
  -> Phase 2 Test (Claude C)
  -> [PASS] -> Phase 3 Lead Review (Claude A)
  -> [PASS] -> Codex B Final Review
  -> [PASS] -> Codex A Acceptance
  -> [PASS] -> Merge Gate
  -> [FAIL at any gate] -> Return to upstream for fix
```

Following TEAM_PIPELINE_V2.md:
- After each Phase 2 test PASS, route back to Claude B for Phase 2 fixes if needed, then to Phase 3.
- After Phase 3 test PASS, route to Claude A lead review.
- Claude A lead review must complete before Codex B review.
- Codex B review max 3 attempts; 3 failures trigger postmortem.

### Path-Format Consistency Validation

The PM requirements document specifies hyphenated paths (`2026-06-16`) as authoritative targets. Automation metadata references no-hyphen paths (`20260616`). This mismatch is intentional smoke validation:

1. Each downstream stage must record whether the no-hyphen metadata path exists.
2. If it does not exist (expected, since the authoritative target uses hyphenated form), record as a pipeline consistency note — not a defect.
3. If a downstream stage silently replaces the hyphenated path with the no-hyphen path or normalizes the mismatch, treat as a documentation defect.

### Safety Validation Per Phase

| Safety Constraint | Phase 2 | Phase 3 |
|---|---|---|
| No real trading enabled | Git diff check | Cross-report review |
| Risk veto unchanged | Git diff check | Cross-report review |
| Execution policy unchanged | Git diff check | Cross-report review |
| Stock-pool filter unchanged | Git diff check | Cross-report review |
| No secrets committed | Git diff + content check | Cross-report review |
| LLM boundaries unchanged | Git diff check | Cross-report review |
| No restricted module changes | Git diff restricted path check | Git diff + report review |
| Auto-merge not bypassed | N/A (no workflow changes) | Gate file review |
| Manual approval preserved | N/A | Pipeline state review |
| No product-readiness claim | Dev report review | All report review |

## Exit Criteria

1. **Phase 1 exit criteria:** ✅ Met — all 14 test cases passed, all gates passed, acceptance `ACCEPTED_WITH_NOTES`.

2. **Phase 2 exit criteria:**
   - [ ] PM requirements doc exists at hyphenated target path with all 6 required sections.
   - [ ] Architecture doc exists at hyphenated target path with all 5 required sections.
   - [ ] Phase 2 dev report documents git evidence, path-consistency checks, and safety confirmation.
   - [ ] Phase 2 test report documents verification results with `PASS`, `PASS_WITH_NOTES`, or `REJECTED`.
   - [ ] No restricted module files modified in `git diff origin/main`.
   - [ ] Path-format mismatch recorded as consistency note in dev or test report.
   - [ ] Feature ID traceable in both upstream docs.

3. **Phase 3 exit criteria:**
   - [ ] All Phase 1 and Phase 2 required artifacts present.
   - [ ] Claude lead review produced with `APPROVED`, `APPROVED_WITH_NOTES`, or `CHANGES_REQUESTED`.
   - [ ] Codex B final review completed (≤3 attempts).
   - [ ] PM acceptance produced with `ACCEPTED` or `ACCEPTED_WITH_NOTES`.
   - [ ] No product-readiness claims in any report.
   - [ ] Manual approval gates preserved in pipeline state.
   - [ ] Auto-merge to main not enabled.

4. **Feature-level exit criteria:**
   - [ ] Real Codex PM stage produced requirements document.
   - [ ] Real Codex Architect stage consumed requirements and produced architecture document.
   - [ ] Claude A/B/C produced planning, development, testing, and review evidence.
   - [ ] Codex B performed final architecture review.
   - [ ] Codex A performed PM acceptance.
   - [ ] All evidence confirms docs-only scope preserved.
   - [ ] All evidence confirms no trading-sensitive code paths modified.
   - [ ] Path-format inconsistency documented as pipeline evidence.
