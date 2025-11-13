# Development startup script for Petrophysics Workspace (Windows PowerShell)
# Starts FastAPI backend (port 5001) and Vite frontend (port 5000)
# Storage: SQLite database (data/petrophysics.db) - active and configured

# Get the script directory
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Start FastAPI server (Uvicorn) in background on port 5001
$env:FLASK_PORT = 5001
Write-Host "Starting backend on port 5001 (SQLite storage active)..."
Set-Location "$SCRIPT_DIR\backend"
$uvicorn = Start-Process "uv" -ArgumentList "run", "uvicorn", "main:app", "--host", "localhost", "--port", "5001", "--reload" -PassThru

# Wait for FastAPI to start
Start-Sleep -Seconds 2

# Install frontend dependencies if needed
Set-Location "$SCRIPT_DIR\frontend"
if (!(Test-Path "node_modules")) {
    npm install
}

# Start Vite dev server (frontend)
Write-Host "Starting frontend on port 5000..."
npm run dev:vite

# Cleanup on exit
try {
    Stop-Process -Id $uvicorn.Id -Force -ErrorAction SilentlyContinue
} catch {
    Write-Host "Failed to stop FastAPI server"
}

