"""
Migration script to restructure the database:
1. Rename project_wells table to wells
2. Update schema to new format
3. Remove app_info and window_state tables
4. Remove selectedLogs from data
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_FILE = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"


def migrate_database():
    """Perform database migration"""
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    print("[Migration] Starting database migration...")
    
    # Step 1: Check if old project_wells table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_wells'")
    if cursor.fetchone():
        print("[Migration] Found project_wells table, migrating data...")
        
        # Create new wells table with updated schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wells_new (
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
        
        # Migrate data from old project_wells to new wells table
        cursor.execute("""
            SELECT 
                well_name, 
                project_path, 
                serialized_data,
                created_at,
                updated_at
            FROM project_wells
        """)
        
        rows = cursor.fetchall()
        migrated_count = 0
        
        for row in rows:
            well_name, project_path, serialized_data, created_at, updated_at = row
            
            # Generate project_session from project_path
            import hashlib
            hash_val = hashlib.md5(project_path.encode()).hexdigest()
            project_session = f"project_{hash_val}"
            
            # Extract project_name from path
            project_name = Path(project_path).name if project_path else "unknown"
            
            # Remove selectedLogs from datasets
            try:
                data = json.loads(serialized_data) if serialized_data else {}
                if 'datasets' in data:
                    for dataset in data.get('datasets', []):
                        if isinstance(dataset, dict) and 'selectedLogs' in dataset:
                            del dataset['selectedLogs']
                
                cleaned_data = json.dumps(data)
            except Exception as e:
                print(f"[Migration] Error cleaning data for {well_name}: {e}")
                cleaned_data = serialized_data
            
            # Insert into new table
            try:
                cursor.execute("""
                    INSERT INTO wells_new 
                    (project_session, project_name, project_path, well_name, datasets, created_date, updated_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (project_session, project_name, project_path, well_name, cleaned_data, created_at, updated_at))
                migrated_count += 1
            except sqlite3.IntegrityError:
                print(f"[Migration] Skipping duplicate well: {well_name} in {project_path}")
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE IF EXISTS project_wells")
        cursor.execute("ALTER TABLE wells_new RENAME TO wells")
        
        print(f"[Migration] Migrated {migrated_count} wells to new schema")
    else:
        print("[Migration] project_wells table not found, creating new wells table...")
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
    
    # Step 2: Remove app_info table if exists
    cursor.execute("DROP TABLE IF EXISTS app_info")
    print("[Migration] Removed app_info table")
    
    # Step 3: Remove window_state table if exists
    cursor.execute("DROP TABLE IF EXISTS window_state")
    print("[Migration] Removed window_state table")
    
    # Step 4: Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_project_session ON wells(project_session)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_project_path ON wells(project_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_well_name ON wells(well_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wells_composite ON wells(project_path, well_name)")
    
    conn.commit()
    conn.close()
    
    print("[Migration] Database migration completed successfully!")


if __name__ == "__main__":
    migrate_database()
