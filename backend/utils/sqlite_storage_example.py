"""
SQLite Storage Implementation Example for Petrophysics Workspace
This shows how to migrate from JSON to SQLite
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import threading

DB_PATH = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"
_lock = threading.Lock()


class SQLiteStorageService:
    """SQLite-based storage as an alternative to JSON storage"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Create database schema if it doesn't exist"""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    session_id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    project_name TEXT,
                    active_well TEXT,
                    selected_wells TEXT,  -- JSON array
                    cli_history TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Layouts table (named layouts per project)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS layouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    layout_name TEXT NOT NULL DEFAULT 'default',
                    rc_dock_layout TEXT,  -- JSON
                    visible_panels TEXT,  -- JSON array
                    window_links TEXT,    -- JSON object
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES projects(session_id) ON DELETE CASCADE,
                    UNIQUE(session_id, layout_name)
                )
            """)
            
            # Wells table (well session data with expiry)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wells (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    well_name TEXT NOT NULL,
                    datasets TEXT,     -- JSON array of datasets
                    total_logs INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES projects(session_id) ON DELETE CASCADE,
                    UNIQUE(session_id, well_name)
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
            
            # Workspace configuration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workspace_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Single row
                    root_path TEXT,
                    current_project_session_id TEXT,
                    version TEXT DEFAULT '2.0.0',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_session ON wells(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_name ON wells(well_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_layouts_session ON layouts(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON well_sessions(expires_at)")
            
            conn.commit()
            conn.close()
    
    def store_session(self, session_id: str, session_data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None):
        """Store well session data in SQLite"""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                now = datetime.utcnow()
                expires_at = now + timedelta(hours=4)
                
                # Insert or update well session metadata
                cursor.execute("""
                    INSERT OR REPLACE INTO well_sessions 
                    (session_id, project_path, project_name, updated_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    metadata.get('project_path') if metadata else None,
                    metadata.get('project_name') if metadata else None,
                    now,
                    expires_at
                ))
                
                # Store each well
                for well_name, well_data in session_data.items():
                    datasets = []
                    all_logs = []
                    
                    if isinstance(well_data, dict) and "datasets" in well_data:
                        for ds in well_data["datasets"]:
                            if isinstance(ds, dict):
                                ds_logs = []
                                if "well_logs" in ds:
                                    for log in ds["well_logs"]:
                                        if isinstance(log, dict) and "name" in log:
                                            log_name = log["name"]
                                            ds_logs.append(log_name)
                                            if log_name not in all_logs:
                                                all_logs.append(log_name)
                                
                                datasets.append({"selectedLogs": ds_logs})
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO wells 
                        (session_id, well_name, datasets, total_logs, last_accessed)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        well_name,
                        json.dumps(datasets),
                        len(all_logs),
                        now
                    ))
                
                conn.commit()
                print(f"[SQLite] Stored {len(session_data)} wells for session {session_id}")
                
            except Exception as e:
                conn.rollback()
                print(f"[SQLite] Error storing session: {e}")
                raise
            finally:
                conn.close()
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load well session data from SQLite"""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            try:
                # Clean expired sessions first
                cursor.execute("DELETE FROM well_sessions WHERE expires_at < ?", (datetime.utcnow(),))
                conn.commit()
                
                # Get session metadata
                cursor.execute("""
                    SELECT * FROM well_sessions WHERE session_id = ?
                """, (session_id,))
                
                session_meta = cursor.fetchone()
                if not session_meta:
                    return None
                
                # Get all wells for this session
                cursor.execute("""
                    SELECT well_name, datasets, total_logs, last_accessed 
                    FROM wells WHERE session_id = ?
                """, (session_id,))
                
                wells_data = {}
                for row in cursor.fetchall():
                    wells_data[row['well_name']] = {
                        'datasets': json.loads(row['datasets']),
                        'totalLogs': row['total_logs'],
                        'lastAccessed': row['last_accessed']
                    }
                
                return {
                    'wells': wells_data,
                    'metadata': {
                        'project_path': session_meta['project_path'],
                        'project_name': session_meta['project_name']
                    }
                }
                
            finally:
                conn.close()
    
    def save_layout(self, project_path: str, layout_data: dict, visible_panels: list, 
                    layout_name: str = "default", window_links: dict = None):
        """Save project layout"""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                # Generate session ID from project path
                import hashlib
                session_id = f"project_{hashlib.md5(project_path.encode()).hexdigest()}"
                
                # Ensure project exists
                cursor.execute("""
                    INSERT OR IGNORE INTO projects (session_id, project_path)
                    VALUES (?, ?)
                """, (session_id, project_path))
                
                # Save layout
                cursor.execute("""
                    INSERT OR REPLACE INTO layouts 
                    (session_id, layout_name, rc_dock_layout, visible_panels, window_links, saved_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    layout_name,
                    json.dumps(layout_data),
                    json.dumps(visible_panels),
                    json.dumps(window_links or {}),
                    datetime.utcnow()
                ))
                
                conn.commit()
                print(f"[SQLite] Saved layout '{layout_name}' for {project_path}")
                
            except Exception as e:
                conn.rollback()
                print(f"[SQLite] Error saving layout: {e}")
                raise
            finally:
                conn.close()
    
    def query_wells_by_log(self, log_name: str) -> List[Dict[str, Any]]:
        """
        ADVANCED QUERY EXAMPLE: Find all wells containing a specific log
        This is MUCH easier in SQLite than JSON!
        """
        with _lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    SELECT w.well_name, w.session_id, ws.project_path, ws.project_name
                    FROM wells w
                    JOIN well_sessions ws ON w.session_id = ws.session_id
                    WHERE w.datasets LIKE ?
                    AND ws.expires_at > ?
                """, (f'%{log_name}%', datetime.utcnow()))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'well_name': row['well_name'],
                        'session_id': row['session_id'],
                        'project_path': row['project_path'],
                        'project_name': row['project_name']
                    })
                
                return results
                
            finally:
                conn.close()
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get statistics about stored data"""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                stats = {}
                
                cursor.execute("SELECT COUNT(*) FROM projects")
                stats['total_projects'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM wells")
                stats['total_wells'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM layouts")
                stats['total_layouts'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM well_sessions WHERE expires_at > ?", 
                             (datetime.utcnow(),))
                stats['active_sessions'] = cursor.fetchone()[0]
                
                # Database file size
                stats['db_size_mb'] = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0
                
                return stats
                
            finally:
                conn.close()


def migrate_json_to_sqlite(json_file: Path, db_path: Path):
    """
    Migration utility: Convert existing JSON storage to SQLite
    
    Usage:
        from backend.utils.json_storage_example import migrate_json_to_sqlite
        migrate_json_to_sqlite(
            Path("data/application_setting.json"),
            Path("data/petrophysics.db")
        )
    """
    print(f"Migrating {json_file} to {db_path}...")
    
    # Load existing JSON data
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Initialize SQLite
    sqlite_service = SQLiteStorageService(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Migrate workspace config
        workspace = data.get('workspace', {})
        cursor.execute("""
            INSERT OR REPLACE INTO workspace_config 
            (id, root_path, current_project_session_id, last_updated)
            VALUES (1, ?, ?, ?)
        """, (
            workspace.get('root'),
            workspace.get('currentProject', {}).get('sessionId') if workspace.get('currentProject') else None,
            datetime.utcnow()
        ))
        
        # Migrate projects
        for session_id, project in data.get('projects', {}).items():
            cursor.execute("""
                INSERT OR REPLACE INTO projects 
                (session_id, project_path, active_well, selected_wells, cli_history, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                project.get('projectPath'),
                project.get('activeWell'),
                json.dumps(project.get('selectedWells', [])),
                project.get('cliHistory'),
                datetime.utcnow()
            ))
            
            # Migrate layouts
            for layout_name, layout_data in project.get('savedLayouts', {}).items():
                cursor.execute("""
                    INSERT OR REPLACE INTO layouts 
                    (session_id, layout_name, rc_dock_layout, visible_panels, window_links, saved_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    layout_name,
                    json.dumps(layout_data.get('rcDockLayout')),
                    json.dumps(layout_data.get('visiblePanels', [])),
                    json.dumps(layout_data.get('windowLinks', {})),
                    layout_data.get('savedAt') or datetime.utcnow()
                ))
        
        # Migrate well sessions
        for session_id, well_session in data.get('wells', {}).items():
            cursor.execute("""
                INSERT OR REPLACE INTO well_sessions 
                (session_id, project_path, project_name, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id,
                well_session.get('projectPath'),
                well_session.get('projectName'),
                well_session.get('updatedAt') or datetime.utcnow(),
                well_session.get('expiresAt')
            ))
            
            # Migrate wells
            for well_name, well_data in well_session.get('wells', {}).items():
                cursor.execute("""
                    INSERT OR REPLACE INTO wells 
                    (session_id, well_name, datasets, total_logs, last_accessed)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    well_name,
                    json.dumps(well_data.get('datasets', [])),
                    well_data.get('totalLogs', 0),
                    well_data.get('lastAccessed') or datetime.utcnow()
                ))
        
        conn.commit()
        print(f"✅ Migration complete!")
        print(f"   - Projects: {len(data.get('projects', {}))}")
        print(f"   - Well sessions: {len(data.get('wells', {}))}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()
