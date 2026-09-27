@echo off
setlocal enabledelayedexpansion
title Atulya - Digital Organism OS
color 0A

echo.
echo   +------------------------------------------+
echo   ^|         ATULYA - DIGITAL ORGANISM OS     ^|
echo   ^|   Tantra . Yantra . Drishti              ^|
echo   +------------------------------------------+
echo.

cd /d "%~dp0"

if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "line=%%A"
        if not "!line:~0,1!"=="#" (
            if not "%%A"=="" set "%%A=%%B"
        )
    )
)

if not defined ATULYA_HOST set "ATULYA_HOST=127.0.0.1"
if not defined ATULYA_PORT set "ATULYA_PORT=8501"

echo   [1/4] Checking Python environment...
where python >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found in PATH. Install Python 3.10+ and try again.
    pause
    exit /b 1
)

echo   [2/4] Checking Python dependencies...
python -c "import fastapi; import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo   Installing Python dependencies...
    pip install fastapi uvicorn python-multipart -q
    if errorlevel 1 (
        echo   WARNING: Some Python packages may have failed to install.
    )
)
python -c "import faster_whisper" >nul 2>&1
if errorlevel 1 (
    echo   Installing local voice - speech-to-text runs on this PC...
    pip install -q -e ".[voice]"
)

echo   [3/4] Building the web app...
rem Always rebuild (about a second) so the UI never lags behind the source.
where node >nul 2>&1
if errorlevel 1 (
    if exist "drishti\dist\index.html" (
        echo   Node.js not found - using the existing build, which may be out of date.
    ) else (
        echo   WARNING: Node.js not found. Install Node.js 18+ from https://nodejs.org
    )
    goto :start_backend
)
pushd drishti
if not exist "node_modules" call npm install --silent
call npm run build --silent
popd
if not exist "drishti\dist\index.html" echo   WARNING: Frontend build failed. Backend-only mode.

:start_backend
    )

    if not exist "drishti\node_modules" (
        echo   Installing npm dependencies...
        pushd drishti
        call npm install --silent
        popd
    )

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
    echo   Run "cd drishti && npm run build" manually to rebuild after changes.
)

:start_backend
echo   [4/4] Starting Atulya backend...
echo.
echo   +------------------------------------------+
echo   ^|  Atulya is starting...                   ^|
echo   ^|                                          ^|
echo   ^|  Drishti:  http://%ATULYA_HOST%:%ATULYA_PORT%        ^|
echo   ^|                                          ^|
echo   ^|  Mobile: Set ATULYA_HOST=0.0.0.0 in .env ^|
echo   ^|          then open http://YOUR_PC_IP:%ATULYA_PORT% ^|
echo   ^|          on your phone's browser          ^|
echo   ^|                                          ^|
echo   ^|  Press Ctrl+C to stop                    ^|
echo   +------------------------------------------+
echo.

start "" cmd /c "timeout /t 2 >nul & start http://%ATULYA_HOST%:%ATULYA_PORT%"

python -m drishti.app

pause
