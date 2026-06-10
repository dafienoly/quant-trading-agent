#!/usr/bin/env bash
# ============================================================
# 量化交易系统 - 一键部署脚本
# 用法: bash scripts/setup.sh
# ============================================================

set -e

# ---------------------------------------------------------------------------
# 颜色定义
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# 定位项目根目录
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "============================================================"
echo "  量化交易系统 - 一键部署"
echo "============================================================"
echo "  项目根目录: ${PROJECT_ROOT}"
echo ""

# ===================================================================
# [1/6] 检查 Python 版本
# ===================================================================
echo "[1/6] 检查 Python 版本..."

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    error "未找到 Python，请先安装 Python >= 3.10"
    exit 1
fi

PY_VERSION=$("$PYTHON_CMD" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$PYTHON_CMD" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON_CMD" -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    error "Python 版本过低: ${PY_VERSION}，需要 >= 3.10"
    exit 1
fi

info "Python 版本: ${PY_VERSION} (>= 3.10) ✓"

# ===================================================================
# [2/6] 创建虚拟环境
# ===================================================================
echo ""
echo "[2/6] 创建虚拟环境..."

VENV_DIR="${PROJECT_ROOT}/.venv"

if [ -d "${VENV_DIR}" ]; then
    warn "虚拟环境已存在: ${VENV_DIR}"
else
    info "正在创建虚拟环境..."
    "$PYTHON_CMD" -m venv "${VENV_DIR}"
    if [ $? -ne 0 ]; then
        error "创建虚拟环境失败"
        exit 1
    fi
    info "虚拟环境创建成功: ${VENV_DIR}"
fi

# 激活虚拟环境
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
    info "虚拟环境已激活"
else
    error "找不到虚拟环境激活脚本: ${VENV_DIR}/bin/activate"
    exit 1
fi

# 升级 pip
info "升级 pip..."
pip install --upgrade pip --quiet

# ===================================================================
# [3/6] 安装依赖
# ===================================================================
echo ""
echo "[3/6] 安装项目依赖..."

info "安装核心依赖 + [dev,ui,backtest]..."
pip install -e "${PROJECT_ROOT}[dev,ui,backtest]" 2>&1 | tail -5

info "安装额外依赖 (uvicorn, requests)..."
pip install uvicorn requests --quiet

info "依赖安装完成 ✓"

# ===================================================================
# [4/6] 创建目录结构
# ===================================================================
echo ""
echo "[4/6] 创建目录结构..."

REQUIRED_DIRS=(
    "data"
    "logs"
    "feedback/bugs/open"
    "feedback/bugs/triaged"
    "feedback/bugs/fixed"
    "feedback/bugs/ignored"
    "runtime/state"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    full_path="${PROJECT_ROOT}/${dir}"
    if [ -d "$full_path" ]; then
        info "目录已存在: ${dir}/"
    else
        mkdir -p "$full_path"
        info "目录已创建: ${dir}/"
    fi
done

# ===================================================================
# [5/6] 配置 .env 文件
# ===================================================================
echo ""
echo "[5/6] 配置环境变量..."

ENV_FILE="${PROJECT_ROOT}/.env"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"

if [ -f "${ENV_FILE}" ]; then
    warn ".env 文件已存在，跳过"
else
    if [ -f "${ENV_EXAMPLE}" ]; then
        cp "${ENV_EXAMPLE}" "${ENV_FILE}"
        info ".env 已从 .env.example 复制"
    else
        # 创建最小 .env
        cat > "${ENV_FILE}" << 'ENVEOF'
# Auto-generated minimal .env - 请根据需要修改
MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY
ENABLE_LIVE_TRADING=false
REQUIRE_HUMAN_CONFIRMATION=true
BROKER_ADAPTER=paper
DATABASE_URL=sqlite:///data/quant_trading.db
LOG_LEVEL=INFO
LOG_FILE=logs/quant_trading.log
ENVEOF
        info ".env 已创建最小配置"
    fi
fi

warn "请检查 .env 文件，确保配置正确（特别是 TUSHARE_TOKEN 等密钥）"

# ===================================================================
# [6/6] 运行预检
# ===================================================================
echo ""
echo "[6/6] 运行启动前检查..."

BOOTSTRAP_SCRIPT="${PROJECT_ROOT}/scripts/bootstrap.py"
if [ -f "${BOOTSTRAP_SCRIPT}" ]; then
    python "${BOOTSTRAP_SCRIPT}"
    if [ $? -ne 0 ]; then
        error "启动前检查未通过，请根据上方提示修复"
        exit 1
    fi
else
    warn "未找到 bootstrap.py，跳过预检"
fi

# ===================================================================
# 完成
# ===================================================================
echo ""
echo "============================================================"
echo "  部署完成!"
echo ""
echo "  启动系统: bash scripts/start.sh"
echo "  停止系统: bash scripts/stop.sh"
echo "  重启系统: bash scripts/restart.sh"
echo "============================================================"
