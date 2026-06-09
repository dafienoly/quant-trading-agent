"""Graceful product shutdown script.

Reads PIDs from runtime/product.pid.json and stops only the processes
recorded by this project, then cleans up the PID file.

Usage:
    python scripts/stop_product.py
"""
from __future__ import annotations

import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_ROOT / "runtime" / "product.pid.json"
STARTUP_LOG = PROJECT_ROOT / "logs" / "product_startup.log"


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(STARTUP_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _terminate_pid(pid: int, name: str) -> bool:
    """Attempt to gracefully terminate a process by PID. Returns True on success."""
    try:
        os.kill(pid, signal.SIGTERM)
        _log(f"已发送 SIGTERM 到 {name} (PID={pid})")
        return True
    except ProcessLookupError:
        _log(f"{name} (PID={pid}) 已不存在")
        return True
    except PermissionError:
        _log(f"ERROR: 无权限终止 {name} (PID={pid})")
        return False
    except OSError as exc:
        _log(f"ERROR: 终止 {name} (PID={pid}) 失败: {exc}")
        return False


def main() -> None:
    _log("=" * 60)
    _log("量化交易系统 - 停止服务")
    _log("=" * 60)

    if not PID_FILE.exists():
        _log("PID 文件不存在，没有正在运行的服务")
        print("没有发现运行中的服务 (PID 文件不存在)")
        return

    try:
        pid_data = json.loads(PID_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"ERROR: 读取 PID 文件失败: {exc}")
        print(f"读取 PID 文件失败: {exc}")
        sys.exit(1)

    pid_keys = ["api_pid", "streamlit_pid"]
    names = {"api_pid": "FastAPI", "streamlit_pid": "Streamlit"}

    all_ok = True
    for key in pid_keys:
        pid = pid_data.get(key)
        if pid is None:
            continue
        name = names.get(key, key)
        ok = _terminate_pid(pid, name)
        if not ok:
            all_ok = False

    # Clean up PID file
    try:
        PID_FILE.unlink()
        _log("PID 文件已清理")
    except OSError as exc:
        _log(f"WARNING: 清理 PID 文件失败: {exc}")

    _log("=" * 60)
    if all_ok:
        _log("所有服务已停止")
        print("所有服务已停止")
    else:
        _log("部分服务停止失败，请手动检查")
        print("部分服务停止失败，请手动检查进程")
        sys.exit(1)


if __name__ == "__main__":
    main()
