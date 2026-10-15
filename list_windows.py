"""قراءة صفحات القوائم على دفعات. لا يكتب في قاعدة البيانات ولا يحذف سجلات."""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from urllib.parse import urlencode

PAGE_SIZE_OPTIONS = frozenset({10, 20, 50, 100})
PAGE_SIZE = 10


def request_page(args) -> int:
    try:
        page = int(args.get('page') or 1)
    except (TypeError, ValueError):
        page = 1
    return max(1, page)


def request_text(args, key: str = 'q') -> str:
    return (args.get(key) or '').strip()


def request_per_page(args) -> int:
    raw = args.get('per') or args.get('page_size') or args.get('size')
    try:
        n = int(raw) if raw not in (None, '') else PAGE_SIZE
    except (TypeError, ValueError):
        n = PAGE_SIZE
    return n if n in PAGE_SIZE_OPTIONS else PAGE_SIZE


def request_export_all(args) -> bool:
    raw = (args.get('export') or '').strip().lower()
    return raw in ('1', 'true', 'yes', 'all')


def window_rows(rows: list, args) -> list:
    """ترقيم الصفحة للعرض، وكل الصفوف المطابقة عند التصدير."""
    if request_export_all(args):
        return list(rows)
    sliced, _total, _page = page_slice(rows, request_page(args), request_per_page(args))
    return sliced


def apply_query_window(query, args):
    """نفس التقسيم على استعلام SQL، ويتجاوز الحد عند التصدير."""
    if request_export_all(args):
        return query
    page = request_page(args)
    per_page = request_per_page(args)
    return query.offset((page - 1) * per_page).limit(per_page)


HIDE_EXPIRED_COOKIE = 'lc_hide_expired'


def request_hide_expired(args, cookies=None) -> bool:
    """إخفاء المنتهي يبقى بعد مغادرة الصفحة: الرابط أولاً، ثم الكوكي."""
    raw = (args.get('hide_expired') or '').strip().lower()
    if raw in ('1', 'true', 'yes'):
        return True
    if raw in ('0', 'false', 'no'):
        return False
    if cookies is None:
        try:
            from flask import request
            cookies = request.cookies
        except Exception:
            cookies = {}
    return (cookies.get(HIDE_EXPIRED_COOKIE) or '').strip() == '1'


def apply_hide_expired_cookie(response, hide_expired: bool, *, explicit: bool = False):
    """يثبّت الاختيار عند الضغط الصريح، ويقرأه تلقائياً عند الرجوع للعقود."""
    if not explicit:
        return response
    try:
        from flask import request, current_app
        secure = bool(
            current_app.config.get('SESSION_COOKIE_SECURE')
            or request.is_secure
        )
    except Exception:
        secure = False
    if hide_expired:
        response.set_cookie(
            HIDE_EXPIRED_COOKIE, '1',
            max_age=400 * 24 * 3600, path='/', samesite='Lax', secure=secure,
        )
    else:
        response.delete_cookie(HIDE_EXPIRED_COOKIE, path='/')
    return response


def request_sort(
    args,
    allowed: set[str] | frozenset[str],
    *,
    default_col: str = 'code',
    default_dir: str = 'asc',
) -> tuple[str, str]:
    col = (args.get('sort') or default_col).strip()
    if col not in allowed:
        col = default_col
    direction = (args.get('dir') or default_dir).strip().lower()
    if direction not in ('asc', 'desc'):
        direction = default_dir
    return col, direction


def parse_month(value: str | None, today: date | None = None) -> tuple[int, int]:
    today = today or date.today()
    raw = (value or '').strip()
    if len(raw) >= 7 and raw[4] == '-':
        try:
            year, month = int(raw[:4]), int(raw[5:7])
            if 1 <= month <= 12:
                return year, month
        except ValueError:
            pass
    return today.year, today.month


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def list_meta_for(total: int, page: int, *, per_page: int = PAGE_SIZE, extra: dict | None = None) -> dict:
    from flask import request

    total = int(total or 0)
    pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = min(max(1, page), pages)
    base = request.args.to_dict(flat=True)

    def link(target: int) -> str:
        query = dict(base)
        query['page'] = str(target)
        return request.path + '?' + urlencode(query)

    meta = {
        'server': True,
        'total': total,
        'page': page,
        'pages': pages,
        'per_page': per_page,
        'prev': link(page - 1) if page > 1 else '',
        'next': link(page + 1) if page < pages else '',
        'q': request_text(request.args),
    }
    if extra:
        meta.update(extra)
    return meta


def page_slice(rows: list, page: int, per_page: int = PAGE_SIZE):
    total = len(rows)
    pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = min(max(1, page), pages)
    start = (page - 1) * per_page
    return rows[start:start + per_page], total, page


def maintenance_visit_query(*, month: str | None, include_open: bool, all_months: bool = False):
    """كل الزيارات افتراضياً. شهر محدد يضيّق القائمة، ومع include_open تبقى غير المكتملة ظاهرة."""
    from sqlalchemy import and_, or_
    from sqlalchemy.orm import joinedload

    from models import Elevator, MaintenanceVisit
    from operations import VISIT_DONE, exclude_fault_visits
    from tenant_scope import tenant_query

    year, month_no = parse_month(month)
    start, end = month_bounds(year, month_no)
    label = f'{year:04d}-{month_no:02d}'
    query = exclude_fault_visits(
        tenant_query(MaintenanceVisit).options(
            joinedload(MaintenanceVisit.elevator).joinedload(Elevator.customer),
            joinedload(MaintenanceVisit.technician),
            joinedload(MaintenanceVisit.contract),
            joinedload(MaintenanceVisit.linked_fault),
        )
    )
    if all_months:
        return query, label
    in_month = and_(
        MaintenanceVisit.visit_date >= start,
        MaintenanceVisit.visit_date <= end,
    )
    if include_open:
        query = query.filter(or_(
            in_month,
            ~MaintenanceVisit.status.in_(VISIT_DONE + ('ملغية',)),
        ))
    else:
        query = query.filter(in_month)
    return query, label
