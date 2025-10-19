# Pre-commit hook to block unwanted .md files
# Only allow: README.md, CHANGELOG.md, ROADMAP.md

$ALLOWED_MD_FILES = @("README.md", "CHANGELOG.md", "ROADMAP.md")

# Get list of staged .md files
$STAGED_MD_FILES = git diff --cached --name-only --diff-filter=A | Where-Object { $_ -match '\.md$' }

if ($STAGED_MD_FILES) {
    $BLOCKED_FILES = @()
    
    foreach ($file in $STAGED_MD_FILES) {
        $basename = Split-Path $file -Leaf
        $isAllowed = $false
        
        foreach ($allowed in $ALLOWED_MD_FILES) {
            if ($basename -eq $allowed) {
                $isAllowed = $true
                break
            }
        }
        
        if (-not $isAllowed) {
            $BLOCKED_FILES += $file
        }
    }
    
    if ($BLOCKED_FILES.Count -gt 0) {
        Write-Host "❌ Error: Attempting to commit unwanted .md files!" -ForegroundColor Red
        Write-Host "Only these .md files are allowed: $($ALLOWED_MD_FILES -join ', ')" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Blocked files:" -ForegroundColor Red
        foreach ($file in $BLOCKED_FILES) {
            Write-Host "  - $file" -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "Please remove these files or update the whitelist in scripts/pre-commit-hook.ps1" -ForegroundColor Yellow
        exit 1
    }
}

exit 0

