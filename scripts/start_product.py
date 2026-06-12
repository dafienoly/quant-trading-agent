"""One-command product startup script.

Runs bootstrap checks, then starts FastAPI and Streamlit as background
processes.  Writes PID information and startup logs.

Usage:
    python scripts/start_product.py [--api-port 8000] [--streamlit-port 8501] [--dry-run] [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_ROOT / "runtime" / "product.pid.json"
STARTUP_LOG = PROJECT_ROOT / "logs" / "product_startup.log"
LIVE_TRADING_CONFIRM = PROJECT_ROOT / "runtime" / "live_trading_confirmed"

DEFAULT_API_PORT = 8000
DEFAULT_STREAMLIT_PORT = 8771
DEFAULT_AKTOOLS_PORT = 8080


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(STARTUP_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def _popen_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _build_service_commands(
    *,
    python_executable: str,
    api_port: int,
    aktools_port: int,
    streamlit_port: int,
) -> dict[str, list[str]]:
    dashboard_path = "src/ui_report/product_dashboard.py"
    return {
        "aktools": [
            python_executable,
            "-m",
            "uvicorn",
            "src.integrations.aktools_compat_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(aktools_port),
        ],
        "api": [
            python_executable,
            "-m",
            "uvicorn",
            "src.api.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(api_port),
        ],
        "streamlit": [
            python_executable,
            "-m",
            "streamlit",
            "run",
            dashboard_path,
            "--server.port",
            str(streamlit_port),
            "--server.headless",
            "true",
        ],
    }


# ---------------------------------------------------------------------------
# Port conflict detection
# ---------------------------------------------------------------------------

def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _find_pid_by_port(port: int) -> int | None:
    """Return the PID of the process listening on *port*, or None."""
    try:
        # Try lsof first (Linux/Mac)
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0])
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        pass

    try:
        # Fallback: ss (Linux)
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "pid=" in line:
                pid_str = line.split("pid=")[-1].split(",")[0].strip()
                try:
                    return int(pid_str)
                except ValueError:
                    continue
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _is_our_pid(pid: int) -> bool:
    """Check if *pid* belongs to a process started by this project."""
    try:
        with open(f"/proc/{pid}/cmdline", "r") as f:
            cmdline = f.read()
        return "quant-trading-agent" in cmdline or "uvicorn" in cmdline or "streamlit" in cmdline
    except (FileNotFoundError, PermissionError):
        return False


def _kill_process(pid: int, name: str) -> bool:
    """Attempt to terminate a process. Returns True on success."""
    try:
        os.kill(pid, signal.SIGTERM)
        _log(f"已发送 SIGTERM 到 {name} (PID={pid})")
        time.sleep(1)
        # Check if process died
        try:
            os.kill(pid, 0)
            # Process still alive, try SIGKILL
            _log(f"进程 {pid} 未响应 SIGTERM，发送 SIGKILL")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
        except OSError:
            pass  # process already dead
        return True
    except ProcessLookupError:
        _log(f"{name} (PID={pid}) 已不存在")
        return True
    except PermissionError:
        _log(f"ERROR: 无权限终止 {name} (PID={pid})")
        return False


def _resolve_port_conflict(port: int, service_name: str, force: bool) -> bool:
    """Resolve port conflict by killing old project processes.

    Returns True if the port is now free (or was never in use).
    """
    if not _port_in_use(port):
        return True

    pid = _find_pid_by_port(port)
    if pid is None:
        _log(f"端口 {port} 被占用但无法识别进程，请手动释放")
        return False

    if _is_our_pid(pid):
        _log(f"端口 {port} 被本项目旧进程占用 (PID={pid})")
        if force or _ask_confirmation(f"终止旧进程 {pid} 释放端口 {port}?"):
            return _kill_process(pid, service_name)
        return False
    else:
        _log(f"端口 {port} 被其他程序占用 (PID={pid})")
        _log(f"请释放端口 {port} 或使用 --{service_name.lower().replace(' ', '-')}-port 指定其他端口")
        return False


def _ask_confirmation(prompt: str) -> bool:
    """Ask user for y/n confirmation. Returns True if confirmed."""
    try:
        answer = input(f"{prompt} [y/N]: ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _port_conflict_dedup_ok(port: int, service: str) -> bool:
    """Return True if we should write a new port_conflict bug (at most 1/hour)."""
    bug_dir = PROJECT_ROOT / "feedback" / "bugs" / "open"
    if not bug_dir.exists():
        return True

    one_hour_ago = datetime.now() - timedelta(hours=1)
    for bug_file in bug_dir.iterdir():
        if not bug_file.name.startswith(f"port_conflict_{port}_"):
            continue
        try:
            data = json.loads(bug_file.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(data.get("timestamp", ""))
            if ts > one_hour_ago:
                return False  # already reported within last hour
        except (ValueError, KeyError, OSError):
            continue
    return True


def _wait_http_ok(url: str, timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            import urllib.request
            response = urllib.request.urlopen(url, timeout=2)
            if response.status < 500:
                return True
        except Exception:
            time.sleep(1)
    return False


def _start_bugfix_job(api_port: int) -> dict:
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        _log("WARNING: 缺少 DEEPSEEK_API_KEY，不启动 BugFix Agent")
        return {"status": "skipped", "reason": "missing_DEEPSEEK_API_KEY"}
    api_url = f"http://127.0.0.1:{api_port}"
    _log("等待 API 就绪...")
    if not _wait_http_ok(f"{api_url}/product/health", timeout_seconds=30):
        _log("WARNING: API 未在 30s 内就绪，跳过 BugFix Agent 启动")
        return {"status": "skipped", "reason": "api_not_ready"}
    try:
        import json
        import urllib.request
        req = urllib.request.Request(f"{api_url}/product/jobs/bug_fix_agent/start", method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        _log(f"BugFix Agent job: {result}")
        return result
    except Exception as exc:
        _log(f"WARNING: 启动 BugFix Agent job 失败: {exc}")
        return {"status": "failed", "reason": str(exc)}


def _write_port_conflict_bug(port: int, service: str) -> None:
    """Write a feedback bug record for port conflict (deduped per hour)."""
    if not _port_conflict_dedup_ok(port, service):
        _log(f"端口 {port} 冲突已在 1 小时内报告过，跳过重复 Bug")
        return

    bug_dir = PROJECT_ROOT / "feedback" / "bugs" / "open"
    bug_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bug_file = bug_dir / f"port_conflict_{port}_{ts}.json"
    bug_data = {
        "type": "port_conflict",
        "service": service,
        "port": port,
        "timestamp": datetime.now().isoformat(),
        "message": f"端口 {port} 已被占用，无法启动 {service}",
        "remedy": f"请释放端口 {port} 或使用 --{service.replace(' ', '-').lower()}-port 指定其他端口",
    }
    bug_file.write_text(json.dumps(bug_data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"端口冲突 bug 记录已写入: {bug_file}")


# ---------------------------------------------------------------------------
# Live-trading safety gate
# ---------------------------------------------------------------------------

def _check_live_trading_safety() -> bool:
    """Return True if safe to proceed (fail-closed)."""
    # Load .env to check ENABLE_LIVE_TRADING
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return True  # no .env means defaults are safe

    env_vars: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env_vars[key.strip()] = value.strip()

    live = env_vars.get("ENABLE_LIVE_TRADING", "false").lower()
    if live not in ("true", "1", "yes", "on"):
        return True  # live trading disabled, safe

    # Live trading enabled — require explicit confirmation file
    if LIVE_TRADING_CONFIRM.exists():
        return True

    _log("ERROR: ENABLE_LIVE_TRADING=true 但缺少确认文件 runtime/live_trading_confirmed")
    _log("  如需启用实盘交易，请创建确认文件:")
    _log(f"    echo confirmed > {LIVE_TRADING_CONFIRM}")
    return False


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

def _start_process(cmd: list[str], name: str) -> subprocess.Popen | None:
    """Start a subprocess and return the Popen object."""
    _log(f"启动 {name}: {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_popen_kwargs(),
        )
        _log(f"{name} 已启动, PID={proc.pid}")
        return proc
    except Exception as exc:
        _log(f"ERROR: 启动 {name} 失败: {exc}")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="量化交易系统一键启动")
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT, help="FastAPI 端口")
    parser.add_argument("--streamlit-port", type=int, default=DEFAULT_STREAMLIT_PORT, help="Streamlit 端口")
    parser.add_argument("--aktools-port", type=int, default=DEFAULT_AKTOOLS_PORT, help="AkTools 端口")
    parser.add_argument("--with-aktools", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-aktools", action="store_true", help="不启动 AkTools 兼容服务")
    parser.add_argument("--with-bugfix", action="store_true", help="启动 BugFix Agent job")
    parser.add_argument("--full", action="store_true", help="启动全部服务（AkTools + BugFixAgent）")
    parser.add_argument("--force", action="store_true", help="强制终止占用端口的旧进程后启动")
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划，不实际启动")
    args = parser.parse_args()

    api_port = args.api_port
    streamlit_port = args.streamlit_port
    aktools_port = args.aktools_port

    # Compute service modes:
    # Default: AkTools + FastAPI + Streamlit
    # --no-aktools: skip AkTools
    # --with-aktools: backward compat (kept for scripts that pass it)
    # --full: implies AkTools + BugFixAgent
    start_aktools = not args.no_aktools or args.with_aktools or args.full
    start_bugfix = args.with_bugfix or args.full

    _log("=" * 60)
    _log("量化交易系统 - 产品启动")
    _log("=" * 60)

    # --- Step 1: Bootstrap ---
    _log("运行启动前检查 (bootstrap)...")
    bootstrap_script = Path(__file__).resolve().parent / "bootstrap.py"
    result = subprocess.run(
        [sys.executable, str(bootstrap_script)],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        _log("ERROR: Bootstrap 检查未通过，请先修复上述问题")
        sys.exit(1)
    _log("Bootstrap 检查通过")

    # --- Step 2: Live trading safety ---
    if not _check_live_trading_safety():
        sys.exit(1)

    # --- Step 3: Dry-run mode (return before port/process changes) ---
    if args.dry_run:
        _log(f"DRY-RUN 模式: show planned services (start_aktools={start_aktools}, start_bugfix={start_bugfix})")
        print("\n[DRY-RUN] 计划启动以下服务:")
        svc_idx = 1
        if start_aktools:
            print(f"  {svc_idx}. AkTools  -> http://localhost:{aktools_port}")
            svc_idx += 1
        print(f"  {svc_idx}. FastAPI   -> http://localhost:{api_port}")
        print(f"  {svc_idx + 1}. Streamlit -> http://localhost:{streamlit_port}")
        if start_bugfix:
            print(f"  {svc_idx + 2}. BugFixAgent (job, requires DEEPSEEK_API_KEY)")
        print(f"\nPID 文件: {PID_FILE}")
        print(f"启动日志: {STARTUP_LOG}")
        _log("DRY-RUN 模式，未启动任何服务")
        return

    # --- Step 4: Port conflict check with auto-resolution ---
    force = args.force
    port_issues = False

    if _port_in_use(api_port):
        _log(f"检测到端口 {api_port} 已被占用 (FastAPI)")
        if _resolve_port_conflict(api_port, "FastAPI", force):
            _log(f"端口 {api_port} 已释放")
            time.sleep(0.5)  # brief wait for OS to release port
        else:
            _write_port_conflict_bug(api_port, "FastAPI")
            port_issues = True

    if _port_in_use(streamlit_port):
        _log(f"检测到端口 {streamlit_port} 已被占用 (Streamlit)")
        if _resolve_port_conflict(streamlit_port, "Streamlit", force):
            _log(f"端口 {streamlit_port} 已释放")
            time.sleep(0.5)
        else:
            _write_port_conflict_bug(streamlit_port, "Streamlit")
            port_issues = True

    if start_aktools and _port_in_use(aktools_port):
        _log(f"检测到端口 {aktools_port} 已被占用 (AkTools)")
        if _resolve_port_conflict(aktools_port, "AkTools", force):
            _log(f"端口 {aktools_port} 已释放")
            time.sleep(0.5)
        else:
            _write_port_conflict_bug(aktools_port, "AkTools")
            port_issues = True

    if port_issues:
        _log("请释放占用端口或使用 --api-port / --streamlit-port 指定其他端口")
        sys.exit(1)

    # --- Step 5: Start services ---
    cmds = _build_service_commands(
        python_executable=sys.executable,
        api_port=api_port,
        aktools_port=aktools_port,
        streamlit_port=streamlit_port,
    )

    aktools_proc = None
    if start_aktools:
        aktools_proc = _start_process(cmds["aktools"], "AkTools")

    api_proc = _start_process(cmds["api"], "FastAPI")
    streamlit_proc = _start_process(cmds["streamlit"], "Streamlit")

    if api_proc is None or streamlit_proc is None:
        # Clean up any started process
        for proc in (api_proc, streamlit_proc):
            if proc is not None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    pass
        _log("ERROR: 服务启动失败，已终止所有进程")
        sys.exit(1)

    # --- Step 6: Write PID file ---
    pid_data = {
        "aktools_pid": aktools_proc.pid if aktools_proc else None,
        "api_pid": api_proc.pid,
        "streamlit_pid": streamlit_proc.pid,
        "aktools_port": aktools_port if start_aktools else None,
        "api_port": api_port,
        "streamlit_port": streamlit_port,
        "bug_fix_agent_requested": start_bugfix,
        "started_at": datetime.now().isoformat(),
    }
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(json.dumps(pid_data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"PID 文件已写入: {PID_FILE}")

    # --- Step 7: Brief health wait ---
    _log("等待服务就绪...")
    time.sleep(12)

    # --- Step 8: Start BugFix Agent job (if requested) ---
    if start_bugfix:
        _start_bugfix_job(api_port)

    # --- Done ---
    _log("=" * 60)
    _log("所有服务已启动!")
    _log(f"  FastAPI:   http://localhost:{api_port}")
    _log(f"  Streamlit: http://localhost:{streamlit_port}")
    _log(f"  产品入口:  http://localhost:{streamlit_port}")
    _log("=" * 60)

    print(f"\n产品已启动: http://localhost:{streamlit_port}\n")


if __name__ == "__main__":
    main()
