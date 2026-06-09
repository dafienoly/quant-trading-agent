@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM 量化交易系统 - 一键部署脚本 (Windows)
REM 用法: scripts\setup.bat
REM ============================================================

echo ============================================================
echo   量化交易系统 - 一键部署
echo ============================================================

REM 定位项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
pushd "%PROJECT_ROOT%"
set "PROJECT_ROOT=%cd%"
popd

echo   项目根目录: %PROJECT_ROOT%
echo.

REM ===================================================================
REM [1/6] 检查 Python 版本
REM ===================================================================
echo [1/6] 检查 Python 版本...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请先安装 Python ^>= 3.10
    echo         下载地址: https://www.python.org/downloads/
    exit /b 1
)

REM 获取 Python 版本号
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VERSION=%%v"
echo [INFO] 检测到 Python 版本: %PY_VERSION%

REM 解析主版本号和次版本号
for /f "tokens=1,2 delims=." %%a in ("%PY_VERSION%") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

if %PY_MAJOR% lss 3 (
    echo [ERROR] Python 版本过低: %PY_VERSION%，需要 ^>= 3.10
    exit /b 1
)
if %PY_MAJOR% equ 3 if %PY_MINOR% lss 10 (
    echo [ERROR] Python 版本过低: %PY_VERSION%，需要 ^>= 3.10
    exit /b 1
)

echo [INFO] Python 版本: %PY_VERSION% ^(^>= 3.10^) OK

REM ===================================================================
REM [2/6] 创建虚拟环境
REM ===================================================================
echo.
echo [2/6] 创建虚拟环境...

set "VENV_DIR=%PROJECT_ROOT%\.venv"

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [WARN] 虚拟环境已存在: %VENV_DIR%
) else (
    echo [INFO] 正在创建虚拟环境...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [ERROR] 创建虚拟环境失败
        exit /b 1
    )
    echo [INFO] 虚拟环境创建成功: %VENV_DIR%
)

REM 激活虚拟环境
if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
    echo [INFO] 虚拟环境已激活
) else (
    echo [ERROR] 找不到虚拟环境激活脚本: %VENV_DIR%\Scripts\activate.bat
    exit /b 1
)

REM 升级 pip
echo [INFO] 升级 pip...
python -m pip install --upgrade pip --quiet

REM ===================================================================
REM [3/6] 安装依赖
REM ===================================================================
echo.
echo [3/6] 安装项目依赖...

echo [INFO] 安装核心依赖 + [dev,ui,backtest]...
pip install -e "%PROJECT_ROOT%[dev,ui,backtest]"
if %errorlevel% neq 0 (
    echo [ERROR] 安装项目依赖失败
    exit /b 1
)

echo [INFO] 安装额外依赖 (uvicorn, requests)...
pip install uvicorn requests --quiet
if %errorlevel% neq 0 (
    echo [WARN] 安装 uvicorn/requests 时出现警告，继续...
)

echo [INFO] 依赖安装完成 OK

REM ===================================================================
REM [4/6] 创建目录结构
REM ===================================================================
echo.
echo [4/6] 创建目录结构...

set "DIRS=data logs feedback\bugs\open feedback\bugs\triaged feedback\bugs\fixed feedback\bugs\ignored runtime\state"

for %%d in (%DIRS%) do (
    set "full_path=%PROJECT_ROOT%\%%d"
    if exist "!full_path!" (
        echo [INFO] 目录已存在: %%d\
    ) else (
        mkdir "!full_path!"
        echo [INFO] 目录已创建: %%d\
    )
)

REM ===================================================================
REM [5/6] 配置 .env 文件
REM ===================================================================
echo.
echo [5/6] 配置环境变量...

set "ENV_FILE=%PROJECT_ROOT%\.env"
set "ENV_EXAMPLE=%PROJECT_ROOT%\.env.example"

if exist "%ENV_FILE%" (
    echo [WARN] .env 文件已存在，跳过
) else (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo [INFO] .env 已从 .env.example 复制
    ) else (
        REM 创建最小 .env
        (
            echo # Auto-generated minimal .env - 请根据需要修改
            echo MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY
            echo ENABLE_LIVE_TRADING=false
            echo REQUIRE_HUMAN_CONFIRMATION=true
            echo BROKER_ADAPTER=paper
            echo DATABASE_URL=sqlite:///data/quant_trading.db
            echo LOG_LEVEL=INFO
            echo LOG_FILE=logs/quant_trading.log
        ) > "%ENV_FILE%"
        echo [INFO] .env 已创建最小配置
    )
)

echo [WARN] 请检查 .env 文件，确保配置正确（特别是 TUSHARE_TOKEN 等密钥）

REM ===================================================================
REM [6/6] 运行预检
REM ===================================================================
echo.
echo [6/6] 运行启动前检查...

set "BOOTSTRAP_SCRIPT=%PROJECT_ROOT%\scripts\bootstrap.py"

if exist "%BOOTSTRAP_SCRIPT%" (
    python "%BOOTSTRAP_SCRIPT%"
    if %errorlevel% neq 0 (
        echo [ERROR] 启动前检查未通过，请根据上方提示修复
        exit /b 1
    )
) else (
    echo [WARN] 未找到 bootstrap.py，跳过预检
)

REM ===================================================================
REM 完成
REM ===================================================================
echo.
echo ============================================================
echo   部署完成!
echo   启动系统: python scripts\start_product.py
echo   停止系统: python scripts\stop_product.py
echo ============================================================

endlocal
