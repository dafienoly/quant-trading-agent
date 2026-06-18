# Team Plan: agent-pipeline-dashboard-report-viewer

## Objective

Build a static dashboard and report viewer that surfaces Agent Pipeline execution status, phase gate results, artifact links, and stage history to the user. The viewer must render from pipeline metadata files (`.agent/state.json`, dev reports, test reports, review docs) without requiring a live backend or database.

## Inputs Reviewed

- AGENTS.md — Hard safety invariants and role boundaries
- docs/process/AGENT_DEVELOPMENT_PIPELINE.md — Stage gates, deliverables, roles
- docs/process/BRANCH_WORKFLOW.md — Branch types and standard flow
- docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md — Issue-driven automation structure
- docs/pipeline/AUTO_MERGE_POLICY.md — Merge gate rules
- Pipeline state from `.agent/state.json` — current stage, team config, phase tracking
- User issue #52 — [V14] Agent Pipeline Dashboard / Report Viewer

## Scope

- Generate a standalone HTML dashboard from local pipeline metadata
- Implement a report viewer that lists, filters, and displays pipeline artifacts (dev reports, test reports, reviews, acceptance docs)
- Support phase-by-phase rendering so the dashboard auto-populates as the pipeline progresses
- Integrate dashboard generation into the pipeline automation flow
- All output is static — no database, no server, no API

## Non-Goals

- No real-time or live-updating dashboard (static regeneration only)
- No trading-system integration
- No modification to broker, execution, risk, order, or live-trading modules
- No weakening of merge gates or auto-merge bypass
- No user authentication or access control
- No interactive UI beyond link navigation (pure static pages)

## Safety Constraints

1. Current task is docs-only / pipeline-only — no trading module changes.
2. Do NOT modify trading-sensitive modules: broker, execution, order, account, risk, miniQMT, live trading, real order submission.
3. Do NOT weaken the Merge Gate or bypass manual approval.
4. Do NOT write API keys, tokens, or secrets into the repository.
5. Do NOT auto-merge to main.
6. Do NOT modify policy enforcement or risk controls.
7. Dashboard generation must never read, cache, or embed secrets.
8. All generated HTML must be self-contained — no CDN dependencies that could leak data.

## Proposed Phases

### Phase 1 — Metadata Schema & Aggregation Layer

**Scope:** Design and implement the data model and aggregation logic that collects pipeline metadata from:
- `.agent/state.json` — stage status, phase tracking
- `.agent/handoff/` — handoff docs per stage
- `docs/dev_reports/` — phase dev reports
- `docs/test_reports/` — phase test reports
- `docs/review/` — review documents
- `docs/acceptance/` — acceptance docs

**Outputs:**
- `scripts/pipeline/dashboard_meta.py` (or equivalent) — reads all metadata, produces a structured JSON summary
- `scripts/pipeline/SCHEMA.md` — documents the JSON schema
- `docs/design/pipeline-report-schema.md` — formal schema reference

**Self-Test:** Run `python scripts/pipeline/dashboard_meta.py --dry-run` against current pipeline state; verify JSON output contains all expected keys and no error.

**Tester Check:** Inject a known state file; verify the aggregation output matches expected values.

**Release Criteria:** Aggregation script runs cleanly on current epic branch state; produces valid JSON with stage_status, phases, handoff index, report index.

---

### Phase 2 — HTML Dashboard Generator

**Scope:** Build the static HTML dashboard generator that renders pipeline status as a visual page:
- Pipeline stage flowchart (gate status per stage)
- Phase progress bar (x/n phases complete)
- Artifact links to each deliverable (dev report, test report, review, acceptance)
- Risk / safety constraint summary section

**Outputs:**
- `scripts/pipeline/dashboard_gen.py` — reads aggregated JSON, renders `dashboard.html`
- `scripts/pipeline/templates/dashboard.html` — Jinja2 or f-string template
- `scripts/pipeline/templates/assets/` — minimal embedded CSS (no external deps)

**Self-Test:** Run `python scripts/pipeline/dashboard_gen.py`; verify `dashboard.html` is produced and opens in browser without errors.

**Tester Check:** Validate HTML structure: all stage blocks present, links resolve (may be 404 for future artifacts), no broken images, no external CDN calls.

**Release Criteria:** Dashboard renders correctly for the current 1-phase pipeline state; all stage boxes visible; future-phase stages show "pending" state.

---

### Phase 3 — Report Viewer

**Scope:** Build a report viewer that lets the user browse pipeline artifacts by phase and type:
- Phase index page (`reports/index.html`) — list all phases with status badges
- Per-phase page (`reports/phase-<n>.html`) — linked dev report, test report, review, acceptance
- Report detail viewer — reads Markdown files and renders to HTML within the viewer

