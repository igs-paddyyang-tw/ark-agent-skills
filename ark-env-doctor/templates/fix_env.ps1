# fix_env.ps1
Write-Host '🔧 Fixing development environment...'

# Create venv if not exists
if (-not (Test-Path "venv")) {
    Write-Host '📦 Creating virtual environment...'
    py -m venv venv
}

# Activate
& venv\Scripts\Activate.ps1

# Install Python packages
if (Test-Path "requirements.txt") {
    Write-Host '📥 Installing Python dependencies...'
    pip install -r requirements.txt
}

# Check Go
if (-not (Get-Command go -ErrorAction SilentlyContinue)) {
    Write-Host '⚠️  Go not found. Install with: winget install GoLang.Go'
}

Write-Host '✅ Done!'
