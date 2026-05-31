@echo off
setlocal enabledelayedexpansion
title Atulya — Digital Organism OS
color 0A

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║         ATULYA — DIGITAL ORGANISM OS     ║
echo   ║   Tantra · Yantra · Drishti                ║
echo   ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ─── Load .env if present ─────────────────────────────────────────
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "line=%%A"
        if not "!line:~0,1!"=="#" (
            if not "%%A"=="" set "%%A=%%B"
        )
    )
)

:: ─── Resolve host and port ───────────────────────────────────────
if not defined ATULYA_HOST set "ATULYA_HOST=127.0.0.1"
if not defined ATULYA_PORT set "ATULYA_PORT=8501"

:: ─── Check Python ────────────────────────────────────────────────
echo   [1/4] Checking Python environment...
where python >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found in PATH. Install Python 3.10+ and try again.
    pause
    exit /b 1
)

:: ─── Install Python dependencies if needed ───────────────────────
echo   [2/4] Checking Python dependencies...
python -c "import fastapi; import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo   Installing Python dependencies...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo   WARNING: Some Python packages may have failed to install.
    )
)

:: ─── Build frontend if dist/ is missing or stale ─────────────────
echo   [3/4] Checking frontend build...
if not exist "drishti\dist\index.html" (
    echo   Building frontend - first-time or after changes...
    
    rem Check Node.js
    where node >nul 2>&1
    if errorlevel 1 (
        echo   WARNING: Node.js not found. Frontend will not be available.
        echo   Install Node.js 18+ from https://nodejs.org and re-run.
        goto :start_backend
    )
    
    rem Install npm dependencies if needed
    if not exist "drishti\node_modules" (
        echo   Installing npm dependencies...
        pushd drishti
        call npm install --silent
        popd
    )
    
    rem Build the Vite project
    pushd drishti
    call npm run build
    popd
    
    if not exist "drishti\dist\index.html" (
        echo   WARNING: Frontend build failed. Backend-only mode.
    ) else (
        echo   Frontend built successfully.
    )
) else (
    echo   Frontend build found. Skipping rebuild.
    echo   Run "cd drishti && npm run build" manually to rebuild after changes
)

:: ─── Start backend server ────────────────────────────────────────
:start_backend
echo   [4/4] Starting Atulya backend...
echo.
echo   ┌──────────────────────────────────────────┐
		echo   │  Atulya is starting...                   │
		echo   │                                          │
		echo   │  Drishti:  http://%ATULYA_HOST%:%ATULYA_PORT%        │
		echo   │                                          │
		echo   │  Mobile: Set ATULYA_HOST=0.0.0.0 in .env │
		echo   │          then open http://YOUR_PC_IP:%ATULYA_PORT% │
		echo   │          on your phone's browser          │
		echo   │                                          │
		echo   │  Press Ctrl+C to stop                    │
		echo   └──────────────────────────────────────────┘
echo.

:: Open browser after a short delay
start "" timeout /t 2 /nobreak >nul & start "" "http://%ATULYA_HOST%:%ATULYA_PORT%"

:: Start the Python backend (serves API + built frontend from dist/)
python -m drishti.app

pause
