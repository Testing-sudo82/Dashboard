import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os
import csv
import io
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # Set a unique, secret key for session management

# Function to connect to SQLite DB
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # To return results as dictionaries
    return conn

# Helper to get date-wise sales summary
def get_sales_summary():
    conn = get_db_connection()
    # Get all unique dates from sales
    dates = [row['date'][:10] for row in conn.execute('SELECT DISTINCT date(date) as date FROM sales ORDER BY date').fetchall()]
    # Get all products
    products = conn.execute('SELECT * FROM products').fetchall()
    # Get all sales
    sales = conn.execute('SELECT * FROM sales ORDER BY date').fetchall()
    # Get product names by id
    product_names = {p['id']: p['name'] for p in products}
    # Get initial stock for each product
    initial_stock = {p['id']: p['total_quantity'] for p in products}
    # Build summary: {date: {product_id: {'sold': x, 'remaining': y}}}
    summary = []
    # For each product, track running stock
    running_stock = {p['id']: 0 for p in products}
    # Calculate initial stock for each product (before any sales)
    for p in products:
        # Get total sold for this product
        total_sold = sum(s['quantity_sold'] for s in sales if s['product_id'] == p['id'])
        running_stock[p['id']] = p['total_quantity']
        # We'll adjust this as we process sales by date
    # For each date, for each product, calculate sold and remaining
    for date in dates:
        for p in products:
            # Sales for this product on this date
            sold_today = sum(s['quantity_sold'] for s in sales if s['product_id'] == p['id'] and s['date'][:10] == date)
            # Remaining at end of day: subtract all sales up to and including this date
            sold_up_to_today = sum(s['quantity_sold'] for s in sales if s['product_id'] == p['id'] and s['date'][:10] <= date)
            remaining = p['total_quantity'] - sold_up_to_today
            summary.append({
                'date': date,
                'product_name': p['name'],
                'sold': sold_today,
                'remaining': remaining
            })
    conn.close()
    return summary

# Home route to display all products and sales summary
@app.route('/')
def index():
    filter_product = request.args.get('filter_product', default=None, type=str)
    filter_date = request.args.get('filter_date', default=None, type=str)
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    sales_summary = get_sales_summary()
    # Convert sqlite3.Row objects to dicts for JSON serialization
    products = [dict(p) for p in products]
    sales_summary = [dict(row) for row in sales_summary]
    return render_template('index.html', products=products, sales_summary=sales_summary, filter_product=filter_product, filter_date=filter_date)

# Route to add new product
@app.route('/add_product_page')
def add_product_page():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    products = [dict(p) for p in products]
    return render_template('addProduct.html', products=products)

