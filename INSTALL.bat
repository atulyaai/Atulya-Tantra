@echo off
echo ============================================
echo   ATULYA TANTRA - Quick Install
echo ============================================
echo.

echo Step 1: Installing Python dependencies...
python -m pip install chromadb psutil ollama fastapi uvicorn requests
echo.

echo Step 2: Installing Ollama...
echo Please download Ollama from: https://ollama.com/download
echo Press any key after Ollama is installed...
pause
echo.

echo Step 3: Downloading Qwen 3 (8B) AI Model...
echo This is a 5.2GB download - please wait...
ollama pull qwen3:8b
echo.

echo ============================================
echo   Installation Complete!
echo ============================================
echo.
echo Your Jarvis AI is ready!
echo Run: python simple_start.py
echo.
pause
