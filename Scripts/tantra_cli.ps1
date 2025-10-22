param(
  [switch]$Init,
  [switch]$List,
  [string]$Open
)

$host.ui.RawUI.WindowTitle = "Tantra CLI"

$version = "v0.1"
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$cwd = (Get-Location).Path

function Show-Banner {
  $banner = @"
╭─── Tantra CLI $version ─────────────────────────────────────────────────────────────────────────────────────────────╮
│                                    │ Tips                                                                            │
│       Welcome back $user!          │ /init    Create TANTRA.md instructions                                          │
│                                    │ /list    Show recent conversation sessions                                       │
│               ▐▛███▜▌              │ /open X  Open a session file                                                     │
│              ▝▜█████▛┘             │                                                                                 │
│                ▘▘ ▝▝               │ Current directory                                                               │
│                                    │ $cwd                                                                            │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
"@
  Write-Host $banner
}

function Init-Instructions {
  $path = Join-Path -Path (Get-Location) -ChildPath 'TANTRA.md'
  if(Test-Path $path){ Write-Host "TANTRA.md already exists"; return }
  @"
# TANTRA Instructions

- You are Tantra. Be concise, human, and proactive.
- Use local tools safely. Ask before destructive changes.
- Maintain conversation context.
"@ | Out-File -FilePath $path -Encoding utf8
  Write-Host "Created TANTRA.md"
}

function List-Sessions {
  $dir = Join-Path -Path (Get-Location) -ChildPath 'data/conversations'
  if(!(Test-Path $dir)){ Write-Host "No conversations yet."; return }
  Get-ChildItem -Recurse -Filter *.jsonl $dir | Sort-Object LastWriteTime -Descending | Select-Object -First 15 | ForEach-Object {
    Write-Host ("{0}  {1}" -f $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'), $_.FullName)
  }
}

function Open-Session([string]$Path){
  if(!(Test-Path $Path)){ Write-Host "Not found: $Path"; return }
  notepad $Path | Out-Null
}

Show-Banner

if($Init){ Init-Instructions; exit }
if($List){ List-Sessions; exit }
if($Open){ Open-Session $Open; exit }

Write-Host "────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────"
Write-Host "> Try \"/list\" or \"/init\""
Write-Host "────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────"