**Outputs:**
- `scripts/pipeline/report_viewer.py` — generates report index and per-phase pages
- `scripts/pipeline/templates/report_index.html`
- `scripts/pipeline/templates/report_phase.html`
- `scripts/pipeline/markdown_renderer.py` — lightweight Markdown-to-HTML converter (or use existing library)

**Self-Test:** Run report viewer generation; verify all links navigate correctly between index and phase pages.

**Tester Check:** Open every generated page; confirm Markdown rendering is readable; verify that missing reports show "not yet available" gracefully.

**Release Criteria:** Report viewer generates complete static site; all current phase 1 artifacts are viewable and linked correctly.

---

### Phase 4 — Pipeline Integration

**Scope:** Wire dashboard and report generation into the pipeline automation so each stage automatically regenerates the dashboard:
- Hook `dashboard_gen.py` into Codex A and Codex B workflow scripts
- Regenerate dashboard after each stage completes
- Add a `--generate-dashboard` flag to pipeline advance commands
- Update `.agent/state.json` to track dashboard regeneration timestamps

**Outputs:**
- Modifications to pipeline control scripts (e.g., `scripts/pipeline/advance_stage.py`)
- `.agent/current_task.yaml` updates for dashboard hook
- Integration test script `scripts/pipeline/test_dashboard_hooks.py`

**Self-Test:** Run full pipeline mock (dry-run mode); confirm dashboard regenerates at each stage transition.

**Tester Check:** Force a stage transition; verify dashboard reflects updated state before and after.

**Release Criteria:** Dashboard auto-regenerates on pipeline stage advance; no pipeline step fails due to dashboard generation.

---

### Phase 5 — Styling & Usability Polish

**Scope:** Improve visual polish, mobile readability, and navigation:
- Responsive CSS for desktop and mobile
- Dark/light mode toggle
- Collapsible phase detail sections
- Breadcrumb navigation
- Human-readable timestamps and status labels

**Outputs:**
- Updated CSS in template assets
- Optional: small JS snippet for theme toggle and collapsible sections (no frameworks)

**Self-Test:** Open dashboard on mobile viewport (375px width); verify all sections readable.

**Tester Check:** Test dark mode, light mode, collapsible sections, breadcrumb nav on both desktop and mobile viewports.

**Release Criteria:** Dashboard passes visual inspection on 375px and 1280px viewports; no layout overflow; all interactive elements work.

---

### Phase 6 — Final Review & Acceptance

**Scope:** End-to-end verification, documentation, and handoff preparation:
- Run full pipeline mock with all phases
- Verify all artifacts are linked correctly
- Write `docs/review/20260617-agent-pipeline-dashboard-report-viewer-claude-lead-review.md`
- Prepare acceptance handoff

**Self-Test:** Full pipeline dry-run from phase 1 → phase 6; dashboard and report viewer produce complete, correct output at each step.

**Tester Check:** Spot-check every generated URL; confirm no 404s, no stale data, no missing phases.

**Release Criteria:** All previous phases complete and verified; Claude Lead Review document written and approved; ready for Codex Review and PM Acceptance.

## Agent Assignments

| Role | Agent | Phases |
|---|---|---|
| Claude Code B (Developer) | Claude B | Phase 1, Phase 2, Phase 3, Phase 4 |
| Claude Code C (Test Engineer) | Claude C | Phase 1 T Check, Phase 2 T Check, Phase 3 T Check, Phase 4 T Check |
| Claude Code B (Developer) | Claude B | Phase 5 |
| Claude Code C (Test Engineer) | Claude C | Phase 5 T Check |
| Claude Code A (Lead / Review) | Claude A | Phase 6 + Claude Lead Review |

**Workflow:** After each phase Developer completes and self-test passes, route to Test Engineer for Tester Check. On pass, advance to next phase. On fail, route back to Developer with bug details.

## Validation Plan

1. **Per-Phase Self-Test:** Each Developer phase must include a self-test command that exits 0 on success and prints clear error on failure.
2. **Per-Phase Tester Check:** Test Engineer runs the self-test plus additional edge-case scenarios before signing off.
3. **Phase Gate:** No phase advances unless its Tester Check passes.
4. **Regression Gate:** Phase N+1 changes must not break Phase N output. Full regeneration test required.
5. **Final Integration Run:** Phase 6 runs the full pipeline mock end-to-end to catch cross-phase issues.

## Exit Criteria

1. All 6 phases complete with passing self-tests and tester checks.
2. Dashboard renders pipeline state correctly for all phases (including pending/future states).
3. Report viewer displays phase artifacts with correct links and Markdown rendering.
4. Pipeline integration hooks regenerate dashboard on stage advance without errors.
5. Styling passes responsive and accessibility checks.
6. Claude Lead Review document written and saved to `docs/review/`.
7. All artifacts committed to `epic/20260617-agent-pipeline-dashboard-report-viewer` branch.
8. No trading-system files modified.
9. No secrets, tokens, or credentials embedded anywhere.
10. Ready for Codex Review and PM Acceptance stages.
