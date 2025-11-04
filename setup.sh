#!/bin/bash
# Setup script for YDL scraper

set -e

echo "================================="
echo "壹点灵 (YDL) 数据采集工具 - 安装"
echo "================================="
echo

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment
if [ ! -d "venv" ]; then
    echo
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo
echo "Installing dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo
echo "Installing Playwright browsers..."
playwright install chromium

# Create necessary directories
echo
echo "Creating directories..."
mkdir -p data/posts data/raw logs

# Create .env from example if not exists
if [ ! -f ".env" ]; then
    echo
    echo "Creating .env file from example..."
    cp env.example .env
    echo "⚠️  Please edit .env to configure your settings."
fi

echo
echo "================================="
echo "✅ Installation complete!"
echo "================================="
echo
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Configure settings: edit .env"
echo "3. Run tests: pytest"
echo "4. Start scraping: python main.py --mode full"
echo

