@echo off
cls
echo ============================================
echo    ATULYA TANTRA - Your Personal Jarvis
echo ============================================
echo.

REM Check if Ollama is running
ollama list >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama server...
    start /B ollama serve
    timeout /t 3 /nobreak >nul
)

echo.
echo Starting Atulya Tantra AI System...
echo Model: Qwen 3 (8B) - High Quality CPU Inference
echo Say "Atulya" to activate voice mode!
echo.

python simple_start.py

pause