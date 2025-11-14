"""
File-based Well Storage Service for Petrophysics Workspace
Uses .ptrc (JSON) files with in-memory cache for eager/lazy loading
SQLite is NOT used for well data - only for other data types
"""

import json
import glob
import os
import asyncio
import threading
from collections import OrderedDict
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path


# Global index to store file paths (loaded during startup)
GLOBAL_FILE_INDEX: Dict[str, str] = {}

# Project-aware in-memory cache with metadata
# Structure: {cache_key: {"data": well_dict, "source": "preload|lazy", "project": project_name}}
IN_MEMORY_CACHE: OrderedDict[str, Dict[str, Any]] = OrderedDict()

# Track which projects have been preloaded
PRELOADED_PROJECTS: set = set()

# Active project (protected from eviction)
ACTIVE_PROJECT: Optional[str] = None

# Cache size limit (soft limit - preloaded projects can exceed this)
# Lazy-loaded wells are evicted when cache exceeds this limit
MAX_CACHE_SIZE = 200
LAZY_CACHE_SIZE = 50  # Max lazy-loaded wells before eviction

# Thread lock for cache operations to prevent race conditions
CACHE_LOCK = threading.Lock()


class FileWellStorageService:
    """
    File-based storage service for well data using .ptrc files.
    Features:
    - File indexing at startup
    - In-memory LRU cache for performance
    - Lazy loading of files
    - Automatic cache eviction
    """
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.file_index = GLOBAL_FILE_INDEX
        self.cache = IN_MEMORY_CACHE
        
    def index_well_files(self):
        """
        Index all .ptrc files in the workspace at startup.
        Stores file paths in GLOBAL_FILE_INDEX without loading content.
        """
        print(f"[FileWellStorage] Indexing .ptrc files in {self.workspace_root}...")
        
        # Find all .ptrc files in the workspace
        pattern = str(self.workspace_root / "**" / "*.ptrc")
        file_paths = glob.glob(pattern, recursive=True)
        
        for path in file_paths:
            # Create a unique key from project and well name
            # Example: "project/10-WELLS/well1.ptrc" -> "project::well1"
            rel_path = Path(path).relative_to(self.workspace_root)
            parts = rel_path.parts
            
            # Find the project folder (parent of 10-WELLS)
            if "10-WELLS" in parts:
                wells_index = parts.index("10-WELLS")
                project_name = parts[wells_index - 1] if wells_index > 0 else "unknown"
                well_filename = parts[-1].replace('.ptrc', '')
                
                # Key format: "project_name::well_name"
                file_key = f"{project_name}::{well_filename}"
                self.file_index[file_key] = path
        
        print(f"[FileWellStorage] Indexed {len(self.file_index)} well files.")
        
        # Print first few entries for debugging
        if self.file_index:
            sample_keys = list(self.file_index.keys())[:3]
            for key in sample_keys:
                print(f"  - {key} -> {self.file_index[key]}")
    
    def get_file_key(self, project_path: str, well_id: str) -> str:
        """Generate file key from project path and well ID"""
        project_name = os.path.basename(os.path.normpath(project_path))
        return f"{project_name}::{well_id}"
    
    def get_cached_well_data(self, project_path: str, well_id: str) -> Optional[Dict[str, Any]]:
        """
        Get well data from cache only (NO disk access).
        Thread-safe implementation for concurrent access.
        
        Args:
            project_path: Path to the project directory
            well_id: Well identifier (filename without extension)
            
        Returns:
            Well data dictionary from cache or None if not cached
        """
        file_key = self.get_file_key(project_path, well_id)
        
        with CACHE_LOCK:
            if file_key in self.cache:
                cache_entry = self.cache[file_key]
                source = cache_entry.get("source", "unknown")
                print(f"[FileWellStorage] Cache HIT for {file_key} (served from memory, {source})")
                # Move to end to mark as most recently used (LRU logic)
                self.cache.move_to_end(file_key)
                return cache_entry["data"]
        
        print(f"[FileWellStorage] Cache MISS for {file_key} (cache-only mode)")
        return None
    
    def load_well_data(self, project_path: str, well_id: str) -> Optional[Dict[str, Any]]:
        """
        Load well data with project-aware caching (eager or lazy).
        Thread-safe implementation for concurrent access.
        
        Args:
            project_path: Path to the project directory
            well_id: Well identifier (filename without extension)
            
        Returns:
            Well data dictionary or None if not found
        """
        file_key = self.get_file_key(project_path, well_id)
        project_name = os.path.basename(os.path.normpath(project_path))
        
        # --- 1. Check Cache (Hit) - Thread-safe ---
        with CACHE_LOCK:
            if file_key in self.cache:
                cache_entry = self.cache[file_key]
                source = cache_entry.get("source", "unknown")
                print(f"[FileWellStorage] Cache HIT for {file_key} (served from memory, {source})")
                # Move to end to mark as most recently used (LRU logic)
                self.cache.move_to_end(file_key)
                return cache_entry["data"]
        
        # --- 2. Load Lazily (Miss) ---
        print(f"[FileWellStorage] Cache MISS for {file_key}, loading from disk...")
        
        # Check if file exists in index (read-only, no lock needed)
        if file_key not in self.file_index:
            print(f"[FileWellStorage] File not found in index: {file_key}")
            return None
        
        file_path = self.file_index[file_key]
        
        # Load the file (I/O outside lock to avoid blocking other requests)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[FileWellStorage] Error loading {file_path}: {e}")
            return None
        
        # --- 3. Update Cache & Smart Eviction (Thread-safe) ---
        with CACHE_LOCK:
            # Double-check cache after acquiring lock (another thread might have loaded it)
            if file_key in self.cache:
                print(f"[FileWellStorage] Another thread already cached {file_key}")
                return self.cache[file_key]["data"]
            
            # Count lazy-loaded entries
            lazy_count = sum(1 for entry in self.cache.values() if entry.get("source") == "lazy")
            
            # Evict if too many lazy entries (protect preloaded/active project entries)
            if lazy_count >= LAZY_CACHE_SIZE:
                # Find and evict oldest lazy entry
                for key in list(self.cache.keys()):
                    entry = self.cache[key]
                    if entry.get("source") == "lazy" and entry.get("project") != ACTIVE_PROJECT:
                        del self.cache[key]
                        print(f"[FileWellStorage] Evicting lazy entry: {key}")
                        break
            
            # Add newly loaded data to cache with metadata
            self.cache[file_key] = {
                "data": data,
                "source": "lazy",
                "project": project_name
            }
            print(f"[FileWellStorage] Cached: {file_key} (cache size: {len(self.cache)}, lazy: {lazy_count + 1})")
        
        return data
    
    def save_well_data(self, well_data: Dict[str, Any], project_path: str) -> bool:
        """
        Save well data to .ptrc file and update cache.
        
        Args:
            well_data: Well data dictionary (must contain 'name' field)
            project_path: Path to the project directory
            
        Returns:
            True if successful, False otherwise
        """
        try:
            well_name = well_data.get("name")
            if not well_name:
                print("[FileWellStorage] Error: well data missing 'name' field")
                return False
            
            # Ensure 10-WELLS directory exists
            wells_dir = os.path.join(project_path, "10-WELLS")
            os.makedirs(wells_dir, exist_ok=True)
            
            # Write to .ptrc file
            file_path = os.path.join(wells_dir, f"{well_name}.ptrc")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(well_data, f, indent=2)
            
            print(f"[FileWellStorage] Saved well to {file_path}")
            
            # Update cache
            file_key = self.get_file_key(project_path, well_name)
            
            # Update index if this is a new file
            if file_key not in self.file_index:
                self.file_index[file_key] = file_path
            
            # Update cache (or add if not present)
            project_name = os.path.basename(os.path.normpath(project_path))
            
            if file_key in self.cache:
                # Move to end since it was just modified
                self.cache.move_to_end(file_key)
                # Update the data but keep existing source metadata
                self.cache[file_key]["data"] = well_data
            else:
                # Need to add to cache
                if len(self.cache) >= MAX_CACHE_SIZE:
                    # Need to evict oldest
                    oldest_key, _ = self.cache.popitem(last=False)
                    print(f"[FileWellStorage] Cache full. Evicting: {oldest_key}")
                
                self.cache[file_key] = {
                    "data": well_data,
                    "source": "saved",
                    "project": project_name
                }
            
            return True
            
        except Exception as e:
            print(f"[FileWellStorage] Error saving well data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def list_wells_in_project(self, project_path: str) -> List[str]:
        """
        List all well files in a project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            List of well IDs (filenames without extension)
        """
        project_name = os.path.basename(os.path.normpath(project_path))
        wells = []
        
        # Search index for wells in this project
        for key in self.file_index.keys():
            if key.startswith(f"{project_name}::"):
                well_id = key.split("::", 1)[1]
                wells.append(well_id)
        
        # Also check filesystem directly (in case index is stale)
        wells_dir = os.path.join(project_path, "10-WELLS")
        if os.path.exists(wells_dir):
            for filename in os.listdir(wells_dir):
                if filename.endswith('.ptrc'):
                    well_id = filename.replace('.ptrc', '')
                    if well_id not in wells:
                        wells.append(well_id)
        
        return sorted(wells)
    
    def delete_well(self, project_path: str, well_id: str) -> bool:
        """
        Delete a well file and remove from cache/index.
        
        Args:
            project_path: Path to the project directory
            well_id: Well identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_key = self.get_file_key(project_path, well_id)
            
            # Remove from cache
            if file_key in self.cache:
                del self.cache[file_key]
                print(f"[FileWellStorage] Removed {file_key} from cache")
            
            # Get file path and delete file
            if file_key in self.file_index:
                file_path = self.file_index[file_key]
                del self.file_index[file_key]
            else:
                file_path = os.path.join(project_path, "10-WELLS", f"{well_id}.ptrc")
            
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[FileWellStorage] Deleted well file: {file_path}")
                return True
            else:
                print(f"[FileWellStorage] Well file not found: {file_path}")
                return False
                
        except Exception as e:
            print(f"[FileWellStorage] Error deleting well: {e}")
            return False
    
    async def preload_project(self, project_path: str, max_concurrent: int = 10) -> Dict[str, Any]:
        """
        EAGER LOADING: Preload all wells from a project into memory at startup.
        
        Uses asyncio.to_thread to prevent blocking the event loop during file I/O.
        
        Args:
            project_path: Path to the project directory
            max_concurrent: Maximum concurrent file loads (default: 10)
            
        Returns:
            Dictionary with preload statistics
        """
        project_name = os.path.basename(os.path.normpath(project_path))
        
        # Check if already preloaded
        if project_name in PRELOADED_PROJECTS:
            print(f"[FileWellStorage] Project '{project_name}' already preloaded, skipping...")
            return {
                "project": project_name,
                "already_loaded": True,
                "total_wells": 0,
                "loaded_wells": 0,
                "failed_wells": []
            }
        
        print(f"[FileWellStorage] EAGER LOADING: Preloading all wells for project '{project_name}'...")
        
        # Find all wells for this project
        wells_to_load = []
        for key, file_path in self.file_index.items():
            if key.startswith(f"{project_name}::"):
                wells_to_load.append((key, file_path))
        
        if not wells_to_load:
            print(f"[FileWellStorage] No wells found for project '{project_name}'")
            PRELOADED_PROJECTS.add(project_name)
            return {
                "project": project_name,
                "total_wells": 0,
                "loaded_wells": 0,
                "failed_wells": []
            }
        
        # Use semaphore to limit concurrent I/O operations
        semaphore = asyncio.Semaphore(max_concurrent)
        loaded_count = 0
        failed_wells = []
        
        async def load_well_async(file_key: str, file_path: str) -> Tuple[str, bool, Optional[Dict]]:
            """Load a single well file asynchronously"""
            async with semaphore:
                try:
                    # Use asyncio.to_thread to run blocking I/O in thread pool
                    data = await asyncio.to_thread(self._load_well_file_sync, file_path)
                    return (file_key, True, data)
                except Exception as e:
                    print(f"[FileWellStorage] Failed to preload {file_key}: {e}")
                    return (file_key, False, None)
        
        # Load all wells concurrently
        tasks = [load_well_async(key, path) for key, path in wells_to_load]
        results = await asyncio.gather(*tasks)
        
        # Process results and update cache
        # NO EVICTION during preload - allow cache to grow for active project
        for file_key, success, data in results:
            if success and data:
                self.cache[file_key] = {
                    "data": data,
                    "source": "preload",
                    "project": project_name
                }
                loaded_count += 1
            else:
                failed_wells.append(file_key)
        
        # Mark project as preloaded and active
        PRELOADED_PROJECTS.add(project_name)
        global ACTIVE_PROJECT
        ACTIVE_PROJECT = project_name
        
        print(f"[FileWellStorage] Preloaded {loaded_count}/{len(wells_to_load)} wells for project '{project_name}'")
        print(f"[FileWellStorage] Cache now contains {len(self.cache)} wells (active project protected)")
        
        return {
            "project": project_name,
            "total_wells": len(wells_to_load),
            "loaded_wells": loaded_count,
            "failed_wells": failed_wells
        }
    
    def _load_well_file_sync(self, file_path: str) -> Dict[str, Any]:
        """
        Synchronous file loading helper for asyncio.to_thread.
        Reads and parses JSON from disk.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def clear_project_cache(self, project_path: str) -> int:
        """
        Clear all cached wells for a specific project.
        Useful when switching projects.
        
        Returns:
            Number of cache entries cleared
        """
        project_name = os.path.basename(os.path.normpath(project_path))
        keys_to_remove = [
            key for key in self.cache.keys()
            if self.cache[key].get("project") == project_name
        ]
        
        for key in keys_to_remove:
            del self.cache[key]
        
        # Remove from preloaded set
        PRELOADED_PROJECTS.discard(project_name)
        
        print(f"[FileWellStorage] Cleared {len(keys_to_remove)} wells from cache for project '{project_name}'")
        return len(keys_to_remove)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        return {
            "cache_size": len(self.cache),
            "max_cache_size": MAX_CACHE_SIZE,
            "indexed_files": len(self.file_index),
            "cached_wells": list(self.cache.keys()),
            "preloaded_projects": list(PRELOADED_PROJECTS)
        }


# Global instance (will be initialized at startup)
file_well_storage: Optional[FileWellStorageService] = None


def get_file_well_storage() -> FileWellStorageService:
    """Get the global file well storage instance"""
    if file_well_storage is None:
        raise RuntimeError("FileWellStorageService not initialized. Call initialize_file_well_storage() first.")
    return file_well_storage


def initialize_file_well_storage(workspace_root: str):
    """Initialize the global file well storage service"""
    global file_well_storage
    file_well_storage = FileWellStorageService(workspace_root)
    file_well_storage.index_well_files()
    return file_well_storage
