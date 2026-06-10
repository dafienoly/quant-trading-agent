#!/usr/bin/env bash
# ============================================================
# 量化交易系统 - 一键启动 (Linux/macOS)
# 自动激活 .venv 虚拟环境后启动 FastAPI + Streamlit
# 用法: bash scripts/start.sh [--api-port 8000] [--streamlit-port 8501]
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"

# --- 检测虚拟环境 ---
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[ERROR] 未找到虚拟环境，请先运行 bash scripts/setup.sh 完成部署"
    echo ""
    echo "  部署: bash scripts/setup.sh"
    exit 1
fi

echo "[INFO] 使用 Python: $VENV_PYTHON"
echo "[INFO] 工作目录: $PROJECT_ROOT"

# --- 启动产品服务 ---
echo ""
echo "============================================================"
echo "  启动量化交易系统 ..."
echo "============================================================"
echo ""

cd "$PROJECT_ROOT"
"$VENV_PYTHON" scripts/start_product.py "$@"