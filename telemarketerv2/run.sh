#!/usr/bin/env bash
# Run the AI Telemarketer backend on Ubuntu/Linux.
# Usage: ./run.sh [--reload]
#   --reload  Enable auto-reload for development (default: off for production).

set -e
cd "$(dirname "$0")"

if [[ ! -d "venv" ]]; then
    echo "Virtual environment not found. Create it with:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

if [[ ! -f ".env" ]]; then
    echo "Warning: .env not found. Copy .env.example or create .env with TWILIO_*, GROQ_API_KEY, NGROK_WEBSOCKET_URL, etc."
fi

RELOAD=""
if [[ "${1:-}" == "--reload" ]]; then
    RELOAD="--reload"
    echo "Starting with --reload (development mode)."
fi

source venv/bin/activate
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 $RELOAD
