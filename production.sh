#!/bin/bash
# Production startup script for Petrophysics Workspace
# Serves built frontend and starts FastAPI backend on port 5000

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set production environment
export NODE_ENV=production
export FLASK_PORT=5000

# Start FastAPI server on port 5000 (serves both API and static files)
echo "Starting production server on port 5000..."
cd "$SCRIPT_DIR/backend" && uv run uvicorn main:app --host 0.0.0.0 --port 5000
