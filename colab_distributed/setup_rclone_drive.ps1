param(
    [string]$Remote = "gdrive",
    [string]$DriveRoot = "npdna_training"
)

$ErrorActionPreference = "Stop"

function Find-Rclone {
    $cmd = Get-Command rclone -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $homeBin = Join-Path $HOME "bin\rclone.exe"
    if (Test-Path $homeBin) {
        return $homeBin
    }

    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path $wingetRoot) {
        $found = Get-ChildItem -Path $wingetRoot -Recurse -Filter rclone.exe -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
        if ($found) {
            return $found
        }
    }

    return $null
}

$rclone = Find-Rclone
if (-not $rclone) {
    Write-Host "rclone was not found. Installing with winget..."
    winget install Rclone.Rclone --accept-package-agreements --accept-source-agreements
    $rclone = Find-Rclone
}

if (-not $rclone) {
    throw "Could not find rclone after install. Open a new PowerShell and run this script again."
}

Write-Host "Using rclone: $rclone"

$remoteLine = "$Remote`:"
$remotes = & $rclone listremotes
if ($remotes -notcontains $remoteLine) {
    Write-Host ""
    Write-Host "Create the Google Drive remote now."
    Write-Host "Use these answers:"
    Write-Host "  n -> New remote"
    Write-Host "  name -> $Remote"
    Write-Host "  Storage -> drive or 24"
    Write-Host "  client_id -> press Enter"
    Write-Host "  client_secret -> press Enter"
    Write-Host "  scope -> full Drive access"
    Write-Host "  root_folder_id -> press Enter"
    Write-Host "  service_account_file -> press Enter"
    Write-Host "  Edit advanced config -> n"
    Write-Host "  Use auto config -> y"
    Write-Host "  Browser -> Allow, then Open rclone"
    Write-Host "  Shared Drive -> n"
    Write-Host "  Keep remote -> y"
    Write-Host "  Quit -> q"
    Write-Host ""
    & $rclone config
}

$remotes = & $rclone listremotes
if ($remotes -notcontains $remoteLine) {
    throw "Remote '$Remote' was not created. Run this script again and choose 'n' for New remote."
}

Write-Host "Remote '$Remote' is ready."

$probe = & $rclone lsd "$Remote`:" 2>&1
if ($LASTEXITCODE -ne 0) {
    $probeText = $probe -join "`n"
    if ($probeText -match "empty token|reconnect|oauth") {
        Write-Host ""
        Write-Host "Remote exists but is not authorized yet."
        Write-Host "A browser window should open now. Sign in, click Allow, then choose Open rclone."
        & $rclone config reconnect "$Remote`:"

        & $rclone lsd "$Remote`:" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Reconnect did not complete. Run: rclone config reconnect $Remote`:"
        }
    }
    else {
        throw "Could not access $Remote`: $probeText"
    }
}

& $rclone mkdir "$Remote`:$DriveRoot"

$env:ATULYA_RCLONE_REMOTE = $Remote
$env:ATULYA_DRIVE_ROOT = $DriveRoot

Write-Host "Deploying training files..."
python colab_distributed\monitor.py --setup

Write-Host ""
Write-Host "Done. Share the '$DriveRoot' folder in Google Drive with other trainer accounts as Editor."
