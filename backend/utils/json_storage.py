import json
import uuid
import hashlib
import threading
from typing import Dict, Optional, Any, List, Union
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal


DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_FILE = DATA_DIR / "application_setting.json"

_lock = threading.Lock()


def serialize_value(value: Any) -> Any:
    """
    Serialize Python values to JSON-compatible format.
    Handles: strings, lists, dicts, numbers, dates, decimals
    
    Args:
        value: Any Python value to serialize
        
    Returns:
        JSON-compatible value
    """
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, (datetime, )):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, list):
        return [serialize_value(item) for item in value]
    elif isinstance(value, dict):
        return {key: serialize_value(val) for key, val in value.items()}
    elif isinstance(value, tuple):
        return [serialize_value(item) for item in value]
    elif isinstance(value, set):
        return list(value)
    else:
        return str(value)


def deserialize_value(value: Any, value_type: Optional[str] = None) -> Any:
    """
    Deserialize JSON value to Python types.
    
    Args:
        value: JSON value to deserialize
        value_type: Optional type hint ('datetime', 'decimal', etc.)
        
    Returns:
        Python value
    """
    if value is None:
        return None
    
    if value_type == 'datetime' and isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return value
    elif value_type == 'decimal' and isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return value
    elif isinstance(value, list):
        return [deserialize_value(item, value_type) for item in value]
    elif isinstance(value, dict):
        return {key: deserialize_value(val, value_type) for key, val in value.items()}
    else:
        return value


def _ensure_data_dir():
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(exist_ok=True)


def _get_safe_key(key_type: str, identifier: str) -> str:
    """
    Generate a safe, namespaced key to prevent cross-project data leakage.
    
    Args:
        key_type: Type of key (e.g., 'layout', 'session', 'selected_wells')
        identifier: Project path or session ID
    
    Returns:
        Namespaced key with hash component for security
    """
    hash_component = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"petro:{key_type}:{hash_component}:{identifier}"


def _generate_session_id(project_path: str) -> str:
    """
    Generate a consistent session ID from a project path.
    
    Args:
        project_path: Full path to the project
    
    Returns:
        Session ID in format 'project_<hash>'
    """
    if not project_path:
        return f"project_{uuid.uuid4().hex[:32]}"
    hash_val = hashlib.md5(project_path.encode()).hexdigest()
    return f"project_{hash_val}"


