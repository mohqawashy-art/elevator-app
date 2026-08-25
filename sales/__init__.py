#!/usr/bin/env python3
"""موديول المبيعات — عروض التركيب والصيانة."""
from __future__ import annotations

from flask import Blueprint

sales_bp = Blueprint('sales', __name__, url_prefix='/sales')


def register_sales_module(app):
    from sales import routes  # noqa: F401
    app.register_blueprint(sales_bp)
