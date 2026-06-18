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

    # Fallback blocked - formal artifacts must not be generated as smoke
    if [[ ! -s "$out_path" ]]; then
      echo "ERROR: claude_lead_plan did not produce a valid artifact at $out_path" >&2
      exit 2
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

    # Fallback blocked - formal artifacts must not be generated as smoke
    if [[ ! -s "$out_path" ]]; then
      echo "ERROR: claude_developer did not produce a valid artifact at $out_path" >&2
      exit 2
    fi
    ;;
  claude_tester)
    # Derive output path and input doc paths from state.json (dynamic)
    phase_number="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("team_pipeline", {}).get("current_phase", 1))
')"
    phase_test_pattern="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("required_docs", {}).get("phase_test_report_pattern", ""))
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
    dev_report_pattern="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("required_docs", {}).get("phase_dev_report_pattern", ""))
')"

    out_dir="docs/test_reports"
    if [[ -n "$phase_test_pattern" ]]; then
      out_path="${phase_test_pattern//<n>/$phase_number}"
    else
      out_path="${out_dir}/${today}-${feature_id}-phase-${phase_number}-test-report.md"
    fi

    # Derive expected dev report path for prompt context
    dev_report_path=""
    if [[ -n "$dev_report_pattern" ]]; then
      dev_report_path="${dev_report_pattern//<n>/$phase_number}"
    fi

    mkdir -p "$out_dir"

    # Try real Claude Code mode when AGENT_REAL_CLAUDE_TESTER=true or AGENT_REAL_CLAUDE_TESTER_STRICT=true
    if [[ "${AGENT_REAL_CLAUDE_TESTER:-}" == "true" || "${AGENT_REAL_CLAUDE_TESTER_STRICT:-}" == "true" ]]; then
      if command -v claude &>/dev/null; then
        prompt_file="$(mktemp)"
        {
          printf '%s\n' "Generate a phase test report in Markdown format. Output ONLY the raw Markdown content to stdout — do NOT write any file, do NOT use any tools, do NOT include conversational text, greetings, or meta-commentary."
          printf '%s\n' ""
          printf '%s\n' "## Context"
          printf '%s\n' ""
          printf '%s\n' "### Current Stage"
          printf '%s\n' "claude_tester — You are Claude Code C (Test Engineer Agent)."
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
          printf '%s\n' "### Development Report"
          printf '%s\n' ""
          if [[ -n "$dev_report_path" && -f "$dev_report_path" ]]; then
            cat "$dev_report_path" 2>/dev/null || printf '%s\n' "(dev report file unavailable)"
          else
            printf '%s\n' "(dev report file not found at: ${dev_report_path})"
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
          printf '%s\n' "#### SELF_TEST_CHECKLIST.md — Key constraints"
          head -40 "$repo_root/docs/policy/SELF_TEST_CHECKLIST.md" 2>/dev/null || printf '%s\n' "(SELF_TEST_CHECKLIST.md unavailable)"
          printf '%s\n' ""
          printf '%s\n' "### Output Format"
          printf '%s\n' ""
          printf '%s\n' "The test report MUST contain these sections (in order):"
          printf '%s\n' ""
          printf '%s\n' "# ${feature_id} Phase ${phase_number} Test Report"
          printf '%s\n' ''
          printf '%s\n' '## Objective'
          printf '%s\n' '## Inputs Reviewed'
          printf '%s\n' '## Test Scope'
          printf '%s\n' '## Test Commands'
          printf '%s\n' '## Test Results'
          printf '%s\n' '## Artifact Verification'
          printf '%s\n' '## Safety Verification'
          printf '%s\n' '## Regression Checks'
          printf '%s\n' '## Risks and Limitations'
          printf '%s\n' '## Handoff to Lead Review'
          printf '%s\n' '## Exit Criteria'
          printf '%s\n' ""
          printf '%s\n' "### Important Notes"
          printf '%s\n' ""
          printf '%s\n' "- This phase only verifies phase ${phase_number} development work."
          printf '%s\n' "- Current task is docs-only / pipeline smoke validation."
          printf '%s\n' "- Do NOT modify production code or trading-sensitive modules: broker, execution, order, account, risk, miniQMT, live trading, real order submission."
          printf '%s\n' "- Do NOT execute any real trading, real order submission, broker connection, or risk policy enforcement."
          printf '%s\n' "- If the current feature is a smoke/test feature, ONLY generate the test report — do NOT modify any production code."
          printf '%s\n' "- For 'Artifact Verification', at minimum check: requirements document exists, architecture document exists, team plan exists, dev report exists, test report generated at expected path."
          printf '%s\n' "- For 'Safety Verification', explicitly state: 'No production trading modules changed. No broker / execution / order / account / risk / miniQMT / live trading code was modified. No real order submission or live trading behavior was introduced.'"
          printf '%s\n' "- For 'Test Results', clearly state PASS/FAIL and list verification commands or static check results."
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
          if [[ "${AGENT_REAL_CLAUDE_TESTER_STRICT:-}" == "true" ]]; then
            echo "ERROR: AGENT_REAL_CLAUDE_TESTER_STRICT=true — real mode failed, aborting." >&2
            exit 2
          fi
          echo "Falling back to mock mode." >&2
        fi
      else
        echo "WARNING: Real Claude mode requested but 'claude' CLI not found." >&2
        if [[ "${AGENT_REAL_CLAUDE_TESTER_STRICT:-}" == "true" ]]; then
          echo "ERROR: AGENT_REAL_CLAUDE_TESTER_STRICT=true but claude CLI unavailable." >&2
          exit 2
        fi
        echo "Falling back to mock mode." >&2
      fi
    fi

    # Fallback blocked - formal artifacts must not be generated as smoke
    if [[ ! -s "$out_path" ]]; then
      echo "ERROR: claude_tester did not produce a valid artifact at $out_path" >&2
      exit 2
    fi

    # === Deterministic state update: always mark all_phases_tested=true ===
    # This must run for both real and mock mode to prevent dev/test infinite loop.
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

    echo "Updated .agent/state.json team_pipeline.all_phases_tested=true"
    ;;
  claude_lead_review)
    # Derive input doc paths from state.json (dynamic)
    phase_number="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("team_pipeline", {}).get("current_phase", 1))
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
    dev_report_pattern="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("required_docs", {}).get("phase_dev_report_pattern", ""))
