import uuid
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Function to connect to SQLite DB
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # To return results as dictionaries
    return conn

# Home route to display all products and sales summary
@app.route('/')
def index():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    sales = conn.execute('SELECT SUM(s.quantity_sold) AS total_sales, p.name FROM sales s JOIN products p ON s.product_id = p.id GROUP BY p.name').fetchall()
    conn.close()
    return render_template('index.html', products=products, sales=sales)

# Route to add new product

@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['name']
    amount_per_piece = float(request.form['amount_per_piece'])
    total_quantity = int(request.form['total_quantity'])

    # Generate a unique product code
    product_code = str(uuid.uuid4())  # Generates a unique product code

    conn = get_db_connection()
    conn.execute('INSERT INTO products (name, product_code, amount_per_piece, total_quantity) VALUES (?, ?, ?, ?)', 
                 (name, product_code, amount_per_piece, total_quantity))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# Route to record a sale (using barcode)
@app.route('/sell_product', methods=['POST'])
def sell_product():
    product_code = request.form['barcode']  # Now using product_code (barcode)
    quantity_sold = int(request.form['quantity_sold'])

    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE product_code = ?', (product_code,)).fetchone()

    if product:
        new_quantity = product['total_quantity'] - quantity_sold
        if new_quantity >= 0:
            conn.execute('UPDATE products SET total_quantity = ? WHERE id = ?', (new_quantity, product['id']))
            conn.execute('INSERT INTO sales (product_id, quantity_sold) VALUES (?, ?)', (product['id'], quantity_sold))
            conn.commit()
            flash(f'{quantity_sold} units of {product["name"]} sold successfully!', 'success')
        else:
            flash('Not enough stock to complete the sale.', 'error')
    else:
        flash('Product not found!', 'error')

    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
