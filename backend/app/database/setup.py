# backend/app/database/setup.py
import sys
import os

# Add parent directory to path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config import DATABASE_URL

def create_tables():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Get path to schema.sql
    schema_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "schema.sql"
    )
    
    with open(schema_path, 'r') as f:
        cursor.execute(f.read())
    
    cursor.close()
    conn.close()
    print("✅ All tables created successfully")

if __name__ == "__main__":
    create_tables()