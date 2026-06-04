"""
LiftCore — Flask Application
app.py
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from models import db, Customer, Elevator, Contract, ContractElevator, Technician
from models import MaintenanceVisit, Fault, Revenue, Expense, Invoice
from models import InventoryItem, StockMovement, PartsBilling, Settings, User
from datetime import datetime, date
import os

app = Flask(__name__)

# =============================================
# الإعدادات
# =============================================
app.config['SECRET_KEY'] = 'liftcore-secret-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///liftcore.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# إنشاء الجداول عند التشغيل الأول
with app.app_context():
    db.create_all()

# =============================================
# Helper — توليد الكودات التلقائية
# =============================================
def next_code(model, prefix, field='code', digits=4):
    last = model.query.order_by(model.id.desc()).first()
    if not last:
        return f'{prefix}{str(1).zfill(digits)}'
    try:
        num = int(getattr(last, field).replace(prefix, '')) + 1
    except:
        num = model.query.count() + 1
    return f'{prefix}{str(num).zfill(digits)}'

# =============================================
# تسجيل الدخول
# =============================================
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, is_active=True).first()
        if user and user.password_hash == password:  # سنضيف hashing لاحقاً
            session['user_id'] = user.id
            session['username'] = user.full_name
            return redirect(url_for('dashboard'))
        error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =============================================
# الداشبورد
# =============================================
@app.route('/dashboard')
def dashboard():
    stats = {
        'customers':  Customer.query.filter_by(status='نشط').count(),
        'elevators':  Elevator.query.count(),
        'contracts':  Contract.query.filter_by(status='نشط').count(),
        'revenue':    db.session.query(db.func.sum(Revenue.total)).scalar() or 0,
        'faults_open':Fault.query.filter_by(status='مفتوح').count(),
        'visits_done':MaintenanceVisit.query.filter_by(status='مكتملة').count(),
        'technicians':Technician.query.filter_by(status='نشط').count(),
        'parts_profit':db.session.query(db.func.sum(PartsBilling.profit)).scalar() or 0,
    }
    return render_template('dashboard.html', stats=stats)

# =============================================
# العملاء
# =============================================
@app.route('/clients')
def clients():
    customers = Customer.query.order_by(Customer.id.desc()).all()
    return render_template('clients.html', customers=customers)

@app.route('/clients/add', methods=['POST'])
def client_add():
    c = Customer(
        code         = next_code(Customer, 'C-', digits=4),
        name         = request.form['name'],
        city         = request.form.get('city',''),
        district     = request.form.get('district',''),
        address      = request.form.get('address',''),
        phone        = request.form.get('phone',''),
        phone2       = request.form.get('phone2',''),
        email        = request.form.get('email',''),
        contact_person = request.form.get('contact_person',''),
        status       = request.form.get('status','نشط'),
        notes        = request.form.get('notes',''),
    )
    db.session.add(c)
    db.session.commit()
    return redirect(url_for('clients'))

@app.route('/clients/edit/<int:id>', methods=['POST'])
def client_edit(id):
    c = Customer.query.get_or_404(id)
    c.name           = request.form['name']
    c.city           = request.form.get('city','')
    c.district       = request.form.get('district','')
    c.address        = request.form.get('address','')
    c.phone          = request.form.get('phone','')
    c.phone2         = request.form.get('phone2','')
    c.email          = request.form.get('email','')
    c.contact_person = request.form.get('contact_person','')
    c.status         = request.form.get('status','نشط')
    c.notes          = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('clients'))

@app.route('/clients/delete/<int:id>', methods=['POST'])
def client_delete(id):
    c = Customer.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('clients'))

@app.route('/api/clients')
def api_clients():
    customers = Customer.query.all()
    return jsonify([{'id':c.id,'code':c.code,'name':c.name,'city':c.city} for c in customers])

# =============================================
# المصاعد
# =============================================
@app.route('/elevators')
def elevators():
    elevs = Elevator.query.order_by(Elevator.id.desc()).all()
    customers = Customer.query.filter_by(status='نشط').all()
    return render_template('elevators.html', elevators=elevs, customers=customers)

@app.route('/elevators/add', methods=['POST'])
def elevator_add():
    e = Elevator(
        code         = next_code(Elevator, 'EL-', digits=4),
        customer_id  = request.form['customer_id'],
        building_name= request.form.get('building_name',''),
        city         = request.form.get('city',''),
        district     = request.form.get('district',''),
        elev_type    = request.form.get('elev_type',''),
        brand        = request.form.get('brand',''),
        model        = request.form.get('model',''),
        capacity_kg  = request.form.get('capacity_kg') or None,
        floors       = request.form.get('floors') or None,
        serial_number= request.form.get('serial_number',''),
        install_date = datetime.strptime(request.form['install_date'], '%Y-%m-%d').date() if request.form.get('install_date') else None,
        status       = request.form.get('status','نشط'),
        notes        = request.form.get('notes',''),
    )
    db.session.add(e)
    db.session.commit()
    return redirect(url_for('elevators'))
@app.route('/elevators/edit/<int:id>', methods=['POST'])
def elevator_edit(id):
    e = Elevator.query.get_or_404(id)
    e.customer_id   = request.form['customer_id']
    e.building_name = request.form.get('building_name','')
    e.city          = request.form.get('city','')
    e.district      = request.form.get('district','')
    e.elev_type     = request.form.get('elev_type','')
    e.brand         = request.form.get('brand','')
    e.model         = request.form.get('model','')
    e.capacity_kg   = request.form.get('capacity_kg') or None
    e.floors        = request.form.get('floors') or None
    e.serial_number = request.form.get('serial_number','')
    e.status        = request.form.get('status','نشط')
    e.notes         = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('elevators'))

@app.route('/elevators/delete/<int:id>', methods=['POST'])
def elevator_delete(id):
    e = Elevator.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    return redirect(url_for('elevators'))

@app.route('/api/elevators/<int:customer_id>')
def api_elevators_by_customer(customer_id):
    elevs = Elevator.query.filter_by(customer_id=customer_id).all()
    return jsonify([{'id':e.id,'code':e.code,'building':e.building_name} for e in elevs])

# =============================================
# العقود
# =============================================
@app.route('/contracts')
def contracts():
    contracts = Contract.query.order_by(Contract.id.desc()).all()
    customers = Customer.query.filter_by(status='نشط').all()
    return render_template('contracts.html', contracts=contracts, customers=customers)
@app.route('/contracts/edit/<int:id>', methods=['POST'])
def contract_edit(id):
    c = Contract.query.get_or_404(id)
    value = float(request.form.get('value', 0))
    tax_pct = float(request.form.get('tax_pct', 15))
    tax_amount = value * tax_pct / 100
    c.customer_id    = request.form['customer_id']
    c.contract_type  = request.form.get('contract_type','')
    c.start_date     = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    c.end_date       = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    c.value          = value
    c.tax_pct        = tax_pct
    c.tax_amount     = tax_amount
    c.total          = value + tax_amount
    c.payment_terms  = request.form.get('payment_terms','')
    c.invoice_status = request.form.get('invoice_status','غير مدفوع')
    c.status         = request.form.get('status','نشط')
    c.notes          = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('contracts'))

@app.route('/contracts/add', methods=['POST'])
def contract_add():
    value = float(request.form.get('value', 0))
    tax_pct = float(request.form.get('tax_pct', 15))
    tax_amount = value * tax_pct / 100
    total = value + tax_amount
    c = Contract(
        code         = next_code(Contract, 'CN-', digits=5),
        customer_id  = request.form['customer_id'],
        contract_type= request.form.get('contract_type',''),
        start_date   = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date(),
        end_date     = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date(),
        maint_frequency = request.form.get('maint_frequency',''),
        visits_per_month = request.form.get('visits_per_month', 1),
        value        = value,
        tax_pct      = tax_pct,
        tax_amount   = tax_amount,
        total        = total,
        payment_terms= request.form.get('payment_terms',''),
        invoice_status = request.form.get('invoice_status','غير مدفوع'),
        status       = request.form.get('status','نشط'),
        notes        = request.form.get('notes',''),
    )
    db.session.add(c)
    db.session.commit()
    return redirect(url_for('contracts'))

@app.route('/contracts/delete/<int:id>', methods=['POST'])
def contract_delete(id):
    c = Contract.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('contracts'))

# =============================================
# الفنيون
# =============================================
@app.route('/technicians')
def technicians():
    techs = Technician.query.order_by(Technician.id.desc()).all()
    return render_template('technicians.html', technicians=techs)

@app.route('/technicians/add', methods=['POST'])
def technician_add():
    t = Technician(
        code          = next_code(Technician, 'Tech-', digits=3),
        name          = request.form['name'],
        phone         = request.form.get('phone',''),
        job_title     = request.form.get('job_title',''),
        specialization= request.form.get('specialization',''),
        city          = request.form.get('city',''),
        emergency     = request.form.get('emergency') == 'on',
        status        = request.form.get('status','نشط'),
        notes         = request.form.get('notes',''),
    )
    db.session.add(t)
    db.session.commit()
    return redirect(url_for('technicians'))
@app.route('/technicians/edit/<int:id>', methods=['POST'])
def technician_edit(id):
    t = Technician.query.get_or_404(id)
    t.name           = request.form['name']
    t.phone          = request.form.get('phone','')
    t.phone2         = request.form.get('phone2','')
    t.job_title      = request.form.get('job_title','')
    t.specialization = request.form.get('specialization','')
    t.city           = request.form.get('city','')
    t.emergency      = request.form.get('emergency') == 'on'
    t.status         = request.form.get('status','نشط')
    t.notes          = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('technicians'))

@app.route('/technicians/delete/<int:id>', methods=['POST'])
def technician_delete(id):
    t = Technician.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    return redirect(url_for('technicians'))

# =============================================
# زيارات الصيانة
# =============================================
@app.route('/maintenance-visits')
def maintenance_visits():
    visits = MaintenanceVisit.query.order_by(MaintenanceVisit.visit_date.desc()).all()
    elevators = Elevator.query.all()
    technicians = Technician.query.filter_by(status='نشط').all()
    return render_template('maintenance-visits.html', visits=visits, elevators=elevators, technicians=technicians)

@app.route('/maintenance-visits/add', methods=['POST'])
def visit_add():
    v = MaintenanceVisit(
        code          = next_code(MaintenanceVisit, 'VI-', digits=5),
        elevator_id   = request.form['elevator_id'],
        technician_id = request.form.get('technician_id') or None,
        contract_id   = request.form.get('contract_id') or None,
        visit_type    = request.form.get('visit_type','دورية'),
        visit_date    = datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date(),
        visit_time    = request.form.get('visit_time',''),
        priority      = request.form.get('priority','عادية'),
        status        = request.form.get('status','مجدولة'),
        works_done    = request.form.get('works_done',''),
        observations  = request.form.get('observations',''),
        notes         = request.form.get('notes',''),
    )
    db.session.add(v)
    db.session.commit()
    return redirect(url_for('maintenance_visits'))
@app.route('/maintenance-visits/edit/<int:id>', methods=['POST'])
def visit_edit(id):
    v = MaintenanceVisit.query.get_or_404(id)
    v.elevator_id   = request.form['elevator_id']
    v.technician_id = request.form.get('technician_id') or None
    v.visit_type    = request.form.get('visit_type','')
    v.visit_date    = datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date()
    v.visit_time    = request.form.get('visit_time','')
    v.priority      = request.form.get('priority','عادية')
    v.status        = request.form.get('status','مجدولة')
    v.works_done    = request.form.get('works_done','')
    v.observations  = request.form.get('observations','')
    v.notes         = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('maintenance_visits'))

@app.route('/maintenance-visits/delete/<int:id>', methods=['POST'])
def visit_delete(id):
    v = MaintenanceVisit.query.get_or_404(id)
    db.session.delete(v)
    db.session.commit()
    return redirect(url_for('maintenance_visits'))

# =============================================
# الأعطال
# =============================================
@app.route('/faults')
def faults():
    faults = Fault.query.order_by(Fault.reported_at.desc()).all()
    elevators = Elevator.query.all()
    technicians = Technician.query.filter_by(status='نشط').all()
    return render_template('faults.html', faults=faults, elevators=elevators, technicians=technicians)

@app.route('/faults/edit/<int:id>', methods=['POST'])
def fault_edit(id):
    f = Fault.query.get_or_404(id)
    f.elevator_id   = request.form['elevator_id']
    f.technician_id = request.form.get('technician_id') or None
    f.fault_type    = request.form.get('fault_type','')
    f.description   = request.form.get('description','')
    f.priority      = request.form.get('priority','عادية')
    f.status        = request.form.get('status','مفتوح')
    f.resolution    = request.form.get('resolution','')
    f.response_time = request.form.get('response_time','')
    f.billed        = request.form.get('billed') == 'on'
    f.notes         = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('faults'))

@app.route('/faults/add', methods=['POST'])
def fault_add():
    f = Fault(
        code          = next_code(Fault, 'FA-', digits=5),
        elevator_id   = request.form['elevator_id'],
        technician_id = request.form.get('technician_id') or None,
        fault_type    = request.form.get('fault_type',''),
        description   = request.form.get('description',''),
        priority      = request.form.get('priority','عادية'),
        status        = request.form.get('status','مفتوح'),
        notes         = request.form.get('notes',''),
    )
    db.session.add(f)
    db.session.commit()
    return redirect(url_for('faults'))

@app.route('/faults/delete/<int:id>', methods=['POST'])
def fault_delete(id):
    f = Fault.query.get_or_404(id)
    db.session.delete(f)
    db.session.commit()
    return redirect(url_for('faults'))

# =============================================
# الإيرادات
# =============================================
@app.route('/revenues')
def revenues():
    revs = Revenue.query.order_by(Revenue.revenue_date.desc()).all()
    customers = Customer.query.all()
    return render_template('revenues.html', revenues=revs, customers=customers)

@app.route('/revenues/edit/<int:id>', methods=['POST'])
def revenue_edit(id):
    r = Revenue.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    tax = amount * 0.15
    r.customer_id    = request.form.get('customer_id') or None
    r.revenue_date   = datetime.strptime(request.form['revenue_date'], '%Y-%m-%d').date()
    r.revenue_type   = request.form.get('revenue_type','')
    r.payment_method = request.form.get('payment_method','')
    r.amount         = amount
    r.tax_amount     = tax
    r.total          = amount + tax
    r.status         = request.form.get('status','محصّل')
    r.reference      = request.form.get('reference','')
    r.notes          = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('revenues'))

@app.route('/revenues/add', methods=['POST'])
def revenue_add():
    amount = float(request.form.get('amount', 0))
    tax = amount * 0.15
    r = Revenue(
        code           = next_code(Revenue, 'REV-', digits=3),
        customer_id    = request.form.get('customer_id') or None,
        contract_id    = request.form.get('contract_id') or None,
        revenue_date   = datetime.strptime(request.form['revenue_date'], '%Y-%m-%d').date(),
        revenue_type   = request.form.get('revenue_type',''),
        payment_method = request.form.get('payment_method',''),
        amount         = amount,
        tax_amount     = tax,
        total          = amount + tax,
        status         = request.form.get('status','محصّل'),
        reference      = request.form.get('reference',''),
        notes          = request.form.get('notes',''),
    )
    db.session.add(r)
    db.session.commit()
    return redirect(url_for('revenues'))

@app.route('/revenues/delete/<int:id>', methods=['POST'])
def revenue_delete(id):
    r = Revenue.query.get_or_404(id)
    db.session.delete(r)
    db.session.commit()
    return redirect(url_for('revenues'))

# =============================================
# المصروفات
# =============================================
@app.route('/expenses')
def expenses():
    exps = Expense.query.order_by(Expense.expense_date.desc()).all()
    return render_template('expenses.html', expenses=exps)
@app.route('/expenses/edit/<int:id>', methods=['POST'])
def expense_edit(id):
    e = Expense.query.get_or_404(id)
    e.expense_date   = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
    e.expense_type   = request.form.get('expense_type','')
    e.description    = request.form.get('description','')
    e.responsible    = request.form.get('responsible','')
    e.payment_method = request.form.get('payment_method','')
    e.amount         = float(request.form.get('amount', 0))
    e.reference      = request.form.get('reference','')
    e.notes          = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('expenses'))

@app.route('/expenses/add', methods=['POST'])
def expense_add():
    e = Expense(
        code           = next_code(Expense, 'EXP-', digits=3),
        expense_date   = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date(),
        expense_type   = request.form.get('expense_type',''),
        description    = request.form.get('description',''),
        responsible    = request.form.get('responsible',''),
        payment_method = request.form.get('payment_method',''),
        amount         = float(request.form.get('amount', 0)),
        reference      = request.form.get('reference',''),
        notes          = request.form.get('notes',''),
    )
    db.session.add(e)
    db.session.commit()
    return redirect(url_for('expenses'))

@app.route('/expenses/delete/<int:id>', methods=['POST'])
def expense_delete(id):
    e = Expense.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    return redirect(url_for('expenses'))

# =============================================
# الفواتير
# =============================================
@app.route('/invoices')
def invoices():
    invs = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
    customers = Customer.query.all()
    return render_template('invoices.html', invoices=invs, customers=customers)

@app.route('/invoices/edit/<int:id>', methods=['POST'])
def invoice_edit(id):
    i = Invoice.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    tax = amount * 0.15
    i.invoice_type   = request.form.get('invoice_type','فاتورة')
    i.customer_id    = request.form.get('customer_id') or None
    i.invoice_date   = datetime.strptime(request.form['invoice_date'], '%Y-%m-%d').date()
    i.due_date       = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date() if request.form.get('due_date') else None
    i.description    = request.form.get('description','')
    i.amount         = amount
    i.tax_amount     = tax
    i.total          = amount + tax
    i.payment_method = request.form.get('payment_method','')
    i.status         = request.form.get('status','غير مدفوعة')
    i.notes          = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('invoices'))

@app.route('/invoices/add', methods=['POST'])
def invoice_add():
    amount = float(request.form.get('amount', 0))
    tax = amount * 0.15
    i = Invoice(
        code           = next_code(Invoice, 'INV-', digits=4),
        invoice_type   = request.form.get('invoice_type','فاتورة'),
        customer_id    = request.form.get('customer_id') or None,
        contract_id    = request.form.get('contract_id') or None,
        invoice_date   = datetime.strptime(request.form['invoice_date'], '%Y-%m-%d').date(),
        description    = request.form.get('description',''),
        amount         = amount,
        tax_amount     = tax,
        total          = amount + tax,
        payment_method = request.form.get('payment_method',''),
        status         = request.form.get('status','غير مدفوعة'),
        notes          = request.form.get('notes',''),
    )
    db.session.add(i)
    db.session.commit()
    return redirect(url_for('invoices'))

@app.route('/invoices/delete/<int:id>', methods=['POST'])
def invoice_delete(id):
    i = Invoice.query.get_or_404(id)
    db.session.delete(i)
    db.session.commit()
    return redirect(url_for('invoices'))

# =============================================
# الأصناف
# =============================================
@app.route('/inventory')
def inventory():
    items = InventoryItem.query.order_by(InventoryItem.id.desc()).all()
    return render_template('inventory.html', items=items)

@app.route('/inventory/edit/<int:id>', methods=['POST'])
def inventory_edit(id):
    item = InventoryItem.query.get_or_404(id)
    item.name        = request.form['name']
    item.category    = request.form.get('category','')
    item.unit        = request.form.get('unit','قطعة')
    item.current_qty = float(request.form.get('current_qty', 0))
    item.min_qty     = float(request.form.get('min_qty', 0))
    item.buy_price   = float(request.form.get('buy_price', 0))
    item.sell_price  = float(request.form.get('sell_price', 0))
    item.supplier    = request.form.get('supplier','')
    item.notes       = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('inventory'))

@app.route('/inventory/add', methods=['POST'])
def inventory_add():
    item = InventoryItem(
        code       = next_code(InventoryItem, '#', digits=3),
        name       = request.form['name'],
        category   = request.form.get('category',''),
        unit       = request.form.get('unit','قطعة'),
        current_qty= float(request.form.get('current_qty', 0)),
        min_qty    = float(request.form.get('min_qty', 0)),
        buy_price  = float(request.form.get('buy_price', 0)),
        sell_price = float(request.form.get('sell_price', 0)),
        supplier   = request.form.get('supplier',''),
        notes      = request.form.get('notes',''),
    )
    db.session.add(item)
    db.session.commit()
    return redirect(url_for('inventory'))

@app.route('/inventory/delete/<int:id>', methods=['POST'])
def inventory_delete(id):
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('inventory'))

# =============================================
# حركة المخزن
# =============================================
@app.route('/stock-movements')
def stock_movements():
    movements = StockMovement.query.order_by(StockMovement.movement_date.desc()).all()
    items = InventoryItem.query.all()
    technicians = Technician.query.filter_by(status='نشط').all()
    return render_template('stock-movements.html', movements=movements, items=items, technicians=technicians)

@app.route('/stock-movements/add', methods=['POST'])
def stock_add():
    item_id   = int(request.form['item_id'])
    qty       = float(request.form.get('quantity', 0))
    direction = request.form.get('direction','صادر')
    unit_price= float(request.form.get('unit_price', 0))

    m = StockMovement(
        code          = next_code(StockMovement, 'MV-', digits=3),
        item_id       = item_id,
        movement_date = datetime.strptime(request.form['movement_date'], '%Y-%m-%d').date(),
        direction     = direction,
        movement_type = request.form.get('movement_type',''),
        quantity      = qty,
        unit_price    = unit_price,
        total_value   = qty * unit_price,
        technician_id = request.form.get('technician_id') or None,
        reason        = request.form.get('reason',''),
        notes         = request.form.get('notes',''),
    )
    db.session.add(m)

    # تحديث الرصيد
    item = InventoryItem.query.get(item_id)
    if direction == 'وارد':
        item.current_qty += qty
    else:
        item.current_qty -= qty

    db.session.commit()
    return redirect(url_for('stock_movements'))

@app.route('/stock-movements/delete/<int:id>', methods=['POST'])
def stock_delete(id):
    m = StockMovement.query.get_or_404(id)
    db.session.delete(m)
    db.session.commit()
    return redirect(url_for('stock_movements'))

# =============================================
# بيان القطع
# =============================================
@app.route('/parts-billing')
def parts_billing():
    parts = PartsBilling.query.order_by(PartsBilling.billing_date.desc()).all()
    customers = Customer.query.all()
    return render_template('parts-billing.html', parts=parts, customers=customers)

@app.route('/parts-billing/edit/<int:id>', methods=['POST'])
def parts_edit(id):
    p = PartsBilling.query.get_or_404(id)
    cost  = float(request.form.get('cost_price', 0))
    sell  = float(request.form.get('sell_price', 0))
    p.customer_id    = request.form.get('customer_id') or None
    p.billing_date   = datetime.strptime(request.form['billing_date'], '%Y-%m-%d').date()
    p.description    = request.form.get('description','')
    p.cost_price     = cost
    p.sell_price     = sell
    p.profit         = sell - cost
    p.payment_method = request.form.get('payment_method','')
    p.status         = request.form.get('status','مكتملة')
    p.notes          = request.form.get('notes','')
    db.session.commit()
    return redirect(url_for('parts_billing'))

@app.route('/parts-billing/add', methods=['POST'])
def parts_add():
    cost  = float(request.form.get('cost_price', 0))
    sell  = float(request.form.get('sell_price', 0))
    p = PartsBilling(
        code          = next_code(PartsBilling, 'PB-', digits=3),
        customer_id   = request.form.get('customer_id') or None,
        contract_id   = request.form.get('contract_id') or None,
        elevator_id   = request.form.get('elevator_id') or None,
        technician_id = request.form.get('technician_id') or None,
        billing_date  = datetime.strptime(request.form['billing_date'], '%Y-%m-%d').date(),
        description   = request.form.get('description',''),
        cost_price    = cost,
        sell_price    = sell,
        profit        = sell - cost,
        payment_method= request.form.get('payment_method',''),
        status        = request.form.get('status','مكتملة'),
        notes         = request.form.get('notes',''),
    )
    db.session.add(p)
    db.session.commit()
    return redirect(url_for('parts_billing'))

@app.route('/parts-billing/delete/<int:id>', methods=['POST'])
def parts_delete(id):
    p = PartsBilling.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for('parts_billing'))

# =============================================
# التقارير
# =============================================
@app.route('/reports')
def reports():
    return render_template('reports.html')

@app.route('/reports/dashboard')
def report_dashboard():
    return render_template('report-dashboard.html')

@app.route('/reports/client-annual')
def report_client_annual():
    customers = Customer.query.all()
    return render_template('report-annual.html', customers=customers)

@app.route('/reports/clients')
def report_clients():
    return render_template('report-clients.html')

@app.route('/reports/elevators')
def report_elevators():
    return render_template('report-elevators.html')

@app.route('/reports/contracts')
def report_contracts():
    return render_template('report-contracts.html')

@app.route('/reports/technicians')
def report_technicians():
    return render_template('report-technicians.html')

@app.route('/reports/maintenance-visits')
def report_maintenance():
    return render_template('report-maintenance.html')

@app.route('/reports/faults')
def report_faults():
    return render_template('report-faults.html')

@app.route('/reports/revenues')
def report_revenues():
    return render_template('report-revenues.html')

@app.route('/reports/expenses')
def report_expenses():
    return render_template('report-expenses.html')

@app.route('/reports/invoices')
def report_invoices():
    return render_template('report-invoices.html')

@app.route('/reports/inventory')
def report_inventory():
    return render_template('report-inventory.html')

@app.route('/reports/stock-movements')
def report_stock():
    return render_template('report-stock.html')

@app.route('/reports/parts-billing')
def report_parts():
    return render_template('report-parts.html')

# =============================================
# الإعدادات
# =============================================
@app.route('/settings')
def settings():
    s = Settings.query.first()
    users = User.query.all()
    return render_template('settings.html', settings=s, users=users)

@app.route('/settings/save', methods=['POST'])
def settings_save():
    s = Settings.query.first()
    if not s:
        s = Settings()
        db.session.add(s)
    s.company_name    = request.form.get('company_name','')
    s.company_name_en = request.form.get('company_name_en','')
    s.phone           = request.form.get('phone','')
    s.email           = request.form.get('email','')
    s.address         = request.form.get('address','')
    s.city            = request.form.get('city','')
    s.cr_number       = request.form.get('cr_number','')
    s.vat_number      = request.form.get('vat_number','')
    s.tax_pct         = float(request.form.get('tax_pct', 15))
    s.currency        = request.form.get('currency','ر.س')
    s.language        = request.form.get('language','ar')
    db.session.commit()
    return redirect(url_for('settings'))

# =============================================
# API للداشبورد (بيانات حقيقية)
# =============================================
@app.route('/api/dashboard')
def api_dashboard():
    from sqlalchemy import extract
    year = int(request.args.get('year', datetime.now().year))

    # إيرادات شهرية
    monthly_rev = []
    monthly_exp = []
    for m in range(1, 13):
        rev = db.session.query(db.func.sum(Revenue.total)).filter(
            extract('year', Revenue.revenue_date) == year,
            extract('month', Revenue.revenue_date) == m
        ).scalar() or 0
        exp = db.session.query(db.func.sum(Expense.amount)).filter(
            extract('year', Expense.expense_date) == year,
            extract('month', Expense.expense_date) == m
        ).scalar() or 0
        monthly_rev.append(round(rev, 2))
        monthly_exp.append(round(exp, 2))

    return jsonify({
        'customers':   Customer.query.filter_by(status='نشط').count(),
        'elevators':   Elevator.query.count(),
        'contracts':   Contract.query.filter_by(status='نشط').count(),
        'technicians': Technician.query.filter_by(status='نشط').count(),
        'revenue':     round(db.session.query(db.func.sum(Revenue.total)).scalar() or 0, 2),
        'expenses':    round(db.session.query(db.func.sum(Expense.amount)).scalar() or 0, 2),
        'faults_open': Fault.query.filter_by(status='مفتوح').count(),
        'visits_done': MaintenanceVisit.query.filter_by(status='مكتملة').count(),
        'parts_profit':round(db.session.query(db.func.sum(PartsBilling.profit)).scalar() or 0, 2),
        'monthly_revenue': monthly_rev,
        'monthly_expenses': monthly_exp,
        'elev_status': {
            'نشط':          Elevator.query.filter_by(status='نشط').count(),
            'تحت الصيانة':  Elevator.query.filter_by(status='تحت الصيانة').count(),
            'متوقف':        Elevator.query.filter_by(status='متوقف').count(),
            'خارج الخدمة':  Elevator.query.filter_by(status='خارج الخدمة').count(),
        },
        'contract_status': {
            'نشط':    Contract.query.filter_by(status='نشط').count(),
            'منتهي':  Contract.query.filter_by(status='منتهي').count(),
            'معلق':   Contract.query.filter_by(status='معلق').count(),
            'ملغي':   Contract.query.filter_by(status='ملغي').count(),
        },
    })
# =============================================
# أضف هذه الـ routes في app.py
# تحت قسم التقارير الموجود
# =============================================

@app.route('/api/reports/clients')
def api_report_clients():
    customers = Customer.query.order_by(Customer.id).all()
    return jsonify([{
        'code':     c.code,
        'name':     c.name,
        'city':     c.city or '',
        'district': c.district or '',
        'phone':    c.phone or '',
        'elevators':len(c.elevators),
        'contracts':len(c.contracts),
        'contract_status': c.contracts[0].status if c.contracts else 'بدون عقد',
        'status':   c.status,
    } for c in customers])


@app.route('/api/reports/elevators')
def api_report_elevators():
    elevs = Elevator.query.order_by(Elevator.id).all()
    return jsonify([{
        'code':       e.code,
        'customer':   e.customer.name,
        'building':   e.building_name or '',
        'city':       e.city or '',
        'elev_type':  e.elev_type or '',
        'brand':      e.brand or '',
        'capacity':   str(e.capacity_kg or '') + ' كجم' if e.capacity_kg else '',
        'status':     e.status,
        'next_maint': str(e.next_maintenance or ''),
    } for e in elevs])


@app.route('/api/reports/contracts')
def api_report_contracts():
    contracts = Contract.query.order_by(Contract.id).all()
    return jsonify([{
        'code':          c.code,
        'customer':      c.customer.name,
        'contract_type': c.contract_type or '',
        'start_date':    str(c.start_date or ''),
        'end_date':      str(c.end_date or ''),
        'elevators':     len(c.elevators),
        'value':         c.value or 0,
        'total':         c.total or 0,
        'status':        c.status,
        'inv_status':    c.invoice_status or '',
    } for c in contracts])


@app.route('/api/reports/technicians')
def api_report_technicians():
    techs = Technician.query.order_by(Technician.id).all()
    return jsonify([{
        'code':           t.code,
        'name':           t.name,
        'phone':          t.phone or '',
        'job_title':      t.job_title or '',
        'specialization': t.specialization or '',
        'city':           t.city or '',
        'status':         t.status,
        'emergency':      'نعم' if t.emergency else 'لا',
        'visits':         len(t.visits),
    } for t in techs])


@app.route('/api/reports/visits')
def api_report_visits():
    visits = MaintenanceVisit.query.order_by(MaintenanceVisit.visit_date.desc()).all()
    return jsonify([{
        'code':       v.code,
        'customer':   v.elevator.customer.name,
        'elevator':   v.elevator.code,
        'technician': v.technician.name if v.technician else '—',
        'visit_type': v.visit_type or '',
        'visit_date': str(v.visit_date or ''),
        'priority':   v.priority or '',
        'status':     v.status,
    } for v in visits])


@app.route('/api/reports/faults')
def api_report_faults():
    faults = Fault.query.order_by(Fault.reported_at.desc()).all()
    return jsonify([{
        'code':       f.code,
        'customer':   f.elevator.customer.name,
        'elevator':   f.elevator.code,
        'fault_type': f.fault_type or '',
        'priority':   f.priority or '',
        'technician': f.technician.name if f.technician else '—',
        'response':   f.response_time or '—',
        'status':     f.status,
        'billed':     'مفوتر' if f.billed else 'غير مفوتر',
    } for f in faults])


@app.route('/api/reports/revenues')
def api_report_revenues():
    from sqlalchemy import extract
    year  = request.args.get('year', datetime.now().year)
    month = request.args.get('month', '')
    q = Revenue.query
    if year:  q = q.filter(extract('year',  Revenue.revenue_date) == int(year))
    if month: q = q.filter(extract('month', Revenue.revenue_date) == int(month))
    revs = q.order_by(Revenue.revenue_date.desc()).all()
    return jsonify([{
        'code':         r.code,
        'customer':     r.customer.name if r.customer else '—',
        'contract':     r.contract.code if r.contract else '—',
        'date':         str(r.revenue_date or ''),
        'revenue_type': r.revenue_type or '',
        'pay_method':   r.payment_method or '',
        'amount':       r.amount or 0,
        'tax':          r.tax_amount or 0,
        'total':        r.total or 0,
        'status':       r.status or '',
    } for r in revs])


@app.route('/api/reports/expenses')
def api_report_expenses():
    from sqlalchemy import extract
    year  = request.args.get('year', datetime.now().year)
    month = request.args.get('month', '')
    q = Expense.query
    if year:  q = q.filter(extract('year',  Expense.expense_date) == int(year))
    if month: q = q.filter(extract('month', Expense.expense_date) == int(month))
    exps = q.order_by(Expense.expense_date.desc()).all()
    return jsonify([{
        'code':         e.code,
        'date':         str(e.expense_date or ''),
        'expense_type': e.expense_type or '',
        'description':  e.description or '',
        'responsible':  e.responsible or '',
        'pay_method':   e.payment_method or '',
        'amount':       e.amount or 0,
    } for e in exps])


@app.route('/api/reports/invoices')
def api_report_invoices():
    invs = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
    return jsonify([{
        'code':         i.code,
        'invoice_type': i.invoice_type or '',
        'customer':     i.customer.name if i.customer else '—',
        'contract':     i.contract.code if i.contract else '—',
        'date':         str(i.invoice_date or ''),
        'description':  i.description or '',
        'amount':       i.amount or 0,
        'tax':          i.tax_amount or 0,
        'total':        i.total or 0,
        'pay_method':   i.payment_method or '',
        'status':       i.status or '',
    } for i in invs])


@app.route('/api/reports/inventory')
def api_report_inventory():
    items = InventoryItem.query.order_by(InventoryItem.id).all()
    return jsonify([{
        'code':        i.code,
        'name':        i.name,
        'category':    i.category or '',
        'current_qty': i.current_qty or 0,
        'unit':        i.unit or '',
        'min_qty':     i.min_qty or 0,
        'buy_price':   i.buy_price or 0,
        'stock_value': i.stock_value,
        'supplier':    i.supplier or '',
        'order_status':i.order_status,
    } for i in items])


@app.route('/api/reports/stock')
def api_report_stock():
    movements = StockMovement.query.order_by(StockMovement.movement_date.desc()).all()
    return jsonify([{
        'code':          m.code,
        'date':          str(m.movement_date or ''),
        'direction':     m.direction or '',
        'movement_type': m.movement_type or '',
        'item':          m.item.name,
        'item_code':     m.item.code,
        'quantity':      m.quantity or 0,
        'unit_price':    m.unit_price or 0,
        'total_value':   m.total_value or 0,
        'technician':    m.technician.name if m.technician else '—',
        'reason':        m.reason or '',
    } for m in movements])


@app.route('/api/reports/parts')
def api_report_parts():
    parts = PartsBilling.query.order_by(PartsBilling.billing_date.desc()).all()
    return jsonify([{
        'code':       p.code,
        'customer':   p.customer.name if p.customer else '—',
        'contract':   p.contract.code if p.contract else '—',
        'date':       str(p.billing_date or ''),
        'description':p.description or '',
        'cost_price': p.cost_price or 0,
        'sell_price': p.sell_price or 0,
        'profit':     p.profit or 0,
        'pay_method': p.payment_method or '',
        'status':     p.status or '',
    } for p in parts])


@app.route('/api/reports/client-annual/<int:customer_id>')
def api_client_annual(customer_id):
    from sqlalchemy import extract
    year = int(request.args.get('year', datetime.now().year))
    c = Customer.query.get_or_404(customer_id)

    # العقود
    contracts = Contract.query.filter_by(customer_id=customer_id).all()

    # الزيارات
    visits = MaintenanceVisit.query.join(Elevator).filter(
        Elevator.customer_id == customer_id,
        extract('year', MaintenanceVisit.visit_date) == year
    ).all()

    # الأعطال
    faults = Fault.query.join(Elevator).filter(
        Elevator.customer_id == customer_id,
        extract('year', Fault.reported_at) == year
    ).all()

    # الإيرادات
    revenues = Revenue.query.filter(
        Revenue.customer_id == customer_id,
        extract('year', Revenue.revenue_date) == year
    ).all()

    # القطع
    parts = PartsBilling.query.filter(
        PartsBilling.customer_id == customer_id,
        extract('year', PartsBilling.billing_date) == year
    ).all()

    planned_visits = len(contracts) * 12  # تقديري
    done_visits    = len([v for v in visits if v.status == 'مكتملة'])
    solved_faults  = len([f for f in faults if f.status in ['محلول','مغلق']])

    return jsonify({
        'customer': {
            'code':    c.code,
            'name':    c.name,
            'city':    c.city or '',
            'address': c.address or '',
            'phone':   c.phone or '',
        },
        'contracts': [{
            'code':       ct.code,
            'type':       ct.contract_type or '',
            'start':      str(ct.start_date or ''),
            'end':        str(ct.end_date or ''),
            'total':      ct.total or 0,
            'status':     ct.status,
        } for ct in contracts],
        'elevators': [{
            'code':      e.code,
            'type':      e.elev_type or '',
            'brand':     e.brand or '',
            'capacity':  str(e.capacity_kg or '') + ' كجم' if e.capacity_kg else '',
        } for e in c.elevators],
        'stats': {
            'planned_visits': planned_visits,
            'done_visits':    done_visits,
            'compliance':     round(done_visits/planned_visits*100) if planned_visits else 0,
            'total_faults':   len(faults),
            'solved_faults':  solved_faults,
            'fault_rate':     round(solved_faults/len(faults)*100) if faults else 100,
            'total_revenue':  sum(r.total for r in revenues),
        },
        'visits': [{
            'date':       str(v.visit_date or ''),
            'tech':       v.technician.name if v.technician else '—',
            'type':       v.visit_type or '',
            'works':      v.works_done or '',
            'status':     v.status,
        } for v in visits],
        'faults': [{
            'type':   f.fault_type or '',
            'date':   str(f.reported_at.date() if f.reported_at else ''),
            'status': f.status,
        } for f in faults],
        'parts': [{
            'description': p.description or '',
            'quantity':    1,
            'date':        str(p.billing_date or ''),
        } for p in parts],
    })
# =============================================
# تشغيل التطبيق
# =============================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)
