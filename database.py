
import sqlite3
from datetime import datetime

DB_NAME = "easypro.db"


def connect():
    db = sqlite3.connect(DB_NAME)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                product TEXT NOT NULL,
                duration INTEGER NOT NULL,
                price INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                payment_method TEXT,
                receipt_file_id TEXT,
                delivery_text TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(orders)")
        }

        if "delivery_text" not in columns:
            db.execute(
                "ALTER TABLE orders ADD COLUMN delivery_text TEXT DEFAULT ''"
            )

        db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                active INTEGER DEFAULT 1
            )
        """)

        default_products = [
            ("duolingo", "Duolingo Super", 100),
            ("google", "Google AI Plus", 150),
            ("capcut", "CapCut Pro", 120),
            ("youtube", "YouTube Premium", 100),
            ("chatgpt", "ChatGPT Plus", 200),
        ]

        for key, name, price in default_products:
            db.execute("""
                INSERT OR IGNORE INTO products
                (product_key, name, price, active)
                VALUES (?, ?, ?, 1)
            """, (key, name, price))

        # PROMOCODES
        db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER NOT NULL,
                max_uses INTEGER DEFAULT 0,
                used_count INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1
            )
        """)

        # Дополнительные поля заказов
        order_columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(orders)")
        }

        if "original_price" not in order_columns:
            db.execute(
                "ALTER TABLE orders ADD COLUMN original_price INTEGER"
            )

        if "coupon_code" not in order_columns:
            db.execute(
                "ALTER TABLE orders ADD COLUMN coupon_code TEXT"
            )

        if "discount_percent" not in order_columns:
            db.execute(
                "ALTER TABLE orders ADD COLUMN discount_percent INTEGER DEFAULT 0"
            )

        # CUSTOMERS
        db.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                is_blocked INTEGER DEFAULT 0
            )
        """)

        # SUPPORT TICKETS
        db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT DEFAULT 'open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT
            )
        """)

        # SUPPORT MESSAGES
        db.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                sender_role TEXT NOT NULL,
                message_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(ticket_id) REFERENCES support_tickets(id)
            )
        """)

        # INDEXES
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_user_id
            ON orders(user_id)
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_support_user_id
            ON support_tickets(user_id)
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_ticket_id
            ON support_messages(ticket_id)
        """)


        db.commit()


# ORDERS


def create_order(
    user_id, username, product, duration, price,
    original_price=None, coupon_code=None, discount_percent=0
):
    if original_price is None:
        original_price = price

    with connect() as db:
        cursor = db.execute("""
            INSERT INTO orders (
                user_id, username, product,
                duration, price, status, created_at,
                original_price, coupon_code, discount_percent
            )
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
        """, (
            user_id,
            username,
            product,
            duration,
            price,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            original_price,
            coupon_code,
            discount_percent
        ))
        db.commit()
        return cursor.lastrowid


def get_order(order_id):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_orders(user_id):
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_all_orders():
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM orders ORDER BY id DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def update_order_status(order_id, status):
    with connect() as db:
        db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (status, order_id)
        )
        db.commit()


def save_payment(order_id, method, receipt_file_id):
    with connect() as db:
        db.execute("""
            UPDATE orders
            SET payment_method = ?, receipt_file_id = ?
            WHERE id = ?
        """, (method, receipt_file_id, order_id))
        db.commit()


def save_delivery(order_id, delivery_text):
    with connect() as db:
        db.execute("""
            UPDATE orders
            SET delivery_text = ?
            WHERE id = ?
        """, (delivery_text, order_id))
        db.commit()


# PRODUCTS

def get_products(active_only=False):
    with connect() as db:
        if active_only:
            rows = db.execute(
                "SELECT * FROM products WHERE active = 1 ORDER BY name"
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM products ORDER BY name"
            ).fetchall()

        return [dict(row) for row in rows]


def get_product(product_key):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM products WHERE product_key = ?",
            (product_key,)
        ).fetchone()
        return dict(row) if row else None


def add_product(product_key, name, price):
    with connect() as db:
        db.execute("""
            INSERT INTO products (product_key, name, price, active)
            VALUES (?, ?, ?, 1)
        """, (product_key, name, price))
        db.commit()


def update_product(product_key, name, price):
    with connect() as db:
        db.execute("""
            UPDATE products
            SET name = ?, price = ?
            WHERE product_key = ?
        """, (name, price, product_key))
        db.commit()


def toggle_product(product_key):
    with connect() as db:
        db.execute("""
            UPDATE products
            SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END
            WHERE product_key = ?
        """, (product_key,))
        db.commit()


def delete_product(product_key):
    with connect() as db:
        db.execute(
            "DELETE FROM products WHERE product_key = ?",
            (product_key,)
        )
        db.commit()

# PROMOCODE FUNCTIONS

def add_promocode(code, discount_percent, max_uses=0):
    with connect() as db:
        db.execute("""
            INSERT INTO promocodes
            (code, discount_percent, max_uses)
            VALUES (?, ?, ?)
        """, (code.upper(), discount_percent, max_uses))
        db.commit()


def get_promocode(code):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM promocodes WHERE code = ?",
            (code.upper(),)
        ).fetchone()
        return dict(row) if row else None


def get_all_promocodes():
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM promocodes ORDER BY code"
        ).fetchall()
        return [dict(row) for row in rows]


