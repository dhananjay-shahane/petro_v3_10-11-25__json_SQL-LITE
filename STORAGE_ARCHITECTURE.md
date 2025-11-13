# Storage Architecture & Recent Changes

## Table of Contents
1. [Files Changed in This Task](#files-changed-in-this-task)
2. [Storage Architecture Overview](#storage-architecture-overview)
3. [Recent Changes Summary](#recent-changes-summary)
4. [File-Based Storage for Wells](#file-based-storage-for-wells)
5. [Smart Duplicate Detection](#smart-duplicate-detection)
6. [Code Organization Changes](#code-organization-changes)
7. [How to Verify Features](#how-to-verify-features)

---

## Files Changed in This Task

### Overview
This task involved implementing smart duplicate detection for LAS imports and reorganizing code for better maintainability.

### Complete List of Modified Files

#### 1. `backend/utils/data_import_export.py`
**Status**: ✅ MODIFIED (Main Changes)

**Lines Changed**: 43-393 (added `create_well_from_las()` function - 357 lines)

**What Changed**:
- Added `create_well_from_las()` function (moved from `las_file_io.py`)
- Implements smart duplicate detection logic
- Compares curve names to find best matching dataset
- Handles three scenarios: skip duplicate, merge curves, create new dataset
- Added import: `from utils.las_file_io import get_well_name_from_las, read_las_file`

**How It Works**:
```python
# Smart duplicate detection algorithm:
1. Extract curve names from new LAS file
2. Compare with existing datasets in well
3. Find dataset with highest overlap ratio (≥50% required)
4. If 100% overlap → skip import (all curves exist)
5. If 50-99% overlap → merge only new curves
6. If <50% overlap → create new dataset with versioning
```

**How to Check**:
```bash
# Import same LAS file twice - should show duplicate message
# Watch server logs for:
[LAS Import] New dataset contains 12 curves: ['GR', 'RHOB', ...]
[LAS Import] Found better match: dataset 'MAIN' with 100.0% overlap
[LAS Import] Skipping duplicate - all curves already exist
```

---

#### 2. `frontend/src/components/dialogs/NewWellDialog.tsx`
**Status**: ✅ MODIFIED (UI Changes)

**Lines Changed**: 164-185 (added duplicate detection UI messages)

**What Changed**:
- Added conditional toast messages based on duplicate detection result
- Three message types:
  1. "Dataset Already Available" - when all curves exist
  2. "Curves Merged" - when some curves are new
  3. "Success" - when new dataset is created
- Shows counts of new vs duplicate curves

**How It Works**:
```typescript
if (result.skipped_duplicate) {
  // Show "Dataset Already Available" message
} else if (result.dataset_merged) {
  // Show "Curves Merged" with counts
} else {
  // Show "Success" message
}
```

**How to Check**:
```bash
# Import LAS file in UI
# Should see one of three messages:
✓ "Dataset Already Available - All 12 curves already exist"
✓ "Curves Merged - Merged 5 new curves (skipped 7 duplicates)"
✓ "Success - Well created successfully"
```

---

#### 3. `backend/utils/las_file_io.py`
**Status**: ✅ MODIFIED (Removed Code)

**Lines Removed**: 357 lines (removed `create_well_from_las()` function)

**What Changed**:
- Removed `create_well_from_las()` function (moved to `data_import_export.py`)
- Kept only helper functions:
  - `get_well_name_from_las()` - Extract well name from LAS metadata
  - `read_las_file()` - Basic LAS file reading

**Why**:
- Better code organization
- Low-level parsing helpers remain in `las_file_io.py`
- Import/export logic consolidated in `data_import_export.py`

**How to Check**:
```bash
# Check file only contains helper functions
grep -n "def create_well_from_las" backend/utils/las_file_io.py
# Should return no results (function removed)
```

---

#### 4. `backend/utils/cli_service.py`
**Status**: ✅ MODIFIED (Import Change)

**Lines Changed**: Updated import statement

**What Changed**:
```python
# OLD:
from utils.las_file_io import create_well_from_las

# NEW:
from utils.data_import_export import create_well_from_las
```

**Why**:
- Follow new code organization
- Import from correct location after function move

**How to Check**:
```bash
# Check import statement
grep "from utils.data_import_export import create_well_from_las" backend/utils/cli_service.py
# Should return the import line
```

---

### Files NOT Changed (Verification)

These files use file-based storage and were implemented in previous tasks:

✅ `backend/utils/file_well_storage.py` - LRU cache implementation (unchanged)  
✅ `backend/main.py` - Server startup with file indexing (unchanged)  
✅ `backend/routers/wells.py` - Wells API endpoints (unchanged)

---

### Quick Verification Checklist

Run these commands to verify all changes:

```bash
# 1. Check data_import_export.py has create_well_from_las
grep -n "def create_well_from_las" backend/utils/data_import_export.py
# Expected: Line number showing function exists

# 2. Check las_file_io.py does NOT have create_well_from_las
grep -n "def create_well_from_las" backend/utils/las_file_io.py
# Expected: No output (function removed)

# 3. Check cli_service.py imports from correct location
grep "from utils.data_import_export import create_well_from_las" backend/utils/cli_service.py
# Expected: Line showing correct import

# 4. Check NewWellDialog has duplicate detection UI
grep -A 5 "skipped_duplicate" frontend/src/components/dialogs/NewWellDialog.tsx
# Expected: Code showing toast message for duplicates

# 5. Restart server and check for file indexing logs
# Expected logs:
[STARTUP] Initializing File-Based Well Storage...
[FileWellStorage] Indexing .ptrc files...
[FileWellStorage] Indexed 21 well files.
```

---

## Storage Architecture Overview

### Storage Rules

**✅ WELL FILES - File-Based Storage (NO SQLite)**
- **Format**: JSON files with `.ptrc` extension (NOT `.json`)
- **Location**: `{project}/10-WELLS/{well_name}.ptrc`
- **Why**: Well files can be 100MB+ and benefit from lazy loading and LRU caching
- **Database**: NO SQLite used for well data

**✅ OTHER DATA - SQLite Database**
- **Database**: `data/petrophysics.db`
- **Used For**: Sessions, layouts, window configs, user settings, CLI history
- **Why**: Small, frequently accessed metadata benefits from SQLite's indexing

### Storage Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Petrophysics Application                  │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
        ┌───────▼────────┐      ┌──────▼──────────┐
        │  Well Data     │      │  Other Data     │
        │  (.ptrc files) │      │  (SQLite DB)    │
        └───────┬────────┘      └──────┬──────────┘
                │                      │
    ┌───────────┴────────┐             │
    │ File-Based Storage │             │
    │ with LRU Cache     │             │
    └────────────────────┘             │
                                       │
                        ┌──────────────▼──────────────┐
                        │ SQLite: petrophysics.db     │
                        │ - Sessions                  │
                        │ - Layouts                   │
                        │ - Settings                  │
                        │ - CLI History               │
                        └─────────────────────────────┘
```

---

## Recent Changes Summary

### Changes Made: November 13, 2025

#### 1. Smart Duplicate Detection for LAS Imports
**What Changed**: Added intelligent duplicate detection when importing LAS files

**Files Modified**:
- `backend/utils/data_import_export.py` (lines 43-393)
- `frontend/src/components/dialogs/NewWellDialog.tsx` (lines 164-185)

**How It Works**: System compares actual log curves (not just dataset names) to detect duplicates and intelligently merges only new data.

#### 2. Code Reorganization
**What Changed**: Moved LAS import logic to better location

**Files Modified**:
- `backend/utils/data_import_export.py` - Now contains `create_well_from_las()`
- `backend/utils/las_file_io.py` - Now only contains helper functions
- `backend/utils/cli_service.py` - Updated imports

**Rationale**: Centralize all import/export logic in `data_import_export.py`

---

## File-Based Storage for Wells

### How It Works

#### 1. Server Startup - File Indexing
When the FastAPI server starts, it indexes all `.ptrc` files:

```python
# backend/main.py - Lifespan Event
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("[STARTUP] Initializing File-Based Well Storage...")
    print("=" * 60)
    
    # Initialize file-based well storage
    file_well_storage.index_well_files()
    
    print("[STARTUP] Well file indexing complete. App is ready.")
    yield
```

**What happens**:
- Scans all `.ptrc` files in workspace
- Creates index of file paths: `{project}::{well_name}` → `/path/to/file.ptrc`
- Does NOT load file contents (only paths)
- Takes < 1 second even with hundreds of wells

**Example Log Output**:
```
============================================================
[STARTUP] Initializing File-Based Well Storage...
============================================================
[FileWellStorage] Indexing .ptrc files in /home/runner/workspace/petrophysics-workplace...
[FileWellStorage] Indexed 21 well files.
  - dfgdfgdf::#13-31 Hoffman Et Al -> /path/to/file.ptrc
  - dfgdfgdf::#21D-14 Rozet -> /path/to/file.ptrc
[STARTUP] Well file indexing complete. App is ready.
```

#### 2. Lazy Loading - Load on Demand

Wells are loaded only when requested (not at startup):

```python
# backend/utils/file_well_storage.py
def load_well(self, project_name: str, well_name: str) -> Optional[Well]:
    cache_key = f"{project_name}::{well_name}"
    
    # Check cache first
    if cache_key in self.well_cache:
        print(f"[FileWellStorage] Cache HIT for {cache_key}")
        # Move to end (most recently used)
        self.well_cache.move_to_end(cache_key)
        return self.well_cache[cache_key]
    
    # Cache MISS - load from disk
    print(f"[FileWellStorage] Cache MISS for {cache_key}, loading from disk...")
    well = Well.deserialize(filepath=file_path)
    
    # Add to cache
    self.well_cache[cache_key] = well
    print(f"[FileWellStorage] Cached: {cache_key} (cache size: {len(self.well_cache)}/50)")
    
    return well
```

**Example Log Output**:
```
[FileWellStorage] Cache MISS for dfgdfgdf::#13-31 Hoffman Et Al, loading from disk...
[FileWellStorage] Cached: dfgdfgdf::#13-31 Hoffman Et Al (cache size: 1/50)
```

#### 3. LRU Cache - In-Memory Performance

**Cache Implementation**: `OrderedDict` (Python built-in)
- **Max Size**: 50 wells
- **Eviction**: Least Recently Used (LRU)
- **Thread-Safe**: Uses thread lock for concurrent access

```python
# backend/utils/file_well_storage.py
class FileWellStorageService:
    def __init__(self, workspace_root: str, cache_size: int = 50):
        self.workspace_root = workspace_root
        self.cache_size = cache_size
        self.well_cache = OrderedDict()  # LRU cache
        self.file_index = {}  # {project::well_name: file_path}
        self.lock = threading.Lock()
```

**How LRU Works**:
1. **Cache HIT**: File already in memory → instant access, moves to end of OrderedDict
2. **Cache MISS**: File not in memory → load from disk, add to cache
3. **Cache FULL**: If cache has 50 items → remove oldest (first in OrderedDict)

**Example Log Output**:
```
# First access - loads from disk
[FileWellStorage] Cache MISS for dfgdfgdf::#13-31 Hoffman Et Al, loading from disk...
[FileWellStorage] Cached: dfgdfgdf::#13-31 Hoffman Et Al (cache size: 1/50)

# Second access - loads from memory
[FileWellStorage] Cache HIT for dfgdfgdf::#13-31 Hoffman Et Al
```

#### 4. File Format - .ptrc Files

**File Extension**: `.ptrc` (NOT `.json`)
**Content**: JSON format
**Location**: `{project}/10-WELLS/{well_name}.ptrc`

**Example File Structure**:
```json
{
  "date_created": "2025-11-13T10:30:00",
  "well_name": "#13-31 Hoffman Et Al",
  "well_type": "Dev",
  "datasets": [
    {
      "name": "MAIN",
      "type": "Cont",
      "well_logs": [
        {
          "name": "GR",
          "unit": "API",
          "data": [45.2, 46.1, 47.3, ...]
        },
        {
          "name": "RHOB",
          "unit": "g/cc",
          "data": [2.45, 2.46, 2.47, ...]
        }
      ]
    }
  ]
}
```

---

## Smart Duplicate Detection

### Overview
When importing LAS files, the system intelligently detects if curves already exist and handles three scenarios.

### Implementation Location
**File**: `backend/utils/data_import_export.py`
**Function**: `create_well_from_las()` (lines 43-393)

### How It Works

#### Step 1: Extract Curve Names from New Dataset
```python
# Get curve names from the new dataset
new_curve_names = set(log.name for log in dataset.well_logs)
print(f"[LAS Import] New dataset contains {len(new_curve_names)} curves: {list(new_curve_names)}")
```

#### Step 2: Find Best Matching Dataset
```python
# Find the BEST matching dataset by checking curves (highest overlap ratio)
matching_dataset = None
best_overlap_ratio = 0

for existing_dataset in well.datasets:
    existing_curve_names = set(log.name for log in existing_dataset.well_logs)
    
    # Calculate curve overlap
    common_curves = new_curve_names.intersection(existing_curve_names)
    unique_new_curves = new_curve_names - existing_curve_names
    
    # Calculate overlap ratio
    overlap_ratio = len(common_curves) / len(new_curve_names)
    
    # Require at least 50% overlap to consider it a match
    if overlap_ratio >= 0.5 and overlap_ratio > best_overlap_ratio:
        best_overlap_ratio = overlap_ratio
        matching_dataset = existing_dataset
```

**Key Points**:
- Compares **curve names** (GR, RHOB, NPHI), not dataset names
- Requires ≥50% overlap to consider a match
- Selects dataset with **highest** overlap ratio (not first match)

#### Step 3: Handle Three Scenarios

**Scenario 1: All Curves Exist (100% overlap)**
```python
if len(new_curves_added) == 0:
    # Skip import - show informative message
    return {
        'skipped_duplicate': True,
        'duplicate_curves': duplicate_curves,
        'new_curves_added': []
    }
```
**Frontend Message**: "Dataset Already Available - All 12 curves already exist"

**Scenario 2: Some Curves New (50-99% overlap)**
```python
else:
    # Merge only new curves
    for log in dataset.well_logs:
        if log.name in new_curves_added:
            matching_dataset.well_logs.append(log)
    
    return {
        'dataset_merged': True,
        'new_curves_added': new_curves_added,
        'duplicate_curves': duplicate_curves
    }
```
**Frontend Message**: "Curves Merged - Merged 5 new curves (skipped 7 duplicate curves)"

**Scenario 3: No Match Found (<50% overlap)**
```python
# Create new dataset with versioning
if dataset_name in existing_names:
    version = 1
    while f"{dataset_name}_{version}" in existing_names:
        version += 1
    dataset_name = f"{dataset_name}_{version}"

well.datasets.append(dataset)
```
**Frontend Message**: "Success - Well created successfully"
**Dataset Names**: MAIN, MAIN_1, MAIN_2, etc.

### Frontend UI Implementation

**File**: `frontend/src/components/dialogs/NewWellDialog.tsx`
**Lines**: 164-185

```typescript
// Show appropriate message based on duplicate detection result
if (result.skipped_duplicate) {
  // All curves already exist
  toast({
    title: "Dataset Already Available",
    description: `All ${result.duplicate_curves?.length || 0} curves already exist`
  });
} else if (result.dataset_merged) {
  // Some curves were new and merged
  const newCount = result.new_curves_added?.length || 0;
  const dupCount = result.duplicate_curves?.length || 0;
  toast({
    title: "Curves Merged",
    description: `Merged ${newCount} new curves (skipped ${dupCount} duplicates)`
  });
} else {
  // New dataset created
  toast({
    title: "Success",
    description: `Well "${result.well.name}" created successfully`
  });
}
```

---

## Code Organization Changes

### What Changed

#### Before (Old Structure)
```
backend/utils/las_file_io.py
├── get_well_name_from_las()     [Helper function]
├── read_las_file()              [Helper function]
└── create_well_from_las()       [Main import logic - 357 lines]

backend/utils/data_import_export.py
├── export_well_to_las()
└── [Other export functions]

backend/utils/cli_service.py
└── Imports from las_file_io.py
```

#### After (New Structure)
```
backend/utils/las_file_io.py
├── get_well_name_from_las()     [Helper function]
└── read_las_file()              [Helper function]

backend/utils/data_import_export.py
├── create_well_from_las()       [Main import logic - MOVED HERE]
├── export_well_to_las()
└── [Other import/export functions]

backend/utils/cli_service.py
└── Imports from data_import_export.py
```

### Why This Change?

**Rationale**:
1. **Better Organization**: `data_import_export.py` is the natural home for import/export operations
2. **Single Responsibility**: `las_file_io.py` now only contains low-level LAS parsing helpers
3. **Easier Maintenance**: All import logic centralized in one place
4. **Reusability**: Helper functions remain separate and can be used by other modules

### Files Modified

#### 1. `backend/utils/data_import_export.py`
**Changes**:
- Added `create_well_from_las()` function (357 lines)
- Added import: `from utils.las_file_io import get_well_name_from_las, read_las_file`

#### 2. `backend/utils/las_file_io.py`
**Changes**:
- Removed `create_well_from_las()` function
- Kept only helper functions:
  - `get_well_name_from_las()` - Extract well name from LAS metadata
  - `read_las_file()` - Basic LAS file reading

#### 3. `backend/utils/cli_service.py`
**Changes**:
- Updated import: `from utils.data_import_export import create_well_from_las`
- Previously imported from: `utils.las_file_io`

---

## How to Verify Features

### 1. Verify File-Based Storage (.ptrc files)

**Check files exist**:
```bash
# List all well files
ls petrophysics-workplace/*/10-WELLS/*.ptrc

# View file content
cat "petrophysics-workplace/dfgdfgdf/10-WELLS/#13-31 Hoffman Et Al.ptrc" | head -n 20
```

**✅ What to look for**:
- Files have `.ptrc` extension (NOT `.db` or `.sql`)
- Files are in `{project}/10-WELLS/` directory
- Each file contains valid JSON with well data
- NO SQLite database files for wells

### 2. Verify Lazy Loading

**Watch server logs** when accessing wells:

```bash
# Look for these log messages:
[FileWellStorage] Cache MISS for dfgdfgdf::#13-31 Hoffman Et Al, loading from disk...
[FileWellStorage] Cached: dfgdfgdf::#13-31 Hoffman Et Al (cache size: 1/50)
```

**✅ What to look for**:
- First access shows "Cache MISS" → file loaded from disk
- File is NOT loaded at server startup (only indexed)
- Only loaded when requested (lazy loading)
- Subsequent accesses show "Cache HIT"

### 3. Verify LRU Caching

**Test**: Access the same well multiple times

**First Access**:
```
[FileWellStorage] Cache MISS for dfgdfgdf::#13-31 Hoffman Et Al, loading from disk...
[FileWellStorage] Cached: dfgdfgdf::#13-31 Hoffman Et Al (cache size: 1/50)
```

**Second Access**:
```
[FileWellStorage] Cache HIT for dfgdfgdf::#13-31 Hoffman Et Al
```

**✅ What to look for**:
- First access = Cache MISS (loads from disk)
- Next accesses = Cache HIT (loads from memory)
- Cache size tracking: "(cache size: 5/50)"
- Maximum 50 files cached in memory
- Oldest files evicted when cache is full

### 4. Verify Smart Duplicate Detection

**Test Steps**:

**Step 1**: Import a LAS file
```
Result: "Success - Well created successfully"
```

**Step 2**: Import the SAME LAS file again
```
Result: "Dataset Already Available - All 12 curves already exist"
```

**Step 3**: Import LAS with some new curves + some duplicates
```
Result: "Curves Merged - Merged 5 new curves (skipped 7 duplicates)"
```

**Server Logs to Look For**:
```bash
[LAS Import] New dataset contains 12 curves: ['GR', 'RHOB', 'NPHI', ...]
[LAS Import] Found better match: dataset 'MAIN' with 12 common curves (100.0% overlap)
[LAS Import] Best matching dataset: 'MAIN' with 100.0% overlap
[LAS Import] Skipping duplicate - all curves already exist
```

**✅ What to look for**:
- System compares curve names (not dataset names)
- Finds dataset with highest overlap ratio
- Shows informative messages for all three scenarios
- Only merges new curves, skips duplicates

### 5. Verify Server Startup Indexing

**Restart the server** and watch startup logs:

```bash
============================================================
[STARTUP] Initializing File-Based Well Storage...
============================================================
[FileWellStorage] Indexing .ptrc files in /home/runner/workspace/petrophysics-workplace...
[FileWellStorage] Indexed 21 well files.
  - dfgdfgdf::#13-31 Hoffman Et Al -> /home/runner/workspace/petrophysics-workplace/dfgdfgdf/10-WELLS/#13-31 Hoffman Et Al.ptrc
  - dfgdfgdf::#21D-14 Rozet -> /home/runner/workspace/petrophysics-workplace/dfgdfgdf/10-WELLS/#21D-14 Rozet Minnelusa Unit.ptrc
[STARTUP] Well file indexing complete. App is ready.
```

**✅ What to look for**:
- Server scans for all `.ptrc` files at startup
- Creates index of file paths (key → path mapping)
- Does NOT load file contents (only paths)
- Shows count of indexed files
- Fast startup (< 1 second even with hundreds of wells)

---

## Summary

### Storage Architecture
- **Well Files**: File-based storage with `.ptrc` JSON files (NO SQLite)
- **Other Data**: SQLite database for sessions, layouts, settings
- **Performance**: LRU cache (50 files) + lazy loading for efficiency

### Recent Changes
1. **Smart Duplicate Detection**: Intelligent curve-based comparison and merging
2. **Code Reorganization**: Centralized import/export logic in `data_import_export.py`
3. **Better User Experience**: Clear messages for all duplicate detection scenarios

### Key Benefits
- ✅ **Fast Startup**: Index files only, don't load contents
- ✅ **Low Memory**: Cache only 50 most recently used wells
- ✅ **Scalability**: Handles hundreds of wells efficiently
- ✅ **No Duplicates**: Smart detection prevents redundant data
- ✅ **Clear Feedback**: Users know exactly what happened during import
