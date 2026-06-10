@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM 量化交易系统 - 一键重启 (Windows)
REM 先停止所有服务，再重新启动
REM 用法: scripts\restart.bat [--api-port 8000] [--streamlit-port 8501]
REM ============================================================

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM --- 检测虚拟环境 ---
set "VENV_ACTIVATE=%PROJECT_ROOT%\.venv\Scripts\activate.bat"

if not exist "%VENV_ACTIVATE%" (
    echo [ERROR] 未找到虚拟环境，请先运行 scripts\setup.bat 完成部署
    pause
    exit /b 1
)

call "%VENV_ACTIVATE%"
if %errorlevel% neq 0 (
    echo [ERROR] 虚拟环境激活失败
    pause
    exit /b 1
)

set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

pushd "%PROJECT_ROOT%"

echo.
echo ============================================================
echo   重启量化交易系统
echo ============================================================

REM --- Step 1: Stop ---
echo.
echo [Step 1/2] 停止服务 ...
"%VENV_PYTHON%" scripts/stop_product.py

REM --- Step 2: Start ---
echo.
echo [Step 2/2] 启动服务 ...
echo.
"%VENV_PYTHON%" scripts/start_product.py %*
set START_EXIT=%errorlevel%

popd

deactivate >nul 2>&1

if %START_EXIT% neq 0 (
    echo.
    echo [ERROR] 重启失败，错误码: %START_EXIT%
    pause
)

endlocal