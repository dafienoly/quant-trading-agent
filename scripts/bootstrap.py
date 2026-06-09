"""Pre-flight bootstrap check script.

Verifies Python version, key dependencies, directory structure, .env file,
and critical configuration defaults before the product starts.

Exit codes:
    0 - all checks passed
    1 - one or more checks failed
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_PYTHON = (3, 11)

REQUIRED_PACKAGES = [
    "akshare",
    "fastapi",
    "uvicorn",
    "streamlit",
    "loguru",
    "pydantic",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DIRS = [
    "data",
    "logs",
    "feedback/bugs/open",
    "feedback/bugs/triaged",
    "feedback/bugs/fixed",
    "feedback/bugs/ignored",
    "runtime/state",
]

CRITICAL_ENV_DEFAULTS = {
    "MAX_TRADING_LEVEL": "LEVEL_1_SIGNAL_ONLY",
    "ENABLE_LIVE_TRADING": "false",
    "BROKER_ADAPTER": "paper",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _status(ok: bool, msg: str, remedy: str = "") -> bool:
    icon = "OK" if ok else "FAIL"
    print(f"  [{icon}] {msg}")
    if not ok and remedy:
        print(f"        -> {remedy}")
    return ok


def check_python_version() -> bool:
    current = sys.version_info[:3]
    ok = current >= MIN_PYTHON
    remedy = (
        f"请升级 Python 到 >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}, 当前版本: "
        f"{current[0]}.{current[1]}.{current[2]}"
        if not ok
        else ""
    )
    return _status(ok, f"Python 版本: {current[0]}.{current[1]}.{current[2]}", remedy)


def check_dependencies() -> bool:
    all_ok = True
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
            _status(True, f"依赖包 {pkg}")
        except ImportError:
            all_ok = False
            _status(False, f"依赖包 {pkg}", f"pip install {pkg}")
    return all_ok


def ensure_directories() -> bool:
    all_ok = True
    for rel in REQUIRED_DIRS:
        d = PROJECT_ROOT / rel
        if d.exists():
            _status(True, f"目录 {rel}/")
        else:
            try:
                d.mkdir(parents=True, exist_ok=True)
                _status(True, f"目录 {rel}/ (已创建)")
            except OSError as exc:
                all_ok = False
                _status(False, f"目录 {rel}/", f"手动创建: mkdir -p {d}  ({exc})")
    return all_ok


def ensure_env_file() -> bool:
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"

    if env_path.exists():
        return _status(True, ".env 文件存在")

    # Try to copy from .env.example
    if example_path.exists():
        try:
            import shutil
            shutil.copy2(example_path, env_path)
            return _status(True, ".env 文件 (从 .env.example 复制)")
        except OSError as exc:
            return _status(False, ".env 文件复制失败", f"手动复制: copy .env.example .env  ({exc})")

    # Create a minimal .env
    minimal_lines = [
        "# Auto-generated minimal .env - 请根据需要修改",
        "MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY",
        "ENABLE_LIVE_TRADING=false",
        "REQUIRE_HUMAN_CONFIRMATION=true",
        "BROKER_ADAPTER=paper",
        "DATABASE_URL=sqlite:///data/quant_trading.db",
        "LOG_LEVEL=INFO",
        "LOG_FILE=logs/quant_trading.log",
    ]
    try:
        env_path.write_text("\n".join(minimal_lines) + "\n", encoding="utf-8")
        return _status(True, ".env 文件 (已创建最小配置)")
    except OSError as exc:
        return _status(False, ".env 文件创建失败", f"手动创建 .env 文件  ({exc})")


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (no interpolation)."""
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def validate_critical_defaults() -> bool:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        # If .env doesn't exist after ensure_env_file, we can't validate
        return _status(False, "无法验证 .env 关键默认值", ".env 文件不存在")

    env_vars = _parse_env_file(env_path)
    all_ok = True
    for key, expected in CRITICAL_ENV_DEFAULTS.items():
        actual = env_vars.get(key, "")
        ok = actual.lower() == expected.lower()
        remedy = (
            f"在 .env 中设置 {key}={expected} (当前: {key}={actual or '<未设置>'})"
            if not ok
            else ""
        )
        _status(ok, f"关键配置 {key}={actual or '<未设置>'} (期望: {expected})", remedy)
        if not ok:
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_bootstrap() -> bool:
    """Run all bootstrap checks. Returns True if all passed."""
    print("=" * 60)
    print("  量化交易系统 - 启动前检查 (Bootstrap)")
    print("=" * 60)

    results: list[bool] = []

    print("\n[1/5] Python 版本检查")
    results.append(check_python_version())

    print("\n[2/5] 依赖包检查")
    results.append(check_dependencies())

    print("\n[3/5] 目录结构检查")
    results.append(ensure_directories())

    print("\n[4/5] .env 文件检查")
    results.append(ensure_env_file())

    print("\n[5/5] 关键配置默认值验证")
    results.append(validate_critical_defaults())

    print("\n" + "=" * 60)
    if all(results):
        print("  所有检查通过 - 系统就绪")
        print("=" * 60)
        return True
    else:
        print("  部分检查未通过 - 请根据上方提示修复")
        print("=" * 60)
        return False


if __name__ == "__main__":
    ok = run_bootstrap()
    sys.exit(0 if ok else 1)
