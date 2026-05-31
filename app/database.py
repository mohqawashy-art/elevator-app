# app/database.py
# إعداد قاعدة البيانات وإنشاء الجداول

import sqlite3
import os

DB_PATH = "data/elevator.db"


def setup_database():
    """ينشئ قاعدة البيانات وكل الجداول المطلوبة."""
    
    # نتأكد إن فولدر data موجود
    os.makedirs("data", exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # جدول العملاء
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            city TEXT,
            district TEXT,
            address TEXT,
            phone TEXT,
            national_id TEXT,
            elevator_count INTEGER DEFAULT 0,
            email TEXT,
            status TEXT DEFAULT 'active',
            registration_date TEXT,
            notes TEXT,
            revenue REAL DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"✅ قاعدة البيانات جاهزة: {DB_PATH}")


if __name__ == "__main__":
    setup_database()