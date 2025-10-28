$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv/Scripts/python.exe")) {
    Write-Host "Python venv not found. Creating .venv..."
    py -3 -m venv .venv
}

Write-Host "Upgrading pip and installing requirements (if present)..."
./.venv/Scripts/python.exe -m pip install --upgrade pip | Out-Null
if (Test-Path "requirements.txt") {
    ./.venv/Scripts/pip.exe install -r requirements.txt | Out-Null
}

Write-Host "Running simple demo..."
./.venv/Scripts/python.exe demos/simple_working_demo.py


