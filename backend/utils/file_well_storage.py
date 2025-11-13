"""
File-based Well Storage Service for Petrophysics Workspace
Uses .ptrc (JSON) files with in-memory LRU cache for efficient lazy loading
SQLite is NOT used for well data - only for other data types
"""

import json
import glob
import os
from collections import OrderedDict
from typing import Dict, Any, Optional, List
from pathlib import Path


# Global index to store file paths (loaded during startup)
GLOBAL_FILE_INDEX: Dict[str, str] = {}

# Simple in-memory LRU cache (loaded on-demand during requests)
IN_MEMORY_CACHE: OrderedDict[str, Any] = OrderedDict()

# Cache size limit (store up to 50 well files in memory)
MAX_CACHE_SIZE = 50


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
    
    def load_well_data(self, project_path: str, well_id: str) -> Optional[Dict[str, Any]]:
        """
        Load well data with LRU caching and lazy loading.
        
        Args:
            project_path: Path to the project directory
            well_id: Well identifier (filename without extension)
            
        Returns:
            Well data dictionary or None if not found
        """
        file_key = self.get_file_key(project_path, well_id)
        
        # --- 1. Check Cache (Hit) ---
        if file_key in self.cache:
            print(f"[FileWellStorage] Cache HIT for {file_key}")
            # Move to end to mark as most recently used (LRU logic)
            self.cache.move_to_end(file_key)
            return self.cache[file_key]
        
        # --- 2. Load Lazily (Miss) ---
        print(f"[FileWellStorage] Cache MISS for {file_key}, loading from disk...")
        
        # Check if file exists in index
        if file_key not in self.file_index:
            # Fallback: try direct path construction
            well_file = os.path.join(project_path, "10-WELLS", f"{well_id}.ptrc")
            if not os.path.exists(well_file):
                print(f"[FileWellStorage] File not found: {file_key}")
                return None
            file_path = well_file
        else:
            file_path = self.file_index[file_key]
        
        # Load the file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[FileWellStorage] Error loading {file_path}: {e}")
            return None
        
        # --- 3. Update Cache & Evict Oldest ---
        
        # Check if cache is full
        if len(self.cache) >= MAX_CACHE_SIZE:
            # Pop the oldest item (first item in OrderedDict)
            oldest_key, _ = self.cache.popitem(last=False)
            print(f"[FileWellStorage] Cache full. Evicting oldest entry: {oldest_key}")
        
        # Add newly loaded data to cache
        self.cache[file_key] = data
        print(f"[FileWellStorage] Cached: {file_key} (cache size: {len(self.cache)}/{MAX_CACHE_SIZE})")
        
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
            if file_key in self.cache:
                # Move to end since it was just modified
                self.cache.move_to_end(file_key)
            
            # Always update the cached data
            if len(self.cache) >= MAX_CACHE_SIZE and file_key not in self.cache:
                # Need to evict oldest
                oldest_key, _ = self.cache.popitem(last=False)
                print(f"[FileWellStorage] Cache full. Evicting: {oldest_key}")
            
            self.cache[file_key] = well_data
            
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
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        return {
            "cache_size": len(self.cache),
            "max_cache_size": MAX_CACHE_SIZE,
            "indexed_files": len(self.file_index),
            "cached_wells": list(self.cache.keys())
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
