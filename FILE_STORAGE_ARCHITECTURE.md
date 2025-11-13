# File-Based Storage Architecture for Well Data

**Purpose**: This document explains how well data is stored using file-based .ptrc JSON files (NO SQLite) with in-memory LRU caching and lazy loading.

---

## Storage Rules

### Critical Constraint: NO SQLite for Well Files

**RULE**: Well data MUST be stored as individual JSON files with `.ptrc` extension. SQLite is PROHIBITED for well data.

**Why This Rule Exists**:

1. **Large File Sizes**: Well files can be 100MB+ with thousands of log curves and data points
2. **Lazy Loading**: File-based storage allows loading wells only when needed (not all at startup)
3. **Memory Efficiency**: LRU cache keeps only recently used wells in memory (50 max)
4. **Streaming-Friendly**: Large files can be read/written without loading entire database into memory
5. **Backup & Version Control**: Individual files are easier to backup, diff, and restore

**File Format Specification**:
- **Extension**: `.ptrc` (NOT `.json` or `.db`)
- **Format**: JSON
- **Location**: `{project}/10-WELLS/{well_name}.ptrc`
- **Content**: Well metadata, datasets, logs, constants

**Example File**:
```
petrophysics-workplace/
└── MyProject/
    └── 10-WELLS/
        ├── Well-001.ptrc    ← Individual JSON file
        ├── Well-002.ptrc    ← Individual JSON file
        └── Well-003.ptrc    ← Individual JSON file
```

---

### Storage Comparison Table

| Data Type | Storage Method | Why |
|-----------|---------------|-----|
| **Well Data** | `.ptrc` JSON files (NO SQLite) | Large files (100MB+), lazy loading, LRU cache |
| **Sessions** | SQLite `petrophysics.db` | Small metadata, frequent queries |
| **Layouts** | SQLite `petrophysics.db` | Small metadata, indexing needed |
| **Settings** | SQLite `petrophysics.db` | Small metadata, relational queries |
| **CLI History** | SQLite `petrophysics.db` | Small metadata, search/filter needed |

**Key Principle**: 
- **Large, infrequently accessed data** → File-based storage
- **Small, frequently queried metadata** → SQLite database

---

## Implementation Mechanics

### 1. Startup: File Indexing

When the FastAPI server starts, it indexes all `.ptrc` files WITHOUT loading their contents.

**File**: `backend/main.py`  
**Hook**: FastAPI lifespan event

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[STARTUP] Initializing File-Based Well Storage...")
    
    # Index all .ptrc files (does NOT load file contents)
    file_well_storage.index_well_files()
    
    print("[STARTUP] Well file indexing complete. App is ready.")
    yield
```

**What Happens**:
1. Scans workspace directory for all `.ptrc` files
2. Creates index: `{project}::{well_name}` → `/path/to/file.ptrc`
3. Stores index in memory (dictionary)
4. Does NOT load file contents (only file paths)
5. Fast startup (< 1 second even with hundreds of wells)

**Log Output**:
```
============================================================
[STARTUP] Initializing File-Based Well Storage...
============================================================
[FileWellStorage] Indexing .ptrc files in /workspace/petrophysics-workplace...
[FileWellStorage] Indexed 21 well files.
  - project1::Well-A -> /path/to/Well-A.ptrc
  - project1::Well-B -> /path/to/Well-B.ptrc
[STARTUP] Well file indexing complete. App is ready.
```

---

### 2. Runtime: Lazy Loading

Wells are loaded from disk ONLY when requested (not at startup).

**File**: `backend/utils/file_well_storage.py`  
**Class**: `FileWellStorageService`  
**Method**: `load_well(project_name, well_name)`

```python
def load_well(self, project_name: str, well_name: str) -> Optional[Well]:
    cache_key = f"{project_name}::{well_name}"
    
    # Check cache first (in-memory)
    if cache_key in self.well_cache:
        print(f"[FileWellStorage] Cache HIT for {cache_key}")
        self.well_cache.move_to_end(cache_key)  # Mark as recently used
        return self.well_cache[cache_key]
    
    # Cache MISS - load from disk
    print(f"[FileWellStorage] Cache MISS for {cache_key}, loading from disk...")
    file_path = self.file_index.get(cache_key)
    well = Well.deserialize(filepath=file_path)
    
    # Add to cache
    self._add_to_cache(cache_key, well)
    
    return well
