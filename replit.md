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

### 2025-11-13: Smart Duplicate Detection & Code Reorganization

#### Smart Duplicate Detection for LAS Imports
Implemented intelligent duplicate detection when loading LAS files. The system now:

**Features:**
1. **Curve-Based Comparison**: Compares actual log curve names (not just dataset names)
2. **Best-Match Selection**: Finds dataset with highest overlap ratio (≥50% required)
3. **Intelligent Merging**: Three outcomes:
   - **All curves exist** → Skip import, show "Dataset already available" message
   - **Some curves new** → Merge only new curves, show count of added vs skipped
   - **No match** → Create new dataset with versioning (MAIN, MAIN_1, MAIN_2, etc.)

**Files Changed:**
- `backend/utils/data_import_export.py`: Added smart duplicate detection logic (lines 43-393)
- `frontend/src/components/dialogs/NewWellDialog.tsx`: Added UI messages for duplicate detection (lines 164-185)

**How It Works:**
```python
# Backend detects duplicates by comparing curve names
new_curve_names = set(log.name for log in dataset.well_logs)
for existing_dataset in well.datasets:
    existing_curve_names = set(log.name for log in existing_dataset.well_logs)
    overlap_ratio = len(common_curves) / len(new_curve_names)
    # Select dataset with highest overlap ratio (≥50%)
```

**User Messages:**
- ℹ️ "Dataset Already Available" - all curves exist
- ✓ "Curves Merged" - X new curves added, Y duplicates skipped
- ✓ "Success" - new dataset created

#### Code Reorganization
Moved LAS import functions for better organization:

**Changes:**
1. Moved `create_well_from_las()` from `backend/utils/las_file_io.py` → `backend/utils/data_import_export.py`
2. Updated imports in:
   - `backend/utils/cli_service.py` - now imports from data_import_export.py
   - `backend/utils/data_import_export.py` - imports helper functions from las_file_io.py
3. Kept helper functions in `backend/utils/las_file_io.py`:
   - `get_well_name_from_las()` - Extract well name from LAS metadata
   - `read_las_file()` - Basic LAS file reading

**Rationale:**
- `data_import_export.py` is the natural home for import/export operations
- Consolidates all LAS import logic in one place
- Keeps low-level parsing helpers separate for reusability

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

---

## How to Verify System Features

### 1. Verify File-Based Storage (.ptrc files)
Check that well data is stored in `.ptrc` JSON files:
```bash
# List well files
ls petrophysics-workplace/*/10-WELLS/*.ptrc

# View file content
cat "petrophysics-workplace/dfgdfgdf/10-WELLS/#13-31 Hoffman Et Al.ptrc" | head -n 20
```

**What to look for:**
- Files have `.ptrc` extension (NOT `.db` or `.sql`)
- Files are in `{project}/10-WELLS/` directory
- Each file is valid JSON containing well data

### 2. Verify Lazy Loading
Watch the server logs when accessing wells:
```bash
# In server logs, look for:
[FileWellStorage] Cache MISS for dfgdfgdf::#13-31 Hoffman Et Al, loading from disk...
[FileWellStorage] Cached: dfgdfgdf::#13-31 Hoffman Et Al (cache size: 1/50)
```

**What to look for:**
- First access shows "Cache MISS" → file loaded from disk
- File is NOT loaded at server startup
- Only loaded when requested (lazy loading)

### 3. Verify LRU Caching
Access the same well multiple times and watch logs:
```bash
# First access:
[FileWellStorage] Cache MISS for dfgdfgdf::#13-31 Hoffman Et Al, loading from disk...

# Subsequent accesses:
[FileWellStorage] Cache HIT for dfgdfgdf::#13-31 Hoffman Et Al
```

**What to look for:**
- First access = Cache MISS (loads from disk)
- Next accesses = Cache HIT (loads from memory)
- Cache size tracking: "(cache size: 5/50)"
- Maximum 50 files cached in memory

### 4. Verify Smart Duplicate Detection
Try importing the same LAS file twice:

**Step 1:** Import a LAS file
- Result: "Success - Well created successfully"

**Step 2:** Import the SAME LAS file again
- Result: "Dataset Already Available - All X curves already exist"

**Step 3:** Import LAS with some new curves + some duplicates
- Result: "Curves Merged - Merged X new curves (skipped Y duplicate curves)"

**What to look for in logs:**
```bash
[LAS Import] New dataset contains 12 curves: ['GR', 'RHOB', 'NPHI', ...]
[LAS Import] Found better match: dataset 'MAIN' with 12 common curves (100.0% overlap)
[LAS Import] Best matching dataset: 'MAIN' with 100.0% overlap
[LAS Import] Skipping duplicate - all curves already exist
```

### 5. Verify Server Startup Indexing
Restart the server and watch startup logs:
```bash
============================================================
[STARTUP] Initializing File-Based Well Storage...
============================================================
[FileWellStorage] Indexing .ptrc files in /home/runner/workspace/petrophysics-workplace...
[FileWellStorage] Indexed 21 well files.
  - dfgdfgdf::#13-31 Hoffman Et Al -> /path/to/file.ptrc
  - dfgdfgdf::#21D-14 Rozet -> /path/to/file.ptrc
[STARTUP] Well file indexing complete. App is ready.
```

**What to look for:**
- Server scans for all `.ptrc` files at startup
- Creates index of file paths
- Does NOT load file contents (only paths)
- Shows count of indexed files
