#!/usr/bin/env python3
"""Diagnose planning district for customer ids (argv)."""
import sys
from datetime import date

from app import app
from models import Contract, ContractElevator, Customer, Elevator, MaintenanceVisit
from operations import (
    _month_bounds,
    _periodic_visit_in_month,
    _planning_site_district,
    list_districts,
    plan_candidates_for_district,
)


def resolve_customers(tokens):
    from sqlalchemy import or_

    out = []
    seen = set()
    for tok in tokens:
        t = (tok or "").strip()
        if not t:
            continue
        rows = []
        if t.isdigit():
            by_id = Customer.query.get(int(t))
            if by_id:
                rows = [by_id]
            if not rows:
                pad = t.zfill(4)
                for pat in (f"C-{pad}", f"C-{t}", f"%-{pad}", f"%-{t}"):
                    q = Customer.query.filter(Customer.code.like(pat)).limit(5).all()
                    rows.extend(q)
        else:
            rows = Customer.query.filter(
                or_(
                    Customer.code.ilike(f"%{t}%"),
                    Customer.name.ilike(f"%{t}%"),
                )
            ).limit(8).all()
        for c in rows:
            if c.id not in seen:
                seen.add(c.id)
                out.append(c)
    return out


def main():
    tokens = sys.argv[1:] or ["34", "22"]
    ym = date.today().strftime("%Y-%m")
    y, m = map(int, ym.split("-"))
    start, end = _month_bounds(y, m)

    with app.app_context():
        print("plan_month", ym)
        districts = list_districts(ym)
        print("districts_count", len(districts))
        for key in ("المعيصم", "حي المعيصm", "الخضراء", "حي الخضراء"):
            if key in districts:
                print("  has", repr(key))
        customers = resolve_customers(tokens)
        if not customers:
            print("No customers matched tokens", tokens)
            return
        for c in customers:
            print("=== Customer id", c.id, "code", c.code, "name", c.name, "===")
            print("  cust district:", repr(c.district), "city:", repr(c.city))
            for ct in Contract.query.filter_by(customer_id=c.id).all():
                print(
                    "  Contract",
                    ct.code,
                    ct.contract_type,
                    "status",
                    ct.status,
                    "end",
                    ct.end_date,
                )
                print(
                    "    contract district:",
                    repr(ct.district),
                    "city:",
                    repr(ct.city),
                )
                links = ContractElevator.query.filter_by(contract_id=ct.id).all()
                link_ids = {lk.elevator_id for lk in links}
                for e in Elevator.query.filter_by(customer_id=c.id).all():
                    on = e.id in link_ids if link_ids else True
                    pd = _planning_site_district(ct, e, c) if on else None
                    print(
                        "    Elev",
                        e.code,
                        "dist",
                        repr(e.district),
                        "on_contract",
                        on,
                        "planning",
                        repr(pd),
                    )
            y, m = map(int, ym.split("-"))
            for e in Elevator.query.filter_by(customer_id=c.id).all():
                v = _periodic_visit_in_month(e.id, y, m)
                if v:
                    print(
                        "    visit in month",
                        v.code,
                        v.visit_date,
                        v.status,
                        "-> excluded from candidates list",
                    )

        target_ids = {c.id for c in customers}
        for dist in districts:
            if dist == "غير محدد":
                continue
            cand = plan_candidates_for_district(ym, dist)
            ids_in = {x.get("customer_id") for x in cand.get("candidates") or []}
            hit = target_ids & ids_in
            if hit:
                print("Candidates in district", repr(dist), "customer_ids", sorted(hit))
        print("--- probe duplicate district labels ---")
        for dist in ("المعيصm", "حي المعيصm", "الخضراء", "حي الخضراء"):
            cand = plan_candidates_for_district(ym, dist)
            ids_in = {x.get("customer_id") for x in cand.get("candidates") or []}
            hit = target_ids & ids_in
            print(
                "filter",
                repr(dist),
                "count",
                cand.get("count"),
                "hits",
                sorted(hit) if hit else [],
            )


if __name__ == "__main__":
    main()
