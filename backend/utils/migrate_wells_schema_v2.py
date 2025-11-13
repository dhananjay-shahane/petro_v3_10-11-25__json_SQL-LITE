"""
Safe database migration script with transaction safety and backups
Implements the approved architecture:
1. Backup database
2. Rename wells -> session_wells
3. Rename project_wells -> wells with new schema
4. Remove selectedLogs from data
5. Drop app_info and window_state tables
"""

import sqlite3
import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime


DB_FILE = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"
BACKUP_DIR = Path(__file__).parent.parent.parent / "data" / "backups"


def backup_database():
    """Create a timestamped backup of the database"""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"petrophysics_backup_{timestamp}.db"
    
    if DB_FILE.exists():
        shutil.copy2(DB_FILE, backup_file)
        print(f"[Backup] Created backup at {backup_file}")
        return backup_file
    return None


def migrate_database(dry_run=False):
    """Perform safe database migration"""
    
    # Step 1: Backup
    backup_file = backup_database()
    if not backup_file and not dry_run:
        print("[Error] Failed to create backup, aborting migration")
        return False
    
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")
        
        print("\n[Migration] Step 1: Creating legacy backup tables...")
        
        # Create legacy copies for rollback
        cursor.execute("DROP TABLE IF EXISTS project_wells_legacy")
        cursor.execute("CREATE TABLE project_wells_legacy AS SELECT * FROM project_wells")
        cursor.execute("DROP TABLE IF EXISTS wells_legacy")  
        cursor.execute("CREATE TABLE wells_legacy AS SELECT * FROM wells")
        
        print("[Migration] Legacy tables created")
        
        # Step 2: Rename session-based wells table to session_wells
        print("\n[Migration] Step 2: Renaming wells -> session_wells...")
        cursor.execute("ALTER TABLE wells RENAME TO session_wells")
        print("[Migration] Session wells table renamed")
        
        # Step 3: Create new persistent wells table with user-requested schema
        print("\n[Migration] Step 3: Creating new wells table...")
        cursor.execute("""
            CREATE TABLE wells (
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
        
        # Step 4: Migrate data from project_wells_legacy to wells
        print("\n[Migration] Step 4: Migrating data to new wells table...")
        cursor.execute("""
            SELECT 
                well_name,
                project_path,
                serialized_data,
                created_at,
                updated_at
            FROM project_wells_legacy
        """)
        
        rows = cursor.fetchall()
        migrated_count = 0
        cleaned_count = 0
        
        for row in rows:
            well_name = row['well_name']
            project_path = row['project_path']
            serialized_data = row['serialized_data']
            created_at = row['created_at']
            updated_at = row['updated_at']
            
            # Generate project_session from project_path
            if project_path:
                hash_val = hashlib.md5(project_path.encode()).hexdigest()
                project_session = f"project_{hash_val}"
                # Extract project_name from path
                project_name = Path(project_path).name
            else:
                # Handle null paths
                project_session = "project_unknown"
                project_name = "unknown"
            
            # Remove selectedLogs from datasets
            try:
                data = json.loads(serialized_data) if serialized_data else {}
                
                # Clean selectedLogs from datasets
                if 'datasets' in data and isinstance(data['datasets'], list):
                    for dataset in data['datasets']:
                        if isinstance(dataset, dict) and 'selectedLogs' in dataset:
                            del dataset['selectedLogs']
                            cleaned_count += 1
                
                cleaned_data = json.dumps(data)
            except Exception as e:
                print(f"[Warning] Error cleaning data for {well_name}: {e}")
                cleaned_data = serialized_data
            
            # Use default timestamps if missing
            created_date = created_at if created_at else datetime.now().isoformat()
            updated_date = updated_at if updated_at else datetime.now().isoformat()
            
            # Insert into new wells table
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO wells 
                    (project_session, project_name, project_path, well_name, datasets, created_date, updated_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (project_session, project_name, project_path, well_name, cleaned_data, created_date, updated_date))
                migrated_count += 1
            except sqlite3.IntegrityError as e:
                print(f"[Warning] Skipping duplicate well: {well_name} in {project_path} - {e}")
        
        print(f"[Migration] Migrated {migrated_count} wells, cleaned {cleaned_count} selectedLogs entries")
        
        # Step 5: Drop old project_wells table
        print("\n[Migration] Step 5: Dropping old project_wells table...")
        cursor.execute("DROP TABLE IF EXISTS project_wells")
        print("[Migration] Old project_wells table dropped")
        
        # Step 6: Remove app_info table
        print("\n[Migration] Step 6: Removing app_info table...")
        cursor.execute("DROP TABLE IF EXISTS app_info")
        print("[Migration] app_info table removed")
        
        # Step 7: Remove window_state table
        print("\n[Migration] Step 7: Removing window_state table...")
        cursor.execute("DROP TABLE IF EXISTS window_state")
        print("[Migration] window_state table removed")
        
        # Step 8: Update indexes
        print("\n[Migration] Step 8: Creating indexes...")
        cursor.execute("DROP INDEX IF EXISTS idx_wells_session")
        cursor.execute("DROP INDEX IF EXISTS idx_wells_name")
        cursor.execute("DROP INDEX IF EXISTS idx_project_wells_path")
        cursor.execute("DROP INDEX IF EXISTS idx_project_wells_name")
        cursor.execute("DROP INDEX IF EXISTS idx_project_wells_composite")
        
        # New indexes for session_wells
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_wells_session ON session_wells(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_wells_name ON session_wells(well_name)")
        
        # New indexes for persistent wells table
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_project_session ON wells(project_session)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_project_path ON wells(project_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_well_name ON wells(well_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_composite ON wells(project_path, well_name)")
        
        print("[Migration] Indexes created")
        
        if dry_run:
            print("\n[Dry Run] Rolling back transaction (no changes made)")
            cursor.execute("ROLLBACK")
            return True
        else:
            # Commit transaction
            cursor.execute("COMMIT")
            print("\n[Migration] ✅ Migration completed successfully!")
            print(f"[Migration] Backup saved at: {backup_file}")
            return True
            
    except Exception as e:
        print(f"\n[Error] Migration failed: {e}")
        cursor.execute("ROLLBACK")
        print("[Rollback] Transaction rolled back, database unchanged")
        return False
    finally:
        conn.close()


def verify_migration():
    """Verify the migration was successful"""
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    print("\n[Verification] Checking migrated database...")
    
    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"[Verification] Tables: {', '.join(tables)}")
    
    # Check wells table schema
    cursor.execute("PRAGMA table_info(wells)")
    columns = [(row[1], row[2]) for row in cursor.fetchall()]
    print(f"[Verification] Wells table columns: {columns}")
    
    # Count wells
    cursor.execute("SELECT COUNT(*) FROM wells")
    well_count = cursor.fetchone()[0]
    print(f"[Verification] Total wells in new table: {well_count}")
    
    # Check for selectedLogs in data
    cursor.execute("SELECT well_name, datasets FROM wells LIMIT 5")
    for row in cursor.fetchall():
        data = json.loads(row[1])
        if 'datasets' in data:
            for ds in data['datasets']:
                if 'selectedLogs' in ds:
                    print(f"[Warning] Found selectedLogs in {row[0]}")
    
    conn.close()
    print("[Verification] ✅ Verification complete")


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        print("Running in DRY RUN mode - no changes will be made\n")
    
    print("=" * 70)
    print("SQLite Database Migration - Wells Schema Restructuring")
    print("=" * 70)
    
    success = migrate_database(dry_run=dry_run)
    
    if success and not dry_run:
        verify_migration()
    elif success and dry_run:
        print("\n✅ Dry run completed - migration would succeed")
    else:
        print("\n❌ Migration failed - check errors above")
        sys.exit(1)
