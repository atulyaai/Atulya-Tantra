param(
    [string]$Remote = "gdrive",
    [string]$DriveRoot = "npdna_training",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$targets = @(
    "$Remote`:$DriveRoot/source/tantra/data",
    "$Remote`:$DriveRoot/source/tantra/outputs"
)

if (-not $Apply) {
    Write-Host "Dry run. These remote folders will be deleted if you rerun with -Apply:"
    foreach ($target in $targets) {
        Write-Host "  $target"
    }
    Write-Host ""
    Write-Host "Run:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File training_collab\cleanup_drive_large.ps1 -Apply"
    exit 0
}

foreach ($target in $targets) {
    Write-Host "Deleting $target"
    rclone purge $target
}

Write-Host "Cleanup complete."