')"
    test_report_pattern="$(python3 -c '
import json
s = json.load(open(".agent/state.json", encoding="utf-8"))
print(s.get("required_docs", {}).get("phase_test_report_pattern", ""))
')"

    out_dir="docs/review"
    out_path="${out_dir}/${today}-${feature_id}-claude-lead-review.md"

    # Derive dev/test report paths for prompt context
    dev_report_path=""
    if [[ -n "$dev_report_pattern" ]]; then
      dev_report_path="${dev_report_pattern//<n>/$phase_number}"
    fi
    test_report_path=""
    if [[ -n "$test_report_pattern" ]]; then
      test_report_path="${test_report_pattern//<n>/$phase_number}"
    fi

    mkdir -p "$out_dir"

    # Try real Claude Code mode when AGENT_REAL_CLAUDE_LEAD_REVIEW=true or AGENT_REAL_CLAUDE_LEAD_REVIEW_STRICT=true
    if [[ "${AGENT_REAL_CLAUDE_LEAD_REVIEW:-}" == "true" || "${AGENT_REAL_CLAUDE_LEAD_REVIEW_STRICT:-}" == "true" ]]; then
      if command -v claude &>/dev/null; then
        prompt_file="$(mktemp)"
        {
          printf '%s\n' "Generate a Claude lead review report in Markdown format. Output ONLY the raw Markdown content to stdout — do NOT write any file, do NOT use any tools, do NOT include conversational text, greetings, or meta-commentary."
          printf '%s\n' ""
          printf '%s\n' "## Context"
          printf '%s\n' ""
          printf '%s\n' "### Current Stage"
          printf '%s\n' "claude_lead_review — You are Claude Code A (Lead Reviewer). You review all prior stage artifacts before handoff to Codex B."
          printf '%s\n' ""
          printf '%s\n' "### Feature ID"
          printf '%s\n' "${feature_id}"
          printf '%s\n' ""
          printf '%s\n' "### Phase Number"
          printf '%s\n' "${phase_number}"
          printf '%s\n' ""
          printf '%s\n' "### Handoff Content (from prior stages)"
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
          printf '%s\n' "### Development Report"
          printf '%s\n' ""
          if [[ -n "$dev_report_path" && -f "$dev_report_path" ]]; then
            cat "$dev_report_path" 2>/dev/null || printf '%s\n' "(dev report file unavailable)"
          else
            printf '%s\n' "(dev report file not found at: ${dev_report_path})"
          fi
          printf '%s\n' ""
          printf '%s\n' "### Test Report"
          printf '%s\n' ""
          if [[ -n "$test_report_path" && -f "$test_report_path" ]]; then
            cat "$test_report_path" 2>/dev/null || printf '%s\n' "(test report file unavailable)"
          else
            printf '%s\n' "(test report file not found at: ${test_report_path})"
          fi
          printf '%s\n' ""
          printf '%s\n' "### Phase Gate Files"
          printf '%s\n' ""
          printf '%s\n' "#### phase_dev_gate.json"
          if [[ -f ".agent/gates/phase_dev_gate.json" ]]; then
            cat ".agent/gates/phase_dev_gate.json" 2>/dev/null
          else
            printf '%s\n' "(phase_dev_gate.json not found)"
          fi
          printf '%s\n' ""
          printf '%s\n' "#### phase_test_gate.json"
          if [[ -f ".agent/gates/phase_test_gate.json" ]]; then
            cat ".agent/gates/phase_test_gate.json" 2>/dev/null
          else
            printf '%s\n' "(phase_test_gate.json not found)"
          fi
          printf '%s\n' ""
          printf '%s\n' "#### team_plan_gate.json"
          if [[ -f ".agent/gates/team_plan_gate.json" ]]; then
            cat ".agent/gates/team_plan_gate.json" 2>/dev/null
          else
            printf '%s\n' "(team_plan_gate.json not found)"
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
          printf '%s\n' "#### SELF_TEST_CHECKLIST.md — Key constraints"
          head -40 "$repo_root/docs/policy/SELF_TEST_CHECKLIST.md" 2>/dev/null || printf '%s\n' "(SELF_TEST_CHECKLIST.md unavailable)"
          printf '%s\n' ""
          printf '%s\n' "### Output Format"
          printf '%s\n' ""
          printf '%s\n' "The lead review report MUST contain these sections (in order):"
          printf '%s\n' ""
          printf '%s\n' "# ${feature_id} Claude Lead Review"
          printf '%s\n' ''
          printf '%s\n' '## Objective'
          printf '%s\n' '## Inputs Reviewed'
          printf '%s\n' '## Review Scope'
          printf '%s\n' '## Artifact Review'
          printf '%s\n' '## Implementation Review'
          printf '%s\n' '## Test Review'
          printf '%s\n' '## Safety Review'
          printf '%s\n' '## Process Review'
          printf '%s\n' '## Findings'
          printf '%s\n' '## Required Fixes'
          printf '%s\n' '## Recommendations'
          printf '%s\n' '## Approval Decision'
          printf '%s\n' '## Handoff to Codex Review'
          printf '%s\n' ""
          printf '%s\n' "### Important Notes"
          printf '%s\n' ""
          printf '%s\n' "- You are Claude Code A (Lead Reviewer). You do NOT modify any production code."
          printf '%s\n' "- Current task is docs-only / pipeline smoke validation."
          printf '%s\n' "- Do NOT modify trading-sensitive modules: broker, execution, order, account, risk, miniQMT, live trading, real order submission."
          printf '%s\n' "- Do NOT introduce real order submission, live trading, account operations, or risk enforcement logic."
          printf '%s\n' "- Approval Decision MUST be one of: APPROVED, APPROVED_WITH_NOTES, CHANGES_REQUESTED, BLOCKED."
          printf '%s\n' "- For 'Safety Review', explicitly state: 'No production trading modules were modified. No broker / execution / order / account / risk / miniQMT / live trading code was changed. No real order submission behavior was introduced.'"
          printf '%s\n' "- For 'Handoff to Codex Review', include: (1) Verify required artifacts exist, (2) Verify no trading-sensitive modules changed, (3) Verify Merge Gate/manual approval remains enforced, (4) Treat as docs-only pipeline validation."
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
          if [[ "${AGENT_REAL_CLAUDE_LEAD_REVIEW_STRICT:-}" == "true" ]]; then
            echo "ERROR: AGENT_REAL_CLAUDE_LEAD_REVIEW_STRICT=true — real mode failed, aborting." >&2
            exit 2
          fi
          echo "Falling back to mock mode." >&2
        fi
      else
        echo "WARNING: Real Claude mode requested but 'claude' CLI not found." >&2
        if [[ "${AGENT_REAL_CLAUDE_LEAD_REVIEW_STRICT:-}" == "true" ]]; then
          echo "ERROR: AGENT_REAL_CLAUDE_LEAD_REVIEW_STRICT=true but claude CLI unavailable." >&2
          exit 2
        fi
        echo "Falling back to mock mode." >&2
      fi
    fi

    # Fallback blocked - formal artifacts must not be generated as smoke
    if [[ ! -s "$out_path" ]]; then
      echo "ERROR: claude_lead_review did not produce a valid artifact at $out_path" >&2
      exit 2
    fi
    ;;
  *)
    echo "Unsupported smoke-test Claude stage: $stage" >&2
    exit 2
    ;;
esac

echo "Claude stage smoke complete in $repo_root"
