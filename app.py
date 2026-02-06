from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from datetime import datetime
from dateutil.relativedelta import relativedelta
from bson.objectid import ObjectId # Penting untuk hapus/edit by ID
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

# --- Helper Functions (Sama seperti sebelumnya) ---
def get_current_period_start():
    today = datetime.now()
    if today.day >= 25:
        return datetime(today.year, today.month, 25)
    else:
        return datetime(today.year, today.month, 25) - relativedelta(months=1)

def get_period_range(start_date):
    end_date = start_date + relativedelta(months=1) - relativedelta(days=1)
    end_date = end_date.replace(hour=23, minute=59, second=59)
    return start_date, end_date

def generate_period_options(num_months=12):
    options = []
    current_start = get_current_period_start()
    for i in range(num_months):
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
                           current_selection=current_selection)

@app.route('/add', methods=['POST'])
def add_transaction():
    trans_type = request.form.get('type')
    amount = int(request.form.get('amount'))
    description = request.form.get('description')
    
    data = {
        'type': trans_type,
        'amount': amount,
        'description': description,
        'date': datetime.now()
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