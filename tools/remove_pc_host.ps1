$ErrorActionPreference = 'Stop'
$taskName = 'Atulya Personal PC Host'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host 'Atulya automatic PC hosting was removed. Project files and personal data were kept.'
} else {
    Write-Host 'Atulya automatic PC hosting is not installed.'
}
