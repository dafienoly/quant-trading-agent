#!/usr/bin/env bash
# ============================================================
# 量化交易系统 - 一键重启 (Linux/macOS)
# 先停止所有服务，再重新启动
# 用法: bash scripts/restart.sh [--api-port 8000] [--aktools-port 8080] [--streamlit-port 8771] [--no-aktools] [--with-bugfix] [--full] [--force]
# 默认启动: AkTools + FastAPI + Streamlit
# --full 额外启动 BugFixAgent; AkShare 是 Python 包, 不是独立服务
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"

# --- 检测虚拟环境 ---
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[ERROR] 未找到虚拟环境，请先运行 bash scripts/setup.sh 完成部署"
    exit 1
fi

echo ""
echo "============================================================"
echo "  重启量化交易系统"
echo "============================================================"

cd "$PROJECT_ROOT"

# Step 1: Stop
echo ""
echo "[Step 1/2] 停止服务 ..."
"$VENV_PYTHON" scripts/stop_product.py

# Step 2: Start
echo ""
echo "[Step 2/2] 启动服务 ..."
echo ""
"$VENV_PYTHON" scripts/start_product.py "$@"