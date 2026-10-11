# Atulya installer for Windows (x64 and ARM64). No administrator rights needed.
#
#   irm https://raw.githubusercontent.com/atulyaai/Atulya-Tantra/main/install.ps1 | iex
#   .\install.ps1 -Service          # also start Atulya automatically at sign-in
#   .\install.ps1 -RemoveService    # remove the sign-in task (keeps data)
#
# Steps: get the code (git, or a zip when git is missing), install uv and a
# private Python 3.12 if no Python >= 3.10 exists, create .venv, run setup.
param(
    [switch]$Service,
    [switch]$NoStart,
    [switch]$RemoveService,
    [string]$Dir = $(if ($env:ATULYA_DIR) { $env:ATULYA_DIR } else { Join-Path $HOME 'Atulya-Tantra' })
)
$ErrorActionPreference = 'Stop'
$repo = 'https://github.com/atulyaai/Atulya-Tantra'
function Say($text) { Write-Host "==> $text" -ForegroundColor Cyan }

if ($RemoveService) {
    & (Join-Path $Dir 'tools\remove_pc_host.ps1')
    return
}

# 1. Code: use this checkout when run from inside it, otherwise clone/download.
$here = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
if ((Test-Path (Join-Path $here 'pyproject.toml')) -and (Select-String -Quiet -Path (Join-Path $here 'pyproject.toml') -Pattern 'name = "atulya')) {
    $Dir = $here
} elseif ((Test-Path (Join-Path $Dir '.git')) -and (Get-Command git -ErrorAction SilentlyContinue)) {
    Say "Updating $Dir"; git -C $Dir pull --ff-only
} elseif (-not (Test-Path (Join-Path $Dir 'pyproject.toml'))) {
    Say "Downloading Atulya into $Dir"
    if (Get-Command git -ErrorAction SilentlyContinue) {
        git clone --depth 1 "$repo.git" $Dir
    } else {
        $zip = Join-Path $env:TEMP 'atulya-main.zip'
        $staging = Join-Path $env:TEMP ('atulya-' + [guid]::NewGuid())
        Invoke-WebRequest "$repo/archive/refs/heads/main.zip" -OutFile $zip -UseBasicParsing
        Expand-Archive $zip -DestinationPath $staging
        Move-Item (Get-ChildItem $staging | Select-Object -First 1).FullName $Dir
        Remove-Item $zip, $staging -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Set-Location $Dir

# 2. Python: reuse a system Python >= 3.10, else a uv-managed private one.
$venvPython = Join-Path $Dir '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    $systemPython = $null
    foreach ($candidate in @(@('py', '-3'), @('python'))) {
        if (Get-Command $candidate[0] -ErrorAction SilentlyContinue) {
            $extra = @($candidate | Select-Object -Skip 1)
            & $candidate[0] @extra -c 'import sys, venv; sys.exit(sys.version_info < (3, 10))' 2>$null
            if ($LASTEXITCODE -eq 0) { $systemPython = $candidate; break }
        }
    }
    if ($systemPython) {
        Say "Creating .venv with $($systemPython -join ' ')"
        $extra = @($systemPython | Select-Object -Skip 1)
        & $systemPython[0] @extra -m venv .venv
    }
    if (-not (Test-Path $venvPython)) {
        if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
            Say 'Installing uv (user-local Python manager)'
            powershell -NoProfile -ExecutionPolicy Bypass -Command 'irm https://astral.sh/uv/install.ps1 | iex'
            $env:Path = "$HOME\.local\bin;$env:Path"
        }
        Say 'Creating .venv with a private Python 3.12'
        if (Test-Path .venv) { Remove-Item .venv -Recurse -Force }
        uv venv --seed --python 3.12 .venv
    }
}

# 3. Config and setup (packages + models sized to this machine).
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Say 'Installing packages and preparing models (first run downloads a few GB)'
& $venvPython tools\bootstrap.py
if ($LASTEXITCODE -ne 0) { throw 'Atulya setup failed; see the messages above.' }

# 4. Optional sign-in task, otherwise run in this window.
if ($Service) {
    & (Join-Path $Dir 'tools\install_pc_host.ps1')
} elseif ($NoStart) {
    Say "Installed. Start with: $Dir\start.bat"
} else {
    Say 'Starting Atulya at http://localhost:8501 (Ctrl+C to stop)'
    & $venvPython -m atulya.cli serve
}
