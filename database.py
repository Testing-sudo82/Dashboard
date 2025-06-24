import sqlite3

def init_db():
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()

            # Drop the old products table if it exists (Warning: This will delete all data)
            cursor.execute('DROP TABLE IF EXISTS products')

            # Create a new products table with 'original_quantity' and 'total_quantity' columns
            cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                                id INTEGER PRIMARY KEY,
                                name TEXT NOT NULL,
                                amount_per_piece REAL NOT NULL,
                                total_quantity INTEGER NOT NULL,
                                original_quantity INTEGER NOT NULL,
                                category TEXT,
                                unit TEXT,
                                date_of_buy TEXT
                            )''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS sales (
                                id INTEGER PRIMARY KEY,
                                product_id INTEGER NOT NULL,
                                quantity_sold INTEGER NOT NULL,
                                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (product_id) REFERENCES products(id)
                            )''')

            conn.commit()

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")

# Initialize the database by creating the tables
init_db()