```

**What Happens**:
1. User requests well data (e.g., clicks on well in UI)
2. System checks if well is in cache (memory)
3. **Cache HIT**: Return well from memory (instant)
4. **Cache MISS**: Load well from disk, add to cache

**Log Output**:
```
# First access (Cache MISS)
[FileWellStorage] Cache MISS for MyProject::Well-001, loading from disk...
[FileWellStorage] Cached: MyProject::Well-001 (cache size: 1/50)

# Second access (Cache HIT)
[FileWellStorage] Cache HIT for MyProject::Well-001
```

---

### 3. Performance: LRU Cache

In-memory cache stores up to 50 recently used wells for fast access.

**Implementation**: Python `OrderedDict` (built-in LRU)

**File**: `backend/utils/file_well_storage.py`

```python
class FileWellStorageService:
    def __init__(self, workspace_root: str, cache_size: int = 50):
        self.workspace_root = workspace_root
        self.cache_size = cache_size  # Maximum 50 wells in memory
        self.well_cache = OrderedDict()  # LRU cache
        self.file_index = {}  # {project::well_name: file_path}
        self.lock = threading.Lock()  # Thread safety
```

**How LRU Works**:

1. **Cache HIT**: Well already in memory
   - Move well to end of OrderedDict (mark as recently used)
   - Return well instantly (no disk I/O)

2. **Cache MISS**: Well not in memory
   - Load well from disk
   - Add to cache (end of OrderedDict)
   - If cache is full (50 items), remove oldest (first in OrderedDict)

3. **Cache Eviction**: Automatic when cache reaches limit
   - Removes least recently used well (first item)
   - Frees memory for new well

**Cache Size Tracking**:
```
[FileWellStorage] Cached: MyProject::Well-001 (cache size: 1/50)
[FileWellStorage] Cached: MyProject::Well-002 (cache size: 2/50)
...
[FileWellStorage] Cached: MyProject::Well-050 (cache size: 50/50)
[FileWellStorage] Cache full, evicting oldest: MyProject::Well-001
[FileWellStorage] Cached: MyProject::Well-051 (cache size: 50/50)
```

**Performance Benefits**:
- **Fast Access**: Cache hits are instant (no disk I/O)
- **Low Memory**: Only 50 wells in memory (not all wells)
- **Automatic Management**: LRU eviction handles memory limits
- **Thread-Safe**: Lock prevents race conditions

---

## Files Changed for Storage Architecture

### Core Implementation Files

#### 1. `backend/utils/file_well_storage.py`
**Status**: Created (Main implementation)

**What It Does**:
- Implements `FileWellStorageService` class
- File indexing at startup
- Lazy loading from disk
- LRU cache management (OrderedDict)
- Thread-safe operations (lock)

**Key Methods**:
```python
def index_well_files(self):
    # Scans .ptrc files and builds index

def load_well(self, project_name, well_name):
    # Lazy loads well with LRU caching

def save_well(self, project_name, well):
    # Saves well to .ptrc file and updates cache

def _add_to_cache(self, cache_key, well):
    # Adds well to LRU cache, evicts oldest if full
```

---

#### 2. `backend/main.py`
**Status**: Modified (Added startup hook)

**What Changed**:
- Added FastAPI lifespan context manager
- Calls `file_well_storage.index_well_files()` at startup
- Initializes file indexing before app starts serving requests

**Code Added**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[STARTUP] Initializing File-Based Well Storage...")
    file_well_storage.index_well_files()
    print("[STARTUP] Well file indexing complete. App is ready.")
    yield
    # Cleanup on shutdown (if needed)

app = FastAPI(lifespan=lifespan)
```

---

#### 3. `backend/routers/wells.py`
**Status**: Modified (Uses file storage)

