"""Graceful product shutdown script.

Reads PIDs from runtime/product.pid.json and stops only the processes
recorded by this project, then cleans up the PID file.

Also attempts to clean up zombie PIDs that are still listening on known
project ports but not recorded in the PID file.

Usage:
    python scripts/stop_product.py
    python scripts/stop_product.py --force  # SIGKILL instead of SIGTERM
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_ROOT / "runtime" / "product.pid.json"
STARTUP_LOG = PROJECT_ROOT / "logs" / "product_startup.log"

KNOWN_PORTS = (8000, 8001, 8002, 8501, 8502, 8771)  # common project ports


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(STARTUP_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _terminate_pid(pid: int, name: str, force: bool = False) -> bool:
    """Attempt to gracefully terminate a process by PID. Returns True on success."""
    sig = signal.SIGKILL if force else signal.SIGTERM
    sig_name = "SIGKILL" if force else "SIGTERM"
    try:
        os.kill(pid, sig)
        _log(f"已发送 {sig_name} 到 {name} (PID={pid})")
        if not force:
            time.sleep(1)
        return True
    except ProcessLookupError:
        _log(f"{name} (PID={pid}) 已不存在 (僵尸 PID，将清理)")
        return True
    except PermissionError:
        _log(f"ERROR: 无权限终止 {name} (PID={pid})")
        return False
    except OSError as exc:
        _log(f"ERROR: 终止 {name} (PID={pid}) 失败: {exc}")
        return False


def _cleanup_zombie_ports() -> list[int]:
    """Find and kill processes listening on known project ports.

    Returns list of PIDs that were killed.
    """
    killed: list[int] = []
    for port in KNOWN_PORTS:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    try:
                        pid = int(line.strip())
                        # Check if it's our project process
                        cmdline_path = f"/proc/{pid}/cmdline"
                        if os.path.exists(cmdline_path):
                            with open(cmdline_path, "r") as f:
                                cmdline = f.read()
                            if any(kw in cmdline for kw in ("uvicorn", "streamlit", "quant-trading-agent")):
                                _log(f"发现僵尸进程 PID={pid} 占用端口 {port}，正在清理...")
                                if _terminate_pid(pid, f"zombie-port-{port}", force=True):
                                    killed.append(pid)
                    except (ValueError, ProcessLookupError):
                        continue
        except FileNotFoundError:
            break  # lsof not available
        except subprocess.TimeoutExpired:
            continue
    return killed


def main() -> None:
    parser = argparse.ArgumentParser(description="量化交易系统 - 停止服务")
    parser.add_argument("--force", action="store_true", help="使用 SIGKILL 强制终止进程")
    args = parser.parse_args()

    _log("=" * 60)
    _log("量化交易系统 - 停止服务")
    _log("=" * 60)

    # --- Step 0: Clean up zombie ports ---
    _log("检查并清理僵尸端口进程...")
    zombies = _cleanup_zombie_ports()
    if zombies:
        _log(f"已清理 {len(zombies)} 个僵尸进程: {zombies}")

    # --- Step 1: Stop processes from PID file ---
    if not PID_FILE.exists():
        _log("PID 文件不存在，没有正在记录的服务需要停止")
        if not zombies:
            print("没有发现运行中的服务 (PID 文件不存在)")
        else:
            print(f"已清理 {len(zombies)} 个僵尸进程，没有 PID 文件记录的服务")
        return

    try:
        pid_data = json.loads(PID_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"ERROR: 读取 PID 文件失败: {exc}")
        print(f"读取 PID 文件失败: {exc}")
        # Even if PID file is corrupt, we already cleaned zombies
        sys.exit(1)

    pid_keys = ["aktools_pid", "api_pid", "streamlit_pid"]
    names = {"aktools_pid": "AkTools", "api_pid": "FastAPI", "streamlit_pid": "Streamlit"}

    all_ok = True
    for key in pid_keys:
        pid = pid_data.get(key)
        if pid is None:
            continue
        name = names.get(key, key)
        ok = _terminate_pid(pid, name, force=args.force)
        if not ok:
            all_ok = False

    # --- Step 2: Clean up PID file ---
    try:
        PID_FILE.unlink()
        _log("PID 文件已清理")
    except OSError as exc:
        _log(f"WARNING: 清理 PID 文件失败: {exc}")

    _log("=" * 60)
    if all_ok:
        _log("所有服务已停止")
        total = len([k for k in pid_keys if pid_data.get(k)]) + len(zombies)
        print(f"所有服务已停止 (共 {total} 个进程)")
    else:
        _log("部分服务停止失败，请手动检查")
        print("部分服务停止失败，请手动检查进程")
        sys.exit(1)


if __name__ == "__main__":
    main()
