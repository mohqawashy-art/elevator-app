# app/database.py
# إنشاء قاعدة البيانات وجدول العملاء

import sqlite3
import os

# 0. نتأكد إن فولدر data موجود
os.makedirs("data", exist_ok=True)

# 1. نتصل بقاعدة البيانات (لو مش موجودة، هيعملها!)
conn = sqlite3.connect("data/elevator.db")
print("✅ تم الاتصال بـ data/elevator.db")

# 2. نعمل "مؤشر" يقدر ينفّذ أوامر SQL
cursor = conn.cursor()

# 3. ننشئ جدول العملاء (لو مش موجود)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        phone TEXT,
        district TEXT
    )
""")
print("✅ تم إنشاء جدول customers")

# 4. نحفظ التغييرات في القاعدة
conn.commit()

# 5. نقفل الاتصال
conn.close()
print("✅ تم إنهاء العملية بنجاح!")