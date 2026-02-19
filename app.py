from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Kunci rahasia untuk session (wajib agar fitur flash message/notifikasi bisa jalan)
app.secret_key = 'kunci_rahasia_dompetku_srii' 

# Konfigurasi MongoDB
client = MongoClient(os.getenv('MONGO_URI'))
db = client[os.getenv('DB_NAME')]
collection = db['transactions']

# Set timezone ke WITA (UTC+8)
WITA = timezone(timedelta(hours=8))

def get_wita_now():
    """Mendapatkan waktu saat ini dalam timezone WITA"""
    return datetime.now(timezone.utc).astimezone(WITA)

def get_current_period_start():
    today = get_wita_now()
    if today.day >= 25:
        return datetime(today.year, today.month, 25, tzinfo=WITA)
    else:
        return (datetime(today.year, today.month, 25, tzinfo=WITA) - relativedelta(months=1)).replace(day=25)

def get_period_range(start_date):
    end_date = start_date + relativedelta(months=1) - relativedelta(days=1)
    end_date = end_date.replace(hour=23, minute=59, second=59)
    return start_date, end_date

def generate_period_options(num_months=12):
    options = []
    # Set the start date to January 25, 2026
    jan_2026 = datetime(2026, 1, 25, tzinfo=WITA)
    current_start = max(get_current_period_start(), jan_2026)  # Take the later date
    
    # Calculate how many months from the start date to show
    months_to_show = 0
    temp_date = current_start
    for _ in range(num_months):
        if temp_date >= jan_2026:
            months_to_show += 1
            temp_date -= relativedelta(months=1)
        else:
            break

    for i in range(months_to_show):
        start = current_start - relativedelta(months=i)
        start_fmt, end_fmt = get_period_range(start)
        label = f"{start.strftime('%d %b %Y')} - {end_fmt.strftime('%d %b %Y')}"
        value = start.strftime('%Y-%m-%d')
        options.append({'label': label, 'value': value, 'is_current': (i == 0)})
    return options

# --- Routes ---

@app.route('/', methods=['GET'])
def index():
    selected_date_str = request.args.get('period')
    if selected_date_str:
        start_date = datetime.strptime(selected_date_str, '%Y-%m-%d')
        start_date = start_date.replace(tzinfo=WITA)
    else:
        start_date = get_current_period_start()

    _, end_date = get_period_range(start_date)
    
    transactions = list(collection.find({
        'date': {'$gte': start_date, '$lte': end_date}
    }).sort('date', -1))

    total_pemasukan = sum(t['amount'] for t in transactions if t['type'] == 'pemasukan')
    total_pengeluaran = sum(t['amount'] for t in transactions if t['type'] == 'pengeluaran')
    saldo = total_pemasukan - total_pengeluaran
    
    period_options = generate_period_options()
    current_selection = start_date.strftime('%Y-%m-%d')

    return render_template('index.html', 
                       transactions=transactions, 
                       pemasukan=total_pemasukan, 
                       pengeluaran=total_pengeluaran, 
                       saldo=saldo,
                       period_options=period_options,
                       current_selection=current_selection,
                       timezone=timezone,  # Tambahkan ini
                       timedelta=timedelta)  # Dan ini

@app.route('/add', methods=['POST'])
def add_transaction():
    trans_type = request.form.get('type')
    amount = int(request.form.get('amount'))
    description = request.form.get('description')
    
    # Pastikan waktu disimpan dalam UTC
    data = {
        'type': trans_type,
        'amount': amount,
        'description': description,
        'date': get_wita_now()  # Disimpan dalam WITA
    }
    
    if trans_type == 'pengeluaran':
        data['category'] = request.form.get('category')
    else:
        data['category'] = '-'

    collection.insert_one(data)
    flash('Transaksi berhasil ditambahkan!', 'success') # Notifikasi Sukses
    return redirect(url_for('index'))

# --- Route Baru: EDIT ---
@app.route('/edit/<id>', methods=['POST'])
def edit_transaction(id):
    trans_type = request.form.get('type')
    amount = int(request.form.get('amount'))
    description = request.form.get('description')
    
    update_data = {
        'type': trans_type,
        'amount': amount,
        'description': description
    }

    if trans_type == 'pengeluaran':
        update_data['category'] = request.form.get('category')
    else:
        update_data['category'] = '-'

    # Update data di database
    collection.update_one({'_id': ObjectId(id)}, {'$set': update_data})
    
    flash('Data berhasil diperbarui!', 'info') # Notifikasi Info
    return redirect(url_for('index'))

# --- Route Baru: HAPUS ---
@app.route('/delete/<id>', methods=['POST'])
def delete_transaction(id):
    collection.delete_one({'_id': ObjectId(id)})
    flash('Data telah dihapus.', 'error') # Notifikasi Error (Merah)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True) 