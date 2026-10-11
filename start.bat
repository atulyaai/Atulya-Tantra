@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 if not exist ".venv\Scripts\python.exe" (
    echo Python was not found; installing a private copy with uv...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
    exit /b !errorlevel!
)
set "VENV_DIR=.venv"
if exist ".venv\Scripts\python.exe" if exist ".venv\pyvenv.cfg" (
    ".venv\Scripts\python.exe" -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo Repairing Atulya's local Python environment...
        call python -m venv --upgrade ".venv"
    )
) else (
    echo Creating Atulya's local Python environment...
    call python -m venv ".venv"
)
if errorlevel 1 (
    echo Could not create or repair the Python environment.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo Python environment setup did not create its interpreter.
    pause
    exit /b 1
)
"%VENV_DIR%\Scripts\python.exe" tools\bootstrap.py
if errorlevel 1 (
    pause
    exit /b 1
)
"%VENV_DIR%\Scripts\python.exe" -m atulya.cli serve
if errorlevel 1 (
    set "RESULT=!errorlevel!"
    pause
    exit /b !RESULT!
)
exit /b 0