def use_promocode(code):
    with connect() as db:
        db.execute("""
            UPDATE promocodes
            SET used_count = used_count + 1
            WHERE code = ?
        """, (code.upper(),))
        db.commit()


def toggle_promocode(code):
    with connect() as db:
        db.execute("""
            UPDATE promocodes
            SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END
            WHERE code = ?
        """, (code.upper(),))
        db.commit()

# ==========================================
# CUSTOMERS / CRM
# ==========================================

def register_customer(user_id, username, full_name):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with connect() as db:
        db.execute("""
            INSERT INTO customers (
                user_id, username, full_name, first_seen, last_seen
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_seen = excluded.last_seen
        """, (user_id, username, full_name, now, now))


def get_customer(user_id):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM customers WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not row:
            return None

        customer = dict(row)

        stats = db.execute("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(
                    CASE WHEN status = 'approved' THEN price ELSE 0 END
                ), 0) AS total_spent
            FROM orders
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        customer.update(dict(stats))
        return customer


def get_all_customers():
    with connect() as db:
        rows = db.execute("""
            SELECT
                c.*,
                COUNT(o.id) AS total_orders,
                COALESCE(SUM(
                    CASE WHEN o.status = 'approved' THEN o.price ELSE 0 END
                ), 0) AS total_spent
            FROM customers c
            LEFT JOIN orders o ON o.user_id = c.user_id
            GROUP BY c.user_id
            ORDER BY c.last_seen DESC
        """).fetchall()

        return [dict(row) for row in rows]


def search_customer(search):
    with connect() as db:
        rows = db.execute("""
            SELECT * FROM customers
            WHERE CAST(user_id AS TEXT) LIKE ?
               OR username LIKE ?
               OR full_name LIKE ?
            LIMIT 20
        """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()

        return [dict(row) for row in rows]


# ==========================================
# SUPPORT TICKETS
# ==========================================

def create_support_ticket(user_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with connect() as db:
        cursor = db.execute("""
            INSERT INTO support_tickets (
                user_id, status, created_at, updated_at
            )
            VALUES (?, 'open', ?, ?)
        """, (user_id, now, now))

        return cursor.lastrowid


def get_active_ticket(user_id):
    with connect() as db:
        row = db.execute("""
            SELECT * FROM support_tickets
            WHERE user_id = ? AND status = 'open'
            ORDER BY id DESC LIMIT 1
        """, (user_id,)).fetchone()

        return dict(row) if row else None


def get_ticket(ticket_id):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)
        ).fetchone()

        return dict(row) if row else None


def get_all_support_tickets(status=None):
    with connect() as db:
        if status:
            rows = db.execute("""
                SELECT * FROM support_tickets
                WHERE status = ?
                ORDER BY updated_at DESC
            """, (status,)).fetchall()
        else:
            rows = db.execute("""
                SELECT * FROM support_tickets
                ORDER BY updated_at DESC
            """).fetchall()

        return [dict(row) for row in rows]


def close_support_ticket(ticket_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with connect() as db:
        db.execute("""
            UPDATE support_tickets
            SET status = 'closed', closed_at = ?, updated_at = ?
            WHERE id = ?
        """, (now, now, ticket_id))


def reopen_support_ticket(ticket_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with connect() as db:
        db.execute("""
            UPDATE support_tickets
            SET status = 'open', closed_at = NULL, updated_at = ?
            WHERE id = ?
        """, (now, ticket_id))


# ==========================================
# SUPPORT MESSAGES
# ==========================================

def save_support_message(ticket_id, sender_id, sender_role, message_text):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with connect() as db:
        db.execute("""
            INSERT INTO support_messages (
                ticket_id, sender_id, sender_role, message_text, created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (ticket_id, sender_id, sender_role, message_text, now))

        db.execute("""
            UPDATE support_tickets SET updated_at = ?
            WHERE id = ?
        """, (now, ticket_id))


def get_support_messages(ticket_id):
    with connect() as db:
        rows = db.execute("""
            SELECT * FROM support_messages
            WHERE ticket_id = ?
            ORDER BY id ASC
        """, (ticket_id,)).fetchall()

        return [dict(row) for row in rows]


def get_bonus_balance(user_id):
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS bonus_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_id INTEGER,
                amount REAL NOT NULL,
                transaction_type TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(order_id, transaction_type)
            )
        """)

        result = db.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM bonus_transactions
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        return result[0]


def add_cashback(user_id, order_id, amount):
    if amount <= 0:
        return False

    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS bonus_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_id INTEGER,
                amount REAL NOT NULL,
                transaction_type TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(order_id, transaction_type)
            )
        """)

        cursor = db.execute("""
            INSERT OR IGNORE INTO bonus_transactions
            (user_id, order_id, amount, transaction_type, description)
            VALUES (?, ?, ?, 'cashback', ?)
        """, (
            user_id,
            order_id,
            amount,
            f"Кэшбэк за заказ №{order_id}"
        ))

        return cursor.rowcount == 1


def get_bonus_history(user_id):
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS bonus_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_id INTEGER,
                amount REAL NOT NULL,
                transaction_type TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(order_id, transaction_type)
            )
        """)

        return db.execute("""
            SELECT *
            FROM bonus_transactions
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,)).fetchall()


