<#
  Atulya portable runtime installer (Windows PowerShell).

  Downloads the offline brain + voice + ears into .\runtime so the whole
  project folder is self-contained and can be copied to another machine.
  Nothing is installed system-wide and nothing runs hidden — see
  install\manifest.json for exactly what is fetched.

  Usage:
    powershell -ExecutionPolicy Bypass -File install\setup.ps1
    powershell -ExecutionPolicy Bypass -File install\setup.ps1 -Mode voice
    powershell -ExecutionPolicy Bypass -File install\setup.ps1 -Mode full
#>
param(
  [ValidateSet("brain", "voice", "full")]
  [string]$Mode = "brain"
)

$ErrorActionPreference = "Stop"
$Root    = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Root "runtime"
$Models  = Join-Path $Runtime "models"
$Bin     = Join-Path $Runtime "bin"

$QwenUrl  = "https://huggingface.co/unsloth/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q4_K_M.gguf"
$QwenDest = Join-Path $Models "Qwen3-0.6B-Q4_K_M.gguf"
$PiperUrl = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
$VoiceOnnx = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx"
$VoiceJson = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"

Write-Host "== Atulya portable runtime =="
Write-Host "Installing into: $Runtime"
Write-Host "Mode: $Mode"
Write-Host "See install\manifest.json for exactly what is downloaded.`n"

New-Item -ItemType Directory -Force -Path $Models, $Bin | Out-Null

function Get-File($url, $dest) {
  if ((Test-Path $dest) -and ((Get-Item $dest).Length -gt 100000)) {
    Write-Host "  already present: $(Split-Path $dest -Leaf)"; return
  }
  Write-Host "  downloading: $(Split-Path $dest -Leaf)"
  Invoke-WebRequest -Uri $url -OutFile "$dest.part" -UseBasicParsing
  Move-Item -Force "$dest.part" $dest
}

Write-Host "[1/4] Brain - Qwen3-0.6B GGUF (~484 MB)"
Get-File $QwenUrl $QwenDest

if ($Mode -eq "voice" -or $Mode -eq "full") {
  Write-Host "[2/4] Voice - Piper TTS + en_US-amy"
  New-Item -ItemType Directory -Force -Path (Join-Path $Models "piper") | Out-Null
  Get-File $VoiceOnnx (Join-Path $Models "piper\en_US-amy-medium.onnx")
  Get-File $VoiceJson (Join-Path $Models "piper\en_US-amy-medium.onnx.json")
  $piperExe = Join-Path $Bin "piper\piper.exe"
  if (-not (Test-Path $piperExe)) {
    $zip = Join-Path $Bin "piper.zip"
    Get-File $PiperUrl $zip
    Expand-Archive -Force -Path $zip -DestinationPath $Bin
    Remove-Item -Force $zip
  }
}

Write-Host "[3/4] Python runtime packages"
$pkgs = @("llama-cpp-python", "edge-tts")
if ($Mode -eq "full") { $pkgs += @("faster-whisper", "mss", "rapidocr-onnxruntime") }
python -m pip install --quiet @pkgs

Write-Host "[4/4] Verify"
python (Join-Path $Root "install\verify.py")

Write-Host "`nDone. The brain lives at: $QwenDest"
Write-Host "Start Atulya with: python -m atulya.cli chat   (or start.bat)"
