#!/bin/bash
set -e

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo "Starting UptimeGuard..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
