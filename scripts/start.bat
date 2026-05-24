@echo off
title NP-DNA Command Center
echo.
echo   ============================
echo    NP-DNA Command Center
echo   ============================
echo.
echo   Starting dashboard server...
echo   Open: http://localhost:8501
echo.
cd /d "%~dp0"
python -m webui.backend.app
pause
