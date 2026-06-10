@echo off
setlocal

REM Quant Trading System - One-Click Stop (Windows)
REM Activates .venv and stops FastAPI + Streamlit
REM Usage: scripts\stop.bat

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found. Run scripts\setup.bat first.
    pause
    exit /b 1
)

pushd "%PROJECT_ROOT%"

"%VENV_PYTHON%" scripts/stop_product.py %*

popd

endlocal