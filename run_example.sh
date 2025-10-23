#!/bin/bash
# Quick start example script

set -e

echo "🚀 Research-to-Blog Pipeline - Quick Start"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Copying from env.example..."
    cp env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your GROQ_API_KEY"
    echo "   Get a free key at: https://console.groq.com"
    echo ""
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
    echo "✓ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate
echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Run the example
echo "🎯 Running example pipeline..."
echo "Topic: 'How do large language models improve code review quality'"
echo ""

python -m app.cli.main run \
    "How do large language models improve code review quality" \
    --audience "software engineers" \
    --goals "Explain LLM capabilities" \
    --goals "Discuss benefits and limitations" \
    --keywords "LLM" \
    --keywords "code review" \
    --out ./outputs

echo ""
echo "✅ Pipeline complete! Check ./outputs/ for results."
echo ""

