"""
Database schema migration script for requested changes
- Add total_wells column to wells table
- Add selected_dataset column to wells and session_wells tables
- Add font_sizes column to layouts table
- Remove legacy tables (well_legacy, project_wells_legacy)
"""

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"


def migrate_database():
    """Apply schema migrations"""
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    print("Starting database schema migration...")
    
    try:
        # 1. Add total_wells column to wells table if it doesn't exist
        print("1. Adding total_wells column to wells table...")
        try:
            cursor.execute("ALTER TABLE wells ADD COLUMN total_wells INTEGER DEFAULT 0")
            print("   ✓ Added total_wells column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ⚠ total_wells column already exists, skipping")
            else:
                raise
        
        # 2. Add selected_dataset column to wells table
        print("2. Adding selected_dataset column to wells table...")
        try:
            cursor.execute("ALTER TABLE wells ADD COLUMN selected_dataset TEXT")
            print("   ✓ Added selected_dataset column to wells table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ⚠ selected_dataset column already exists in wells, skipping")
            else:
                raise
        
        # 3. Add selected_dataset column to session_wells table
        print("3. Adding selected_dataset column to session_wells table...")
        try:
            cursor.execute("ALTER TABLE session_wells ADD COLUMN selected_dataset TEXT")
            print("   ✓ Added selected_dataset column to session_wells table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ⚠ selected_dataset column already exists in session_wells, skipping")
            else:
                raise
        
        # 4. Verify projects table has active_well column (should already exist)
        print("4. Verifying projects table has active_well column...")
        cursor.execute("PRAGMA table_info(projects)")
        columns = [col[1] for col in cursor.fetchall()]
        if "active_well" in columns:
            print("   ✓ active_well column exists in projects table")
        else:
            cursor.execute("ALTER TABLE projects ADD COLUMN active_well TEXT")
            print("   ✓ Added active_well column to projects table")
        
        # 5. Add font_sizes column to layouts table
        print("5. Adding font_sizes column to layouts table...")
        try:
            cursor.execute("ALTER TABLE layouts ADD COLUMN font_sizes TEXT")
            print("   ✓ Added font_sizes column to layouts table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ⚠ font_sizes column already exists, skipping")
            else:
                raise
        
        # 6. Remove legacy tables if they exist
        print("6. Removing legacy tables...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        if "well_legacy" in existing_tables:
            cursor.execute("DROP TABLE well_legacy")
            print("   ✓ Dropped well_legacy table")
        else:
            print("   ⚠ well_legacy table doesn't exist, skipping")
        
        if "project_wells_legacy" in existing_tables:
            cursor.execute("DROP TABLE project_wells_legacy")
            print("   ✓ Dropped project_wells_legacy table")
        else:
            print("   ⚠ project_wells_legacy table doesn't exist, skipping")
        
        # Commit all changes
        conn.commit()
        print("\n✅ Database migration completed successfully!")
        
        # Show updated schema
        print("\n📋 Updated tables schema:")
        for table in ['wells', 'session_wells', 'projects', 'layouts']:
            print(f"\n{table}:")
            cursor.execute(f"PRAGMA table_info({table})")
            for col in cursor.fetchall():
                print(f"  - {col[1]} ({col[2]})")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
