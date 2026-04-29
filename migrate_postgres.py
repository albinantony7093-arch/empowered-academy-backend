#!/usr/bin/env python3
"""
Migration script to add new columns to the PostgreSQL users table.
"""

import os
import sys
sys.path.append('.')

from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate_users_table():
    print("Connecting to PostgreSQL database...")
    
    try:
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            # Check current table structure
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            existing_columns = [col[0] for col in columns]
            
            print("Current columns:", existing_columns)
            
            # Define new columns to add
            new_columns = [
                ("phone_number", "VARCHAR"),
                ("date_of_birth", "DATE"),
                ("gender", "VARCHAR"),
                ("target_exam", "VARCHAR"),
                ("level", "VARCHAR"),
                ("preferred_subjects", "TEXT"),
                ("study_goal", "TEXT")
            ]
            
            # Add missing columns
            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        print(f"Added column: {col_name}")
                    except Exception as e:
                        print(f"Error adding column {col_name}: {e}")
                        conn.rollback()
            
            print("Migration completed!")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    migrate_users_table()