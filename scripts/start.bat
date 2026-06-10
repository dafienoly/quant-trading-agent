@echo off
setlocal

REM Quant Trading System - One-Click Start (Windows)
REM Activates .venv and starts FastAPI + Streamlit
REM Usage: scripts\start.bat [--api-port 8000] [--streamlit-port 8501]

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found. Run scripts\setup.bat first.
    echo.
    echo   Setup: scripts\setup.bat
    pause
    exit /b 1
)

echo [INFO] Using Python: %VENV_PYTHON%
echo [INFO] Working dir:  %PROJECT_ROOT%
echo.

pushd "%PROJECT_ROOT%"

"%VENV_PYTHON%" scripts/start_product.py %*
set START_EXIT=%errorlevel%

popd

if %START_EXIT% neq 0 (
    echo.
    echo [ERROR] Start failed, exit code: %START_EXIT%
    pause
)

endlocal