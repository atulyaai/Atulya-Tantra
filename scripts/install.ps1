# Atulya Tantra - Auto-Installation Script for Windows
# Version: 2.0.1
# This script automatically detects the Windows system and installs Atulya Tantra from zero

param(
    [switch]$SkipOptional,
    [switch]$SkipTests,
    [switch]$CreateService
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Blue"
$Cyan = "Cyan"

# Logging functions
function Write-Log {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" -ForegroundColor $Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor $Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $Blue
}

# Banner
function Show-Banner {
    Write-Host @"
╔══════════════════════════════════════════════════════════════╗
║                    Atulya Tantra AGI System                ║
║                    Auto-Installation Script                ║
║                        Version 2.0.1                       ║
╚══════════════════════════════════════════════════════════════╝
"@ -ForegroundColor $Cyan
}

# System detection
function Test-SystemRequirements {
    Write-Log "Detecting Windows system..."
    
    $OSVersion = [System.Environment]::OSVersion.Version
    $OSName = (Get-WmiObject -Class Win32_OperatingSystem).Caption
    
    Write-Info "Detected: $OSName (Version $($OSVersion.Major).$($OSVersion.Minor))"
    
    # Check PowerShell version
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        Write-Error "PowerShell 5.0 or higher is required"
        exit 1
    }
    
    # Check if running as administrator
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
    
    if (-not $isAdmin) {
        Write-Warning "Not running as administrator. Some features may not work properly."
        Write-Host "Continue anyway? (y/N): " -NoNewline
        $response = Read-Host
        if ($response -notmatch '^[Yy]$') {
            exit 1
        }
    }
    
    Write-Log "System requirements check completed"
}

# Install Chocolatey if not present
function Install-Chocolatey {
    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Log "Installing Chocolatey package manager..."
        
        try {
            Set-ExecutionPolicy Bypass -Scope Process -Force
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
            iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
            Write-Log "Chocolatey installed successfully"
        }
        catch {
            Write-Error "Failed to install Chocolatey: $_"
            exit 1
        }
    }
    else {
        Write-Log "Chocolatey already installed"
    }
}

# Install system dependencies
function Install-SystemDependencies {
    Write-Log "Installing system dependencies..."
    
    $packages = @(
        "python3",
        "git",
        "curl",
        "wget",
        "7zip"
    )
    
    foreach ($package in $packages) {
        Write-Info "Installing $package..."
        try {
            choco install $package -y
        }
        catch {
            Write-Warning "Failed to install $package via Chocolatey, trying alternative method..."
            # Alternative installation methods can be added here
        }
    }
    
    Write-Log "System dependencies installation completed"
}

# Install Python dependencies
function Install-PythonDependencies {
    Write-Log "Installing Python dependencies..."
    
    # Check Python installation
    try {
        $pythonVersion = python --version 2>&1
        Write-Info "Found Python: $pythonVersion"
    }
    catch {
        Write-Error "Python not found. Please install Python 3.8+ and try again"
        exit 1
    }
    
    # Create virtual environment
    Write-Info "Creating virtual environment..."
    python -m venv .venv
    
    # Activate virtual environment
    $venvPath = Join-Path $PWD ".venv\Scripts\Activate.ps1"
    & $venvPath
    
    # Upgrade pip
    Write-Info "Upgrading pip..."
    python -m pip install --upgrade pip
    
    # Install requirements
    if (Test-Path "requirements.txt") {
        Write-Info "Installing requirements from requirements.txt..."
        pip install -r requirements.txt
    }
    else {
        Write-Error "requirements.txt not found!"
        exit 1
    }
    
    Write-Log "Python dependencies installed successfully"
}

# Setup data directories
function Initialize-Directories {
    Write-Log "Setting up data directories..."
    
    $directories = @(
        "data",
        "data\logs",
        "data\uploads",
        "data\cache",
        "data\security",
        "data\analytics",
        "data\database",
        "data\models",
        "data\models\audio",
        "data\models\vision",
        "data\models\text"
    )
    
    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Info "Created directory: $dir"
        }
    }
    
    Write-Log "Data directories created successfully"
}

# Initialize configuration
function Initialize-Configuration {
    Write-Log "Initializing configuration..."
    
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Warning "Created .env from .env.example. Please edit it with your API keys."
        }
        else {
            Write-Error ".env.example not found!"
            exit 1
        }
    }
    
    Write-Log "Configuration initialized"
}

