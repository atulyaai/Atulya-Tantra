@echo off
setlocal
title Atulya Tantra WebUI

cd /d "%~dp0"

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
  )
)

if "%ATULYA_BACKEND_PYTHON%"=="" set "ATULYA_BACKEND_PYTHON=python"

if not exist "webui\dist\index.html" (
  echo Building WebUI...
  pushd webui
  if not exist "node_modules" npm install
  npm run build
  if errorlevel 1 exit /b 1
  popd
)

echo Starting Atulya Tantra WebUI at http://127.0.0.1:8501
start "" "http://127.0.0.1:8501"
"%ATULYA_BACKEND_PYTHON%" -u -m webui.backend.app

endlocal
