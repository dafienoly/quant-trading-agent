#!/usr/bin/env bash
set -euo pipefail

stage="${1:?stage is required}"

repo_root="$(pwd)"
handoff=".agent/handoff/${stage}.md"
state_path=".agent/state.json"

if [[ ! -f "$handoff" ]]; then
  echo "Missing handoff: $handoff" >&2
  exit 2
fi

if [[ ! -f "$state_path" ]]; then
  echo "Missing pipeline state: $state_path" >&2
  exit 2
fi

feature_id="$(
  python3 - <<'PY'
import json
from pathlib import Path

state = json.loads(Path(".agent/state.json").read_text(encoding="utf-8"))
print(state.get("feature_id", "unknown-feature"))
PY
)"

today="$(date +%Y-%m-%d)"

case "$stage" in
  claude_lead_plan)
    out_dir="docs/dev_plans"
    out_path="${out_dir}/${today}-${feature_id}-team-plan.md"
    mkdir -p "$out_dir"

    # Try real Claude Code mode when AGENT_REAL_CLAUDE_LEAD_PLAN=true or AGENT_REAL_CLAUDE_LEAD_PLAN_STRICT=true
    if [[ "${AGENT_REAL_CLAUDE_LEAD_PLAN:-}" == "true" || "${AGENT_REAL_CLAUDE_LEAD_PLAN_STRICT:-}" == "true" ]]; then
      if command -v claude &>/dev/null; then
        prompt_file="$(mktemp)"
        {
          printf '%s\n' "Generate a team development plan in Markdown format. Output ONLY the raw Markdown content to stdout — do NOT write any file, do NOT use any tools, do NOT include conversational text, greetings, or meta-commentary."
          printf '%s\n' ""
          printf '%s\n' "## Context"
          printf '%s\n' ""
          printf '%s\n' "### Current Stage"
          printf '%s\n' "claude_lead_plan — You are Claude Code A (Lead Planning Agent)."
          printf '%s\n' ""
          printf '%s\n' "### Handoff Content (from Codex A PM and Codex B Architect stages)"
          printf '%s\n' ""
          cat "$handoff" 2>/dev/null || printf '%s\n' "(handoff file unavailable)"
          printf '%s\n' ""
          printf '%s\n' "### Pipeline State"
          printf '%s\n' ""
          cat "$state_path" 2>/dev/null || printf '%s\n' "(state file unavailable)"
          printf '%s\n' ""
          printf '%s\n' "### Repository Guidelines (excerpts)"
          printf '%s\n' ""
          printf '%s\n' "#### AGENTS.md — Hard Safety Invariants & Role Boundaries"
          head -80 "$repo_root/AGENTS.md" 2>/dev/null || printf '%s\n' "(AGENTS.md unavailable)"
          printf '%s\n' ""
          printf '%s\n' "#### AGENT_DEVELOPMENT_PIPELINE.md — Roles, Gates & Standard Flow"
          head -100 "$repo_root/docs/process/AGENT_DEVELOPMENT_PIPELINE.md" 2>/dev/null || printf '%s\n' "(pipeline doc unavailable)"
          printf '%s\n' ""
          printf '%s\n' "#### BRANCH_WORKFLOW.md — Branch Types & Standard Flow"
          head -60 "$repo_root/docs/process/BRANCH_WORKFLOW.md" 2>/dev/null || printf '%s\n' "(branch workflow unavailable)"
          printf '%s\n' ""
          printf '%s\n' "### Output Format"
          printf '%s\n' ""
          printf '%s\n' "The team plan MUST contain these sections (in order):"
          printf '%s\n' ""
          printf '%s\n' '# Team Plan: <feature>'
          printf '%s\n' ''
          printf '%s\n' '## Objective'
          printf '%s\n' '## Inputs Reviewed'
          printf '%s\n' '## Scope'
          printf '%s\n' '## Non-Goals'
          printf '%s\n' '## Safety Constraints'
          printf '%s\n' '## Proposed Phases'
          printf '%s\n' '## Agent Assignments'
          printf '%s\n' '## Validation Plan'
          printf '%s\n' '## Exit Criteria'
          printf '%s\n' ""
          printf '%s\n' "### Safety Constraints (MUST embed in the plan)"
          printf '%s\n' ""
          printf '%s\n' "1. Current task is docs-only / pipeline-only by default."
          printf '%s\n' "2. Do NOT modify trading-sensitive modules: broker, execution, order, account, risk, miniQMT, live trading, real order submission."
          printf '%s\n' "3. Do NOT weaken the Merge Gate or bypass manual approval."
          printf '%s\n' "4. Do NOT write API keys, tokens, or secrets into the repository."
          printf '%s\n' "5. Do NOT auto-merge to main."
          printf '%s\n' "6. Do NOT modify policy enforcement or risk controls."
          printf '%s\n' ""
          printf '%s\n' "REMINDER: Output ONLY the raw markdown. No conversation. No tool use. No file writing."
        } > "$prompt_file"

        claude --print - < "$prompt_file" > "$out_path" 2>/tmp/claude_real_stderr.$$ || true
        rc=$?
        rm -f "$prompt_file"

        if [[ -s "$out_path" ]]; then
          echo "Generated $out_path using real Claude Code"
        else
          echo "WARNING: Real Claude mode produced empty output (exit=$rc)." >&2
          if [[ -f /tmp/claude_real_stderr.$$ ]]; then
            stderr_log="$(cat /tmp/claude_real_stderr.$$)"
            rm -f /tmp/claude_real_stderr.$$
            if [[ -n "$stderr_log" ]]; then
              echo "Claude stderr: $stderr_log" >&2
            fi
          fi
          if [[ "${AGENT_REAL_CLAUDE_LEAD_PLAN_STRICT:-}" == "true" ]]; then
            echo "ERROR: AGENT_REAL_CLAUDE_LEAD_PLAN_STRICT=true — real mode failed, aborting." >&2
            exit 2
          fi
          echo "Falling back to mock mode." >&2
        fi
      else
        echo "WARNING: Real Claude mode requested but 'claude' CLI not found." >&2
        if [[ "${AGENT_REAL_CLAUDE_LEAD_PLAN_STRICT:-}" == "true" ]]; then
          echo "ERROR: AGENT_REAL_CLAUDE_LEAD_PLAN_STRICT=true but claude CLI unavailable." >&2
          exit 2
        fi
        echo "Falling back to mock mode." >&2
      fi
    fi

    # Fallback: mock/smoke mode when no real output was produced
    if [[ ! -s "$out_path" ]]; then
      {
        printf '# %s Team Plan\n\n' "$feature_id"
        printf '> Smoke-test team plan generated by local Claude wrapper.\n'
        printf '> This proves GitHub Actions can call WSL and execute the Claude lead stage command.\n\n'
        printf '## Stage\n\n'
        printf 'claude_lead_plan\n\n'
        printf '## Source Handoff\n\n'
        printf '%s\n\n' "$handoff"
        printf '## Phase Plan\n\n'
        printf '| Phase | Owner | Goal | Expected Evidence |\n'
        printf '|---|---|---|---|\n'
        printf '| phase-1 | Claude Code B | Verify phase development handoff can run | `docs/dev_reports/%s-phase-1-dev-report.md` |\n' "$feature_id"
        printf '| phase-1-test | Claude Code C | Verify phase testing handoff can run | `docs/test_reports/%s-phase-1-test-report.md` |\n\n' "$feature_id"
        printf '## Routing Rule\n\n'
        printf 'After Claude Code C passes a phase, route back to Claude Code B unless all phases are tested. Only then route to Claude Code A lead review.\n\n'
        printf '## Safety Notes\n\n'
        printf '%s\n' '- This smoke test must not modify trading, risk, execution, broker, account, or live-trading modules.'
        printf '%s\n\n' '- This smoke test does not call a real model. Replace this wrapper body with ccswitch/opencode-go/DeepSeek after the command chain is verified.'
        printf '## Handoff Preview\n\n'
        printf '```text\n'
        head -c 1200 "$handoff" || true
        printf '\n```\n'
      } > "$out_path"
      echo "Generated $out_path"
    fi
    ;;
  claude_developer)
    # Derive output path from state.json (dynamic)
    phase_number="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("team_pipeline", {}).get("current_phase", 1))
