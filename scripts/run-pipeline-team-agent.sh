#!/usr/bin/env bash
set -euo pipefail

stage="${1:?stage is required}"
mode="${2:-}"
repo_root="."
handoff=".agent/handoff/${stage}.md"
state_path=".agent/state.json"
tmp_dir=".agent/tmp"
preflight_only="false"

export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$PATH"

if [[ "$mode" == "--preflight-only" ]]; then
  preflight_only="true"
elif [[ -n "$mode" ]]; then
  echo "Unsupported Team Pipeline runner option: $mode" >&2
  exit 2
fi

OPENCODE_LEAD_MODEL="opencode-go/glm-5.2"
OPENCODE_LEAD_VARIANT="max"
OPENCODE_TESTER_MODEL="opencode-go/deepseek-v4-pro"
OPENCODE_TESTER_VARIANT="max"
OPENCODE_DEVELOPER_MODEL="opencode-go/deepseek-v4-flash"
OPENCODE_DEVELOPER_VARIANT="max"
PREFLIGHT_TIMEOUT_SECONDS="${AGENT_PREFLIGHT_TIMEOUT_SECONDS:-180}"

if ! [[ "$PREFLIGHT_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
  echo "AGENT_PREFLIGHT_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi

case "$stage" in
  claude_lead_plan|claude_lead_review|postmortem|claude_developer|bugfix|claude_tester)
    ;;
  *)
    echo "Unsupported Team Pipeline stage: $stage" >&2
    exit 2
    ;;
esac

mkdir -p "$tmp_dir"
prompt_file="${tmp_dir}/${stage}.prompt.md"
stdout_file="${tmp_dir}/${stage}.stdout.log"
stderr_file="${tmp_dir}/${stage}.stderr.log"
metadata_file="${tmp_dir}/${stage}.execution.json"
starting_branch="$(git branch --show-current)"

if [[ "$preflight_only" != "true" ]]; then
  if [[ ! -f "$handoff" ]]; then
    echo "Missing handoff: $handoff" >&2
    exit 2
  fi

  if [[ ! -f "$state_path" ]]; then
    echo "Missing pipeline state: $state_path" >&2
    exit 2
  fi
fi

write_common_prompt() {
  cat <<EOF
你正在执行 GitHub Agent Pipeline 的正式阶段，stage ID 为 \`${stage}\`。

硬约束：
1. 先读取并遵守 AGENTS.md 及 handoff 中的文档顺序。
2. 必须使用 superpowers，先加载 using-superpowers，再选择当前任务需要的技能。
3. 所有用户可见输出和新增文档默认使用中文；代码标识和 JSON key 保留英文。
4. 只使用仓库相对路径。
5. 不得使用 mock、smoke、fallback 或预览产物冒充正式交付。
6. 不得自动合并 main，不得执行真实交易，不得绕过风控、股票池或人工确认。
7. 不得读取、输出或提交密钥、Token、Cookie、账户或 Broker 凭据。
8. 当前由 GitHub Stage Runner 管理提交与推送。不要执行 git commit、git push、git merge 或 gh pr merge。
9. 完成前必须运行可复现验证，并让现有阶段 gate 能从仓库文件独立确认结果。

下面是当前 handoff：

EOF
  cat "$handoff"
}

write_stage_prompt() {
  write_common_prompt
  cat <<'EOF'

执行要求：
EOF
  case "$stage" in
    claude_lead_plan)
      cat <<'EOF'
- 你是 OpenCode Team Leader。
- 使用 superpowers 的 writing-plans 能力检查并完善阶段计划。
- 读取需求和架构文档，将工作拆成可独立开发、测试和回退的阶段。
- 写入 handoff 指定的 team plan，不要只在 stdout 给建议。
- 每个阶段必须包含范围、非目标、分支、测试命令、验收条件和受限模块声明。
EOF
      ;;
    claude_lead_review)
      cat <<'EOF'
- 你是 OpenCode Team Leader Reviewer。
- 使用 superpowers 的 requesting-code-review 和 verification-before-completion。
- 审阅全部阶段开发报告、测试报告、git diff、gate 和安全边界。
- 写入 handoff 指定的 lead review 报告，不要修改业务代码。
- 若阶段不完整或测试证据不足，必须 fail closed 并退回开发/测试循环。
EOF
      ;;
    postmortem)
      cat <<'EOF'
- 你是 OpenCode Team Leader，负责失败复盘。
- 使用 superpowers 的 systematic-debugging 查明流程失败根因。
- 生成 handoff 指定的复盘文档，给出可验证的流程整改项。
- 不得借复盘阶段修改业务代码或绕过 gate。
EOF
      ;;
    claude_tester)
      cat <<'EOF'
- 你是 OpenCode Test Engineer，不是开发工程师。
- 必须使用 superpowers 的 verification-before-completion；遇到失败时使用 systematic-debugging。
- 严格执行 docs/process/TEST_ENGINEER_WORKFLOW.md：从当前 commit 创建临时 test 分支，完成测试后回到原分支并删除临时分支。
- 在原开发分支只能写入测试报告和允许的反馈 Bug 文件，不得修改业务代码。
- 复跑开发报告命令，并补充正常、非法、异常、fail-closed 和安全路径。
- 最终报告结论只能是 PASS、PASS_WITH_NOTES 或 REJECTED。
EOF
      ;;
    claude_developer|bugfix)
      cat <<'EOF'
- 你是 OpenCode Developer，兼容 stage ID 仍为 claude_developer。
- 必须先加载 using-superpowers；行为变更使用 test-driven-development；完成声明前使用 verification-before-completion。
- 使用 build Agent 的完整开发权限完成当前阶段，但不得执行提交、推送、合并或读取密钥。
- 按需求、架构和当前阶段计划实现最小必要变更，先写失败测试，再实现，再回归。
- 写入 handoff 指定的开发或修复报告，记录精确命令和结果。
- 报告中声称的每个变更文件必须真实存在，并出现在当前未提交 diff 中；非文档阶段必须同时包含实现和测试变更。
- 报告必须包含 `## 最终结论` 章节，并在该章节中显式给出 **PASS** 或 **PASS_WITH_NOTES** 决策标记，以便 gate 校验。
- 不得擅自扩大需求，不得触碰未经架构授权的受限交易模块。
EOF
      ;;
  esac
}

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Required command is unavailable: $name" >&2
    exit 2
  fi
}