def _load_data() -> Dict[str, Any]:
    """
    Load application data with camelCase schema structure.
    
    SCHEMA STRUCTURE (camelCase):
    {
      "appInfo": {
        "version": "2.0.0",
        "name": "Petrophysics Workspace",
        "lastUpdated": "2025-11-05T12:00:00+00:00"
      },
      "workspace": {
        "root": "/workspace/path",
        "currentProject": {
          "sessionId": "project_abc123",
          "path": "/project/path",
          "name": "Project Name",
          "openedAt": "2025-11-05T12:00:00+00:00"
        }
      },
      "projects": {
        "session_id": {
          "projectPath": "/project/path",
          "activeWell": "Well Name",
          "layout": {
            "windows": [{"id": "cliWindow", "type": "cli"}],
            "activeWindowId": "cliWindow",
            "links": ["cliWindow"],
            "unlinks": []
          },
          "visiblePanels": ["wells", "cli"],
          "layoutSavedAt": "2025-11-05T12:00:00+00:00",
          "selectedWells": [],
          "cliHistory": ""
        }
      },
      "wells": {
        "session_id": {
          "projectPath": "/project/path",
          "projectName": "Project Name",
          "wells": {
            "Well Name": {
              "datasets": [{"selectedLogs": ["GR", "RHOB"]}],
              "totalLogs": 10,
              "lastAccessed": "2025-11-05T12:00:00+00:00"
            }
          },
          "updatedAt": "2025-11-05T12:00:00+00:00",
          "expiresAt": "2025-11-05T16:00:00+00:00"
        }
      }
    }
    """
    _ensure_data_dir()
    
    from datetime import timezone
    now_utc = datetime.now(timezone.utc).isoformat()
    
    clean_structure = {
        "appInfo": {
            "version": "2.0.0",
            "name": "Petrophysics Workspace",
            "lastUpdated": now_utc
        },
        "workspace": {
            "root": "/home/runner/workspace/petrophysics-workplace",
            "currentProject": None
        },
        "projects": {},
        "wells": {}
    }
    
    if not DATA_FILE.exists():
        return clean_structure
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            
            # Return data as-is if it already has camelCase keys
            if "appInfo" in data:
                return data
            
            # Migrate from old snake_case structure to camelCase
            migrated = {}
            
            # App info
            if "app_info" in data:
                old_app_info = data["app_info"]
                migrated["appInfo"] = {
                    "version": old_app_info.get("version", "2.0.0"),
                    "name": old_app_info.get("name", "Petrophysics Workspace"),
                    "lastUpdated": old_app_info.get("last_updated", now_utc)
                }
            else:
                migrated["appInfo"] = clean_structure["appInfo"]
            
            # Workspace
            if "workspace" in data:
                old_workspace = data["workspace"]
                old_current_project = old_workspace.get("current_project")
                
                if old_current_project:
                    migrated["workspace"] = {
                        "root": old_workspace.get("root", clean_structure["workspace"]["root"]),
                        "currentProject": {
                            "sessionId": _generate_session_id(old_current_project.get("path", "")),
                            "path": old_current_project.get("path"),
                            "name": old_current_project.get("name"),
                            "openedAt": old_current_project.get("opened_at", now_utc)
                        }
                    }
                else:
                    migrated["workspace"] = clean_structure["workspace"]
            else:
                migrated["workspace"] = clean_structure["workspace"]
            
            # Projects - convert keys to sessionIds and use camelCase
            migrated["projects"] = {}
            for project_path, project_data in data.get("projects", {}).items():
                session_id = _generate_session_id(project_path)
                migrated["projects"][session_id] = {
                    "projectPath": project_path,
                    "activeWell": project_data.get("active_well", ""),
                    "layout": project_data.get("layout", {}),
                    "visiblePanels": project_data.get("visible_panels", []),
                    "layoutSavedAt": project_data.get("layout_saved_at", now_utc),
                    "selectedWells": project_data.get("selected_wells", []),
                    "cliHistory": project_data.get("cli_history", "")
                }
            
            # Wells - ensure camelCase
            migrated["wells"] = {}
            for session_id, well_session in data.get("wells", {}).items():
                well_data = {
                    "projectPath": well_session.get("project_path", ""),
                    "projectName": well_session.get("project_name", ""),
                    "wells": {},
                    "updatedAt": well_session.get("updated_at", now_utc),
                    "expiresAt": well_session.get("expires_at", (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat())
                }
                
                # Convert well data to camelCase
                for well_name, well_info in well_session.get("wells", {}).items():
                    datasets = []
                    for dataset in well_info.get("datasets", []):
                        datasets.append({
                            "selectedLogs": dataset.get("selectedLogs", dataset.get("logs", []))
                        })
                    
                    well_data["wells"][well_name] = {
                        "datasets": datasets,
                        "totalLogs": well_info.get("total_logs", well_info.get("totalLogs", 0)),
                        "lastAccessed": well_info.get("last_accessed", well_info.get("lastAccessed", now_utc))
                    }
                
                migrated["wells"][session_id] = well_data
            
            return migrated
            
    except (json.JSONDecodeError, FileNotFoundError):
        return clean_structure


def _save_data(data: Dict[str, Any]):
    """
    Save data to the JSON file.
    Thread-safe saving with file locking.
    
    Args:
        data: Dictionary containing all data to save
    """
    _ensure_data_dir()
    
    # Write to temp file first, then rename for atomic operation
    temp_file = DATA_FILE.with_suffix('.tmp')
    
    with open(temp_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    # Atomic rename
    temp_file.replace(DATA_FILE)


def _clean_expired_sessions(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove expired well data from storage.
    
    Args:
        data: Data dictionary
    
    Returns:
        Cleaned data dictionary
    """
    from datetime import timezone
    now = datetime.now(timezone.utc)
    to_delete = []
    
    # Clean wells section
    for well_id, well_data in data.get("wells", {}).items():
        expires_at_str = well_data.get("expiresAt")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if now > expires_at:
                    to_delete.append(well_id)
            except (ValueError, TypeError):
                to_delete.append(well_id)
    
    for well_id in to_delete:
        del data["wells"][well_id]
    
    return data


class JsonStorageService:
    """Handles storing and retrieving project data in JSON files."""
    
    SESSION_EXPIRY_SECONDS = 14400  # 4 hours
    
    def generate_session_id(self) -> str:
        """Generates a unique session ID."""
        return str(uuid.uuid4())
    
    def store_session(self, session_id: str, session_data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None):
        """
        Store well metadata in camelCase structure.
        
        STRUCTURE PER WELL (camelCase):
        {
          "Well Name": {
            "datasets": [
              {
                "selectedLogs": ["GR", "RHOB", "NPHI"]
              }
            ],
            "totalLogs": 5,
            "lastAccessed": "2025-11-05T10:00:00+00:00"
          }
        }
        
        Args:
            session_id: Project identifier (e.g., "project_abc123")
            session_data: Well data dictionary
            metadata: Project metadata (path, name, etc.)
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            # Build clean well metadata
            clean_wells = {}
            for well_name, well_data in session_data.items():
                datasets = []
                all_logs = []
                
                # Extract dataset info
                if isinstance(well_data, dict) and "datasets" in well_data:
                    for ds in well_data["datasets"]:
                        if isinstance(ds, dict):
                            ds_logs = []
                            
                            # Get log names
                            if "well_logs" in ds:
                                for log in ds["well_logs"]:
                                    if isinstance(log, dict) and "name" in log:
                                        log_name = log["name"]
                                        ds_logs.append(log_name)
                                        if log_name not in all_logs:
                                            all_logs.append(log_name)
                            
                            # Add dataset with selectedLogs only (camelCase)
                            datasets.append({
                                "selectedLogs": ds_logs
                            })
                
                # Store clean well data (camelCase)
                clean_wells[well_name] = {
                    "datasets": datasets,
                    "totalLogs": len(all_logs),
                    "lastAccessed": now_utc
                }
            
            # Store in wells section (camelCase)
            if "wells" not in data:
                data["wells"] = {}
            
            data["wells"][session_id] = {
                "projectPath": metadata.get("project_path") if metadata else None,
                "projectName": metadata.get("project_name") if metadata else None,
                "wells": clean_wells,
                "updatedAt": now_utc,
                "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=self.SESSION_EXPIRY_SECONDS)).isoformat()
            }
            
            # Update appInfo lastUpdated
            data["appInfo"]["lastUpdated"] = now_utc
            
            # Clean expired entries
            data = _clean_expired_sessions(data)
            
            _save_data(data)
            print(f"  [STORAGE] Stored {len(clean_wells)} wells for project {session_id}")
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load well data for a project from clean storage.
        
        Returns:
            Dictionary with 'wells' key containing well data, or None if not found
        """
        with _lock:
            data = _load_data()
            data = _clean_expired_sessions(data)
            
            project_data = data.get("wells", {}).get(session_id)
            
            if not project_data:
                print(f"  [STORAGE] No session data found for {session_id}")
                return None
            
            # Check if expired
            expires_at_str = project_data.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if datetime.now() > expires_at:
                        del data["wells"][session_id]
                        _save_data(data)
                        print(f"  [STORAGE] Session {session_id} expired and removed")
                        return None
                except (ValueError, TypeError):
                    pass
            
            # Log retrieval
            well_count = len(project_data.get("wells", {}))
            print(f"  [STORAGE] Retrieved session data for {session_id}: {well_count} wells")
            
            # Return in expected format
            return {
                "wells": project_data.get("wells", {}),
                "metadata": {
                    "project_path": project_data.get("project_path"),
                    "project_name": project_data.get("project_name")
                }
            }
    
    def delete_session(self, session_id: str):
        """Remove project well data from storage."""
        with _lock:
            data = _load_data()
            
            if session_id in data.get("wells", {}):
                del data["wells"][session_id]
                _save_data(data)
                print(f"  [STORAGE] Deleted well data for {session_id}")
    
    def session_exists(self, session_id: str) -> bool:
        """Check if project well data exists."""
        with _lock:
            data = _load_data()
            data = _clean_expired_sessions(data)
            return session_id in data.get("wells", {})
    
    def extend_session(self, session_id: str):
        """Extend well data expiry by 4 hours."""
        with _lock:
            data = _load_data()
            
            if session_id in data.get("wells", {}):
                data["wells"][session_id]["expires_at"] = (
                    datetime.now() + timedelta(seconds=self.SESSION_EXPIRY_SECONDS)
                ).isoformat()
                _save_data(data)
                print(f"  [STORAGE] Extended expiry for {session_id}")
    
    def get_session_ttl(self, session_id: str) -> int:
        """Get time remaining before well data expires (seconds)."""
        with _lock:
            data = _load_data()
            
            project_data = data.get("wells", {}).get(session_id)
            if not project_data:
                return -2  # Doesn't exist
            
            expires_at_str = project_data.get("expires_at")
            if not expires_at_str:
                return -1  # No expiry
            
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                ttl = (expires_at - datetime.now()).total_seconds()
                return int(ttl) if ttl > 0 else -2
            except (ValueError, TypeError):
                return -2
    
    def save_layout(self, project_path: str, layout_data: dict, visible_panels: list, layout_name: str = "default", window_links: dict = None):
        """
        Save workspace layout for a specific project with named layouts and window link/unlink data.
        Ensures layout is saved in the correct schema format with windows, activeWindowId, links, and unlinks.
        
        Args:
            project_path: Project path to associate layout with
            layout_data: Layout configuration (rc-dock layout structure)
            visible_panels: List of visible panel IDs
            layout_name: Name of the layout (default: "default")
            window_links: Dictionary mapping window IDs to their linked windows
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            # Generate session ID for this project
            session_id = _generate_session_id(project_path)
            
            if session_id not in data["projects"]:
                data["projects"][session_id] = {
                    "projectPath": project_path,
                    "activeWell": "",
                    "selectedWells": [],
                    "cliHistory": "",
                    "savedLayouts": {}
                }
            
            # Ensure savedLayouts exists
            if "savedLayouts" not in data["projects"][session_id]:
                data["projects"][session_id]["savedLayouts"] = {}
            
            # Save the rc-dock layout and window link states
            data["projects"][session_id]["savedLayouts"][layout_name] = {
                "rcDockLayout": layout_data,  # Full rc-dock layout structure
                "visiblePanels": visible_panels,
                "windowLinks": window_links or {},  # Save window link/unlink states
                "savedAt": now_utc
            }
            
            # Also save to the old format for backward compatibility
            data["projects"][session_id]["layout"] = layout_data
            data["projects"][session_id]["visiblePanels"] = visible_panels
            data["projects"][session_id]["layoutSavedAt"] = now_utc
            
            # Update appInfo lastUpdated
            data["appInfo"]["lastUpdated"] = now_utc
            
            _save_data(data)
            print(f"  [STORAGE] Layout '{layout_name}' saved for project: {project_path} with {len(visible_panels)} panels")
    
    def load_layout(self, project_path: str, layout_name: str = "default") -> Optional[Dict[str, Any]]:
        """
        Load workspace layout for a specific project by name.
        Returns layout with rc-dock structure and window link states.
        
        Args:
            project_path: Project path
            layout_name: Name of the layout to load (default: "default")
        
        Returns:
            Dictionary with 'layout', 'visiblePanels', 'windowLinks', and 'savedAt' keys, or None if not found
        """
        with _lock:
            data = _load_data()
            
            # Generate session ID for this project
            session_id = _generate_session_id(project_path)
            
            project = data["projects"].get(session_id)
            if not project:
                print(f"  [STORAGE] No project found for: {project_path}")
                return None
            
            # Try to load named layout first
            saved_layouts = project.get("savedLayouts", {})
            if layout_name in saved_layouts:
                named_layout = saved_layouts[layout_name]
                print(f"  [STORAGE] Retrieved layout '{layout_name}' for project {project_path}")
                return {
                    "layout": named_layout.get("rcDockLayout"),
                    "visiblePanels": named_layout.get("visiblePanels", []),
                    "windowLinks": named_layout.get("windowLinks", {}),
                    "savedAt": named_layout.get("savedAt")
                }
            
            # Fall back to old format layout
            if "layout" in project:
                layout = project["layout"]
                print(f"  [STORAGE] Retrieved default layout for project {project_path}")
                return {
                    "layout": layout,
                    "visiblePanels": project.get("visiblePanels", []),
                    "windowLinks": {},
                    "savedAt": project.get("layoutSavedAt")
                }
            
            print(f"  [STORAGE] No layout found for project: {project_path}")
            return None
    
    def get_saved_layout_names(self, project_path: str) -> List[str]:
        """
        Get list of all saved layout names for a project.
        
        Args:
            project_path: Project path
            
        Returns:
            List of layout names
        """
        with _lock:
            data = _load_data()
            session_id = _generate_session_id(project_path)
            
            project = data["projects"].get(session_id)
            if not project:
                return []
            
            saved_layouts = project.get("savedLayouts", {})
            layout_names = list(saved_layouts.keys())
            
            print(f"  [STORAGE] Found {len(layout_names)} saved layouts for project {project_path}")
            return layout_names
    
    def delete_layout(self, project_path: str, layout_name: str = "default"):
        """
        Remove a specific saved layout for a project.
        
        Args:
            project_path: Project path
            layout_name: Name of the layout to delete (default: "default")
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            
            # Generate session ID for this project
            session_id = _generate_session_id(project_path)
            
            if session_id in data["projects"]:
                project = data["projects"][session_id]
                
                # If deleting a named layout, remove it from savedLayouts
                if layout_name and layout_name != "default":
                    saved_layouts = project.get("savedLayouts", {})
                    if layout_name in saved_layouts:
                        del saved_layouts[layout_name]
                        project["savedLayouts"] = saved_layouts
                        print(f"  [STORAGE] Named layout '{layout_name}' deleted for project: {project_path}")
                    else:
                        print(f"  [STORAGE] Layout '{layout_name}' not found for project: {project_path}")
                else:
                    # Delete default layout (old format)
                    project.pop("layout", None)
                    project.pop("visiblePanels", None)
                    project.pop("layoutSavedAt", None)
                    print(f"  [STORAGE] Default layout deleted for project: {project_path}")
                
                # Update appInfo lastUpdated
                data["appInfo"]["lastUpdated"] = datetime.now(timezone.utc).isoformat()
                
                # Remove project entry if it only has projectPath left
                if len(project) == 1 and "projectPath" in project:
                    del data["projects"][session_id]
                
                _save_data(data)
    
    def save_selected_wells(self, project_path: str, well_names: list):
        """
        Save selected wells for a project (used for filtering the wells list).
        
        Args:
            project_path: Project path
            well_names: List of selected well names
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            # Generate session ID for this project
            session_id = _generate_session_id(project_path)
            
            if session_id not in data["projects"]:
                data["projects"][session_id] = {
                    "projectPath": project_path,
                    "activeWell": "",
                    "cliHistory": ""
                }
            
            data["projects"][session_id]["selectedWells"] = well_names
            data["appInfo"]["lastUpdated"] = now_utc
            
            _save_data(data)
    
    def load_selected_wells(self, project_path: str) -> Optional[list]:
        """
        Load selected wells for a project (used for filtering the wells list).
        
        Returns:
            List of well names, or None if not found
        """
        with _lock:
            data = _load_data()
            session_id = _generate_session_id(project_path)
            
            project = data["projects"].get(session_id)
            if not project or "selectedWells" not in project:
                return None
            
            return project["selectedWells"]
    
    def save_active_well(self, project_path: str, well_name: str):
        """
        Save the active well for a project (for Data Browser display, doesn't filter list).
        
        Args:
            project_path: Project path
            well_name: Active well name
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            # Generate session ID for this project
            session_id = _generate_session_id(project_path)
            
            if session_id not in data["projects"]:
                data["projects"][session_id] = {
                    "projectPath": project_path,
                    "selectedWells": [],
                    "cliHistory": ""
                }
            
            data["projects"][session_id]["activeWell"] = well_name
            data["appInfo"]["lastUpdated"] = now_utc
            
            _save_data(data)
    
    def load_active_well(self, project_path: str) -> Optional[str]:
        """
        Load the active well for a project (for Data Browser display, doesn't filter list).
        
        Returns:
            Active well name, or None if not found
        """
        with _lock:
            data = _load_data()
            session_id = _generate_session_id(project_path)
            
            project = data["projects"].get(session_id)
            if not project or "activeWell" not in project:
                return None
            
            return project["activeWell"]
    
    def save_cli_history(self, project_path: str, history: str):
        """
        Save CLI command history for a project.
        
        Args:
            project_path: Project path
            history: Command history as a string
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            # Generate session ID for this project
            session_id = _generate_session_id(project_path)
            
            if session_id not in data["projects"]:
                data["projects"][session_id] = {
                    "projectPath": project_path,
                    "activeWell": "",
                    "selectedWells": []
                }
            
            data["projects"][session_id]["cliHistory"] = history  # Use camelCase key
            data["appInfo"]["lastUpdated"] = now_utc
            
            _save_data(data)
    
    def load_cli_history(self, project_path: str) -> Optional[str]:
        """
        Load CLI command history for a project.
        
        Returns:
            Command history string, or None if not found
        """
        with _lock:
            data = _load_data()
            
            # Generate session ID for this project
            session_id = _generate_session_id(project_path)
            
            project = data["projects"].get(session_id)
            if not project or "cliHistory" not in project:  # Use camelCase key
                return None
            
            return project["cliHistory"]
    
    def save_current_project(self, project_path: str, project_name: str):
        """
        Save the currently opened project information.
        
        Args:
            project_path: Absolute path to the project
            project_name: Name of the project
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            # Ensure workspace exists
            if "workspace" not in data:
                data["workspace"] = {
                    "root": "/home/runner/workspace/petrophysics-workplace",
                    "currentProject": None
                }
            
            # Generate session ID for this project
            session_id = _generate_session_id(project_path)
            
            # Save with camelCase keys
            data["workspace"]["currentProject"] = {
                "sessionId": session_id,
                "path": project_path,
                "name": project_name,
                "openedAt": now_utc
            }
            
            # Update appInfo lastUpdated
            data["appInfo"]["lastUpdated"] = now_utc
            
            _save_data(data)
            print(f"  [STORAGE] Current project set: {project_name} at {project_path}")
    
    def load_current_project(self) -> Optional[Dict[str, str]]:
        """
        Load the currently opened project information.
        
        Returns:
            Dictionary with 'projectPath', 'projectName', 'openedAt' or None if not set
        """
        with _lock:
            data = _load_data()
            workspace = data.get("workspace", {})
            current_project = workspace.get("currentProject")  # Use camelCase key
            
            if current_project:
                return {
                    "projectPath": current_project.get("path"),
                    "projectName": current_project.get("name"),
                    "openedAt": current_project.get("openedAt")  # Use camelCase key
                }
            return None
    
    def delete_current_project(self):
        """Remove the current project setting."""
        with _lock:
            from datetime import timezone
            data = _load_data()
            if "workspace" in data:
                data["workspace"]["currentProject"] = None  # Use camelCase key
                data["appInfo"]["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            _save_data(data)
            print(f"  [STORAGE] Current project cleared")
    
    def delete_all_project_data(self, project_path: str):
        """
        Delete all JSON data associated with a project.
        This includes: layout, selected wells, active well, CLI history, and sessions.
        
        Args:
            project_path: Project path to clean up
        """
        with _lock:
            data = _load_data()
            
            # Delete project data
            if project_path in data["projects"]:
                del data["projects"][project_path]
                print(f"  [STORAGE] Deleted project data for: {project_path}")
            
            # Delete current project if it matches
            current_project = data.get("current_project")
            if current_project and current_project.get("projectPath") == project_path:
                data["current_project"] = None
                print(f"  [STORAGE] Cleared current project: {project_path}")
            
            _save_data(data)
    
    def get_all_keys(self) -> List[str]:
        """
        Get all keys currently stored (for inspection purposes).
        
        Returns:
            List of key names
        """
        with _lock:
            data = _load_data()
            keys = []
            
            # Add session keys
            for session_id in data["sessions"].keys():
                keys.append(f"session:{session_id}")
            
            # Add project keys
            for project_path in data["projects"].keys():
                keys.append(f"project:{project_path}")
            
            # Add current project key
            if data.get("current_project"):
                keys.append("current_project")
            
            return keys
    
    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get storage statistics and information.
        
        Returns:
            Dictionary with storage statistics
        """
        with _lock:
            data = _load_data()
            
            total_sessions = len(data.get("sessions", {}))
            total_projects = len(data.get("projects", {}))
            
            file_size = 0
            if DATA_FILE.exists():
                file_size = DATA_FILE.stat().st_size
            
            return {
                "total_sessions": total_sessions,
                "total_projects": total_projects,
                "file_size_bytes": file_size,
                "file_size_kb": round(file_size / 1024, 2),
                "file_path": str(DATA_FILE),
                "current_project": data.get("current_project")
            }
    
    def clear_all_data(self):
        """DANGER: Clear all data from storage (use for testing/debugging only)"""
        with _lock:
            data = {
                "sessions": {},
                "projects": {},
                "current_project": None,
                "windows": {
                    "count": 0,
                    "active_window_id": None,
                    "window_ids": [],
                    "window_links": {}
                }
            }
            _save_data(data)
            print(f"  [STORAGE] All data cleared")
    
    def save_window_data(self, project_path: str, window_count: int, active_window_id: Optional[str], window_ids: List[str], window_links: Dict[str, Any]):
        """
        Save window management data for a specific project.
        
        Args:
            project_path: Project path
            window_count: Number of open windows
            active_window_id: ID of the currently active window
            window_ids: List of all window IDs
            window_links: Dictionary mapping window IDs to their link states
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            session_id = _generate_session_id(project_path)
            
            if session_id not in data["projects"]:
                data["projects"][session_id] = {
                    "projectPath": project_path,
                    "activeWell": "",
                    "selectedWells": [],
                    "cliHistory": ""
                }
            
            data["projects"][session_id]["windowState"] = {
                "count": window_count,
                "activeWindowId": active_window_id,
                "windowIds": window_ids,
                "windowLinks": window_links
            }
            
            data["appInfo"]["lastUpdated"] = now_utc
            
            _save_data(data)
            print(f"  [STORAGE] Window data saved for {project_path}: {window_count} windows, active: {active_window_id}")
    
    def load_window_data(self, project_path: str) -> Dict[str, Any]:
        """
        Load window management data for a specific project.
        
        Args:
            project_path: Project path
        
        Returns:
            Dictionary with window count, active window ID, window IDs, and window links
        """
        with _lock:
            data = _load_data()
            session_id = _generate_session_id(project_path)
            
            project = data["projects"].get(session_id)
            if not project or "windowState" not in project:
                return {
                    "count": 0,
                    "active_window_id": None,
                    "window_ids": [],
                    "window_links": {}
                }
            
            window_state = project["windowState"]
            return {
                "count": window_state.get("count", 0),
                "active_window_id": window_state.get("activeWindowId"),
                "window_ids": window_state.get("windowIds", []),
                "window_links": window_state.get("windowLinks", {})
            }
    
    def update_active_window(self, project_path: str, window_id: str):
        """
        Update the active window ID for a specific project.
        
        Args:
            project_path: Project path
            window_id: ID of the window to set as active
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            session_id = _generate_session_id(project_path)
            
            if session_id in data["projects"] and "windowState" in data["projects"][session_id]:
                data["projects"][session_id]["windowState"]["activeWindowId"] = window_id
                data["appInfo"]["lastUpdated"] = now_utc
                _save_data(data)
                print(f"  [STORAGE] Active window updated to: {window_id} for project {project_path}")
    
    def add_window(self, project_path: str, window_id: str):
        """
        Add a new window to the window list for a specific project.
        By default, links the new window to all existing windows.
        
        Args:
            project_path: Project path
            window_id: ID of the window to add
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            session_id = _generate_session_id(project_path)
            
            if session_id not in data["projects"]:
                data["projects"][session_id] = {
                    "projectPath": project_path,
                    "activeWell": "",
                    "selectedWells": [],
                    "cliHistory": ""
                }
            
            if "windowState" not in data["projects"][session_id]:
                data["projects"][session_id]["windowState"] = {
                    "count": 0,
                    "activeWindowId": None,
                    "windowIds": [],
                    "windowLinks": {}
                }
            
            window_state = data["projects"][session_id]["windowState"]
            
            if window_id not in window_state["windowIds"]:
                # Get all existing windows before adding the new one
                existing_windows = window_state["windowIds"].copy()
                
                # Add the new window
                window_state["windowIds"].append(window_id)
                window_state["count"] = len(window_state["windowIds"])
                
                # Link the new window to all existing windows (default behavior)
                if window_id not in window_state["windowLinks"]:
                    window_state["windowLinks"][window_id] = []
                
                for existing_window_id in existing_windows:
                    # Link new window to existing window
                    if existing_window_id not in window_state["windowLinks"][window_id]:
                        window_state["windowLinks"][window_id].append(existing_window_id)
                    
                    # Link existing window to new window (bidirectional)
                    if existing_window_id not in window_state["windowLinks"]:
                        window_state["windowLinks"][existing_window_id] = []
                    if window_id not in window_state["windowLinks"][existing_window_id]:
                        window_state["windowLinks"][existing_window_id].append(window_id)
                
                data["appInfo"]["lastUpdated"] = now_utc
                _save_data(data)
                print(f"  [STORAGE] Window added for {project_path}: {window_id}, total: {window_state['count']}, linked to {len(existing_windows)} windows")
    
    def remove_window(self, project_path: str, window_id: str):
        """
        Remove a window from the window list for a specific project.
        
        Args:
            project_path: Project path
            window_id: ID of the window to remove
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            session_id = _generate_session_id(project_path)
            
            if session_id in data["projects"] and "windowState" in data["projects"][session_id]:
                window_state = data["projects"][session_id]["windowState"]
                
                if window_id in window_state["windowIds"]:
                    window_state["windowIds"].remove(window_id)
                    window_state["count"] = len(window_state["windowIds"])
                    
                    # Clear active window if it was the removed window
                    if window_state["activeWindowId"] == window_id:
                        window_state["activeWindowId"] = None
                    
                    # Remove any link data for this window
                    if window_id in window_state["windowLinks"]:
                        del window_state["windowLinks"][window_id]
                    
                    data["appInfo"]["lastUpdated"] = now_utc
                    _save_data(data)
                    print(f"  [STORAGE] Window removed for {project_path}: {window_id}, total: {window_state['count']}")
    
    def link_windows(self, project_path: str, window_id1: str, window_id2: str):
        """
        Link two windows together for a specific project.
        
        Args:
            project_path: Project path
            window_id1: First window ID
            window_id2: Second window ID
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            session_id = _generate_session_id(project_path)
            
            if session_id in data["projects"] and "windowState" in data["projects"][session_id]:
                window_state = data["projects"][session_id]["windowState"]
                
                # Store bidirectional link
                if window_id1 not in window_state["windowLinks"]:
                    window_state["windowLinks"][window_id1] = []
                if window_id2 not in window_state["windowLinks"]:
                    window_state["windowLinks"][window_id2] = []
                
                if window_id2 not in window_state["windowLinks"][window_id1]:
                    window_state["windowLinks"][window_id1].append(window_id2)
                if window_id1 not in window_state["windowLinks"][window_id2]:
                    window_state["windowLinks"][window_id2].append(window_id1)
                
                data["appInfo"]["lastUpdated"] = now_utc
                _save_data(data)
                print(f"  [STORAGE] Windows linked for {project_path}: {window_id1} <-> {window_id2}")
    
    def unlink_windows(self, project_path: str, window_id1: str, window_id2: str):
        """
        Unlink two windows for a specific project.
        
        Args:
            project_path: Project path
            window_id1: First window ID
            window_id2: Second window ID
        """
        with _lock:
            from datetime import timezone
            data = _load_data()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            session_id = _generate_session_id(project_path)
            
            if session_id in data["projects"] and "windowState" in data["projects"][session_id]:
                window_state = data["projects"][session_id]["windowState"]
                
                # Remove bidirectional link
                if window_id1 in window_state["windowLinks"] and window_id2 in window_state["windowLinks"][window_id1]:
                    window_state["windowLinks"][window_id1].remove(window_id2)
                
                if window_id2 in window_state["windowLinks"] and window_id1 in window_state["windowLinks"][window_id2]:
                    window_state["windowLinks"][window_id2].remove(window_id1)
                
                data["appInfo"]["lastUpdated"] = now_utc
                _save_data(data)
                print(f"  [STORAGE] Windows unlinked for {project_path}: {window_id1} <-> {window_id2}")
    
    def get_linked_windows(self, project_path: str, window_id: str) -> List[str]:
        """
        Get all windows linked to a specific window for a specific project.
        
        Args:
            project_path: Project path
            window_id: Window ID to check
        
        Returns:
            List of linked window IDs
        """
        with _lock:
            data = _load_data()
            session_id = _generate_session_id(project_path)
            
            if session_id in data["projects"] and "windowState" in data["projects"][session_id]:
                window_state = data["projects"][session_id]["windowState"]
                return window_state["windowLinks"].get(window_id, [])
            
            return []


# Global instance
storage_service = JsonStorageService()
