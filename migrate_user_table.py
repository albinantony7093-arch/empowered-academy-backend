#!/usr/bin/env python3
"""
Migration script to add new columns to the users table.
Run this once to update the existing database schema.
"""

import sqlite3
import os

def migrate_users_table():
    # Find the database file
    db_path = None
    possible_paths = [
        'empowered_academy.db',
        'app.db',
        'database.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("No database file found. The new schema will be created when the app starts.")
        return
    
    print(f"Found database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current table structure
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    existing_columns = [col[1] for col in columns]
    
    print("Current columns:", existing_columns)
    
    # Define new columns to add
    new_columns = [
        ("phone_number", "VARCHAR"),
        ("date_of_birth", "DATE"),
        ("gender", "VARCHAR"),
        ("target_exam", "VARCHAR"),
        ("level", "VARCHAR"),
        ("preferred_subjects", "VARCHAR"),
        ("study_goal", "VARCHAR")
    ]
    
    # Add missing columns
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                print(f"Added column: {col_name}")
            except sqlite3.Error as e:
                print(f"Error adding column {col_name}: {e}")
    
    conn.commit()
    conn.close()
    print("Migration completed!")

if __name__ == "__main__":
    migrate_users_table()