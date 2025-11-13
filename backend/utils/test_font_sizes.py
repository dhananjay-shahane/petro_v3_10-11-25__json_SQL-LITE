"""
Test script to verify font sizes are saved and retrieved from SQLite layouts table
"""

import sqlite3
import json
from pathlib import Path

DB_FILE = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"

def check_font_sizes_in_database():
    """Check what font_sizes data exists in the layouts table"""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=" * 80)
    print("CHECKING FONT SIZES IN LAYOUTS TABLE")
    print("=" * 80)
    
    # Get all layouts with their font sizes
    cursor.execute("""
        SELECT 
            l.session_id,
            l.layout_name,
            l.font_sizes,
            l.saved_at,
            p.project_path,
            p.project_name
        FROM layouts l
        LEFT JOIN projects p ON l.session_id = p.session_id
        ORDER BY l.saved_at DESC
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("\n⚠️  No layouts found in database")
    else:
        print(f"\n✅ Found {len(rows)} layout(s)\n")
        
        for row in rows:
            print(f"Project: {row['project_name']} ({row['project_path']})")
            print(f"Layout Name: {row['layout_name']}")
            print(f"Session ID: {row['session_id']}")
            print(f"Saved At: {row['saved_at']}")
            
            # Parse and display font sizes
            if row['font_sizes']:
                try:
                    font_sizes = json.loads(row['font_sizes'])
                    print(f"Font Sizes: {json.dumps(font_sizes, indent=2)}")
                except Exception as e:
                    print(f"Font Sizes (raw): {row['font_sizes']}")
                    print(f"  Error parsing: {e}")
            else:
                print("Font Sizes: NULL or empty")
            
            print("-" * 80)
    
    conn.close()
    print("\n")


if __name__ == "__main__":
    check_font_sizes_in_database()
