# app/customers.py
# Functions للتعامل مع جدول العملاء في قاعدة البيانات

import sqlite3
from app.database import DB_PATH


# ========================================
# CREATE - إضافة
# ========================================

def add_customer(code, name, **kwargs):
    """
    تضيف عميل جديد لقاعدة البيانات.
    
    المطلوب:
        code: كود العميل (مثل C-0001) - يجب أن يكون فريد
        name: اسم العميل
    
    الاختياري (kwargs):
        city, district, address, phone, national_id,
        elevator_count, email, status, registration_date,
        notes, revenue
    
    ترجع: id العميل الجديد (رقم تلقائي)
    
    مثال:
        new_id = add_customer(
            "C-0001", "فندق الزمزم",
            city="مكة", phone="0501234567", elevator_count=4
        )
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


# ========================================
# READ - قراءة
# ========================================

def get_customer_by_code(code):
    """
    ترجع بيانات عميل بالكود.
    
    code: كود العميل
    
    ترجع: dict بكل البيانات، أو None لو العميل مش موجود
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM customers WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def get_all_customers():
    """
    ترجع كل العملاء، مرتبين بالكود.
    
    ترجع: لستة من dictionaries
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM customers ORDER BY code")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def count_customers():
    """ترجع عدد العملاء الإجمالي في القاعدة."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM customers")
    count = cursor.fetchone()[0]
    conn.close()
    
    return count


def search_by_name(name_part):
    """
    تبحث عن عملاء بجزء من الاسم (بحث جزئي).
    
    name_part: نص للبحث (ولو جزء من الاسم)
    
    ترجع: لستة من العملاء اللي اسمهم يحتوي على النص ده
    
    مثال:
        search_by_name("الزمزم")  # كل اللي فيهم "الزمزم"
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM customers WHERE name LIKE ? ORDER BY name",
        (f"%{name_part}%",)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


# ========================================
# UPDATE - تحديث
# ========================================

def update_customer(code, **kwargs):
    """
    تحدّث بيانات عميل موجود.
    
    code: كود العميل (المطلوب التحديث له)
    **kwargs: الحقول اللي عايز تغيرها
    
    ترجع: True لو اتحدث بنجاح، False لو العميل مش موجود
    
    مثال:
        update_customer("C-0001", phone="0599999999", city="جدة")
    """
    if not kwargs:
        return False  # مفيش حاجة نغيرها
    
    # نبني SET clause ديناميكياً
    # مثلاً: "phone = ?, city = ?"
    set_clauses = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    
    # القيم + الكود في الآخر للـ WHERE
    values = tuple(kwargs.values()) + (code,)
    
    sql = f"UPDATE customers SET {set_clauses} WHERE code = ?"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(sql, values)
    updated = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return updated


# ========================================
# DELETE - حذف
# ========================================

def delete_customer(code):
    """
    تحذف عميل بالكود.
    
    code: كود العميل
    
    ترجع: True لو اتحذف، False لو العميل مش موجود
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM customers WHERE code = ?", (code,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted