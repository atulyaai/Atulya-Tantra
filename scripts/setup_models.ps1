# Atulya Tantra - Model Setup Script (PowerShell)
# Downloads recommended lightweight models for the system

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "🤖 Atulya Tantra - Model Setup" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if Ollama is installed
try {
    $null = Get-Command ollama -ErrorAction Stop
    Write-Host "✅ Ollama found" -ForegroundColor Green
} catch {
    Write-Host "❌ Ollama not found!" -ForegroundColor Red
    Write-Host "Please install Ollama first: https://ollama.com" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "📥 Downloading recommended models..." -ForegroundColor Cyan
Write-Host ""

# Model 1: phi3:mini (Recommended - Small & Fast)
Write-Host "1️⃣  phi3:mini (Recommended)" -ForegroundColor Green
Write-Host "   Size: ~2.2GB | Speed: Fast | Quality: Good"
$existing = ollama list | Select-String "phi3:mini"
if ($existing) {
    Write-Host "   ✅ Already installed" -ForegroundColor Green
} else {
    Write-Host "   📥 Downloading..." -ForegroundColor Yellow
    ollama pull phi3:mini
    Write-Host "   ✅ Installed successfully" -ForegroundColor Green
}
Write-Host ""

# Model 2: gemma:2b (Alternative - Even Smaller)
Write-Host "2️⃣  gemma:2b (Alternative - Smaller)" -ForegroundColor Yellow
Write-Host "   Size: ~1.4GB | Speed: Very Fast | Quality: Good"
$response = Read-Host "   Install gemma:2b? (y/N)"
if ($response -match '^[Yy]$') {
    $existing = ollama list | Select-String "gemma:2b"
    if ($existing) {
        Write-Host "   ✅ Already installed" -ForegroundColor Green
    } else {
        Write-Host "   📥 Downloading..." -ForegroundColor Yellow
        ollama pull gemma:2b
        Write-Host "   ✅ Installed successfully" -ForegroundColor Green
    }
}
Write-Host ""

# Model 3: mistral (Optional - Better Quality)
Write-Host "3️⃣  mistral (Optional - Better Quality)" -ForegroundColor Magenta
Write-Host "   Size: ~4.1GB | Speed: Moderate | Quality: Excellent"
$response = Read-Host "   Install mistral? (y/N)"
if ($response -match '^[Yy]$') {
    $existing = ollama list | Select-String "mistral"
    if ($existing) {
        Write-Host "   ✅ Already installed" -ForegroundColor Green
    } else {
        Write-Host "   📥 Downloading..." -ForegroundColor Yellow
        ollama pull mistral
        Write-Host "   ✅ Installed successfully" -ForegroundColor Green
    }
}
Write-Host ""

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "✅ Model Setup Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Installed models:" -ForegroundColor Cyan
ollama list
Write-Host ""
Write-Host "To use a specific model, edit configuration/settings.py:" -ForegroundColor Yellow
Write-Host "  default_model = 'phi3:mini'  # or 'gemma:2b' or 'mistral'"
Write-Host ""

