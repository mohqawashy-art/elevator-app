# بيانات العميل
customer_name = "عمر احمد العمودي"
contract_number = "CN-00001"
contract_value = 1800

# عرض بيانات العميل
print("اسم العميل:", customer_name)
print("رقم العقد:", contract_number)
print("قيمة العقد:", contract_value, "ريال")

# الحسابات
months_paid = 6
monthly_value = contract_value / 12
total_paid = monthly_value * months_paid

# عرض الحسابات
print("القيمة الشهرية:", monthly_value, "ريال")
print("عدد الشهور المدفوعة:", months_paid)
print("إجمالي المدفوع:", total_paid, "ريال")
