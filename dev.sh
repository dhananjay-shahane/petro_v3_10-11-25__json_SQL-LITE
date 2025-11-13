#!/bin/bash
# Development startup script for Petrophysics Workspace
# Starts FastAPI backend (port 5001) and Vite frontend (port 5000)
# Storage: SQLite database (data/petrophysics.db) - active and configured

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Start FastAPI server in background on port 5001
export FLASK_PORT=5001
cd "$SCRIPT_DIR/backend" && uv run uvicorn main:app --host localhost --port 5001 --reload &
API_PID=$!

# Wait for FastAPI to start
echo "Starting backend on port 5001 (SQLite storage active)..."
sleep 3

# Start Vite dev server on port 5000 (frontend)
echo "Starting frontend on port 5000..."
cd "$SCRIPT_DIR/frontend"
npm run dev:vite

# Cleanup on exit
kill $API_PID 2>/dev/null
