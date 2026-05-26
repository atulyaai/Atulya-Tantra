@echo off
setlocal
title Atulya Tantra Dashboard
cd /d "%~dp0"
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)
echo.
echo   ============================
echo    Atulya Tantra Dashboard
echo   ============================
echo.
echo   Starting dashboard server...
echo   Open: http://localhost:8501
echo.
if defined ATULYA_BACKEND_PYTHON (
    "%ATULYA_BACKEND_PYTHON%" -m webui.backend.app
) else (
    python -m webui.backend.app
)
pause