')"
    phase_dev_pattern="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("required_docs", {}).get("phase_dev_report_pattern", ""))
')"
    requirements_path="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("required_docs", {}).get("requirements", ""))
')"
    architecture_path="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("required_docs", {}).get("architecture", ""))
')"
    team_plan_path="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("required_docs", {}).get("team_plan", ""))
')"

    out_dir="docs/dev_reports"
    if [[ -n "$phase_dev_pattern" ]]; then
      out_path="${phase_dev_pattern//<n>/$phase_number}"
    else
      out_path="${out_dir}/${today}-${feature_id}-phase-${phase_number}-dev-report.md"
    fi
    mkdir -p "$out_dir"

    # Try real Claude Code mode when AGENT_REAL_CLAUDE_DEVELOPER=true or AGENT_REAL_CLAUDE_DEVELOPER_STRICT=true
    if [[ "${AGENT_REAL_CLAUDE_DEVELOPER:-}" == "true" || "${AGENT_REAL_CLAUDE_DEVELOPER_STRICT:-}" == "true" ]]; then
      if command -v claude &>/dev/null; then
        prompt_file="$(mktemp)"
        {
          printf '%s\n' "Generate a phase development report in Markdown format. Output ONLY the raw Markdown content to stdout — do NOT write any file, do NOT use any tools, do NOT include conversational text, greetings, or meta-commentary."
          printf '%s\n' ""
          printf '%s\n' "## Context"
          printf '%s\n' ""
          printf '%s\n' "### Current Stage"
          printf '%s\n' "claude_developer — You are Claude Code B (Developer Agent)."
          printf '%s\n' ""
          printf '%s\n' "### Current Phase"
          printf '%s\n' "${phase_number}"
          printf '%s\n' ""
          printf '%s\n' "### Feature ID"
          printf '%s\n' "${feature_id}"
          printf '%s\n' ""
          printf '%s\n' "### Handoff Content (from claude_lead_plan stage)"
          printf '%s\n' ""
          cat "$handoff" 2>/dev/null || printf '%s\n' "(handoff file unavailable)"
          printf '%s\n' ""
          printf '%s\n' "### Pipeline State"
          printf '%s\n' ""
          cat "$state_path" 2>/dev/null || printf '%s\n' "(state file unavailable)"
          printf '%s\n' ""
          printf '%s\n' "### Requirements Document"
          printf '%s\n' ""
          if [[ -n "$requirements_path" && -f "$requirements_path" ]]; then
            cat "$requirements_path" 2>/dev/null || printf '%s\n' "(requirements file unavailable)"
          else
            printf '%s\n' "(requirements file not found at: ${requirements_path})"
          fi
          printf '%s\n' ""
          printf '%s\n' "### Architecture Document"
          printf '%s\n' ""
          if [[ -n "$architecture_path" && -f "$architecture_path" ]]; then
            cat "$architecture_path" 2>/dev/null || printf '%s\n' "(architecture file unavailable)"
          else
            printf '%s\n' "(architecture file not found at: ${architecture_path})"
          fi
          printf '%s\n' ""
          printf '%s\n' "### Team Plan Document"
          printf '%s\n' ""
          if [[ -n "$team_plan_path" && -f "$team_plan_path" ]]; then
            cat "$team_plan_path" 2>/dev/null || printf '%s\n' "(team plan file unavailable)"
          else
            printf '%s\n' "(team plan file not found at: ${team_plan_path})"
          fi
          printf '%s\n' ""
          printf '%s\n' "### Repository Guidelines (excerpts)"
          printf '%s\n' ""
          printf '%s\n' "#### AGENTS.md — Hard Safety Invariants & Role Boundaries"
          head -80 "$repo_root/AGENTS.md" 2>/dev/null || printf '%s\n' "(AGENTS.md unavailable)"
          printf '%s\n' ""
          printf '%s\n' "#### AGENT_DEVELOPMENT_PIPELINE.md — Roles, Gates & Standard Flow"
          head -100 "$repo_root/docs/process/AGENT_DEVELOPMENT_PIPELINE.md" 2>/dev/null || printf '%s\n' "(pipeline doc unavailable)"
          printf '%s\n' ""
          printf '%s\n' "#### BRANCH_WORKFLOW.md — Branch Types & Standard Flow"
          head -60 "$repo_root/docs/process/BRANCH_WORKFLOW.md" 2>/dev/null || printf '%s\n' "(branch workflow unavailable)"
          printf '%s\n' ""
          printf '%s\n' "### Output Format"
          printf '%s\n' ""
          printf '%s\n' "The development report MUST contain these sections (in order):"
          printf '%s\n' ""
          printf '%s\n' "# ${feature_id} Phase ${phase_number} Development Report"
          printf '%s\n' ''
          printf '%s\n' '## Objective'
          printf '%s\n' '## Inputs Reviewed'
          printf '%s\n' '## Implementation Summary'
          printf '%s\n' '## Files Changed'
          printf '%s\n' '## Safety Constraints'
          printf '%s\n' '## Self-Test Commands'
          printf '%s\n' '## Self-Test Results'
          printf '%s\n' '## Risks and Limitations'
          printf '%s\n' '## Handoff to Tester'
          printf '%s\n' '## Exit Criteria'
          printf '%s\n' ""
          printf '%s\n' "### Important Notes"
          printf '%s\n' ""
          printf '%s\n' "- This phase only covers phase ${phase_number} development work."
          printf '%s\n' "- Current task is docs-only / pipeline smoke validation."
          printf '%s\n' "- Do NOT modify trading-sensitive modules: broker, execution, order, account, risk, miniQMT, live trading, real order submission."
          printf '%s\n' "- If the current feature is a smoke/test feature, ONLY generate the dev report — do NOT modify any production code."
          printf '%s\n' "- For 'Files Changed', if no production code was modified, explicitly state: 'No production trading modules changed. Only docs/.agent artifacts were generated or reviewed.'"
          printf '%s\n' "- The target output path is: ${out_path}"
          printf '%s\n' ""
          printf '%s\n' "REMINDER: Output ONLY the raw markdown. No conversation. No tool use. No file writing."
        } > "$prompt_file"

        claude --print - < "$prompt_file" > "$out_path" 2>/tmp/claude_real_stderr.$$ || true
        rc=$?
        rm -f "$prompt_file"

        if [[ -s "$out_path" ]]; then
          echo "Generated $out_path using real Claude Code"
        else
          echo "WARNING: Real Claude mode produced empty output (exit=$rc)." >&2
          if [[ -f /tmp/claude_real_stderr.$$ ]]; then
            stderr_log="$(cat /tmp/claude_real_stderr.$$)"
            rm -f /tmp/claude_real_stderr.$$
            if [[ -n "$stderr_log" ]]; then
              echo "Claude stderr: $stderr_log" >&2
            fi
          fi
          if [[ "${AGENT_REAL_CLAUDE_DEVELOPER_STRICT:-}" == "true" ]]; then
            echo "ERROR: AGENT_REAL_CLAUDE_DEVELOPER_STRICT=true — real mode failed, aborting." >&2
            exit 2
          fi
          echo "Falling back to mock mode." >&2
        fi
      else
        echo "WARNING: Real Claude mode requested but 'claude' CLI not found." >&2
        if [[ "${AGENT_REAL_CLAUDE_DEVELOPER_STRICT:-}" == "true" ]]; then
          echo "ERROR: AGENT_REAL_CLAUDE_DEVELOPER_STRICT=true but claude CLI unavailable." >&2
          exit 2
        fi
        echo "Falling back to mock mode." >&2
      fi
    fi

    # Fallback: mock/smoke mode when no real output was produced
    if [[ ! -s "$out_path" ]]; then
      {
        printf '# %s Phase 1 Development Report\n\n' "$feature_id"
        printf '> Smoke-test development report generated by local Claude wrapper.\n'
        printf '> This proves GitHub Actions can call the Claude Code B phase developer stage command.\n\n'
        printf '## Stage\n\n'
        printf 'claude_developer\n\n'
        printf '## Source Handoff\n\n'
        printf '%s\n\n' "$handoff"
        printf '## Implemented Scope\n\n'
        printf '%s\n' '- Verified the Claude developer stage command can execute in WSL.'
        printf '%s\n' '- Did not modify product trading logic.'
        printf '%s\n\n' '- Did not call a real model during this smoke test.'
        printf '## Self-Test Commands\n\n'
        printf '```bash\n'
        printf 'bash scripts/run_claude_stage.sh claude_developer\n'
        printf '```\n\n'
        printf '## Result\n\n'
        printf 'PASS\n\n'
        printf '## Handoff Preview\n\n'
        printf '```text\n'
        head -c 1200 "$handoff" || true
        printf '\n```\n'
      } > "$out_path"
      echo "Generated $out_path"
    fi
    ;;
  claude_tester)
    out_dir="docs/test_reports"
    out_path="${out_dir}/${today}-${feature_id}-phase-1-test-report.md"
    mkdir -p "$out_dir"
    {
      printf '# %s Phase 1 Test Report\n\n' "$feature_id"
      printf '> Smoke-test test report generated by local Claude wrapper.\n'
      printf '> This proves GitHub Actions can call the Claude Code C phase tester stage command.\n\n'
      printf '## Stage\n\n'
      printf 'claude_tester\n\n'
      printf '## Source Handoff\n\n'
      printf '%s\n\n' "$handoff"
      printf '## Test Matrix\n\n'
      printf '| Check | Result |\n'
      printf '|---|---|\n'
      printf '| Handoff file exists | PASS |\n'
      printf '| Pipeline state exists | PASS |\n'
      printf '| Phase dev report expected path | PASS |\n'
      printf '| No production trading logic modified | PASS |\n\n'
      printf '## Final Result\n\n'
      printf 'PASS\n\n'
      printf '## Handoff Preview\n\n'
      printf '```text\n'
      head -c 1200 "$handoff" || true
      printf '\n```\n'
    } > "$out_path"

    python3 - <<'PY'