@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['name']
    amount_per_piece = float(request.form['amount_per_piece'])
    total_quantity = int(request.form['total_quantity'])
    category = request.form.get('category', '')
    unit = request.form.get('unit', '')
    date_of_buy = datetime.now().strftime('%Y-%m-%d')

    conn = get_db_connection()
    # Add original_quantity to products table
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        amount_per_piece REAL NOT NULL,
        total_quantity INTEGER NOT NULL,
        original_quantity INTEGER NOT NULL,
        category TEXT,
        unit TEXT,
        date_of_buy TEXT
    )''')
    conn.execute('INSERT INTO products (name, amount_per_piece, total_quantity, original_quantity, category, unit, date_of_buy) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                 (name, amount_per_piece, total_quantity, total_quantity, category, unit, date_of_buy))
    conn.commit()
    # Get the last inserted product (for CSV)
    product = conn.execute('SELECT * FROM products ORDER BY id DESC LIMIT 1').fetchone()
    conn.close()

    # Write to products.csv
    product_csv_path = 'products.csv'
    write_header = not os.path.exists(product_csv_path)
    with open(product_csv_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(['id', 'name', 'amount_per_piece', 'total_quantity', 'original_quantity', 'category', 'unit', 'date_of_buy'])
        writer.writerow([product['id'], product['name'], product['amount_per_piece'], product['total_quantity'], product['original_quantity'], product['category'], product['unit'], product['date_of_buy']])

    return redirect(url_for('add_product_page'))

# Route to record a sale (using barcode)
@app.route('/sell_product', methods=['POST'])
def sell_product():
    product_name = request.form['product_name']
    quantity_sold = int(request.form['quantity_sold'])

    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE name = ?', (product_name,)).fetchone()

    if product:
        if product['total_quantity'] < quantity_sold:
            flash('quantity not enough', 'error')
        else:
            new_quantity = product['total_quantity'] - quantity_sold
            conn.execute('UPDATE products SET total_quantity = ? WHERE id = ?', (new_quantity, product['id']))
            conn.execute('INSERT INTO sales (product_id, quantity_sold) VALUES (?, ?)', (product['id'], quantity_sold))
            conn.commit()
            flash(f'{quantity_sold} units of {product["name"]} sold successfully!', 'success')
            # Write to sales.csv
            sales_csv_path = 'sales.csv'
            write_header = not os.path.exists(sales_csv_path)
            with open(sales_csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(['product_id', 'product_name', 'quantity_sold', 'date'])
                writer.writerow([product['id'], product['name'], quantity_sold, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    else:
        flash('Product not found!', 'error')

    conn.close()
    return redirect(url_for('index'))

@app.route('/export_sales_csv')
def export_sales_csv():
    sales_summary = get_sales_summary()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Product Name', 'Product Remaining at End of Day', 'Product Sold'])
    for row in sales_summary:
        writer.writerow([row['date'], row['product_name'], row['remaining'], row['sold']])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='Sales.csv')

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        unit = request.form['unit']
        amount_per_piece = float(request.form['amount_per_piece'])
        total_quantity = int(request.form['total_quantity'])
        conn.execute('UPDATE products SET name=?, category=?, unit=?, amount_per_piece=?, total_quantity=? WHERE id=?',
                     (name, category, unit, amount_per_piece, total_quantity, product_id))
        conn.commit()
        conn.close()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('index'))
    else:
        product = conn.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
        conn.close()
        if not product:
            flash('Product not found!', 'error')
            return redirect(url_for('index'))
        return render_template('edit_product.html', product=dict(product))

@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id=?', (product_id,))
    conn.commit()
    conn.close()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/restock_product', methods=['POST'])
def restock_product():
    product_id = int(request.form['product_id'])
    quantity = int(request.form['quantity'])
    supplier = request.form.get('supplier', '')
    purchase_price = request.form.get('purchase_price', None)
    conn = get_db_connection()
    # Update product stock
    conn.execute('UPDATE products SET total_quantity = total_quantity + ? WHERE id = ?', (quantity, product_id))
    # Log restock in restocks table
    conn.execute('''CREATE TABLE IF NOT EXISTS restocks (
        id INTEGER PRIMARY KEY,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        supplier TEXT,
        purchase_price REAL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')
    conn.execute('INSERT INTO restocks (product_id, quantity, supplier, purchase_price) VALUES (?, ?, ?, ?)',
                 (product_id, quantity, supplier, purchase_price))
    conn.commit()
    conn.close()
    flash('Product restocked successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/summary')
def summary():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    products = [dict(p) for p in products]
    sales_summary = get_sales_summary()
    # Calculate total amount, gain, loss for each row
    for row in sales_summary:
        # Find product price
        product = next((p for p in products if p['name'] == row['product_name']), None)
        price = product['amount_per_piece'] if product else 0
        row['total_amount'] = row['sold'] * price
        # For gain/loss, you can implement your own logic. Here, gain = total_amount, loss = 0 (placeholder)
        row['gain'] = row['total_amount']
        row['loss'] = 0
    return render_template('summary.html', sales_summary=sales_summary)

if __name__ == '__main__':
    app.run(host = '0.0.0.0')
