# 2026-06-12 Product Startup Services Architecture Review

结论：**不通过，需整改后再次提交 Review。**

## Review 范围

- 需求/开发指导：`docs/design/2026-06-12-product-startup-services-development-guide.md`
- 开发报告：`docs/dev_reports/2026-06-12-product-startup-services-dev-report.md`
- 测试报告：`docs/test_reports/2026-06-12-product-startup-services-test-report.md`
- 核查代码：
  - `scripts/start_product.py`
  - `scripts/start.sh`
  - `scripts/restart.sh`
  - `tests/test_product_process_manager.py`
  - `tests/test_aktools_compat_app.py`

## 阻断问题

### S2: FastAPI/Streamlit 启动失败时会遗留 AkTools 进程

位置：`scripts/start_product.py:447-464`

当前默认启动顺序为 AkTools -> FastAPI -> Streamlit。若 AkTools 已启动、随后 FastAPI 或 Streamlit 启动失败，失败清理逻辑只遍历 `(api_proc, streamlit_proc)`，没有终止 `aktools_proc`。

这违反了开发指导中的明确要求：

- `docs/design/2026-06-12-product-startup-services-development-guide.md:100`
- “Partial startup cleanup must terminate AkTools if it was already started and another required service fails.”

影响：

- `bash scripts/start.sh` 失败后可能留下 AkTools 占用 8080 端口。
- 后续一键启动可能继续失败或进入端口冲突路径。
- 用户会认为启动失败已“终止所有进程”，但实际仍有后台进程残留。

复现方式：

使用 monkeypatch 模拟 AkTools 启动成功、FastAPI 启动失败，结果为：

```text
system_exit 1
[('AkTools', False), ('Streamlit', True)]
```

其中 `AkTools=False` 表示未被 terminate。

整改要求：

1. 抽取统一清理函数，例如 `_terminate_processes(*procs)`。
2. 失败清理必须覆盖 `aktools_proc`、`api_proc`、`streamlit_proc`。
3. 清理日志不得声称“已终止所有进程”，除非确实尝试清理全部已启动进程。
4. 在 `tests/test_product_process_manager.py` 增加持久化测试：
   - 默认启动 AkTools 成功；
   - FastAPI 启动失败；
   - 断言 AkTools 被 terminate；
   - 断言 Streamlit 如已启动也被 terminate；
   - 断言程序以非 0 退出。

### S2: WSL 一键启动脚本缺少 LF 换行约束

位置：仓库根目录缺少 `.gitattributes`，当前工作区 `scripts/start.sh`、`scripts/restart.sh`、`scripts/stop.sh` 被 checkout 为 CRLF。

验证结果：

```text
git ls-files --eol scripts/start.sh scripts/restart.sh scripts/stop.sh
i/lf    w/crlf  attr/                  scripts/restart.sh
i/lf    w/crlf  attr/                  scripts/start.sh
i/lf    w/crlf  attr/                  scripts/stop.sh
```

在当前 Windows 工作区调用 WSL bash 校验：

```text
bash -n scripts/start.sh
scripts/start.sh: line 36: syntax error: unexpected end of file from `if' command on line 17
```

原因是 `core.autocrlf=true` 时工作区 shell 脚本变为 CRLF，WSL bash 可能将 `then\r` / `fi\r` 解释异常。项目目标环境明确包含 WSL，一键启动入口必须避免这种跨 Agent、跨平台的不稳定性。

整改要求：

1. 新增 `.gitattributes`：

```gitattributes
*.sh text eol=lf
scripts/*.sh text eol=lf
```

2. 重新规范化 `scripts/*.sh` 为 LF。
3. 复跑并记录：

```bash
git ls-files --eol scripts/start.sh scripts/restart.sh scripts/stop.sh
bash -n scripts/start.sh
bash -n scripts/restart.sh
bash -n scripts/stop.sh
```

期望工作区显示 `w/lf`，且 `bash -n` 全部通过。

## 已通过项

- 默认 dry-run 能列出 AkTools、FastAPI、Streamlit。
- `--no-aktools` dry-run 能跳过 AkTools。
- `--full` dry-run 能列出 BugFixAgent。
- AkTools 兼容 App 测试通过。
- 聚焦测试通过：

```text
13 passed, 2 warnings
```

- Ruff 通过：

```text
All checks passed!
```

## 本次 Review 执行命令

```bash
git status --short --branch
git show --stat --oneline -1
python -m pytest tests/test_product_process_manager.py tests/test_aktools_compat_app.py -q --basetemp=runtime/pytest-tmp-startup-review
python -m ruff check scripts/start_product.py tests/test_product_process_manager.py tests/test_aktools_compat_app.py
bash -n scripts/start.sh
python scripts/start_product.py --dry-run
python scripts/start_product.py --dry-run --no-aktools
python scripts/start_product.py --dry-run --full
git ls-files --eol scripts/start.sh scripts/restart.sh scripts/stop.sh
```

## 复审准入条件

开发工程师完成整改后，必须提交新的 dev report；测试工程师必须在独立本地测试分支完成复测，并在原开发分支提交 test report。复审至少需要看到：

- AkTools 部分启动失败清理测试。
- shell 脚本 LF 换行约束测试。
- `bash -n` 三个脚本全部通过。
- 默认、`--no-aktools`、`--full` dry-run 仍然通过。
- 未启用真实自动交易。
