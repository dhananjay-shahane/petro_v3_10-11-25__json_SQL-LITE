"""
SQLite Storage Service for Petrophysics Workspace
Production-ready replacement for JSON storage with better performance and scalability
"""

import os
import sqlite3
import json
import hashlib
import threading
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal


DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_FILE = DB_DIR / "petrophysics.db"

_lock = threading.Lock()
_connection_pool = {}


def _ensure_db_dir():
    """Ensure the database directory exists"""
    DB_DIR.mkdir(exist_ok=True)


def _get_connection() -> sqlite3.Connection:
    """Get a thread-safe database connection"""
    thread_id = threading.get_ident()
    
    if thread_id not in _connection_pool:
        conn = sqlite3.connect(str(DB_FILE), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
        _connection_pool[thread_id] = conn
    
    return _connection_pool[thread_id]


def _generate_session_id(project_path: str) -> str:
    """Generate consistent session ID from project path"""
    if not project_path:
        import uuid
        return f"project_{uuid.uuid4().hex[:32]}"
    hash_val = hashlib.md5(project_path.encode()).hexdigest()
    return f"project_{hash_val}"


def serialize_value(value: Any) -> Any:
    """Serialize Python values to JSON-compatible format"""
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    elif isinstance(value, dict):
        return {key: serialize_value(val) for key, val in value.items()}
    elif isinstance(value, set):
        return list(value)
    else:
        return str(value)


def deserialize_value(value: Any, value_type: Optional[str] = None) -> Any:
    """Deserialize JSON value to Python types"""
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


class SQLiteStorageService:
    """SQLite-based storage service compatible with JsonStorageService API"""
    
    SESSION_EXPIRY_SECONDS = 14400  # 4 hours
    
    def __init__(self):
        self.db_path = DB_FILE
        _ensure_db_dir()
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            # Workspace configuration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workspace_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    root_path TEXT,
                    current_project_session_id TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                INSERT OR IGNORE INTO workspace_config (id, root_path)
                VALUES (1, '/home/runner/workspace/petrophysics-workplace')
            """)
            
            # Projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    session_id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    project_name TEXT,
                    active_well TEXT,
                    selected_wells TEXT,
                    cli_history TEXT,
                    ui_state TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            try:
                cursor.execute("ALTER TABLE projects ADD COLUMN ui_state TEXT")
                print("  [STORAGE] Added ui_state column to projects table")
            except Exception:
                pass
            
            # Layouts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS layouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    layout_name TEXT NOT NULL DEFAULT 'default',
                    rc_dock_layout TEXT,
                    visible_panels TEXT,
                    window_links TEXT,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES projects(session_id) ON DELETE CASCADE,
                    UNIQUE(session_id, layout_name)
                )
            """)
            
            # Well sessions metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS well_sessions (
                    session_id TEXT PRIMARY KEY,
                    project_path TEXT,
                    project_name TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES projects(session_id) ON DELETE CASCADE
                )
            """)
            
            # Session wells table (session-based, temporary)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_wells (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    well_name TEXT NOT NULL,
                    datasets TEXT,
                    total_logs INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES well_sessions(session_id) ON DELETE CASCADE,
                    UNIQUE(session_id, well_name)
                )
            """)
            
            # Wells table (permanent storage)
            # Stores complete well data as JSON for independent storage from .ptrc files
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wells (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_session TEXT NOT NULL,
                    project_name TEXT,
                    project_path TEXT NOT NULL,
                    well_name TEXT NOT NULL,
                    datasets TEXT NOT NULL,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_path, well_name)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_wells_session ON session_wells(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_wells_name ON session_wells(well_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_layouts_session ON layouts(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON well_sessions(expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_path ON projects(project_path)")
            
            # Indexes for wells (permanent storage)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_project_session ON wells(project_session)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_project_path ON wells(project_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_well_name ON wells(well_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_composite ON wells(project_path, well_name)")
            
            conn.commit()
    
    def generate_session_id(self) -> str:
        """Generate a unique session ID"""
        import uuid
        return str(uuid.uuid4())
    
    def store_session(self, session_id: str, session_data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None):
        """Store well session data"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                now = datetime.utcnow()
                expires_at = now + timedelta(seconds=self.SESSION_EXPIRY_SECONDS)
                
                # Clean expired sessions first
                cursor.execute("DELETE FROM well_sessions WHERE expires_at < ?", (now,))
                
                # Insert or update well session metadata
                cursor.execute("""
                    INSERT OR REPLACE INTO well_sessions 
                    (session_id, project_path, project_name, updated_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    metadata.get('project_path') if metadata else None,
                    metadata.get('project_name') if metadata else None,
                    now.isoformat(),
                    expires_at.isoformat()
                ))
                
                # Store each well in session_wells
                for well_name, well_data in session_data.items():
                    all_logs = []
                    
                    if isinstance(well_data, dict) and "datasets" in well_data:
                        for ds in well_data["datasets"]:
                            if isinstance(ds, dict) and "well_logs" in ds:
                                for log in ds["well_logs"]:
                                    if isinstance(log, dict) and "name" in log:
                                        log_name = log["name"]
                                        if log_name not in all_logs:
                                            all_logs.append(log_name)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO session_wells 
                        (session_id, well_name, datasets, total_logs, last_accessed)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        well_name,
                        json.dumps(well_data.get("datasets", [])),
                        len(all_logs),
                        now.isoformat()
                    ))
                
                conn.commit()
                print(f"  [STORAGE] Stored {len(session_data)} wells for project {session_id}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error storing session: {e}")
                raise
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load well session data"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                # Clean expired sessions
                cursor.execute("DELETE FROM well_sessions WHERE expires_at < ?", (datetime.utcnow().isoformat(),))
                conn.commit()
                
                # Get session metadata
                cursor.execute("""
                    SELECT * FROM well_sessions WHERE session_id = ?
                """, (session_id,))
                
                session_meta = cursor.fetchone()
                if not session_meta:
                    print(f"  [STORAGE] No session data found for {session_id}")
                    return None
                
                # Check expiry
                if session_meta['expires_at']:
                    try:
                        expires_at = datetime.fromisoformat(session_meta['expires_at'])
                        if datetime.utcnow() > expires_at:
                            cursor.execute("DELETE FROM well_sessions WHERE session_id = ?", (session_id,))
                            conn.commit()
                            print(f"  [STORAGE] Session {session_id} expired and removed")
                            return None
                    except (ValueError, TypeError):
                        pass
                
                # Get all wells for this session
                cursor.execute("""
                    SELECT well_name, datasets, total_logs, last_accessed 
                    FROM session_wells WHERE session_id = ?
                """, (session_id,))
                
                wells_data = {}
                for row in cursor.fetchall():
                    wells_data[row['well_name']] = {
                        'datasets': json.loads(row['datasets']) if row['datasets'] else [],
                        'totalLogs': row['total_logs'],
                        'lastAccessed': row['last_accessed']
                    }
                
                well_count = len(wells_data)
                print(f"  [STORAGE] Retrieved session data for {session_id}: {well_count} wells")
                
                return {
                    'wells': wells_data,
                    'metadata': {
                        'project_path': session_meta['project_path'],
                        'project_name': session_meta['project_name']
                    }
                }
                
            except Exception as e:
                print(f"  [STORAGE] Error loading session: {e}")
                return None
    
    def delete_session(self, session_id: str):
        """Remove project well data from storage"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("DELETE FROM well_sessions WHERE session_id = ?", (session_id,))
                conn.commit()
                print(f"  [STORAGE] Deleted well data for {session_id}")
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error deleting session: {e}")
    
    def session_exists(self, session_id: str) -> bool:
        """Check if project well data exists"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            # Clean expired first
            cursor.execute("DELETE FROM well_sessions WHERE expires_at < ?", (datetime.utcnow().isoformat(),))
            conn.commit()
            
            cursor.execute("SELECT 1 FROM well_sessions WHERE session_id = ?", (session_id,))
            return cursor.fetchone() is not None
    
    def extend_session(self, session_id: str):
        """Extend well data expiry by 4 hours"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                new_expiry = (datetime.utcnow() + timedelta(seconds=self.SESSION_EXPIRY_SECONDS)).isoformat()
                cursor.execute("""
                    UPDATE well_sessions SET expires_at = ? WHERE session_id = ?
                """, (new_expiry, session_id))
                conn.commit()
                print(f"  [STORAGE] Extended expiry for {session_id}")
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error extending session: {e}")
    
    def get_session_ttl(self, session_id: str) -> int:
        """Get time remaining before well data expires (seconds)"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT expires_at FROM well_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if not row:
                return -2
            
            expires_at_str = row['expires_at']
            if not expires_at_str:
                return -1
            
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                ttl = (expires_at - datetime.utcnow()).total_seconds()
                return int(ttl) if ttl > 0 else -2
            except (ValueError, TypeError):
                return -2
    
    def save_layout(self, project_path: str, layout_data: dict, visible_panels: list, 
                    layout_name: str = "default", window_links: dict = None, font_sizes: dict = None):
        """Save workspace layout for a specific project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                now = datetime.utcnow().isoformat()
                # Normalize project path to ensure consistent session IDs
                normalized_path = os.path.normpath(project_path).replace('\\', '/')
                session_id = _generate_session_id(normalized_path)
                
                print(f"  [STORAGE] Saving layout '{layout_name}' for project: {normalized_path} (session: {session_id[:12]}...)")
                
                # Ensure project exists
                cursor.execute("""
                    INSERT OR IGNORE INTO projects (session_id, project_path, updated_at)
                    VALUES (?, ?, ?)
                """, (session_id, normalized_path, now))
                
                # Save layout with font sizes
                cursor.execute("""
                    INSERT OR REPLACE INTO layouts 
                    (session_id, layout_name, rc_dock_layout, visible_panels, window_links, font_sizes, saved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    layout_name,
                    json.dumps(layout_data),
                    json.dumps(visible_panels),
                    json.dumps(window_links or {}),
                    json.dumps(font_sizes or {}),
                    now
                ))
                
                # Update project timestamp
                cursor.execute("UPDATE projects SET updated_at = ? WHERE session_id = ?", (now, session_id))
                
                conn.commit()
                print(f"  [STORAGE] Layout '{layout_name}' saved for project: {project_path} with {len(visible_panels)} panels")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error saving layout: {e}")
                raise
    
    def load_layout(self, project_path: str, layout_name: str = "default") -> Optional[Dict[str, Any]]:
        """Load workspace layout for a specific project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            # Normalize project path to ensure consistent session IDs
            normalized_path = os.path.normpath(project_path).replace('\\', '/')
            session_id = _generate_session_id(normalized_path)
            
            print(f"  [STORAGE] Loading layout '{layout_name}' for project: {normalized_path} (session: {session_id[:12]}...)")
            
            cursor.execute("""
                SELECT rc_dock_layout, visible_panels, window_links, font_sizes, saved_at
                FROM layouts
                WHERE session_id = ? AND layout_name = ?
            """, (session_id, layout_name))
            
            row = cursor.fetchone()
            if not row:
                print(f"  [STORAGE] No layout '{layout_name}' found for project: {normalized_path}")
                return None
            
            # Parse font_sizes with default fallback for backward compatibility
            font_sizes = {}
            if row['font_sizes']:
                try:
                    font_sizes = json.loads(row['font_sizes'])
                except (json.JSONDecodeError, TypeError):
                    font_sizes = {}
            
            print(f"  [STORAGE] Retrieved layout '{layout_name}' for project {normalized_path}")
            return {
                "layout": json.loads(row['rc_dock_layout']) if row['rc_dock_layout'] else None,
                "visiblePanels": json.loads(row['visible_panels']) if row['visible_panels'] else [],
                "windowLinks": json.loads(row['window_links']) if row['window_links'] else {},
                "fontSizes": font_sizes,
                "savedAt": row['saved_at']
            }
    
    def get_saved_layout_names(self, project_path: str) -> List[str]:
        """Get list of all saved layout names for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            session_id = _generate_session_id(project_path)
            
            cursor.execute("""
                SELECT layout_name FROM layouts WHERE session_id = ?
            """, (session_id,))
            
            names = [row['layout_name'] for row in cursor.fetchall()]
            print(f"  [STORAGE] Found {len(names)} saved layouts for project: {project_path}")
            return names
    
    def list_saved_layouts(self, project_path: str) -> List[Dict[str, Any]]:
        """Get list of saved layouts with metadata"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            session_id = _generate_session_id(project_path)
            
            cursor.execute("""
                SELECT layout_name, saved_at FROM layouts WHERE session_id = ?
                ORDER BY saved_at DESC
            """, (session_id,))
            
            layouts = []
            for row in cursor.fetchall():
                layouts.append({
                    "name": row['layout_name'],
                    "savedAt": row['saved_at']
                })
            
            print(f"  [STORAGE] Found {len(layouts)} layouts for project: {project_path}")
            return layouts
    
    def delete_layout(self, project_path: str, layout_name: str):
        """Delete a saved layout"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                session_id = _generate_session_id(project_path)
                
                cursor.execute("""
                    DELETE FROM layouts WHERE session_id = ? AND layout_name = ?
                """, (session_id, layout_name))
                
                conn.commit()
                print(f"  [STORAGE] Deleted layout '{layout_name}' for project: {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error deleting layout: {e}")
    
    def save_active_well(self, project_path: str, well_name: str):
        """Save the active well for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                now = datetime.utcnow().isoformat()
                session_id = _generate_session_id(project_path)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO projects (session_id, project_path, updated_at)
                    VALUES (?, ?, ?)
                """, (session_id, project_path, now))
                
                cursor.execute("""
                    UPDATE projects SET active_well = ?, updated_at = ? WHERE session_id = ?
                """, (well_name, now, session_id))
                
                conn.commit()
                print(f"  [STORAGE] Saved active well '{well_name}' for project {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error saving active well: {e}")
    
    def load_active_well(self, project_path: str) -> Optional[str]:
        """Load the active well for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            session_id = _generate_session_id(project_path)
            
            cursor.execute("SELECT active_well FROM projects WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row and row['active_well']:
                print(f"  [STORAGE] Retrieved active well '{row['active_well']}' for project {project_path}")
                return row['active_well']
            
            return None
    
    def save_selected_wells(self, project_path: str, well_names: List[str]):
        """Save selected wells for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                now = datetime.utcnow().isoformat()
                session_id = _generate_session_id(project_path)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO projects (session_id, project_path, updated_at)
                    VALUES (?, ?, ?)
                """, (session_id, project_path, now))
                
                cursor.execute("""
                    UPDATE projects SET selected_wells = ?, updated_at = ? WHERE session_id = ?
                """, (json.dumps(well_names), now, session_id))
                
                conn.commit()
                print(f"  [STORAGE] Saved {len(well_names)} selected wells for project {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error saving selected wells: {e}")
    
    def load_selected_wells(self, project_path: str) -> List[str]:
        """Load selected wells for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            session_id = _generate_session_id(project_path)
            
            cursor.execute("SELECT selected_wells FROM projects WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row and row['selected_wells']:
                wells = json.loads(row['selected_wells'])
                print(f"  [STORAGE] Retrieved {len(wells)} selected wells for project {project_path}")
                return wells
            
            return []
    
    def save_cli_history(self, project_path: str, history: str):
        """Save CLI history for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                now = datetime.utcnow().isoformat()
                session_id = _generate_session_id(project_path)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO projects (session_id, project_path, updated_at)
                    VALUES (?, ?, ?)
                """, (session_id, project_path, now))
                
                cursor.execute("""
                    UPDATE projects SET cli_history = ?, updated_at = ? WHERE session_id = ?
                """, (history, now, session_id))
                
                conn.commit()
                print(f"  [STORAGE] Saved CLI history for project {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error saving CLI history: {e}")
    
    def load_cli_history(self, project_path: str) -> str:
        """Load CLI history for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            session_id = _generate_session_id(project_path)
            
            cursor.execute("SELECT cli_history FROM projects WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row and row['cli_history']:
                print(f"  [STORAGE] Retrieved CLI history for project {project_path}")
                return row['cli_history']
            
            return ""
    
    def save_ui_state(self, project_path: str, ui_state: dict):
        """Save UI state for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                now = datetime.utcnow().isoformat()
                session_id = _generate_session_id(project_path)
                ui_state_json = json.dumps(ui_state)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO projects (session_id, project_path, updated_at)
                    VALUES (?, ?, ?)
                """, (session_id, project_path, now))
                
                cursor.execute("""
                    UPDATE projects SET ui_state = ?, updated_at = ? WHERE session_id = ?
                """, (ui_state_json, now, session_id))
                
                conn.commit()
                print(f"  [STORAGE] Saved UI state for project {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error saving UI state: {e}")
    
    def load_ui_state(self, project_path: str) -> Optional[dict]:
        """Load UI state for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            session_id = _generate_session_id(project_path)
            
            cursor.execute("SELECT ui_state FROM projects WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row and row['ui_state']:
                try:
                    ui_state = json.loads(row['ui_state'])
                    print(f"  [STORAGE] Retrieved UI state for project {project_path}")
                    return ui_state
                except json.JSONDecodeError as e:
                    print(f"  [STORAGE] Error decoding UI state: {e}")
                    return None
            
            return None
    
    def save_current_project(self, project_path: str, project_name: str):
        """Save the currently opened project information"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                now = datetime.utcnow().isoformat()
                session_id = _generate_session_id(project_path)
                
                cursor.execute("""
                    UPDATE workspace_config SET current_project_session_id = ?, last_updated = ? WHERE id = 1
                """, (session_id, now))
                
                cursor.execute("""
                    INSERT OR IGNORE INTO projects (session_id, project_path, project_name, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (session_id, project_path, project_name, now))
                
                cursor.execute("""
                    UPDATE projects SET project_name = ?, updated_at = ? WHERE session_id = ?
                """, (project_name, now, session_id))
                
                conn.commit()
                print(f"  [STORAGE] Current project set: {project_name} at {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error saving current project: {e}")
    
    def load_current_project(self) -> Optional[Dict[str, Any]]:
        """Load the currently opened project information"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT wc.current_project_session_id, p.project_path, p.project_name
                FROM workspace_config wc
                LEFT JOIN projects p ON wc.current_project_session_id = p.session_id
                WHERE wc.id = 1
            """)
            
            row = cursor.fetchone()
            if row and row['current_project_session_id']:
                print(f"  [STORAGE] Retrieved current project: {row['project_name'] or 'Unknown'}")
                return {
                    "sessionId": row['current_project_session_id'],
                    "projectPath": row['project_path'],
                    "projectName": row['project_name']
                }
            
            return None
    
    def delete_current_project(self):
        """Clear the currently opened project information"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    UPDATE workspace_config 
                    SET current_project_session_id = NULL, last_updated = ?
                    WHERE id = 1
                """, (datetime.utcnow().isoformat(),))
                
                conn.commit()
                print("  [STORAGE] Current project cleared")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error deleting current project: {e}")
    
    def delete_all_project_data(self, project_path: str):
        """Delete all data for a specific project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                session_id = _generate_session_id(project_path)
                
                # Delete layouts, windows, wells (will cascade via foreign keys)
                cursor.execute("DELETE FROM projects WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM well_sessions WHERE session_id = ?", (session_id,))
                
                conn.commit()
                print(f"  [STORAGE] Deleted all data for project: {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error deleting project data: {e}")
    
    def get_all_keys(self) -> List[str]:
        """Get all session keys (project session IDs)"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT session_id FROM projects")
            keys = [row['session_id'] for row in cursor.fetchall()]
            
            print(f"  [STORAGE] Retrieved {len(keys)} project keys")
            return keys
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get information about storage"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM projects")
            total_projects = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM well_sessions")
            total_sessions = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM session_wells")
            total_session_wells = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM wells")
            total_persistent_wells = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM layouts")
            total_layouts = cursor.fetchone()[0]
            
            # Get database file size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            info = {
                "storage_type": "sqlite",
                "database_path": str(self.db_path),
                "database_size_bytes": db_size,
                "database_size_mb": round(db_size / (1024 * 1024), 2),
                "total_projects": total_projects,
                "total_well_sessions": total_sessions,
                "total_session_wells": total_session_wells,
                "total_persistent_wells": total_persistent_wells,
                "total_layouts": total_layouts
            }
            
            print(f"  [STORAGE] Storage info: {total_projects} projects, {total_persistent_wells} persistent wells, {db_size/1024:.1f} KB")
            return info
    
    def clear_all_data(self):
        """Clear all data from storage (DANGEROUS - use with caution)"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("DELETE FROM session_wells")
                cursor.execute("DELETE FROM wells")
                cursor.execute("DELETE FROM well_sessions")
                cursor.execute("DELETE FROM layouts")
                cursor.execute("DELETE FROM projects")
                cursor.execute("UPDATE workspace_config SET current_project_session_id = NULL WHERE id = 1")
                
                conn.commit()
                print("  [STORAGE] ⚠️  All data cleared")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error clearing data: {e}")
    
    def update_active_window(self, project_path: str, window_id: str):
        """Update the active window ID for a project"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                session_id = _generate_session_id(project_path)
                
                cursor.execute("""
                    UPDATE window_state 
                    SET active_window_id = ?, updated_at = ?
                    WHERE session_id = ?
                """, (window_id, datetime.utcnow().isoformat(), session_id))
                
                # If no row exists, insert one
                if cursor.rowcount == 0:
                    cursor.execute("""
                        INSERT INTO window_state (session_id, window_count, active_window_id, window_ids, window_links, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (session_id, 1, window_id, json.dumps([window_id]), json.dumps({}), datetime.utcnow().isoformat()))
                
                conn.commit()
                print(f"  [STORAGE] Updated active window to '{window_id}' for {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error updating active window: {e}")
    
    def add_window(self, project_path: str, window_id: str):
        """Add a window to the project's window list"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                session_id = _generate_session_id(project_path)
                
                # Get current window state
                cursor.execute("SELECT window_ids, window_count FROM window_state WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                
                if row:
                    window_ids = json.loads(row['window_ids']) if row['window_ids'] else []
                    if window_id not in window_ids:
                        window_ids.append(window_id)
                        cursor.execute("""
                            UPDATE window_state 
                            SET window_ids = ?, window_count = ?, updated_at = ?
                            WHERE session_id = ?
                        """, (json.dumps(window_ids), len(window_ids), datetime.utcnow().isoformat(), session_id))
                else:
                    # Create new window state
                    cursor.execute("""
                        INSERT INTO window_state (session_id, window_count, active_window_id, window_ids, window_links, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (session_id, 1, window_id, json.dumps([window_id]), json.dumps({}), datetime.utcnow().isoformat()))
                
                conn.commit()
                print(f"  [STORAGE] Added window '{window_id}' for {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error adding window: {e}")
    
    def remove_window(self, project_path: str, window_id: str):
        """Remove a window from the project's window list"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                session_id = _generate_session_id(project_path)
                
                cursor.execute("SELECT window_ids, window_links, active_window_id FROM window_state WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                
                if row:
                    window_ids = json.loads(row['window_ids']) if row['window_ids'] else []
                    window_links = json.loads(row['window_links']) if row['window_links'] else {}
                    active_window = row['active_window_id']
                    
                    if window_id in window_ids:
                        window_ids.remove(window_id)
                    
                    # Remove from links
                    if window_id in window_links:
                        del window_links[window_id]
                    
                    # Clear active if it was this window
                    if active_window == window_id:
                        active_window = window_ids[0] if window_ids else None
                    
                    cursor.execute("""
                        UPDATE window_state 
                        SET window_ids = ?, window_count = ?, window_links = ?, active_window_id = ?, updated_at = ?
                        WHERE session_id = ?
                    """, (json.dumps(window_ids), len(window_ids), json.dumps(window_links), active_window, datetime.utcnow().isoformat(), session_id))
                
                conn.commit()
                print(f"  [STORAGE] Removed window '{window_id}' for {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error removing window: {e}")
    
    def link_windows(self, project_path: str, window_id1: str, window_id2: str):
        """Link two windows together"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                session_id = _generate_session_id(project_path)
                
                cursor.execute("SELECT window_links FROM window_state WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                
                window_links = {}
                if row and row['window_links']:
                    window_links = json.loads(row['window_links'])
                
                # Add bidirectional links
                if window_id1 not in window_links:
                    window_links[window_id1] = []
                if window_id2 not in window_links[window_id1]:
                    window_links[window_id1].append(window_id2)
                
                if window_id2 not in window_links:
                    window_links[window_id2] = []
                if window_id1 not in window_links[window_id2]:
                    window_links[window_id2].append(window_id1)
                
                cursor.execute("""
                    UPDATE window_state 
                    SET window_links = ?, updated_at = ?
                    WHERE session_id = ?
                """, (json.dumps(window_links), datetime.utcnow().isoformat(), session_id))
                
                conn.commit()
                print(f"  [STORAGE] Linked windows '{window_id1}' and '{window_id2}' for {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error linking windows: {e}")
    
    def unlink_windows(self, project_path: str, window_id1: str, window_id2: str):
        """Unlink two windows"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                session_id = _generate_session_id(project_path)
                
                cursor.execute("SELECT window_links FROM window_state WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                
                if row and row['window_links']:
                    window_links = json.loads(row['window_links'])
                    
                    # Remove bidirectional links
                    if window_id1 in window_links and window_id2 in window_links[window_id1]:
                        window_links[window_id1].remove(window_id2)
                    
                    if window_id2 in window_links and window_id1 in window_links[window_id2]:
                        window_links[window_id2].remove(window_id1)
                    
                    cursor.execute("""
                        UPDATE window_state 
                        SET window_links = ?, updated_at = ?
                        WHERE session_id = ?
                    """, (json.dumps(window_links), datetime.utcnow().isoformat(), session_id))
                    
                    conn.commit()
                    print(f"  [STORAGE] Unlinked windows '{window_id1}' and '{window_id2}' for {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error unlinking windows: {e}")
    
    def get_linked_windows(self, project_path: str, window_id: str) -> List[str]:
        """Get all windows linked to a specific window"""
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            session_id = _generate_session_id(project_path)
            
            cursor.execute("SELECT window_links FROM window_state WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row and row['window_links']:
                window_links = json.loads(row['window_links'])
                return window_links.get(window_id, [])
            
            return []
    
    # ===== Permanent Well Storage Methods =====
    
    def save_well(self, well_data: Dict[str, Any], project_path: str) -> bool:
        """
        Save or update a well in permanent storage.
        Uses upsert (INSERT OR REPLACE) to handle both new and existing wells.
        
        Args:
            well_data: Dictionary representation of the well (from well.to_dict())
            project_path: Path to the project
            
        Returns:
            bool: True if successful
        """
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                well_name = well_data.get('well_name')
                
                # Generate project_session from project_path
                if project_path:
                    hash_val = hashlib.md5(project_path.encode()).hexdigest()
                    project_session = f"project_{hash_val}"
                    # Extract project_name from path
                    project_name = Path(project_path).name
                else:
                    project_session = "project_unknown"
                    project_name = "unknown"
                
                # Serialize full well data as JSON
                serialized_data = json.dumps(well_data, default=serialize_value)
                
                # Upsert well into database
                cursor.execute("""
                    INSERT OR REPLACE INTO wells 
                    (project_session, project_name, project_path, well_name, datasets, updated_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    project_session,
                    project_name,
                    project_path,
                    well_name,
                    serialized_data,
                    datetime.utcnow().isoformat()
                ))
                
                conn.commit()
                print(f"  [STORAGE] Saved well '{well_name}' to wells table")
                return True
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error saving well: {e}")
                return False
    
    def get_well(self, project_path: str, well_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a well from permanent storage.
        
        Args:
            project_path: Path to the project
            well_name: Name of the well
            
        Returns:
            Dict containing well data or None if not found
        """
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT datasets, created_date, updated_date
                FROM wells 
                WHERE project_path = ? AND well_name = ?
            """, (project_path, well_name))
            
            row = cursor.fetchone()
            
            if row:
                well_data = json.loads(row['datasets'])
                well_data['_metadata'] = {
                    'created_date': row['created_date'],
                    'updated_date': row['updated_date']
                }
                return well_data
            
            return None
    
    def get_project_wells(self, project_path: str) -> List[Dict[str, Any]]:
        """
        Get all wells for a project (without full serialized data for performance).
        
        Args:
            project_path: Path to the project
            
        Returns:
            List of well summaries
        """
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, well_name, project_name, created_date, updated_date
                FROM wells 
                WHERE project_path = ?
                ORDER BY well_name
            """, (project_path,))
            
            wells = []
            for row in cursor.fetchall():
                wells.append({
                    'id': row['id'],
                    'well_name': row['well_name'],
                    'project_name': row['project_name'],
                    'created_date': row['created_date'],
                    'updated_date': row['updated_date']
                })
            
            return wells
    
    def delete_well(self, project_path: str, well_name: str) -> bool:
        """
        Delete a well from permanent storage.
        
        Args:
            project_path: Path to the project
            well_name: Name of the well
            
        Returns:
            bool: True if deleted, False if not found
        """
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    DELETE FROM wells 
                    WHERE project_path = ? AND well_name = ?
                """, (project_path, well_name))
                
                deleted = cursor.rowcount > 0
                conn.commit()
                
                if deleted:
                    print(f"  [STORAGE] Deleted well '{well_name}' from wells table")
                
                return deleted
                
            except Exception as e:
                conn.rollback()
                print(f"  [STORAGE] Error deleting well: {e}")
                return False
    
    def query_wells(self, project_path: Optional[str] = None, 
                    well_name: Optional[str] = None,
                    dataset_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query wells with filters.
        
        Args:
            project_path: Filter by project path (optional)
            well_name: Filter by well name (partial match, optional)
            dataset_name: Filter by dataset name (optional)
            
        Returns:
            List of matching wells
        """
        with _lock:
            conn = _get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT id, well_name, project_path, project_name, project_session,
                       created_date, updated_date
                FROM wells 
                WHERE 1=1
            """
            params = []
            
            if project_path:
                query += " AND project_path = ?"
                params.append(project_path)
            
            if well_name:
                query += " AND well_name LIKE ?"
                params.append(f"%{well_name}%")
            
            if dataset_name:
                # Use JSON query to filter by dataset name in datasets column
                query += " AND datasets LIKE ?"
                params.append(f'%"name": "{dataset_name}"%')
            
            query += " ORDER BY well_name"
            
            cursor.execute(query, params)
            
            wells = []
            for row in cursor.fetchall():
                wells.append({
                    'id': row['id'],
                    'well_name': row['well_name'],
                    'project_path': row['project_path'],
                    'project_name': row['project_name'],
                    'project_session': row['project_session'],
                    'created_date': row['created_date'],
                    'updated_date': row['updated_date']
                })
            
            return wells
    
    def bulk_save_wells(self, wells_data: List[Dict[str, Any]], project_path: str) -> Dict[str, Any]:
        """
        Bulk save multiple wells to permanent storage.
        
        Args:
            wells_data: List of well dictionaries (from well.to_dict())
            project_path: Path to the project
            
        Returns:
            Dict with success count and errors
        """
        saved_count = 0
        errors = []
        
        for well_data in wells_data:
            try:
                if self.save_well(well_data, project_path):
                    saved_count += 1
                else:
                    errors.append({
                        'well_name': well_data.get('well_name'),
                        'error': 'Save failed'
                    })
            except Exception as e:
                errors.append({
                    'well_name': well_data.get('well_name'),
                    'error': str(e)
                })
        
        print(f"  [STORAGE] Bulk saved {saved_count}/{len(wells_data)} wells")
        return {
            'saved': saved_count,
            'total': len(wells_data),
            'errors': errors
        }


# Create singleton instance
storage_service = SQLiteStorageService()
