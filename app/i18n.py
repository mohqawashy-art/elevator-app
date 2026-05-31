# app/i18n.py
# نظام الترجمة - Internationalization System
# Bilingual support: Arabic and English

# اللغة الحالية - default Arabic
_current_language = "ar"


TRANSLATIONS = {
    "ar": {
        # ===== عام =====
        "app_name": "نظام إدارة المصاعد",
        "yes": "نعم",
        "no": "لا",
        "save": "حفظ",
        "cancel": "إلغاء",
        "delete": "حذف",
        "edit": "تعديل",
        "search": "بحث",
        "add": "إضافة",
        "back": "رجوع",
        "exit": "خروج",
        
        # ===== أعمدة جدول العملاء =====
        "code": "الكود",
        "name": "الاسم",
        "city": "المدينة",
        "district": "الحي",
        "address": "العنوان",
        "phone": "الجوال",
        "national_id": "رقم الهوية",
        "elevator_count": "عدد المصاعد",
        "email": "البريد الإلكتروني",
        "status": "الحالة",
        "registration_date": "تاريخ التسجيل",
        "notes": "ملاحظات",
        "revenue": "الإيرادات",
        
        # ===== حالات العميل =====
        "status_active": "نشط",
        "status_inactive": "غير نشط",
        "status_suspended": "معلق",
        
        # ===== رسائل النظام =====
        "customer_added": "تم إضافة العميل بنجاح",
        "customer_updated": "تم تحديث بيانات العميل",
        "customer_deleted": "تم حذف العميل",
        "customer_not_found": "العميل غير موجود",
        "customer_exists": "العميل موجود من قبل",
        "operation_success": "تمت العملية بنجاح",
        "operation_failed": "فشلت العملية",
        "field_required": "هذا الحقل مطلوب",
        "no_customers": "لا يوجد عملاء بعد",
    },
    
    "en": {
        # ===== General =====
        "app_name": "Elevator Management System",
        "yes": "Yes",
        "no": "No",
        "save": "Save",
        "cancel": "Cancel",
        "delete": "Delete",
        "edit": "Edit",
        "search": "Search",
        "add": "Add",
        "back": "Back",
        "exit": "Exit",
        
        # ===== Customer table columns =====
        "code": "Code",
        "name": "Name",
        "city": "City",
        "district": "District",
        "address": "Address",
        "phone": "Phone",
        "national_id": "National ID",
        "elevator_count": "Number of Elevators",
        "email": "Email",
        "status": "Status",
        "registration_date": "Registration Date",
        "notes": "Notes",
        "revenue": "Revenue",
        
        # ===== Customer statuses =====
        "status_active": "Active",
        "status_inactive": "Inactive",
        "status_suspended": "Suspended",
        
        # ===== System messages =====
        "customer_added": "Customer added successfully",
        "customer_updated": "Customer updated successfully",
        "customer_deleted": "Customer deleted",
        "customer_not_found": "Customer not found",
        "customer_exists": "Customer already exists",
        "operation_success": "Operation successful",
        "operation_failed": "Operation failed",
        "field_required": "This field is required",
        "no_customers": "No customers yet",
    }
}


def set_language(lang):
    """
    يغير اللغة الحالية.
    Sets the current language.
    
    lang: 'ar' or 'en'
    """
    global _current_language
    if lang in TRANSLATIONS:
        _current_language = lang
        return True
    return False


def get_language():
    """
    يرجع اللغة الحالية.
    Returns the current language code.
    """
    return _current_language


def t(key):
    """
    يرجع الترجمة للمفتاح في اللغة الحالية.
    Returns translation for given key in current language.
    
    لو المفتاح مش موجود، يرجع المفتاح نفسه (آمن).
    If key not found, returns the key itself (safe fallback).
    """
    return TRANSLATIONS[_current_language].get(key, key)