import subprocess
from pathlib import Path

content = subprocess.check_output(['git', 'show', 'HEAD:static/liftcore-i18n-ui.js']).decode('utf-8')
content = content.replace('window.__LC_I18N_UI = {', 'window.__LC_TRANSLATIONS = {', 1)
content = content.replace(
    '/**\n * LiftCore — قاموس ترجمة موسّع (يُدمج مع liftcore-i18n.js)\n */',
    '/**\n * LiftCore — ملف الترجمة المركزي (عربي → English)\n * كل النصوص تُضاف هنا؛ المحرك يطبّقها على كل الصفحات.\n */',
)

maintenance = """
  /* — الصيانة — */
  'خريطة اليوم': "Today's Map",
  'جوال الفني': 'Technician Mobile',
  'تخطيط الشهر': 'Month Planning',
  'شهر العرض': 'Display Month',
  'الشهر التالي': 'Next Month',
  'إلغاء التصفية': 'Clear Filter',
  'لا تنبيهات عاجلة — الوضع طبيعي': 'No urgent alerts — status normal',
  'عرض زيارات اليوم في الجدول': "Show today's visits in table",
  'عرض الزيارات الجارية': 'Show in-progress visits',
  'عرض الزيارات المتأخرة': 'Show overdue visits',
  'عرض المكتملة اليوم': 'Show completed today',
  'عرض زيارات هذا الشهر': 'Show this month visits',
  'اضغط لعرض الزيارات في الجدول': 'Click to show visits in table',
  'مكتملة اليوم': 'Completed Today',
  'متأخرة': 'Overdue',
  'مجدولة': 'Scheduled',
  'ملغية': 'Cancelled',
  'زيارة طارئة': 'Emergency Visit',
  'زيارة متابعة': 'Follow-up Visit',
  'زيارة فحص': 'Inspection Visit',
  'منخفضة': 'Low',
  'متوسطة': 'Medium',
  'عادية': 'Normal',
  'عالية': 'High',
  'بحث بالكود أو العميل أو الفني...': 'Search by code, client, or technician...',
  'زيارات اليوم على الخريطة': "Today's Visits on Map",
  'يُعرض اسم العميل في يوم الزيارة': 'Client name shown on visit day',
  'متأخرة / ملغية': 'Overdue / Cancelled',
  'إضافة زيارة صيانة جديدة': 'Add New Maintenance Visit',
  'بيانات الزيارة': 'Visit Details',
  'كود الزيارة': 'Visit Code',
  'يُولَّد تلقائياً': 'Auto-generated',
  'الربط بالبيانات': 'Linked Data',
  'تاريخ الزيارة': 'Visit Date',
  'وقت الزيارة': 'Visit Time',
  'بيان قطع الغيار': 'Parts Billing',
  'تصدير': 'Export',
  'إجراءات': 'Actions',
"""

needle = "  'All Statuses': 'All Statuses',\n};"
if needle in content:
    content = content.replace(needle, "  'All Statuses': 'All Statuses'," + maintenance + "};\nwindow.__LC_I18N_UI = window.__LC_TRANSLATIONS;\n")
else:
    raise SystemExit('needle not found')

Path('static/liftcore-translations.js').write_text(content, encoding='utf-8', newline='\n')
print('written', len(content))
