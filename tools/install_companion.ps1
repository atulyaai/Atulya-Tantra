$ErrorActionPreference = 'Stop'
$companionRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$companionPython = Join-Path $companionRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath (Join-Path $companionRoot 'data\companion\secrets.enc'))) {
    throw 'Connect this PC with Connect-This-PC.cmd before installing automatic startup.'
}
if (-not (Test-Path -LiteralPath $companionPython)) { throw 'Project Python environment is missing.' }
$companionUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$companionAction = New-ScheduledTaskAction -Execute $companionPython -Argument '-u -m tools.device_companion --saved' -WorkingDirectory $companionRoot
$companionTrigger = New-ScheduledTaskTrigger -AtLogOn -User $companionUser
$companionSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'Atulya PC Companion' -Action $companionAction -Trigger $companionTrigger -Settings $companionSettings -Description 'Connects this PC outbound to its paired Atulya server. Revoke its device credential to disconnect.' -Force | Out-Null
Write-Host 'Atulya companion will start after Windows sign-in. This does not prevent sleep or open inbound network ports.'
