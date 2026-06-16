#!/usr/bin/env bash
set -u
mkdir -p "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp"
: > "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stdout.log"
: > "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stderr.log"
rm -f "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.output.md" "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.exitcode"
export PATH="$HOME/.nvm/versions/node/v22.16.0/bin:$HOME/.local/bin:$HOME/.opencode/bin:$PATH"
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export ALL_PROXY=socks5://127.0.0.1:7890
export NO_PROXY=localhost,127.0.0.1
if [ -n "" ] && [ -x "$CODEX_CLI_PATH" ]; then
  CODEX_BIN="$CODEX_CLI_PATH"
elif [ -x "/home/ly/.nvm/versions/node/v22.16.0/bin/codex" ]; then
  CODEX_BIN="/home/ly/.nvm/versions/node/v22.16.0/bin/codex"
else
  CODEX_BIN="$(command -v codex || true)"
fi
if [ -z "$CODEX_BIN" ]; then
  echo "ERROR: codex CLI not found" >> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stderr.log"
  echo "PATH=$PATH" >> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stderr.log"
  echo 127 > "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.exitcode"
  exit 127
fi
echo "Using Codex: $CODEX_BIN" >> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stdout.log"
"$CODEX_BIN" --version >> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stdout.log" 2>> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stderr.log" || true
"$CODEX_BIN" login status >> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stdout.log" 2>> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stderr.log" || true
echo "Running Codex codex_architect with 20m timeout..." >> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stdout.log"
timeout --kill-after=30 1200 "$CODEX_BIN" exec \
  --cd "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent" \
  --sandbox read-only \
  --color never \
  --output-last-message "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.output.md" \
  - < "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.prompt.md" >> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stdout.log" 2>> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stderr.log"
CODEX_EXIT=$?
echo "$CODEX_EXIT" > "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.exitcode"
if [ "$CODEX_EXIT" -eq 124 ]; then
  echo "ERROR: Codex codex_architect timed out after 20 minutes" >> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stderr.log"
fi
if [ -s "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.output.md" ]; then
  echo "OUTPUT_FILE: /mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.output.md" >> "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/.agent/tmp/codex_architect.stdout.log"
fi
exit "$CODEX_EXIT"