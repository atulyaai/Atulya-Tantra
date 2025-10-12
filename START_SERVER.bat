@echo off
echo ==========================================
echo   Starting Atulya Tantra Server
echo ==========================================
echo.

echo Starting server on http://localhost:8000
echo.
echo Access from:
echo   - Web browser: http://localhost:8000
echo   - API docs: http://localhost:8000/docs
echo   - Mobile: http://YOUR_IP:8000
echo.
echo Press Ctrl+C to stop server
echo.

cd server
python main.py

pause

