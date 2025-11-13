"""
Migration utility to convert JSON storage to SQLite
Run this script to migrate existing data from application_setting.json to petrophysics.db
"""

import json
from pathlib import Path
from datetime import datetime
from sqlite_storage import SQLiteStorageService, _generate_session_id


JSON_FILE = Path(__file__).parent.parent.parent / "data" / "application_setting.json"
BACKUP_FILE = JSON_FILE.with_suffix('.json.backup')


def backup_json_file():
    """Create backup of JSON file before migration"""
    if JSON_FILE.exists():
        import shutil
        shutil.copy2(JSON_FILE, BACKUP_FILE)
        print(f"✅ Backed up JSON file to: {BACKUP_FILE}")
        return True
    else:
        print("⚠️  No JSON file found to migrate")
        return False


def load_json_data():
    """Load existing JSON data"""
    if not JSON_FILE.exists():
        print("No JSON file found")
        return None
    
    with open(JSON_FILE, 'r') as f:
        data = json.load(f)
    
    print(f"📂 Loaded JSON data from: {JSON_FILE}")
    return data


def migrate_data(dry_run=False):
    """
    Migrate JSON data to SQLite
    
    Args:
        dry_run: If True, only show what would be migrated without making changes
    """
    print("\n" + "="*60)
    print("🔄 JSON to SQLite Migration Tool")
    print("="*60 + "\n")
    
    # Load JSON data
    data = load_json_data()
    if not data:
        print("❌ No data to migrate")
        return False
    
    # Show migration summary
    num_projects = len(data.get('projects', {}))
    num_wells_sessions = len(data.get('wells', {}))
    num_layouts = sum(len(p.get('savedLayouts', {})) for p in data.get('projects', {}).values())
    
    print(f"📊 Migration Summary:")
    print(f"   - Projects: {num_projects}")
    print(f"   - Well Sessions: {num_wells_sessions}")
    print(f"   - Saved Layouts: {num_layouts}")
    print(f"   - Workspace: {'configured' if data.get('workspace') else 'not configured'}")
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("\nData to be migrated:")
        print(json.dumps({
            'projects': list(data.get('projects', {}).keys()),
            'well_sessions': list(data.get('wells', {}).keys()),
            'workspace': data.get('workspace', {}).get('root')
        }, indent=2))
        return True
    
    # Create backup
    if not backup_json_file():
        return False
    
    print("\n🚀 Starting migration...\n")
    
    # Initialize SQLite
    from sqlite_storage import SQLiteStorageService, _get_connection
    sqlite_service = SQLiteStorageService()
    conn = _get_connection()
    cursor = conn.cursor()
    
    migrated_counts = {
        'projects': 0,
        'layouts': 0,
        'wells': 0,
        'well_sessions': 0
    }
    
    try:
        # Migrate workspace config
        workspace = data.get('workspace', {})
        if workspace:
            cursor.execute("""
                UPDATE workspace_config 
                SET root_path = ?, last_updated = ?
                WHERE id = 1
            """, (
                workspace.get('root', '/home/runner/workspace/petrophysics-workplace'),
                datetime.utcnow().isoformat()
            ))
            
            current_project = workspace.get('currentProject')
            if current_project:
                cursor.execute("""
                    UPDATE workspace_config 
                    SET current_project_session_id = ?
                    WHERE id = 1
                """, (current_project.get('sessionId'),))
            
            print("✓ Migrated workspace configuration")
        
        # Migrate projects
        for session_id, project in data.get('projects', {}).items():
            cursor.execute("""
                INSERT OR REPLACE INTO projects 
                (session_id, project_path, project_name, active_well, selected_wells, cli_history, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                project.get('projectPath'),
                project.get('projectName'),
                project.get('activeWell'),
                json.dumps(project.get('selectedWells', [])),
                project.get('cliHistory', ''),
                datetime.utcnow().isoformat()
            ))
            migrated_counts['projects'] += 1
            
            # Migrate layouts for this project
            saved_layouts = project.get('savedLayouts', {})
            for layout_name, layout_data in saved_layouts.items():
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
                    layout_data.get('savedAt', datetime.utcnow().isoformat())
                ))
                migrated_counts['layouts'] += 1
            
            # Migrate legacy layout if exists and no saved layouts
            if not saved_layouts and 'layout' in project:
                cursor.execute("""
                    INSERT OR REPLACE INTO layouts 
                    (session_id, layout_name, rc_dock_layout, visible_panels, window_links, saved_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    'default',
                    json.dumps(project.get('layout')),
                    json.dumps(project.get('visiblePanels', [])),
                    json.dumps({}),
                    project.get('layoutSavedAt', datetime.utcnow().isoformat())
                ))
                migrated_counts['layouts'] += 1
        
        print(f"✓ Migrated {migrated_counts['projects']} projects")
        print(f"✓ Migrated {migrated_counts['layouts']} layouts")
        
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
                well_session.get('updatedAt', datetime.utcnow().isoformat()),
                well_session.get('expiresAt')
            ))
            migrated_counts['well_sessions'] += 1
            
            # Migrate wells for this session
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
                    well_data.get('lastAccessed', datetime.utcnow().isoformat())
                ))
                migrated_counts['wells'] += 1
        
        print(f"✓ Migrated {migrated_counts['well_sessions']} well sessions")
        print(f"✓ Migrated {migrated_counts['wells']} wells")
        
        # Commit all changes
        conn.commit()
        
        print("\n" + "="*60)
        print("✅ Migration completed successfully!")
        print("="*60)
        print(f"\nMigration Summary:")
        print(f"   Projects:      {migrated_counts['projects']}")
        print(f"   Layouts:       {migrated_counts['layouts']}")
        print(f"   Well Sessions: {migrated_counts['well_sessions']}")
        print(f"   Wells:         {migrated_counts['wells']}")
        print(f"\nBackup saved to: {BACKUP_FILE}")
        print(f"SQLite database: {sqlite_service.db_path if hasattr(sqlite_service, 'db_path') else 'data/petrophysics.db'}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        print(f"   Database changes rolled back")
        print(f"   Original JSON file preserved at: {BACKUP_FILE}")
        raise


def verify_migration():
    """Verify that migration was successful by comparing data"""
    print("\n" + "="*60)
    print("🔍 Verifying Migration")
    print("="*60 + "\n")
    
    # Load JSON data
    json_data = load_json_data()
    if not json_data:
        print("No JSON data to verify against")
        return False
    
    # Initialize SQLite
    from sqlite_storage import SQLiteStorageService, _get_connection
    sqlite_service = SQLiteStorageService()
    conn = _get_connection()
    cursor = conn.cursor()
    
    # Check counts
    cursor.execute("SELECT COUNT(*) FROM projects")
    db_projects = cursor.fetchone()[0]
    json_projects = len(json_data.get('projects', {}))
    
    cursor.execute("SELECT COUNT(*) FROM layouts")
    db_layouts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM well_sessions")
    db_sessions = cursor.fetchone()[0]
    json_sessions = len(json_data.get('wells', {}))
    
    cursor.execute("SELECT COUNT(*) FROM wells")
    db_wells = cursor.fetchone()[0]
    
    print(f"📊 Verification Results:")
    print(f"   Projects:      JSON={json_projects}, DB={db_projects} {'✓' if json_projects == db_projects else '✗'}")
    print(f"   Layouts:       DB={db_layouts}")
    print(f"   Well Sessions: JSON={json_sessions}, DB={db_sessions} {'✓' if json_sessions == db_sessions else '✗'}")
    print(f"   Wells:         DB={db_wells}")
    
    all_match = (json_projects == db_projects and json_sessions == db_sessions)
    
    if all_match:
        print("\n✅ Verification passed - all data migrated correctly!")
    else:
        print("\n⚠️  Verification warning - some counts don't match")
    
    return all_match


def rollback_migration():
    """Rollback migration by restoring JSON backup"""
    if not BACKUP_FILE.exists():
        print("❌ No backup file found to rollback")
        return False
    
    import shutil
    shutil.copy2(BACKUP_FILE, JSON_FILE)
    print(f"✅ Rolled back to backup: {BACKUP_FILE} -> {JSON_FILE}")
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--dry-run":
            migrate_data(dry_run=True)
        elif command == "--verify":
            verify_migration()
        elif command == "--rollback":
            rollback_migration()
        elif command == "--help":
            print("""
JSON to SQLite Migration Tool

Usage:
    python migrate_to_sqlite.py [command]

Commands:
    (no args)    - Run full migration
    --dry-run    - Show what would be migrated without making changes
    --verify     - Verify migration was successful
    --rollback   - Restore JSON backup (undo migration)
    --help       - Show this help message

Examples:
    # Preview migration
    python migrate_to_sqlite.py --dry-run
    
    # Run migration
    python migrate_to_sqlite.py
    
    # Verify it worked
    python migrate_to_sqlite.py --verify
    
    # Rollback if needed
    python migrate_to_sqlite.py --rollback
""")
        else:
            print(f"Unknown command: {command}")
            print("Use --help for usage information")
    else:
        # Run full migration
        if migrate_data():
            verify_migration()