# Install optional dependencies
function Install-OptionalDependencies {
    if ($SkipOptional) {
        Write-Info "Skipping optional dependencies installation"
        return
    }
    
    Write-Log "Installing optional dependencies..."
    
    # Install FFmpeg for audio processing
    try {
        choco install ffmpeg -y
        Write-Info "FFmpeg installed successfully"
    }
    catch {
        Write-Warning "Failed to install FFmpeg via Chocolatey"
    }
    
    # Install Visual Studio Build Tools for Python packages that need compilation
    try {
        choco install visualstudio2019buildtools -y
        Write-Info "Visual Studio Build Tools installed successfully"
    }
    catch {
        Write-Warning "Failed to install Visual Studio Build Tools"
    }
    
    Write-Log "Optional dependencies installation completed"
}

# Run system tests
function Invoke-SystemTests {
    if ($SkipTests) {
        Write-Info "Skipping system tests"
        return
    }
    
    Write-Log "Running system tests..."
    
    $venvPath = Join-Path $PWD ".venv\Scripts\Activate.ps1"
    & $venvPath
    
    if (Test-Path "testing") {
        try {
            python -m pytest testing/ -v
            Write-Log "Tests completed successfully"
        }
        catch {
            Write-Warning "Some tests failed, but continuing installation..."
        }
    }
    else {
        Write-Warning "No tests found, skipping..."
    }
}

# Initialize database
function Initialize-Database {
    Write-Log "Initializing database..."
    
    $venvPath = Join-Path $PWD ".venv\Scripts\Activate.ps1"
    & $venvPath
    
    if (Test-Path "scripts\init_admin_db.py") {
        try {
            python scripts\init_admin_db.py
            Write-Log "Database initialized successfully"
        }
        catch {
            Write-Warning "Database initialization failed, but continuing..."
        }
    }
    else {
        Write-Warning "Database initialization script not found, skipping..."
    }
}

# Create Windows service
function New-WindowsService {
    if (-not $CreateService) {
        Write-Info "Skipping Windows service creation"
        return
    }
    
    Write-Log "Creating Windows service..."
    
    $serviceName = "AtulyaTantra"
    $serviceDisplayName = "Atulya Tantra AGI System"
    $serviceDescription = "Advanced Artificial General Intelligence System"
    
    $pythonPath = Join-Path $PWD ".venv\Scripts\python.exe"
    $scriptPath = Join-Path $PWD "server.py"
    
    try {
        # Create service using sc.exe
        $command = "sc.exe create `"$serviceName`" binPath= `"$pythonPath $scriptPath`" DisplayName= `"$serviceDisplayName`" start= auto"
        Invoke-Expression $command
        
        # Set service description
        sc.exe description $serviceName $serviceDescription
        
        Write-Log "Windows service '$serviceName' created successfully"
        Write-Info "Use 'sc.exe start $serviceName' to start the service"
    }
    catch {
        Write-Warning "Failed to create Windows service: $_"
    }
}

# Create desktop shortcut
function New-DesktopShortcut {
    Write-Log "Creating desktop shortcut..."
    
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Atulya Tantra.lnk")
    $Shortcut.TargetPath = Join-Path $PWD ".venv\Scripts\python.exe"
    $Shortcut.Arguments = "server.py"
    $Shortcut.WorkingDirectory = $PWD
    $Shortcut.Description = "Atulya Tantra AGI System"
    $Shortcut.Save()
    
    Write-Log "Desktop shortcut created successfully"
}

# Main installation function
function Start-Installation {
    Show-Banner
    
    Write-Log "Starting Atulya Tantra installation..."
    
    Test-SystemRequirements
    Install-Chocolatey
    Install-SystemDependencies
    Install-PythonDependencies
    Initialize-Directories
    Initialize-Configuration
    Install-OptionalDependencies
    Initialize-Database
    Invoke-SystemTests
    New-WindowsService
    New-DesktopShortcut
    
    Write-Log "Installation completed successfully!"
    
    Write-Host @"
╔══════════════════════════════════════════════════════════════╗
║                    Installation Complete!                  ║
╚══════════════════════════════════════════════════════════════╝
"@ -ForegroundColor $Green
    
    Write-Host "Next steps:" -ForegroundColor $Blue
    Write-Host "1. Edit .env file with your API keys"
    Write-Host "2. Start the server: .venv\Scripts\python server.py"
    Write-Host "3. Access the web interface: http://localhost:8000"
    Write-Host "4. Admin panel: http://localhost:8000/admin"
    
    if ($CreateService) {
        Write-Host "5. Start as service: sc.exe start AtulyaTantra"
    }
}

# Run main function
Start-Installation
