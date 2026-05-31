# app/customers.py
# Functions للتعامل مع جدول العملاء

import sqlite3
from app.database import DB_PATH


def add_customer(code, name, **kwargs):
    """
    تضيف عميل جديد لقاعدة البيانات.
    
    المطلوب: code, name
    الاختياري: city, district, address, phone, national_id,
              elevator_count, email, status, registration_date,
              notes, revenue
    
    ترجع id العميل الجديد.
    """
    data = {"code": code, "name": name, **kwargs}
    
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    values = tuple(data.values())
    
    sql = f"INSERT INTO customers ({columns}) VALUES ({placeholders})"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql, values)
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as e:
        raise ValueError(f"خطأ: {e}")
    finally:
        conn.close()


def get_customer_by_code(code):
    """ترجع بيانات عميل بالكود، أو None لو مش موجود."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM customers WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def get_all_customers():
    """ترجع كل العملاء كلستة من dictionaries."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM customers ORDER BY code")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def count_customers():
    """ترجع عدد العملاء في القاعدة."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM customers")
    count = cursor.fetchone()[0]
    conn.close()
    
    return count


def delete_customer(code):
    """تحذف عميل بالكود. ترجع True لو اتحذف، False لو مش موجود."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM customers WHERE code = ?", (code,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted