#!/usr/bin/env bash
set -e

echo "==> Checking Homebrew..."
if ! command -v brew &>/dev/null; then
  echo "Homebrew not found. Install it from https://brew.sh first, then re-run this script."
  exit 1
fi

echo "==> Installing ffmpeg + gh via Homebrew (skips if already installed)..."
brew list ffmpeg &>/dev/null || brew install ffmpeg
brew list gh &>/dev/null || brew install gh

echo "==> Creating virtual environment (venv/)..."
python3 -m venv venv
source venv/bin/activate

echo "==> Installing mcmosaic + Python dependencies..."
pip install --upgrade pip
pip install -e .

echo ""
echo "Setup complete. Next steps:"
echo "  source venv/bin/activate"
echo "  mcmosaic image input.png output.png"
echo "  mcmosaic video input.mp4 output.mp4"
echo "  mcmosaic video-alpha input.mp4 --frames-dir frames"
echo ""
echo "blocks/ is fetched automatically on first run -- nothing to set up by hand."
