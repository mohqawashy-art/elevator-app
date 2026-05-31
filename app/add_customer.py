# app/add_customer.py
# إضافة عميل لقاعدة البيانات + قراءة كل العملاء

import sqlite3

# 1. نتصل بالقاعدة
conn = sqlite3.connect("data/elevator.db")
cursor = conn.cursor()

# 2. نضيف عميل جديد
cursor.execute("""
    INSERT INTO customers (code, name, phone, district)
    VALUES (?, ?, ?, ?)
""", ("C-1001", "فندق الزمزم", "0501234567", "العزيزية"))

# 3. نحفظ التغيير
conn.commit()
print("✅ تم إضافة العميل!")

# 4. نقرا كل العملاء الموجودين
cursor.execute("SELECT * FROM customers")
all_customers = cursor.fetchall()

print(f"\n📊 عدد العملاء في القاعدة: {len(all_customers)}\n")

for customer in all_customers:
    print(f"   {customer}")

# 5. نقفل الاتصال
conn.close()