**What Changed**:
- Replaced SQLite queries with file storage calls
- Uses `file_well_storage.load_well()` to load wells
- Uses `file_well_storage.save_well()` to save wells

**Example**:
```python
# OLD (SQLite)
well = db.query(Well).filter_by(name=well_name).first()

# NEW (File-based)
well = file_well_storage.load_well(project_name, well_name)
```

---

### Files NOT Changed (SQLite Still Used)

These files continue to use SQLite for non-well data:

✅ `backend/utils/sqlite_storage.py` - Sessions, layouts, settings  
✅ `backend/routers/workspace.py` - Workspace metadata  
✅ `data/petrophysics.db` - SQLite database for metadata  

**Why**: Small metadata benefits from SQLite's indexing and query capabilities.

---

## How to Verify Storage Architecture

### Verification Checklist

#### ✅ 1. Check .ptrc Files Exist

**Command**:
```bash
ls petrophysics-workplace/*/10-WELLS/*.ptrc
```

**Expected Output**:
```
petrophysics-workplace/MyProject/10-WELLS/Well-001.ptrc
petrophysics-workplace/MyProject/10-WELLS/Well-002.ptrc
petrophysics-workplace/MyProject/10-WELLS/Well-003.ptrc
```

**Verify**:
- ✅ Files have `.ptrc` extension (NOT `.db` or `.sql`)
- ✅ Files are in `{project}/10-WELLS/` directory
- ✅ Files are JSON format

**Check File Content**:
```bash
cat "petrophysics-workplace/MyProject/10-WELLS/Well-001.ptrc" | head -20
```

**Expected**: Valid JSON with well data

---

#### ✅ 2. Verify Server Startup Indexing

**Action**: Restart the server and watch logs

**Expected Logs**:
```
============================================================
[STARTUP] Initializing File-Based Well Storage...
============================================================
[FileWellStorage] Indexing .ptrc files in /workspace/petrophysics-workplace...
[FileWellStorage] Indexed 21 well files.
  - MyProject::Well-001 -> /path/to/Well-001.ptrc
  - MyProject::Well-002 -> /path/to/Well-002.ptrc
[STARTUP] Well file indexing complete. App is ready.
```

**Verify**:
- ✅ Server scans for `.ptrc` files at startup
- ✅ Creates file index (project::well → path)
- ✅ Does NOT load file contents (only paths)
- ✅ Fast startup (< 1 second)

---

#### ✅ 3. Verify Lazy Loading

**Action**: Access a well in the UI or API

**Expected Logs (First Access)**:
```
[FileWellStorage] Cache MISS for MyProject::Well-001, loading from disk...
[FileWellStorage] Cached: MyProject::Well-001 (cache size: 1/50)
```

**Verify**:
- ✅ "Cache MISS" on first access → file loaded from disk
- ✅ File is NOT loaded at server startup
- ✅ Only loaded when requested (lazy loading)

---

#### ✅ 4. Verify LRU Caching

**Action**: Access the same well multiple times

**Expected Logs**:
```
# First access
[FileWellStorage] Cache MISS for MyProject::Well-001, loading from disk...
[FileWellStorage] Cached: MyProject::Well-001 (cache size: 1/50)

# Second access (immediate)
[FileWellStorage] Cache HIT for MyProject::Well-001

# Third access
[FileWellStorage] Cache HIT for MyProject::Well-001
```

**Verify**:
- ✅ First access = Cache MISS (loads from disk)
- ✅ Subsequent accesses = Cache HIT (loads from memory)
- ✅ Cache size tracking: "(cache size: X/50)"
- ✅ Maximum 50 wells in memory

---

#### ✅ 5. Verify NO SQLite for Wells

**Command**:
```bash
# Check SQLite database does NOT contain well data
sqlite3 data/petrophysics.db "SELECT name FROM sqlite_master WHERE type='table';" 2>/dev/null
```

**Expected Output** (should NOT include wells table):
```
sessions
layouts
settings
cli_history
```

**Verify**:
- ✅ No `wells` table in SQLite
- ✅ No `datasets` table in SQLite
- ✅ No `well_logs` table in SQLite
- ✅ Only metadata tables (sessions, layouts, settings)

