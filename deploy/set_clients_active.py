#!/usr/bin/env python3
"""Set all customers to active (نشط). Run on server: python3 deploy/set_clients_active.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app, db
from models import Customer


def main():
    with app.app_context():
        rows = Customer.query.all()
        n = 0
        for c in rows:
            if c.status != 'نشط':
                c.status = 'نشط'
                n += 1
        db.session.commit()
        print(f"Updated {n} / {len(rows)} customers -> نشط")


if __name__ == '__main__':
    main()
