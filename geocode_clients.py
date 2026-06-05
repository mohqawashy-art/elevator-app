"""
تحديث إحداثيات GPS للعملاء (OpenStreetMap / Google).
تشغيل: python geocode_clients.py
"""

from app import app, db
from geocode import geocode_customer
from models import Customer


def main():
    with app.app_context():
        customers = Customer.query.order_by(Customer.id).all()
        ok = fail = skip = 0
        for c in customers:
            if c.lat and c.lng:
                try:
                    float(c.lat)
                    float(c.lng)
                    skip += 1
                    continue
                except (TypeError, ValueError):
                    pass
            if geocode_customer(c, delay=1.05):
                ok += 1
            else:
                fail += 1
        db.session.commit()
        print(f"تم: {ok} | كان لديه GPS: {skip} | فشل: {fail}")
        if fail:
            print("تلميح: راجع حقول الحي والمدينة للعملاء الذين فشل تحديد موقعهم.")


if __name__ == "__main__":
    main()
