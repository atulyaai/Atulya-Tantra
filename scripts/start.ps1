Param(
  [ValidateSet('start','install','migrate','help')]
  [string]$Command = 'start'
)

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[SUCCESS] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARNING] $msg" -ForegroundColor Yellow }
function Write-ErrorMsg($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Ensure-Python {
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-ErrorMsg "Python is not installed or not in PATH"
    exit 1
  }
  Write-Info (python --version)
}

function Ensure-Venv {
  if (-not (Test-Path ".venv")) {
    Write-Warn ".venv not found. Creating..."
    python -m venv .venv
    Write-Success "Virtual environment created"
  }
}

function Activate-Venv {
  Write-Info "Activating virtual environment..."
  $venvPath = ".venv/Scripts/Activate.ps1"
  if (-not (Test-Path $venvPath)) { $venvPath = ".venv\Scripts\Activate.ps1" }
  . $venvPath
}

function Install-Dependencies {
  Write-Info "Installing dependencies..."
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  Write-Success "Dependencies installed"
}

function Ensure-Env {
  if (-not (Test-Path ".env")) {
    Write-Warn ".env not found. Creating from env.example..."
    Copy-Item env.example .env
    Write-Warn "Edit .env with your secrets before production"
  }
}

function Create-Dirs {
  Write-Info "Creating directories..."
  New-Item -ItemType Directory -Force -Path logs | Out-Null
  New-Item -ItemType Directory -Force -Path data\cache | Out-Null
  New-Item -ItemType Directory -Force -Path data\uploads | Out-Null
  New-Item -ItemType Directory -Force -Path data\vectors | Out-Null
}

function Run-Migrations {
  Write-Info "Running database migrations..."
  alembic upgrade head
}

function Start-App {
  Write-Info "Starting Atulya Tantra..."
  $env:PYTHONPATH = "$PWD"
  python start.py
}

switch ($Command) {
  'install' {
    Ensure-Python
    Ensure-Venv
    Activate-Venv
    Install-Dependencies
    Create-Dirs
    Write-Success "Install complete"
  }
  'migrate' {
    Activate-Venv
    Run-Migrations
  }
  'help' {
    Write-Host "Usage: .\scripts\start.ps1 [start|install|migrate|help]"
  }
  default {
    Ensure-Python
    Ensure-Venv
    Activate-Venv
    Install-Dependencies
    Ensure-Env
    Create-Dirs
    Run-Migrations
    Start-App
  }
}