require_opencode_runtime() {
  local model="$1"
  require_command opencode

  if ! timeout --signal=TERM --kill-after=10s "${PREFLIGHT_TIMEOUT_SECONDS}s" \
    opencode debug skill >"${tmp_dir}/opencode-skills.json" \
    2>"${tmp_dir}/opencode-skills.stderr"; then
    echo "OpenCode skill discovery failed." >&2
    exit 2
  fi
  if ! grep -q '"name": "using-superpowers"' "${tmp_dir}/opencode-skills.json"; then
    echo "OpenCode superpowers skill 'using-superpowers' is unavailable." >&2
    exit 2
  fi

  if ! timeout --signal=TERM --kill-after=10s "${PREFLIGHT_TIMEOUT_SECONDS}s" \
    opencode models >"${tmp_dir}/opencode-models.txt" \
    2>"${tmp_dir}/opencode-models.stderr"; then
    echo "OpenCode model discovery failed." >&2
    exit 2
  fi
  if ! grep -Fxq "$model" "${tmp_dir}/opencode-models.txt"; then
    echo "Required OpenCode model is unavailable: $model" >&2
    exit 2
  fi

  if ! timeout --signal=TERM --kill-after=10s "${PREFLIGHT_TIMEOUT_SECONDS}s" \
    opencode debug agent build >"${tmp_dir}/opencode-build-agent.txt" \
    2>"${tmp_dir}/opencode-build-agent.stderr"; then
    echo "OpenCode build agent configuration is unavailable." >&2
    exit 2
  fi
}

write_execution_metadata() {
  local provider="$1"
  local model="$2"
  local effort="$3"
  local workflow="$4"
  python3 - "$metadata_file" "$stage" "$provider" "$model" "$effort" "$workflow" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path, stage, provider, model, effort, workflow = sys.argv[1:]
payload = {
    "stage": stage,
    "provider": provider,
    "model": model,
    "effort_or_variant": effort,
    "workflow": workflow,
    "superpowers_required": True,
    "completed_at": datetime.now(timezone.utc).isoformat(),
}
Path(path).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
}

verify_probe_output() {
  local path="$1"
  local role="$2"
  if ! grep -q "PIPELINE_RUNTIME_OK" "$path"; then
    echo "Runtime preflight for '$role' did not return PIPELINE_RUNTIME_OK." >&2
    exit 2
  fi
}

verify_git_state_unchanged() {
  local before="$1"
  local after
  after="$(git status --porcelain=v1 --untracked-files=all)"
  if [[ "$after" != "$before" ]]; then
    echo "Runtime preflight modified the repository; failing closed." >&2
    diff -u <(printf '%s\n' "$before") <(printf '%s\n' "$after") >&2 || true
    exit 2
  fi
}

run_opencode_preflight() {
  local role="$1"
  local model="$2"
  local variant="$3"
  local before
  before="$(git status --porcelain=v1 --untracked-files=all)"
  stdout_file="${tmp_dir}/runtime-preflight-${role}.stdout.log"
  stderr_file="${tmp_dir}/runtime-preflight-${role}.stderr.log"
  metadata_file="${tmp_dir}/runtime-preflight-${role}.execution.json"

  require_opencode_runtime "$model"
  set +e
  timeout --signal=TERM --kill-after=10s "${PREFLIGHT_TIMEOUT_SECONDS}s" \
    opencode run \
    --model "$model" \
    --variant "$variant" \
    --agent plan \
    --format json \
    --dir "$repo_root" \
    --title "pipeline-runtime-preflight-${role}" \
    "这是只读运行时探针。不要调用任何工具，不要读取或修改文件，只输出 PIPELINE_RUNTIME_OK。" \
    >"$stdout_file" 2>"$stderr_file"
  local status=$?
  set -e
  if [[ $status -ne 0 ]]; then
    cat "$stderr_file" >&2
    if [[ $status -eq 124 || $status -eq 137 ]]; then
      echo "Runtime preflight for '$role' timed out after ${PREFLIGHT_TIMEOUT_SECONDS}s." >&2
    fi
    exit "$status"
  fi
  verify_probe_output "$stdout_file" "$role"
  verify_git_state_unchanged "$before"
  write_execution_metadata "opencode" "$model" "$variant" "runtime-preflight+superpowers"
}