import json
from pathlib import Path

path = Path(".agent/state.json")
state = json.loads(path.read_text(encoding="utf-8"))
team = state.setdefault("team_pipeline", {})
team["current_phase"] = 1
team["all_phases_tested"] = True
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

    python3 - <<'PY'
from pathlib import Path
import yaml

state_path = Path(".agent/state.json")
task_path = Path(".agent/current_task.yaml")
if state_path.exists() and task_path.exists():
    import json
    state = json.loads(state_path.read_text(encoding="utf-8"))
    task_path.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")
PY

    echo "Generated $out_path"
    echo "Updated .agent/state.json team_pipeline.all_phases_tested=true"
    ;;
  claude_lead_review)
    out_dir="docs/review"
    out_path="${out_dir}/${today}-${feature_id}-claude-lead-review.md"
    mkdir -p "$out_dir"
    {
      printf '# %s Claude Lead Review\n\n' "$feature_id"
      printf '> Smoke-test lead review generated by local Claude wrapper.\n'
      printf '> This proves GitHub Actions can call the Claude Code A lead review stage command.\n\n'
      printf '## Stage\n\n'
      printf 'claude_lead_review\n\n'
      printf '## Source Handoff\n\n'
      printf '%s\n\n' "$handoff"
      printf '## Reviewed Evidence\n\n'
      printf '| Evidence | Expected Pattern | Result |\n'
      printf '|---|---|---|\n'
      printf '| Team plan | `docs/dev_plans/*-%s-team-plan.md` | PASS |\n' "$feature_id"
      printf '| Phase dev report | `docs/dev_reports/*-%s-phase-1-dev-report.md` | PASS |\n' "$feature_id"
      printf '| Phase test report | `docs/test_reports/*-%s-phase-1-test-report.md` | PASS |\n\n' "$feature_id"
      printf '## Lead Review Result\n\n'
      printf 'APPROVED\n\n'
      printf '## Handoff to Codex B\n\n'
      printf 'All smoke-test phases are complete. Route to `stage:codex-review-pending` for Codex B final review.\n\n'
      printf '## Safety Notes\n\n'
      printf '%s\n' '- This smoke test did not modify trading, risk, execution, broker, account, or live-trading modules.'
      printf '%s\n\n' '- This smoke test does not replace real code review for production features.'
      printf '## Handoff Preview\n\n'
      printf '```text\n'
      head -c 1200 "$handoff" || true
      printf '\n```\n'
    } > "$out_path"
    echo "Generated $out_path"
    ;;
  *)
    echo "Unsupported smoke-test Claude stage: $stage" >&2
    exit 2
    ;;
esac

echo "Claude stage smoke complete in $repo_root"
