@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM 量化交易系统 - 一键停止 (Windows)
REM 自动激活 .venv 虚拟环境后停止 FastAPI + Streamlit
REM 用法: scripts\stop.bat
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

REM --- 激活虚拟环境 ---
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
echo   停止量化交易系统 ...
echo ============================================================
echo.

"%VENV_PYTHON%" scripts/stop_product.py %*

popd

REM --- 退出虚拟环境 ---
deactivate >nul 2>&1

endlocal