@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM 量化交易系统 - 一键启动 (Windows)
REM 自动激活 .venv 虚拟环境后启动 FastAPI + Streamlit
REM 用法: scripts\start.bat [--api-port 8000] [--streamlit-port 8501]
REM ============================================================

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM --- 检测虚拟环境 ---
set "VENV_ACTIVATE=%PROJECT_ROOT%\.venv\Scripts\activate.bat"

if not exist "%VENV_ACTIVATE%" (
    echo [ERROR] 未找到虚拟环境，请先运行 scripts\setup.bat 完成部署
    echo.
    echo   部署: scripts\setup.bat
    pause
    exit /b 1
)

REM --- 激活虚拟环境 ---
call "%VENV_ACTIVATE%"
if %errorlevel% neq 0 (
    echo [ERROR] 虚拟环境激活失败
    pause
    exit /b 1
)

REM --- 确认使用 venv 内的 Python ---
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
echo [INFO] 使用 Python: %VENV_PYTHON%
echo [INFO] 工作目录: %PROJECT_ROOT%

REM --- 启动产品服务 ---
echo.
echo ============================================================
echo   启动量化交易系统 ...
echo ============================================================
echo.

pushd "%PROJECT_ROOT%"

"%VENV_PYTHON%" scripts/start_product.py %*
set START_EXIT=%errorlevel%

popd

REM --- 退出虚拟环境 ---
deactivate >nul 2>&1

if %START_EXIT% neq 0 (
    echo.
    echo [ERROR] 启动失败，错误码: %START_EXIT%
    pause
)

endlocal