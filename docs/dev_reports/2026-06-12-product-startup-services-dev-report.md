# Product Startup Services — Development Report
# 产品启动服务 — 开发报告

Date: 2026-06-12
Developer Role: Developer Agent
Branch: feature/quant-factor-v1

---

## 1. Scope / 范围

- **Development Guide / 开发指南:** `docs/design/2026-06-12-product-startup-services-development-guide.md`
- **Architecture / 架构:** `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md`
- **Requirements / 需求:** `docs/requirements/2026-06-11-wsl-product-runtime-ai-agent-requirements.md`
- **Python:** `.venv/bin/python` → Python 3.13.5

---

## 2. Modified Files / 修改文件

### Source / 源码

| File / 文件 | Action / 操作 | Purpose / 目的 |
|---|---|---|
| `scripts/start_product.py` | Modified | Add `--no-aktools`, `--full` flags; default AkTools ON; dry-run before port check |
| `scripts/start.sh` | Modified | Update usage header for new flags |
| `scripts/restart.sh` | Modified | Update usage header for new flags |

### Docs / 文档

| File / 文件 | Action / 操作 | Purpose / 目的 |
|---|---|---|
| `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md` | Modified | Add §9.5 describing default startup behavior and agent classification |
| `docs/user_guides/2026-06-11-a-share-live-data-closed-loop-user-manual.md` | Modified | Rewrite §3.2 with one-command startup; move manual cmds to troubleshooting §3.3 |

### Tests / 测试

| File / 文件 | Action / 操作 | Purpose / 目的 |
|---|---|---|
| `tests/test_product_process_manager.py` | Modified | Add `TestStartupModes` (8 new tests) |

---

## 3. Feature-to-Code Map / 功能映射

| Requirement / 需求 ID | Code / 实现位置 | Tests / 测试 |
|---|---|---|
| Default startup includes AkTools | `start_product.py:368` — `start_aktools = not args.no_aktools ...` | `test_default_startup_includes_aktools` |
| `--no-aktools` skips AkTools | `start_product.py:368` — `not args.no_aktools` check | `test_no_aktools_skips_aktools` |
| `--full` implies AkTools + BugFix | `start_product.py:368-369` — `start_bugfix = args.with_bugfix or args.full` | `test_full_implies_aktools_and_bugfix` |
| `--with-aktools` backward compat | `start_product.py:353` — `argparse.SUPPRESS` hidden flag | `test_with_aktools_backward_compat` |
| Dry-run lists planned services | `start_product.py:387-403` — before port check | `test_dry_run_default_lists_aktools` |
| PID metadata accuracy | `start_product.py:505-514` — `aktools_pid`, `bug_fix_agent_requested` | `test_pid_metadata_aktools_only_when_started` |
| Dry-run returns before port check | `start_product.py:387` — moved before Step 4 | — |
| Doc: default startup behavior | `architecture.md:§9.5` | — |
| Doc: user manual quick start | `user_manual.md:§3.2` | — |

---

## 4. Verification / 验证

### Commands & Results / 命令与结果

```bash
# Ruff
.venv/bin/python -m ruff check scripts/start_product.py tests/test_product_process_manager.py
# Result: All checks passed!

# Shell syntax
bash -n scripts/start.sh && echo "start.sh OK" && bash -n scripts/restart.sh && echo "restart.sh OK"
# Result: start.sh OK, restart.sh OK

# Py_compile
.venv/bin/python -m py_compile scripts/start_product.py
# Result: No errors.

# Pytest
.venv/bin/python -m pytest tests/test_product_process_manager.py tests/test_aktools_compat_app.py -q
# Result: 13 passed (3 original + 8 startup mode + 2 aktools)
```

### Dry-Run Smoke Results / Dry-Run 验证结果

**Default:** `bash scripts/start.sh --dry-run`

```
[DRY-RUN] 计划启动以下服务:
  1. AkTools  -> http://localhost:8080
  2. FastAPI   -> http://localhost:8000
  3. Streamlit -> http://localhost:8771
```

**--no-aktools:** `bash scripts/start.sh --dry-run --no-aktools`

```
[DRY-RUN] 计划启动以下服务:
  1. FastAPI   -> http://localhost:8000
  2. Streamlit -> http://localhost:8771
```

**--full:** `bash scripts/start.sh --dry-run --full`

```
[DRY-RUN] 计划启动以下服务:
  1. AkTools  -> http://localhost:8080
  2. FastAPI   -> http://localhost:8000
  3. Streamlit -> http://localhost:8771
  4. BugFixAgent (job, requires DEEPSEEK_API_KEY)
```

### Git / Git 检查

```bash
git status --short --branch
git diff --stat
git diff --check
```

**Result:** Clean. No trailing whitespace or conflict markers. Feedback files (`feedback/bugs/triaged/`, `feedback/index.json`) have pre-existing changes not introduced by this task.

---

## 5. Acceptance Gate Check / 验收门禁确认

| Requirement / 要求 | Status / 状态 |
|---|---|
| `bash scripts/start.sh --dry-run` lists AkTools, FastAPI, Streamlit | **PASS** |
| `--dry-run --full` lists BugFixAgent | **PASS** |
| `--dry-run --no-aktools` skips AkTools | **PASS** |
| Tests prove default startup includes AkTools | **PASS** (`test_default_startup_includes_aktools`) |
| Docs state AkShare is not standalone service | **PASS** (§3.2 note + architecture §9.5) |
| Docs state which Agents are background jobs vs API-internal | **PASS** (architecture §9.5) |
| No change enables real automatic trading | **PASS** (no changes to `ENABLE_LIVE_TRADING`, risk, execution) |

---

## 6. Safety Confirmation / 安全确认

- [x] **默认 AkTools + FastAPI + Streamlit，不改默认交易模式**
- [x] **`--full` 在缺少 `DEEPSEEK_API_KEY` 时不静默启动 BugFixAgent**（`_start_bugfix_job` 检查 key）
- [x] **Risk Agent 一票否决未被绕过**（未修改 `risk_engine/`）
- [x] **`LEVEL_3_AUTO` 未启用**
- [x] **未提交密钥**
- [x] **未创建虚假服务进程**（FactorDiscoveryAgent 等仍是 API 内部模块）

---

## 7. Deliverables / 交付物

1. `scripts/start_product.py` updated with `--no-aktools`, `--full`, and default AkTools startup.
2. `scripts/start.sh` / `restart.sh` usage headers updated.
3. 8 new tests covering all startup modes in `test_product_process_manager.py`.
4. Dry-run moved before port conflict check (fixes usability bug).
5. Architecture doc updated with startup behavior clarification.
6. User manual rewritten for one-command startup.
7. All verification checks pass.
8. This development report in Chinese + English.

Signed-off for / 移交: **Test Engineer Agent** verification.
