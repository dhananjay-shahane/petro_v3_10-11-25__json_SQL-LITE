# Petrophysics Workspace

## Overview
A full-stack petrophysics data analysis and visualization application for managing wells, logs, cross-plots, and zonation data.

**Tech Stack:**
- **Frontend**: React + TypeScript + Vite (port 5000)
- **Backend**: FastAPI + Python 3.11 (port 5001 in dev, port 5000 in production)
- **Storage**: 
  - Well Data: File-based (.ptrc JSON files) with in-memory LRU cache
  - Other Data: SQLite (`data/petrophysics.db`) for sessions, layouts, settings
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

## Storage Architecture

### Well Data Storage (File-Based)
- **Format**: Individual JSON files with `.ptrc` extension
- **Location**: `{project}/10-WELLS/{well_name}.ptrc`
- **Features**:
  - File indexing at server startup for fast lookups
  - In-memory LRU cache (50 files max) for performance
  - Lazy loading: Files loaded on-demand, not all at once
  - Automatic cache eviction when limit reached
- **Implementation**: `backend/utils/file_well_storage.py`

### Other Data Storage (SQLite)
- **Database**: `data/petrophysics.db`
- **Used For**: 
  - Sessions and session metadata
  - Project layouts and window configurations
  - User settings and preferences
  - CLI history
  - Workspace state
- **Backup**: Files stored in `data/backups/`
- **Migrations**: Available in `backend/utils/migrate_*.py`

### Why This Architecture?
- **Wells**: Large files (can be 100MB+) benefit from lazy loading and LRU caching
- **Metadata**: Small, frequently accessed data benefits from SQLite's indexing and query capabilities
- **Separation**: Clear boundary between well data and application metadata

## Recent Changes

### 2025-11-13: Storage Architecture Migration
- **Migrated well data from SQLite to file-based storage**
  - Created `FileWellStorageService` with LRU cache (OrderedDict-based)
  - Implemented file indexing at server startup via FastAPI lifespan hook
  - Added lazy loading for well files with automatic cache management
  - Updated wells router to use file storage instead of SQLite
  - Updated projects router to remove SQLite migration endpoints
- **SQLite retained for non-well data**
  - Sessions, layouts, window configs, settings still use SQLite
  - Clear separation between well data and metadata
- **Performance improvements**
  - Cache HIT/MISS tracking for monitoring
  - Up to 50 well files cached in memory
  - Automatic eviction of least recently used files

### 2025-11-13: Initial Replit Setup
- Installed Python 3.11 with uv package manager
- Installed Node.js dependencies
- Created production deployment script
- Configured deployment for autoscale
- Added .gitignore for Python and Node.js
- Workflow configured for port 5000 with webview output
