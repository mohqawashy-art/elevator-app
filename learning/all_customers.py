# قائمة بأول 3 عملاء عندنا بكل تفاصيلهم
customers = [
    {
        "name": "عمر احمد العمودي",
        "contract_number": "CN-00001",
        "contract_value": 1800,
        "area": "الشرائع"
    },
    {
        "name": "علي جوبير المسعودي",
        "contract_number": "CN-00002",
        "contract_value": 1200,
        "area": "الشرائع"
    },
    {
        "name": "سعد عبيد المطرفى",
        "contract_number": "CN-00003",
        "contract_value": 1300,
        "area": "الشرائع"
    }
]

# طباعة عدد العملاء
print("عدد العملاء:", len(customers))
print()

# حلقة تطبع بيانات كل عميل تلقائياً
for customer in customers:
    print("=====================================")
    print("الاسم:", customer["name"])
    print("رقم العقد:", customer["contract_number"])
    print("قيمة العقد:", customer["contract_value"], "ريال")
    print("المنطقة:", customer["area"])
    # البحث عن العملاء أصحاب العقود الكبيرة
print()
print("===== العملاء أصحاب العقود الكبيرة (أكبر من 1500 ريال) =====")
for customer in customers:
    if customer["contract_value"] > 1500:
        print(customer["name"], "- قيمة العقد:", customer["contract_value"], "ريال")
        # حساب إجمالي قيمة العقود تلقائياً
print()
print("===== الإحصائيات =====")

total = 0  # نبدأ من صفر

for customer in customers:
    total = total + customer["contract_value"]

print("إجمالي قيمة العقود:", total, "ريال")
print("متوسط قيمة العقد:", total / len(customers), "ريال")
