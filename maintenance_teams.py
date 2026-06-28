"""فرق الصيانة الدورية — تعيين وتوزيع جغرافي (حد أقصى 6 مصاعد/فريق/يوم)."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

from models import MaintenanceTeam, MaintenanceVisit, Technician, db

MAX_VISITS_PER_TEAM_DAY = 6
DEFAULT_CLUSTER_RADIUS_KM = 5.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def location_district(elev, cust=None) -> str:
    """منطقة/موقع الزيارة — أساسها المصعد ثم العميل."""
    if elev and (getattr(elev, 'district', None) or '').strip():
        return elev.district.strip()
    if elev and (getattr(elev, 'building_name', None) or '').strip():
        return elev.building_name.strip()
    if elev and (getattr(elev, 'city', None) or '').strip():
        return elev.city.strip()
    if cust and (getattr(cust, 'district', None) or '').strip():
        return cust.district.strip()
    if cust and (getattr(cust, 'city', None) or '').strip():
        return cust.city.strip()
    return 'غير محدد'


def item_cluster_key(item: dict) -> str:
    """مفتاح تجميع بدون إحداثيات — مبني على موقع المصعد، مع تجميع مصاعد نفس المبنى."""
    elev = item.get('elevator')
    cust = item.get('customer') or (elev.customer if elev else None)
    base = location_district(elev, cust)
    if elev:
        building = (elev.building_name or '').strip()
        address = (elev.address or '').strip()
        if building:
            return f'{base}|{building}'
        if address:
            return f'{base}|{address[:48]}'
    if cust and cust.lat and cust.lng:
        return f'{base}|@{cust.lat},{cust.lng}'
    if elev:
        return f'{base}|elev:{elev.id}'
    return base


def visit_coordinates(v: MaintenanceVisit) -> tuple[float, float] | None:
    elev = v.elevator
    cust = elev.customer if elev else None
    if elev and getattr(elev, 'lat', None) and getattr(elev, 'lng', None):
        return float(elev.lat), float(elev.lng)
    if cust and cust.lat and cust.lng:
        return float(cust.lat), float(cust.lng)
    return None


def item_coordinates(item: dict) -> tuple[float, float] | None:
    elev = item.get('elevator')
    cust = item.get('customer') or (elev.customer if elev else None)
    if elev and getattr(elev, 'lat', None) and getattr(elev, 'lng', None):
        return float(elev.lat), float(elev.lng)
    if cust and cust.lat and cust.lng:
        return float(cust.lat), float(cust.lng)
    return None


def cluster_by_geography(
    items: list,
    *,
    max_size: int = MAX_VISITS_PER_TEAM_DAY,
    max_radius_km: float = DEFAULT_CLUSTER_RADIUS_KM,
    coords_fn,
    district_fn=None,
) -> list[list]:
    """مجموعات متجاورة جغرافياً — مناطق قريبة (مثل الخضراء والشرائع) في مجموعة واحدة."""
    if not items:
        return []

    with_coords: list[tuple[object, float, float]] = []
    by_district: dict[str, list] = defaultdict(list)

    for it in items:
        c = coords_fn(it)
        if c:
            with_coords.append((it, c[0], c[1]))
        else:
            d = (district_fn(it) if district_fn else 'غير محدد') or 'غير محدد'
            by_district[str(d).strip() or 'غير محدد'].append(it)

    chunks: list[list] = []
    unassigned = sorted(with_coords, key=lambda row: (row[1], row[2]))
    while unassigned:
        seed_it, slat, slng = unassigned.pop(0)
        cluster_items = [seed_it]
        cluster_coords = [(slat, slng)]
        while len(cluster_items) < max_size and unassigned:
            clat = sum(c[0] for c in cluster_coords) / len(cluster_coords)
            clng = sum(c[1] for c in cluster_coords) / len(cluster_coords)
            best_i = None
            best_d = max_radius_km + 1
            for i, (_, lat, lng) in enumerate(unassigned):
                d = haversine_km(clat, clng, lat, lng)
                if d < best_d:
                    best_d = d
                    best_i = i
            if best_i is None or best_d > max_radius_km:
                break
            it, lat, lng = unassigned.pop(best_i)
            cluster_items.append(it)
            cluster_coords.append((lat, lng))
        chunks.append(cluster_items)

    for d in sorted(by_district.keys()):
        batch = by_district[d]
        for i in range(0, len(batch), max_size):
            chunks.append(batch[i:i + max_size])

    return chunks


def team_display_label(team: MaintenanceTeam | None) -> str:
    if not team:
        return '— بدون فريق —'
    leader = team.leader or Technician.query.get(team.leader_id)
    leader_name = leader.name if leader else '—'
    return f'{team.name} — {leader_name}'


def team_to_dict(team: MaintenanceTeam) -> dict:
    leader = team.leader or Technician.query.get(team.leader_id)
    assistant = team.assistant
    if team.assistant_id and not assistant:
        assistant = Technician.query.get(team.assistant_id)
    return {
        'id': team.id,
        'code': team.code,
        'name': team.name,
        'label': team_display_label(team),
        'leader_id': team.leader_id,
        'leader_name': leader.name if leader else '—',
        'assistant_id': team.assistant_id,
        'assistant_name': assistant.name if assistant else '',
        'active': bool(team.active),
        'sort_order': team.sort_order or 0,
        'notes': team.notes or '',
    }


def list_active_teams() -> list[MaintenanceTeam]:
    return (
        MaintenanceTeam.query
        .filter_by(active=True)
        .order_by(MaintenanceTeam.sort_order, MaintenanceTeam.name)
        .all()
    )


def list_all_teams() -> list[MaintenanceTeam]:
    return (
        MaintenanceTeam.query
        .order_by(MaintenanceTeam.sort_order, MaintenanceTeam.name)
        .all()
    )


def assign_visit_to_team(visit: MaintenanceVisit, team: MaintenanceTeam) -> None:
    from technician_assignments import sync_visit_technicians

    visit.maintenance_team_id = team.id
    tech_ids = [team.leader_id]
    if team.assistant_id and team.assistant_id != team.leader_id:
        tech_ids.append(team.assistant_id)
    visit.technician_id = team.leader_id
    sync_visit_technicians(visit, tech_ids)


def assign_visits_to_team(
    visit_ids: list[int], team_id: int, plan_month: str = '',
) -> int:
    from operations import _reorder_routes

    team = MaintenanceTeam.query.get(int(team_id))
    if not team or not team.active:
        raise ValueError('الفريق غير موجود أو غير نشط')
    updated = 0
    plan_months: set[str] = set()
    for vid in visit_ids:
        v = MaintenanceVisit.query.get(int(vid))
        if not v:
            continue
        assign_visit_to_team(v, team)
        if plan_month and not v.plan_month:
            v.plan_month = plan_month
        if v.plan_month:
            plan_months.add(v.plan_month)
        updated += 1
    db.session.commit()
    for pm in plan_months:
        _reorder_routes(pm)
    return updated


def assign_district_team(
    plan_month: str,
    district: str,
    team_id: int,
    *,
    only_unassigned: bool = True,
) -> int:
    from operations import _visits_for_plan_month, visit_district_name, _reorder_routes

    team = MaintenanceTeam.query.get(int(team_id))
    if not team or not team.active:
        raise ValueError('الفريق غير موجود أو غير نشط')
    visits = _visits_for_plan_month(plan_month)
    updated = 0
    for v in visits:
        if visit_district_name(v) != district:
            continue
        if only_unassigned and v.maintenance_team_id:
            continue
        assign_visit_to_team(v, team)
        updated += 1
    db.session.commit()
    _reorder_routes(plan_month)
    return updated


def _chunk_geographic(visits: list[MaintenanceVisit], max_size: int = MAX_VISITS_PER_TEAM_DAY) -> list[list[MaintenanceVisit]]:
    """تقسيم زيارات اليوم إلى مجموعات جغرافية متجاورة بحد أقصى max_size."""
    from operations import visit_district_name

    return cluster_by_geography(
        visits,
        max_size=max_size,
        max_radius_km=DEFAULT_CLUSTER_RADIUS_KM,
        coords_fn=visit_coordinates,
        district_fn=visit_district_name,
    )


def _team_day_load(team_day_count: dict[tuple[int, date], int], team_id: int, day: date) -> int:
    return team_day_count.get((team_id, day), 0)


def distribute_plan_to_teams(plan_month: str, *, preview_only: bool = False) -> dict:
    """توزيع زيارات الخطة على الفرق — جغرافياً بحد أقصى 6 مصاعد لكل فريق في اليوم."""
    from operations import _visits_for_plan_month, get_plan, visit_district_name

    teams = list_active_teams()
    if not teams:
        return {'error': 'لا توجد فرق صيانة نشطة — أنشئ فرقاً من «إدارة الفرق» أولاً'}

    visits = [
        v for v in _visits_for_plan_month(plan_month)
        if v.status in ('مجدولة', 'مُرسلة للفني') and not v.maintenance_team_id
    ]
    if not visits:
        current = get_plan(plan_month)
        return {
            'preview': preview_only,
            'plan_month': plan_month,
            'would_assign': 0,
            'current_total': current.get('total', 0),
            'hint': 'لا توجد زيارات غير موزعة على فرق',
            'by_team': [],
        }

    by_day: dict[date, list[MaintenanceVisit]] = defaultdict(list)
    for v in visits:
        if v.visit_date:
            by_day[v.visit_date].append(v)

    assignments: list[tuple[MaintenanceTeam, MaintenanceVisit]] = []
    team_day_count: dict[tuple[int, date], int] = defaultdict(int)
    preview_by_team: dict[int, dict] = defaultdict(lambda: {
        'team_id': 0, 'team': '', 'count': 0, 'days': defaultdict(int),
    })

    for day in sorted(by_day.keys()):
        chunks = _chunk_geographic(by_day[day], MAX_VISITS_PER_TEAM_DAY)
        for chunk in chunks:
            remaining = list(chunk)
            while remaining:
                best_team = None
                best_load = 999
                for team in teams:
                    load = _team_day_load(team_day_count, team.id, day)
                    if load >= MAX_VISITS_PER_TEAM_DAY:
                        continue
                    if load < best_load:
                        best_load = load
                        best_team = team
                if not best_team:
                    break
                space = MAX_VISITS_PER_TEAM_DAY - _team_day_load(team_day_count, best_team.id, day)
                take = remaining[:space]
                for v in take:
                    assignments.append((best_team, v))
                    team_day_count[(best_team.id, day)] += 1
                    if preview_only:
                        entry = preview_by_team[best_team.id]
                        entry['team_id'] = best_team.id
                        entry['team'] = team_display_label(best_team)
                        entry['count'] += 1
                        entry['days'][str(day)] = entry['days'].get(str(day), 0) + 1
                remaining = remaining[space:]

    if preview_only:
        samples = []
        for team, v in assignments[:15]:
            samples.append({
                'team': team_display_label(team),
                'elevator': v.elevator.code if v.elevator else '',
                'visit_date': str(v.visit_date),
                'district': visit_district_name(v),
            })
        by_team_list = []
        for tid, info in preview_by_team.items():
            by_team_list.append({
                'team_id': tid,
                'team': info['team'],
                'count': info['count'],
                'max_per_day': MAX_VISITS_PER_TEAM_DAY,
            })
        by_team_list.sort(key=lambda x: -x['count'])
        unassigned = len(visits) - len(assignments)
        payload = {
            'preview': True,
            'plan_month': plan_month,
            'would_assign': len(assignments),
            'would_skip': unassigned,
            'teams_used': len(by_team_list),
            'by_team': by_team_list,
            'samples': samples,
            'max_per_team_day': MAX_VISITS_PER_TEAM_DAY,
            'geo_radius_km': DEFAULT_CLUSTER_RADIUS_KM,
        }
        if unassigned:
            payload['hint'] = (
                f'تعذّر توزيع {unassigned} زيارة — جميع الفرق ممتلئة (6/يوم). '
                'أضف فرقاً أو غيّر تواريخ الزيارات.'
            )
        return payload

    for team, v in assignments:
        assign_visit_to_team(v, team)
    db.session.commit()

    from operations import _reorder_routes
    _reorder_routes(plan_month)
    result = get_plan(plan_month)
    return {
        **result,
        'assigned': len(assignments),
        'skipped': len(visits) - len(assignments),
        'max_per_team_day': MAX_VISITS_PER_TEAM_DAY,
        'geo_radius_km': DEFAULT_CLUSTER_RADIUS_KM,
    }
