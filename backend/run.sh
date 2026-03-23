#!/bin/bash
cd "$(dirname "$0")"
echo "Setting up virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
echo "Installing requirements..."
pip install -r requirements.txt
echo "Starting FastAPI server..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000
