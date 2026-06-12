#!/usr/bin/env bash
# ============================================================
# 量化交易系统 - 一键停止 (Linux/macOS)
# 自动激活 .venv 虚拟环境后停止 FastAPI + Streamlit
# 用法: bash scripts/stop.sh
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
echo "  停止量化交易系统 ..."
echo "============================================================"
echo ""

cd "$PROJECT_ROOT"
"$VENV_PYTHON" scripts/stop_product.py "$@"