from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

USERS = {
    'admin': '1234'
}

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username = request.form['email']
        password = request.form['password']

        if username in USERS and USERS[username] == password:
            return redirect(url_for('dashboard'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'

    return render_template('login.html', error=error)


@app.route('/dashboard')
def dashboard():
    # مؤقتاً — لاحقاً هتيجي من قاعدة البيانات
    stats = {
        'clients_count': 127,
        'elevators_count': 284,
        'active_contracts': 130,
        'expired_contracts': 12,
        'today_visits': 9,
        'open_faults': 5,
        'unpaid_invoices': 18,
        'available_technicians': 7,
    }
    return render_template('dashboard.html', stats=stats)

@app.route('/clients')
def clients():
    return render_template('clients.html')

@app.route('/elevators')
def elevators():
    return render_template('elevators.html')

@app.route('/contracts')
def contracts():
    return render_template('contracts.html')

@app.route('/technicians')
def technicians():
    return render_template('technicians.html')

if __name__ == '__main__':
    app.run(debug=True)