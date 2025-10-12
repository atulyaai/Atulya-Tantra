# Setup script for Windows PowerShell

Write-Host "🚀 Setting up Atulya Tantra..." -ForegroundColor Green

# Check Python
try {
    python --version | Out-Null
} catch {
    Write-Host "❌ Python not found! Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

# Check Ollama
try {
    ollama --version | Out-Null
} catch {
    Write-Host "❌ Ollama not found! Download from: https://ollama.ai/" -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host "📦 Installing Python dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt

# Download model
Write-Host "🤖 Downloading AI model..." -ForegroundColor Cyan
ollama pull phi3:mini

Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🎤 Run: python clients\gui\voice_gui.py" -ForegroundColor Yellow

