"""One-command product startup script.

Runs bootstrap checks, then starts FastAPI and Streamlit as background
processes.  Writes PID information and startup logs.

Usage:
    python scripts/start_product.py [--api-port 8000] [--streamlit-port 8501] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_ROOT / "runtime" / "product.pid.json"
STARTUP_LOG = PROJECT_ROOT / "logs" / "product_startup.log"
LIVE_TRADING_CONFIRM = PROJECT_ROOT / "runtime" / "live_trading_confirmed"

DEFAULT_API_PORT = 8000
DEFAULT_STREAMLIT_PORT = 8501


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
# Port conflict detection
# ---------------------------------------------------------------------------

def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _write_port_conflict_bug(port: int, service: str) -> None:
    """Write a feedback bug record for port conflict."""
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
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # Windows
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
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划，不实际启动")
    args = parser.parse_args()

    api_port = args.api_port
    streamlit_port = args.streamlit_port

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

    # --- Step 3: Port conflict check ---
    port_issues = False
    if _port_in_use(api_port):
        _log(f"ERROR: 端口 {api_port} 已被占用 (FastAPI)")
        _write_port_conflict_bug(api_port, "FastAPI")
        port_issues = True
    if _port_in_use(streamlit_port):
        _log(f"ERROR: 端口 {streamlit_port} 已被占用 (Streamlit)")
        _write_port_conflict_bug(streamlit_port, "Streamlit")
        port_issues = True
    if port_issues:
        _log("请释放占用端口或使用 --api-port / --streamlit-port 指定其他端口")
        sys.exit(1)

    # --- Step 4: Dry-run mode ---
    if args.dry_run:
        print("\n[DRY-RUN] 计划启动以下服务:")
        print(f"  1. FastAPI   -> http://localhost:{api_port}")
        print(f"  2. Streamlit -> http://localhost:{streamlit_port}")
        print(f"\nPID 文件: {PID_FILE}")
        print(f"启动日志: {STARTUP_LOG}")
        _log("DRY-RUN 模式，未启动任何服务")
        return

    # --- Step 5: Start services ---
    api_cmd = [
        sys.executable, "-m", "uvicorn",
        "src.api.app:app",
        "--host", "0.0.0.0",
        "--port", str(api_port),
    ]
    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(PROJECT_ROOT / "src" / "ui_report" / "product_dashboard.py"),
        "--server.port", str(streamlit_port),
        "--server.headless", "true",
    ]

    api_proc = _start_process(api_cmd, "FastAPI")
    streamlit_proc = _start_process(streamlit_cmd, "Streamlit")

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
        "api_pid": api_proc.pid,
        "streamlit_pid": streamlit_proc.pid,
        "api_port": api_port,
        "streamlit_port": streamlit_port,
        "started_at": datetime.now().isoformat(),
    }
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(json.dumps(pid_data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"PID 文件已写入: {PID_FILE}")

    # --- Step 7: Brief health wait ---
    _log("等待服务就绪...")
    time.sleep(3)

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
