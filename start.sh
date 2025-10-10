#!/bin/bash

# Heat Up service startup script

echo "🔥 Heat Up - Telegram Session Warmup Service"
echo "============================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating from .env.example..."
    
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file"
        echo "⚠️  Please edit .env and add your API keys!"
        echo ""
        exit 1
    else
        echo "❌ .env.example not found!"
        exit 1
    fi
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate venv
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Start service
echo "🚀 Starting Heat Up service..."
echo "   Access API at: http://localhost:8080"
echo "   Documentation: http://localhost:8080/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python main.py

