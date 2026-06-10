@echo off
setlocal

REM Quant Trading System - One-Click Restart (Windows)
REM Stops all services, then starts them again
REM Usage: scripts\restart.bat [--api-port 8000] [--streamlit-port 8501]

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found. Run scripts\setup.bat first.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Restarting Quant Trading System
echo ============================================================

pushd "%PROJECT_ROOT%"

echo.
echo [Step 1/2] Stopping services ...
"%VENV_PYTHON%" scripts/stop_product.py

echo.
echo [Step 2/2] Starting services ...
echo.
"%VENV_PYTHON%" scripts/start_product.py %*
set START_EXIT=%errorlevel%

popd

if %START_EXIT% neq 0 (
    echo.
    echo [ERROR] Restart failed, exit code: %START_EXIT%
    pause
)

endlocal