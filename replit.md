# Petrophysics Workspace

## Overview
A full-stack petrophysics data analysis and visualization application for managing wells, logs, cross-plots, and zonation data.

**Tech Stack:**
- **Frontend**: React + TypeScript + Vite (port 5000)
- **Backend**: FastAPI + Python 3.11 (port 5001 in dev, port 5000 in production)
- **Database**: SQLite (`data/petrophysics.db`)
- **Package Managers**: uv (Python), npm (Node.js)

## Project Structure
```
.
├── frontend/           # React + Vite frontend
│   ├── src/
│   │   ├── components/ # UI components (panels, dialogs, workspace)
│   │   ├── pages/      # Page components
│   │   ├── lib/        # API utilities and config
│   │   └── types/      # TypeScript type definitions
│   └── vite.config.ts  # Vite configuration (configured for Replit)
├── backend/            # FastAPI backend
│   ├── routers/        # API endpoints
│   ├── utils/          # Business logic and utilities
│   ├── main.py         # FastAPI application entry point
│   └── pyproject.toml  # Python dependencies (uv)
├── data/               # SQLite database and settings
│   └── petrophysics.db # Main database
├── dev.sh              # Development startup script
└── production.sh       # Production startup script
```

## Development
```bash
npm run dev  # or bash dev.sh
```
This starts:
- Backend on http://localhost:5001 (FastAPI with auto-reload)
- Frontend on http://0.0.0.0:5000 (Vite dev server)

## Production
```bash
npm run build  # Build frontend assets
npm start      # or bash production.sh
```
Production mode serves both static files and API from port 5000.

## Key Features
- Well data management and visualization
- Log plotting and cross-plotting
- Zonation analysis
- Data import/export (LAS files)
- CLI terminal interface
- Project and workspace management
- Storage inspector

## Configuration Notes
- **Frontend**: Configured with `allowedHosts: true` for Replit's proxy environment
- **CORS**: Enabled for all origins in development mode
- **Proxy**: Frontend proxies `/api` requests to backend on port 5001
- **Upload Limit**: 500 MB max file size for LAS files
- **Session**: 30-day session timeout

## Database
- SQLite database located at `data/petrophysics.db`
- Backup files stored in `data/backups/`
- Schema migrations available in `backend/utils/migrate_*.py`

## Recent Changes
- 2025-11-13: Initial setup for Replit environment
  - Installed Python 3.11 with uv package manager
  - Installed Node.js dependencies
  - Created production deployment script
  - Configured deployment for autoscale
  - Added .gitignore for Python and Node.js
  - Workflow configured for port 5000 with webview output
