# Database Schema Updates Summary

## Overview
This document summarizes all database schema updates and API changes made to support font sizes in layouts and improve layout data retrieval.

## Database Schema Changes

### 1. Wells Table
**New Columns Added:**
- `total_wells` (INTEGER) - To track total number of wells
- `selected_dataset` (TEXT) - To store selected dataset information, ensuring only selected data is shown (not all log data)

### 2. Session Wells Table
**New Columns Added:**
- `selected_dataset` (TEXT) - For session-based selected dataset tracking

### 3. Projects Table
**Verified Columns:**
- `active_well` (TEXT) - Already existed, now properly utilized for storing the active well

### 4. Layouts Table
**New Columns Added:**
- `font_sizes` (TEXT) - Stores font size settings as JSON

**Example font_sizes data:**
```json
{
  "fontSizes": {
    "dataBrowser": 10,
    "wellList": 10,
    "feedbackLog": 10,
    "zonationList": 10,
    "cliTerminal": 10
  }
}
```

### 5. Legacy Tables Removed
- ✅ Dropped `project_wells_legacy` table
- ℹ️ `well_legacy` table didn't exist (already cleaned up)

## API Changes

### 1. Layout Save Request Model (`LayoutSaveRequest`)
**New Field:**
- `fontSizes: Optional[dict]` - Optional font size configuration

### 2. Layout Response Model (`LayoutResponse`)
**New Field:**
- `fontSizes: Optional[dict]` - Returns font size configuration with layout

### 3. Storage Service Updates (`SQLiteStorageService`)

#### `save_layout()` method:
- **New parameter:** `font_sizes: dict = None`
- **Path normalization:** Added `os.path.normpath()` to ensure consistent session IDs
- **Improved logging:** Shows normalized path and session ID for debugging
- **Database:** Saves font_sizes to the `font_sizes` column

#### `load_layout()` method:
- **Path normalization:** Added `os.path.normpath()` to match save behavior
- **Improved logging:** Shows normalized path and session ID for debugging
- **Backward compatibility:** Handles missing font_sizes gracefully with empty dict default
- **Returns:** Includes `fontSizes` field in response

### 4. Workspace Router Updates

#### GET `/api/workspace/layout`
- **Returns:** Now includes `fontSizes` field in response
- **Backward compatible:** Returns empty dict `{}` if no font sizes saved

#### POST `/api/workspace/layout`
- **Accepts:** Optional `fontSizes` field in request body
- **Saves:** Font sizes to database
- **Returns:** Saved font sizes in response

## Key Improvements

### 1. Path Normalization
**Problem:** Layout data not being retrieved due to inconsistent project path formats
**Solution:** 
- Both `save_layout()` and `load_layout()` now normalize paths using `os.path.normpath()`
- Converts backslashes to forward slashes for cross-platform compatibility
- Ensures consistent session ID generation

**Example:**
```python
# Before: Different paths could produce different session IDs
"/home/runner/workspace/project" vs "\\home\\runner\\workspace\\project"

# After: Both normalize to the same format
normalized_path = os.path.normpath(project_path).replace('\\', '/')
```

### 2. Enhanced Logging
**Added diagnostic logging:**
- Shows normalized project path
- Shows first 12 characters of session ID
- Helps debug layout retrieval issues

**Example log output:**
```
[STORAGE] Saving layout 'default' for project: /home/runner/workspace/project (session: project_35ee...)
[STORAGE] Loading layout 'default' for project: /home/runner/workspace/project (session: project_35ee...)
```

### 3. Backward Compatibility
- Existing layouts without `font_sizes` work correctly (returns empty dict)
- All optional fields have proper defaults
- No breaking changes to existing API contracts

## Migration

### Running the Migration
```bash
cd backend
python utils/migrate_schema_updates.py
```

### Migration Script Location
`backend/utils/migrate_schema_updates.py`

## Testing

### 1. Test Font Size Save/Load
```bash
# POST to save layout with font sizes
curl -X POST http://localhost:5001/api/workspace/layout \
  -H "Content-Type: application/json" \
  -d '{
    "projectPath": "/path/to/project",
    "layout": {...},
    "visiblePanels": [...],
    "fontSizes": {
      "dataBrowser": 12,
      "wellList": 10
    }
  }'

# GET to retrieve layout with font sizes
curl http://localhost:5001/api/workspace/layout?projectPath=/path/to/project&layoutName=default
```

### 2. Test Layout Retrieval
- Open a project
- Verify layout is automatically loaded
- Check browser console logs for: "Auto-loaded saved layout 'default' from storage"

## Files Modified

1. `backend/models.py` - Added fontSizes to request/response models
2. `backend/utils/sqlite_storage.py` - Updated save_layout and load_layout methods
3. `backend/routers/workspace.py` - Updated router to handle fontSizes
4. `backend/utils/migrate_schema_updates.py` - New migration script

## Next Steps

### Frontend Integration
To use font sizes on the frontend:
1. Send `fontSizes` when saving layout
2. Retrieve `fontSizes` from layout response
3. Apply font sizes to respective UI components

**Example:**
```typescript
// Save layout with font sizes
const response = await axios.post('/api/workspace/layout', {
  projectPath: currentProject,
  layout: layoutData,
  visiblePanels: panels,
  fontSizes: {
    dataBrowser: 10,
    wellList: 10,
    feedbackLog: 10,
    zonationList: 10,
    cliTerminal: 10
  }
});

// Load and apply font sizes
const layoutResponse = await axios.get('/api/workspace/layout', {
  params: { projectPath: currentProject }
});
const fontSizes = layoutResponse.data.fontSizes || {};
// Apply fontSizes to components...
```

## Troubleshooting

### Layout Not Loading
1. Check server logs for session ID
2. Verify project path is being normalized consistently
3. Check database directly:
```sql
SELECT session_id, layout_name, font_sizes FROM layouts;
```

### Font Sizes Not Persisting
1. Verify frontend is sending fontSizes in POST request
2. Check server logs for "saved with font sizes"
3. Query database to confirm data saved