---

#### ✅ 6. Verify Cache Performance

**Action**: Monitor server logs during normal usage

**Look For**:
```
[FileWellStorage] Cache HIT for MyProject::Well-001
[FileWellStorage] Cache HIT for MyProject::Well-002
[FileWellStorage] Cache MISS for MyProject::Well-055, loading from disk...
```

**Metrics**:
- **High Cache Hit Rate**: Most accesses should be cache hits
- **Low Cache Miss Rate**: Only first access should miss
- **Cache Size Tracking**: Monitor "(cache size: X/50)"

---

## Quick Reference

### Storage Rules Summary

| Rule | Description |
|------|-------------|
| **NO SQLite for Wells** | Wells MUST use .ptrc JSON files |
| **File Extension** | `.ptrc` (NOT `.json` or `.db`) |
| **File Location** | `{project}/10-WELLS/{well_name}.ptrc` |
| **SQLite for Metadata** | Sessions, layouts, settings use SQLite |
| **Lazy Loading** | Wells loaded on-demand, not at startup |
| **LRU Cache** | 50 wells max in memory, automatic eviction |

---

### Log Signatures

**Startup Indexing**:
```
[STARTUP] Initializing File-Based Well Storage...
[FileWellStorage] Indexing .ptrc files in /workspace/...
[FileWellStorage] Indexed N well files.
```

**Lazy Loading**:
```
[FileWellStorage] Cache MISS for project::well, loading from disk...
[FileWellStorage] Cached: project::well (cache size: X/50)
```

**LRU Caching**:
```
[FileWellStorage] Cache HIT for project::well
```

**Cache Eviction** (when full):
```
[FileWellStorage] Cache full, evicting oldest: project::well
```

---

### File Structure

```
petrophysics-workplace/
├── Project-A/
│   └── 10-WELLS/
│       ├── Well-001.ptrc    ← File-based storage
│       ├── Well-002.ptrc    ← Individual JSON files
│       └── Well-003.ptrc    ← NO SQLite for wells
└── Project-B/
    └── 10-WELLS/
        ├── Well-004.ptrc
        └── Well-005.ptrc

data/
└── petrophysics.db    ← SQLite for metadata ONLY
                         (sessions, layouts, settings)
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────┐
│         FastAPI Application                 │
└─────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
┌───────▼───────┐      ┌────────▼────────┐
│  Well Data    │      │  Metadata       │
│  (Large)      │      │  (Small)        │
└───────┬───────┘      └────────┬────────┘
        │                       │
┌───────▼───────────────┐       │
│ File-Based Storage    │       │
│ .ptrc JSON files      │       │
│                       │       │
│ Features:             │       │
│ ✓ Lazy Loading        │       │
│ ✓ LRU Cache (50 max)  │       │
│ ✓ Startup Indexing    │       │
│ ✓ Thread-Safe         │       │
└───────────────────────┘       │
                                │
                    ┌───────────▼──────────┐
                    │ SQLite Database      │
                    │ petrophysics.db      │
                    │                      │
                    │ Tables:              │
                    │ • sessions           │
                    │ • layouts            │
                    │ • settings           │
                    │ • cli_history        │
                    └──────────────────────┘
```

---

## Summary

**Storage Architecture**:
- **Well Data**: File-based `.ptrc` JSON files (NO SQLite)
- **Metadata**: SQLite database for sessions, layouts, settings
- **Performance**: LRU cache (50 files) + lazy loading

**Key Benefits**:
- ✅ **Fast Startup**: Index files only, don't load contents
- ✅ **Low Memory**: Cache only 50 most recently used wells
- ✅ **Scalability**: Handles hundreds of wells efficiently
- ✅ **Simplicity**: Individual files are easy to backup and manage
- ✅ **Separation**: Clear boundary between well data and metadata

**Critical Constraints**:
- ❌ **NO SQLite for wells** - only .ptrc files
- ✅ **Lazy loading** - wells loaded on-demand
- ✅ **LRU caching** - automatic memory management
- ✅ **Startup indexing** - fast file discovery

---

**Last Updated**: November 13, 2025
