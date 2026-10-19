@echo off
cd /d "%~dp0"
"%~dp0.venv\Scripts\pythonw.exe" -m tools.companion_setup
