param([string]$Python)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $projectDirectory '.venv\Scripts\python.exe' }
$buildDirectory = Join-Path $projectDirectory 'data\pc-build'
$outputDirectory = Join-Path $projectDirectory 'dist\windows'
Push-Location $projectDirectory
try {
    & $Python -m PyInstaller --noconfirm --onefile --windowed --name Atulya-PC-Companion --paths . --distpath $outputDirectory --workpath $buildDirectory --specpath $buildDirectory tools/pc_companion_app.py
    if ($LASTEXITCODE -ne 0) { throw 'Companion build failed. Install PyInstaller in the build environment first.' }
    $executable = Join-Path $outputDirectory 'Atulya-PC-Companion.exe'
    $report = Join-Path $buildDirectory ('selftest-' + [guid]::NewGuid().ToString() + '.json')
    $process = Start-Process -FilePath $executable -ArgumentList '--self-test',('"' + $report + '"') -PassThru -Wait -WindowStyle Hidden
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw 'Packaged companion self-test failed.' }
    $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if (-not ($result.ok -and $result.packaged)) { throw 'Packaged runtime did not pass.' }
    Get-FileHash -LiteralPath $executable -Algorithm SHA256
} finally { Pop-Location }
