@echo off
setlocal enabledelayedexpansion

REM Quant Trading System - One-Click Setup (Windows)
REM Installs venv, dependencies, directories, and config.
REM Usage: scripts\setup.bat

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
pushd "%PROJECT_ROOT%"
set "PROJECT_ROOT=%cd%"
popd

echo ============================================================
echo  Quant Trading System - One-Click Setup
echo ============================================================
echo  Project Root: %PROJECT_ROOT%
echo.

REM ===================================================================
REM [1/6] Check Python version
REM ===================================================================
echo [1/6] Checking Python version...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python ^>= 3.10
    echo         https://www.python.org/downloads/
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VERSION=%%v"
echo [INFO] Python version: %PY_VERSION%

for /f "tokens=1,2 delims=." %%a in ("%PY_VERSION%") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

if %PY_MAJOR% lss 3 (
    echo [ERROR] Python version too old: %PY_VERSION%, need ^>= 3.10
    exit /b 1
)
if %PY_MAJOR% equ 3 if %PY_MINOR% lss 10 (
    echo [ERROR] Python version too old: %PY_VERSION%, need ^>= 3.10
    exit /b 1
)

echo [INFO] Python %PY_VERSION% OK

REM ===================================================================
REM [2/6] Create virtual environment
REM ===================================================================
echo.
echo [2/6] Creating virtual environment...

set "VENV_DIR=%PROJECT_ROOT%\.venv"

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [WARN] Virtual environment already exists: %VENV_DIR%
) else (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
    echo [INFO] Virtual environment created: %VENV_DIR%
)

if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
    echo [INFO] Virtual environment activated
) else (
    echo [ERROR] Activation script not found: %VENV_DIR%\Scripts\activate.bat
    exit /b 1
)

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM ===================================================================
REM [3/6] Install dependencies
REM ===================================================================
echo.
echo [3/6] Installing dependencies...

echo [INFO] Installing core + [dev,ui,backtest] extras...
pip install -e "%PROJECT_ROOT%[dev,ui,backtest]"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install project dependencies
    exit /b 1
)

echo [INFO] Installing uvicorn, requests...
pip install uvicorn requests --quiet
if %errorlevel% neq 0 (
    echo [WARN] uvicorn/requests install warnings (non-fatal)
)

echo [INFO] Dependencies installed OK

REM ===================================================================
REM [4/6] Create directory structure
REM ===================================================================
echo.
echo [4/6] Creating directory structure...

set "DIRS=data logs feedback\bugs\open feedback\bugs\triaged feedback\bugs\fixed feedback\bugs\ignored runtime\state"

for %%d in (%DIRS%) do (
    set "full_path=%PROJECT_ROOT%\%%d"
    if exist "!full_path!" (
        echo [INFO] Directory exists: %%d\
    ) else (
        mkdir "!full_path!"
        echo [INFO] Directory created: %%d\
    )
)

REM ===================================================================
REM [5/6] Configure .env file
REM ===================================================================
echo.
echo [5/6] Configuring environment variables...

set "ENV_FILE=%PROJECT_ROOT%\.env"
set "ENV_EXAMPLE=%PROJECT_ROOT%\.env.example"

if exist "%ENV_FILE%" (
    echo [WARN] .env file already exists, skipping
) else (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo [INFO] .env copied from .env.example
    ) else (
        REM Create minimal .env
        (
            echo # Auto-generated minimal .env - edit as needed
            echo MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY
            echo ENABLE_LIVE_TRADING=false
            echo REQUIRE_HUMAN_CONFIRMATION=true
            echo BROKER_ADAPTER=paper
            echo DATABASE_URL=sqlite:///data/quant_trading.db
            echo LOG_LEVEL=INFO
            echo LOG_FILE=logs/quant_trading.log
        ) > "%ENV_FILE%"
        echo [INFO] Minimal .env created
    )
)

echo [WARN] Review .env and update secrets (e.g. TUSHARE_TOKEN)

REM ===================================================================
REM [6/6] Run bootstrap check
REM ===================================================================
echo.
echo [6/6] Running pre-flight checks...

set "BOOTSTRAP_SCRIPT=%PROJECT_ROOT%\scripts\bootstrap.py"

if exist "%BOOTSTRAP_SCRIPT%" (
    python "%BOOTSTRAP_SCRIPT%"
    if %errorlevel% neq 0 (
        echo [ERROR] Bootstrap check failed. Fix issues above.
        exit /b 1
    )
) else (
    echo [WARN] bootstrap.py not found, skipping
)

REM ===================================================================
REM Complete
REM ===================================================================
echo.
echo ============================================================
echo  Setup complete!
echo.
echo  Start:   scripts\start.bat
echo  Stop:    scripts\stop.bat
echo  Restart: scripts\restart.bat
echo ============================================================

endlocal