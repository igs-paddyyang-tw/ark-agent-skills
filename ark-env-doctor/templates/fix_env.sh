#!/bin/bash
set -e
echo '🔧 Fixing development environment...'

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo '📦 Creating virtual environment...'
    python3 -m venv venv
fi

# Activate
source venv/bin/activate

# Install Python packages
if [ -f "requirements.txt" ]; then
    echo '📥 Installing Python dependencies...'
    pip install -r requirements.txt
fi

# Install Go if missing
if ! command -v go &> /dev/null; then
    echo '⚠️  Go not found. Install with:'
    echo '    brew install go       # macOS'
    echo '    sudo apt install golang  # Ubuntu'
fi

echo '✅ Done!'
