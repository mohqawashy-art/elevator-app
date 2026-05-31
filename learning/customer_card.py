# كارت بيانات أول عميل (عمر احمد العمودي)
customer = {
    "name": "عمر احمد العمودي",
    "contract_number": "CN-00001",
    "contract_value": 1800,
    "phone": "0555514201",
    "area": "الشرائع",
    "city": "مكة المكرمة"
}

# طباعة بيانات العميل
print("===== بيانات العميل =====")
print("الاسم:", customer["name"])
print("رقم العقد:", customer["contract_number"])
print("قيمة العقد:", customer["contract_value"], "ريال")
print("الجوال:", customer["phone"])
print("المنطقة:", customer["area"])
print("المدينة:", customer["city"])