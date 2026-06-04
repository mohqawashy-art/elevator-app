/**
 * LiftCore — ربط التقارير بالبيانات الحقيقية
 * reports_live.js
 * ضع هذا الملف في: static/reports_live.js
 * وأضف في كل صفحة تقرير: <script src="{{ url_for('static', filename='reports_live.js') }}"></script>
 */

// خريطة الـ API لكل تقرير
const REPORT_API = {
  'report-clients':     '/api/reports/clients',
  'report-elevators':   '/api/reports/elevators',
  'report-contracts':   '/api/reports/contracts',
  'report-technicians': '/api/reports/technicians',
  'report-maintenance': '/api/reports/visits',
  'report-faults':      '/api/reports/faults',
  'report-revenues':    '/api/reports/revenues',
  'report-expenses':    '/api/reports/expenses',
  'report-invoices':    '/api/reports/invoices',
  'report-inventory':   '/api/reports/inventory',
  'report-stock':       '/api/reports/stock',
  'report-parts':       '/api/reports/parts',
};

// تحميل البيانات وتحديث الجدول
async function loadReportData(reportId, extraParams = '') {
  const apiUrl = REPORT_API[reportId];
  if (!apiUrl) return;

  try {
    const res = await fetch(apiUrl + (extraParams ? '?' + extraParams : ''));
    const data = await res.json();

    // تحديث عداد السجلات
    const countEl = document.getElementById('report-count');
    if (countEl) countEl.textContent = data.length + ' سجل';

    // تحديث الجدول
    const tbody = document.getElementById('report-tbody');
    if (!tbody || data.length === 0) {
      if (tbody) tbody.innerHTML = `
        <tr><td colspan="20" style="text-align:center;padding:30px;color:var(--text3)">
          لا توجد بيانات
        </td></tr>`;
      return;
    }

    // بناء الصفوف من البيانات
    tbody.innerHTML = data.map(row => {
      const cells = Object.values(row).map(val => {
        if (typeof val === 'number') {
          return `<td style="font-family:var(--font-en)">${val.toLocaleString()}</td>`;
        }
        return `<td>${val}</td>`;
      }).join('');
      return `<tr>${cells}</tr>`;
    }).join('');

    // تحديث الإحصائيات
    updateReportStats(reportId, data);

    // تحديث تاريخ التقرير
    const dateEl = document.getElementById('rpt-date-range');
    if (dateEl) dateEl.textContent = 'تاريخ التقرير: ' + new Date().toLocaleDateString('ar-SA');

  } catch(e) {
    console.log('Report API error:', e);
  }
}

// تحديث الإحصائيات حسب نوع التقرير
function updateReportStats(reportId, data) {
  const statsEls = document.querySelectorAll('.rpt-stat-val');
  if (!statsEls.length) return;

  switch(reportId) {
    case 'report-revenues':
      const totalRev  = data.reduce((s,r) => s + r.total, 0);
      const collected = data.filter(r => r.status === 'محصّل').reduce((s,r) => s + r.total, 0);
      const pending   = data.filter(r => r.status === 'معلق').reduce((s,r) => s + r.total, 0);
      if(statsEls[0]) statsEls[0].textContent = totalRev.toLocaleString() + ' ر.س';
      if(statsEls[1]) statsEls[1].textContent = collected.toLocaleString() + ' ر.س';
      if(statsEls[2]) statsEls[2].textContent = pending.toLocaleString() + ' ر.س';
      if(statsEls[3]) statsEls[3].textContent = data.length;
      break;

    case 'report-expenses':
      const totalExp   = data.reduce((s,e) => s + e.amount, 0);
      const salaries   = data.filter(e => e.expense_type === 'رواتب').reduce((s,e) => s + e.amount, 0);
      const partsExp   = data.filter(e => e.expense_type === 'قطع غيار').reduce((s,e) => s + e.amount, 0);
      if(statsEls[0]) statsEls[0].textContent = totalExp.toLocaleString() + ' ر.س';
      if(statsEls[1]) statsEls[1].textContent = salaries.toLocaleString() + ' ر.س';
      if(statsEls[2]) statsEls[2].textContent = partsExp.toLocaleString() + ' ر.س';
      if(statsEls[3]) statsEls[3].textContent = data.length;
      break;

    case 'report-parts':
      const totalCost   = data.reduce((s,p) => s + p.cost_price, 0);
      const totalSell   = data.reduce((s,p) => s + p.sell_price, 0);
      const totalProfit = data.reduce((s,p) => s + p.profit, 0);
      if(statsEls[0]) statsEls[0].textContent = data.length;
      if(statsEls[1]) statsEls[1].textContent = totalCost.toLocaleString() + ' ر.س';
      if(statsEls[2]) statsEls[2].textContent = totalSell.toLocaleString() + ' ر.س';
      if(statsEls[3]) statsEls[3].textContent = totalProfit.toLocaleString() + ' ر.س';
      break;

    case 'report-inventory':
      const totalVal  = data.reduce((s,i) => s + i.stock_value, 0);
      const lowItems  = data.filter(i => i.order_status === 'منخفض').length;
      const outItems  = data.filter(i => i.order_status === 'نافد').length;
      if(statsEls[0]) statsEls[0].textContent = data.length;
      if(statsEls[1]) statsEls[1].textContent = totalVal.toLocaleString() + ' ر.س';
      if(statsEls[2]) statsEls[2].textContent = lowItems;
      if(statsEls[3]) statsEls[3].textContent = outItems;
      break;

    default:
      if(statsEls[0]) statsEls[0].textContent = data.length;
      break;
  }
}

// تصدير Excel من البيانات الحقيقية
function exportReportExcel(reportId) {
  const apiUrl = REPORT_API[reportId];
  if (!apiUrl) return;

  fetch(apiUrl)
    .then(r => r.json())
    .then(data => {
      if (!data.length) return;
      const headers = Object.keys(data[0]);
      const rows = [headers, ...data.map(r => Object.values(r))];
      const csv = rows.map(r => r.join(',')).join('\n');
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], {type:'text/csv;charset=utf-8'}));
      a.download = reportId + '.csv';
      a.click();
    });
}
