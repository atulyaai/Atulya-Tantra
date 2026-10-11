$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$pythonw = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$taskName = 'Atulya Personal PC Host'

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $pythonw)) {
    throw 'The project-local Python environment is missing. Start Atulya once to prepare it, then retry this setup.'
}

# Hosting should not trigger multi-gigabyte model downloads. Repair runtime
# Python packages only when the existing environment reports a broken install.
& $python -m pip check *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Repairing Atulya runtime packages (model weights are not downloaded).'
    & $python -m pip install -r (Join-Path $projectRoot 'requirements.lock.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Runtime package repair failed; the PC host task was not installed.' }
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Runtime packages are still inconsistent; the PC host task was not installed.' }
}

$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonw -Argument '-m atulya.cli pc-host' -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Starts Atulya on this PC after sign-in. The app listens only on loopback.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host 'Atulya personal-PC hosting is installed and starting.'
Write-Host 'Local address: http://localhost:8501'
Write-Host 'Logs: data\logs\pc-host.log'
Write-Host 'The host stays private. Add a private-network HTTPS route separately to reach it from other devices.'