verify_branch_restored() {
  local ending_branch
  ending_branch="$(git branch --show-current)"
  if [[ "$ending_branch" != "$starting_branch" ]]; then
    echo "Agent left the repository on branch '$ending_branch'; expected '$starting_branch'. Attempting auto-restore." >&2
    if git checkout "$starting_branch" 2>/dev/null; then
      echo "Auto-restored to '$starting_branch'." >&2
    else
      echo "Auto-restore failed; failing closed." >&2
      exit 2
    fi
  fi
}

verify_tester_did_not_modify_business_code() {
  local changed_path
  while IFS= read -r changed_path; do
    [[ -z "$changed_path" ]] && continue
    case "$changed_path" in
      .agent/*|docs/test_reports/*|feedback/bugs/open/*)
        ;;
      *)
        echo "Test Engineer modified a disallowed path on the original branch: $changed_path" >&2
        exit 2
        ;;
    esac
  done < <(
    {
      git diff --name-only
      git ls-files --others --exclude-standard
    } | sort -u
  )
}

if [[ "$preflight_only" == "true" ]]; then
  case "$stage" in
    claude_lead_plan|claude_lead_review|postmortem)
      run_opencode_preflight "lead" "$OPENCODE_LEAD_MODEL" "$OPENCODE_LEAD_VARIANT"
      ;;
    claude_tester)
      run_opencode_preflight \
        "tester" "$OPENCODE_TESTER_MODEL" "$OPENCODE_TESTER_VARIANT"
      ;;
    claude_developer|bugfix)
      run_opencode_preflight \
        "developer" "$OPENCODE_DEVELOPER_MODEL" "$OPENCODE_DEVELOPER_VARIANT"
      ;;
  esac
  echo "Team Pipeline runtime preflight completed: $stage"
  exit 0
fi

write_stage_prompt >"$prompt_file"

case "$stage" in
  claude_lead_plan|claude_lead_review|postmortem)
    require_opencode_runtime "$OPENCODE_LEAD_MODEL"
    if ! opencode run \
       --model "$OPENCODE_LEAD_MODEL" \
       --variant "$OPENCODE_LEAD_VARIANT" \
       --agent build \
       --format json \
       --dir "$repo_root" \
       --title "pipeline-${stage}" \
       "$(cat "$prompt_file")" >"$stdout_file" 2>"$stderr_file"; then
      cat "$stderr_file" >&2
      exit 2
    fi
    write_execution_metadata \
      "opencode" "$OPENCODE_LEAD_MODEL" "$OPENCODE_LEAD_VARIANT" "superpowers"
    ;;
  claude_tester)
    require_opencode_runtime "$OPENCODE_TESTER_MODEL"
    if ! opencode run \
      --model "$OPENCODE_TESTER_MODEL" \
      --variant "$OPENCODE_TESTER_VARIANT" \
      --agent build \
      --format json \
      --dir "$repo_root" \
      --title "pipeline-${stage}" \
      "$(cat "$prompt_file")" >"$stdout_file" 2>"$stderr_file"; then
      cat "$stderr_file" >&2
      exit 2
    fi
    verify_branch_restored
    verify_tester_did_not_modify_business_code
    write_execution_metadata \
      "opencode" "$OPENCODE_TESTER_MODEL" "$OPENCODE_TESTER_VARIANT" "superpowers"
    ;;
  claude_developer|bugfix)
    require_opencode_runtime "$OPENCODE_DEVELOPER_MODEL"
    echo "Prompt file size: $(wc -c < "$prompt_file") bytes"
    echo "Handoff file size: $(wc -c < "$handoff") bytes"
    if ! opencode run \
      --model "$OPENCODE_DEVELOPER_MODEL" \
      --variant "$OPENCODE_DEVELOPER_VARIANT" \
      --agent build \
      --format json \
      --dir "$repo_root" \
      --title "pipeline-${stage}" \
      "$(cat "$prompt_file")" >"$stdout_file" 2>"$stderr_file"; then
      echo "OpenCode Developer exited non-zero. stderr:" >&2
      cat "$stderr_file" >&2
      exit 2
    fi
    echo "OpenCode Developer completed. stdout lines: $(wc -l < "$stdout_file"), stderr lines: $(wc -l < "$stderr_file")"
    echo "stdout preview:" >&2
    head -5 "$stdout_file" >&2
    echo "stderr preview:" >&2
    head -5 "$stderr_file" >&2
    verify_branch_restored
    write_execution_metadata \
      "opencode" "$OPENCODE_DEVELOPER_MODEL" "$OPENCODE_DEVELOPER_VARIANT" \
      "build+superpowers"
    ;;
esac

echo "Team Pipeline stage completed: $stage"
