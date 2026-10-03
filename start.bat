@echo off
setlocal enabledelayedexpansion
title Atulya - Digital Organism OS
color 0A

echo.
echo   +------------------------------------------+
echo   ^|         ATULYA - DIGITAL ORGANISM OS     ^|
echo   ^|   Atulya . Yantra . Drishti             ^|
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
python -c "import fastapi; import uvicorn; import faster_whisper; import edge_tts" >nul 2>&1
if errorlevel 1 (
    echo   Installing Atulya and local voice - first run only...
    pip install -q -e ".[voice]"
    if errorlevel 1 echo   WARNING: Some Python packages may have failed to install.
)

rem Local brain: llama.cpp runs the small Qwen model on this PC, no internet needed
rem after the first download. The extra index has ready-made Windows builds, so
rem no C++ compiler is required.
python -c "import llama_cpp" >nul 2>&1
if errorlevel 1 (
    echo   Installing the local brain - first run only...
    pip install -q --prefer-binary "llama-cpp-python>=0.2.90" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
    if errorlevel 1 echo   WARNING: Local brain failed to install. Atulya will say so when you talk to it.
)
if not defined ATULYA_AUTO_DOWNLOAD_MODEL set "ATULYA_AUTO_DOWNLOAD_MODEL=true"
echo   Checking the brain model - the first run downloads about 400 MB...
python -c "from atulya.local_provider import _ensure_model; p = _ensure_model(); print('   Brain model: ' + (p.name if p else 'not downloaded'))"

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
