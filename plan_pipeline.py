"""مسار واحد لتخطيط الصيانة: توليد + توزيع جغرافي على الفرق."""

from __future__ import annotations

from maintenance_teams import (
    DEFAULT_CLUSTER_RADIUS_KM,
    MAX_VISITS_PER_TEAM_DAY,
    distribute_plan_to_teams,
    list_active_teams,
    team_to_dict,
    visit_coordinates,
)
from operations import generate_monthly_plan, get_plan, _visits_for_plan_month


def _truthy(val, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).lower() in ('1', 'true', 'yes', 'on')


def get_plan_readiness(plan_month: str) -> dict:
    teams = list_active_teams()
    visits = _visits_for_plan_month(plan_month)
    pending = [
        v for v in visits
        if v.status in ('مجدولة', 'مُرسلة للفني') and not v.maintenance_team_id
    ]
    with_coords = sum(1 for v in pending if visit_coordinates(v))
    return {
        'plan_month': plan_month,
        'teams_count': len(teams),
        'teams': [team_to_dict(t) for t in teams],
        'plan_visits_total': len(visits),
        'unassigned_visits': len(pending),
        'visits_with_coords': with_coords,
        'coords_missing': max(0, len(pending) - with_coords),
        'teams_ready': len(teams) > 0,
        'max_per_team_day': MAX_VISITS_PER_TEAM_DAY,
        'geo_radius_km': DEFAULT_CLUSTER_RADIUS_KM,
    }


def _build_summary_ar(
    plan_month: str,
    readiness: dict,
    gen: dict,
    dist: dict | None,
    *,
    after_confirm: bool = False,
) -> list[str]:
    lines: list[str] = []
    lines.append(f'شهر الخطة: {plan_month}')

    if readiness['teams_count']:
        lines.append(f'الفرق: {readiness["teams_count"]} فريق نشط')
    else:
        lines.append('تنبيه: لا توجد فرق — أنشئها من الفنيين ← فرق الصيانة')

    if after_confirm:
        created = gen.get('created', 0)
        linked = gen.get('linked', 0)
        lines.append(f'تم التوليد: {created} زيارة جديدة' + (f' + ربط {linked}' if linked else ''))
        assigned = gen.get('teams_assigned', dist.get('assigned', 0) if dist else 0)
        skipped = gen.get('teams_skipped', dist.get('skipped', 0) if dist else 0)
        lines.append(f'تم التوزيع: {assigned} زيارة على الفرق' + (f' (تعذّر {skipped})' if skipped else ''))
    else:
        would_create = gen.get('would_create', 0)
        would_link = gen.get('would_link', 0)
        elev_scope = gen.get('elevators_in_scope', 0)
        clusters = gen.get('geo_clusters')
        if elev_scope:
            lines.append(f'المصاعد المشمولة: {elev_scope} مصعد (زيارة لكل مصعد)')
        lines.append(
            f'سيُولَّد: {would_create} زيارة'
            + (f' + يُربط {would_link} موجودة' if would_link else '')
        )
        if clusters:
            lines.append(
                f'   تجميع جغرافي: {clusters} مجموعة — حتى {gen.get("max_per_cluster", MAX_VISITS_PER_TEAM_DAY)} مصعد/مجموعة/يوم'
            )
        pending_after = readiness['unassigned_visits'] + would_create
        lines.append(
            f'سيُوزَّع بعد التأكيد: نحو {pending_after} زيارة '
            f'(حد {MAX_VISITS_PER_TEAM_DAY}/فريق/يوم — نطاق ~{DEFAULT_CLUSTER_RADIUS_KM} كم)'
        )
        if readiness['coords_missing'] and pending_after:
            lines.append(
                f'   {readiness["visits_with_coords"]} زيارة بإحداثيات — '
                f'{readiness["coords_missing"]} بدون خريطة (يُجمَّعون بحسب موقع المصعد/المبنى)'
            )

    if dist and not after_confirm:
        would = dist.get('would_assign', 0)
        if would and readiness['unassigned_visits']:
            lines.append(f'   معاينة على الزيارات الحالية فقط: {would} زيارة')
        if dist.get('by_team'):
            for row in dist['by_team'][:6]:
                lines.append(f'   · {row.get("team", "—")}: {row.get("count", 0)}')

    if gen.get('hint'):
        lines.append('ملاحظة: ' + str(gen['hint']))
    if gen.get('team_distribution_error'):
        lines.append('تنبيه التوزيع: ' + str(gen['team_distribution_error']))

    return lines


def preview_full_plan(year: int, month: int, *, replace_draft: bool = False) -> dict:
    plan_month = f'{year}-{month:02d}'
    readiness = get_plan_readiness(plan_month)
    gen = generate_monthly_plan(year, month, replace_draft=replace_draft, preview_only=True)
    dist = distribute_plan_to_teams(plan_month, preview_only=True) if readiness['teams_ready'] else {
        'error': 'لا توجد فرق صيانة نشطة',
        'would_assign': 0,
        'by_team': [],
    }
    would_create = gen.get('would_create', 0)
    hint = gen.get('hint') or ''
    no_contracts = hint.startswith('لا توجد عقود')
    has_work = (
        would_create > 0
        or gen.get('would_link', 0) > 0
        or readiness['unassigned_visits'] > 0
    )
    can_run = readiness['teams_ready'] and has_work and not no_contracts
    return {
        'preview': True,
        'plan_month': plan_month,
        'readiness': readiness,
        'generate': gen,
        'distribute': dist,
        'would_distribute_total': readiness['unassigned_visits'] + would_create,
        'can_confirm': can_run,
        'summary_lines': _build_summary_ar(plan_month, readiness, gen, dist, after_confirm=False),
    }


def run_full_plan(year: int, month: int, *, replace_draft: bool = False) -> dict:
    plan_month = f'{year}-{month:02d}'
    readiness = get_plan_readiness(plan_month)
    if not readiness['teams_ready']:
        return {'error': 'لا توجد فرق صيانة — أنشئ فرقاً من الفنيين ← فرق الصيانة ثم أعد المحاولة'}

    gen = generate_monthly_plan(year, month, replace_draft=replace_draft, preview_only=False)
    dist = distribute_plan_to_teams(plan_month, preview_only=False)
    if dist.get('error'):
        gen['team_distribution_error'] = dist['error']
    else:
        gen['teams_assigned'] = dist.get('assigned', 0)
        gen['teams_skipped'] = dist.get('skipped', 0)

    plan = get_plan(plan_month)
    gen.update({
        'total': plan.get('total', gen.get('total')),
        'team_summary': plan.get('team_summary', []),
        'tech_summary': plan.get('tech_summary', []),
        'visits': plan.get('visits', []),
        'confirmed': True,
        'summary_lines': _build_summary_ar(plan_month, readiness, gen, dist, after_confirm=True),
    })
    return gen
