<#
.SYNOPSIS
    Atulya Agent Setup Script — installs core + optional features.
.DESCRIPTION
    Installs required dependencies and optionally downloads the vision model.
#>

param(
    [switch]$Vision,
    [switch]$All,
    [switch]$Dev
)

$ROOT = Split-Path -Parent $PSScriptRoot
$VENV = Join-Path $ROOT "agent_env"

Write-Host "=== Atulya Agent Installation ===" -ForegroundColor Cyan

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found. Install Python 3.9+ from python.org" -ForegroundColor Red
    exit 1
}
Write-Host "Python: $($python.Source)" -ForegroundColor Green

# Create virtual env if not exists
if (-not (Test-Path $VENV)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $VENV
    if (-not $?) { Write-Host "Failed to create venv" -ForegroundColor Red; exit 1 }
}

# Activate
$activate = Join-Path $VENV "Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
}

# Install core deps
Write-Host "Installing core dependencies..." -ForegroundColor Yellow
pip install -r (Join-Path $ROOT "requirements.txt") 2>&1 | Out-Null

# Install optional deps
if ($Vision -or $All) {
    Write-Host "Installing vision dependencies..." -ForegroundColor Yellow
    pip install llama-cpp-python 2>&1 | Out-Null
    Write-Host "Downloading LLaVA vision model..." -ForegroundColor Yellow
    python -c "
import asyncio
from atulya.agent.tools import download_vision_model
async def download():
    v = VisionAnalyzer()
    r = await v.download_model()
    print(r)
asyncio.run(download())
"
}

if ($All) {
    Write-Host "Installing email dependencies..." -ForegroundColor Yellow
    pip install aioimaplib aiosmtplib 2>&1 | Out-Null
}

if ($Dev) {
    Write-Host "Installing dev dependencies..." -ForegroundColor Yellow
    pip install pytest pytest-asyncio 2>&1 | Out-Null
}

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Cyan
Write-Host "To start Atulya Agent:"
Write-Host "  cd '$ROOT'"
Write-Host "  .\agent_env\Scripts\Activate.ps1"
Write-Host "  python -m uvicorn drishti.dashboard.app:app"
Write-Host ""
Write-Host "Optional features:"
Write-Host "  ./install_agent.ps1 -Vision   # adds vision model"
Write-Host "  ./install_agent.ps1 -All      # installs everything"
Write-Host ""
Write-Host "Configure email: POST /api/agent/email/configure"
Write-Host "Or edit: config/agent_config.json"
