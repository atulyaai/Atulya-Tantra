param(
    [int]$Count = 10,
    [string]$Prefix = "gdrive_acc",
    [string]$DriveRoot = "npdna_training",
    [switch]$DeployAll
)

$ErrorActionPreference = "Stop"

Write-Host "This creates one rclone Google Drive remote per account."
Write-Host "Google still requires one browser Allow step per account."
Write-Host ""

for ($i = 1; $i -le $Count; $i++) {
    $remote = "$Prefix$i"
    Write-Host "============================================================"
    Write-Host "Account $i of $Count -> remote '$remote'"
    Write-Host "When the browser opens, sign in with Google account #$i."
    Write-Host "============================================================"

    powershell -ExecutionPolicy Bypass -File colab_distributed\setup_rclone_drive.ps1 `
        -Remote $remote `
        -DriveRoot $DriveRoot

    if ($DeployAll) {
        $env:ATULYA_RCLONE_REMOTE = $remote
        $env:ATULYA_DRIVE_ROOT = $DriveRoot
        python colab_distributed\monitor.py --setup
    }
}

Write-Host ""
Write-Host "All requested remotes are configured."
Write-Host "Use 'rclone listremotes' to see them."
