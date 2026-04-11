"""
CS4092 Online Shopping Application - Backend API
Flask + PostgreSQL (psycopg2)
"""

import os
from datetime import date, timedelta
from functools import wraps
from flask import Flask, request, jsonify, g, session
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
CORS(app, supports_credentials=True)

# ── Database connection ─────────────────────────────────────
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "shopping",
    "user": "postgres",
    "password": "123456",
    "options": "-c client_encoding=UTF8",
}

def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        g.db.set_client_encoding('UTF8')
        g.db.autocommit = False
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        if exc:
            db.rollback()
        db.close()


# ── Auth helpers ─────────────────────────────────────────────
def login_required(role=None):
    """Decorator: checks session for logged-in user. role='customer'|'staff'|None"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "Authentication required"}), 401
            if role and session.get("role") != role:
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ════════════════════════════════════════════════════════════

@app.route("/api/register", methods=["POST"])
def register():
    """Register a new customer."""
    data = request.json
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            """INSERT INTO customer (email, password, first_name, last_name)
               VALUES (%s, %s, %s, %s) RETURNING customer_id""",
            (data["email"], generate_password_hash(data["password"]),
             data["first_name"], data["last_name"]),
        )
        cid = cur.fetchone()["customer_id"]
        db.commit()
        session["user_id"] = cid
        session["role"] = "customer"
        return jsonify({"customer_id": cid}), 201
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        return jsonify({"error": "Email already exists"}), 409


@app.route("/api/login", methods=["POST"])
def login():
    """Login for customer or staff."""
    data = request.json
    db = get_db()
    cur = db.cursor()
    # Try customer first
    cur.execute("SELECT customer_id, password FROM customer WHERE email=%s", (data["email"],))
    row = cur.fetchone()
    if row and check_password_hash(row["password"], data["password"]):
        session["user_id"] = row["customer_id"]
        session["role"] = "customer"
        return jsonify({"role": "customer", "id": row["customer_id"]})
    # Try staff
    cur.execute("SELECT staff_id, password FROM staff WHERE email=%s", (data["email"],))
    row = cur.fetchone()
    if row and (row["password"] == data["password"] or check_password_hash(row["password"], data["password"])):
        session["user_id"] = row["staff_id"]
        session["role"] = "staff"
        return jsonify({"role": "staff", "id": row["staff_id"]})
    return jsonify({"error": "Invalid credentials"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.route("/api/me", methods=["GET"])
@login_required()
def me():
    db = get_db()
    cur = db.cursor()
    if session["role"] == "customer":
        cur.execute("SELECT customer_id, email, first_name, last_name, balance FROM customer WHERE customer_id=%s",
                    (session["user_id"],))
    else:
        cur.execute("SELECT staff_id, email, first_name, last_name, job_title FROM staff WHERE staff_id=%s",
                    (session["user_id"],))
    return jsonify(cur.fetchone())


# ════════════════════════════════════════════════════════════
#  PRODUCT ROUTES
# ════════════════════════════════════════════════════════════

@app.route("/api/products", methods=["GET"])
def list_products():
    """Browse/search products. Query params: ?search=&category=&type="""
    db = get_db()
    cur = db.cursor()
    query = """
        SELECT p.*, c.category_name,
               COALESCE(SUM(s.quantity), 0) AS total_stock
        FROM product p
        LEFT JOIN category c ON p.category_id = c.category_id
        LEFT JOIN stock s ON p.product_id = s.product_id
        WHERE 1=1
    """
    params = []
    if request.args.get("search"):
        query += " AND (p.name ILIKE %s OR p.description ILIKE %s)"
        like = f"%{request.args['search']}%"
        params += [like, like]
    if request.args.get("category"):
        query += " AND c.category_name = %s"
        params.append(request.args["category"])
    if request.args.get("type"):
        query += " AND p.product_type = %s"
        params.append(request.args["type"])
    query += " GROUP BY p.product_id, c.category_name ORDER BY p.name"
    cur.execute(query, params)
    return jsonify(cur.fetchall())


@app.route("/api/products/<int:pid>", methods=["GET"])
def get_product(pid):
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT p.*, c.category_name, COALESCE(SUM(s.quantity),0) AS total_stock
        FROM product p
        LEFT JOIN category c ON p.category_id = c.category_id
        LEFT JOIN stock s ON p.product_id = s.product_id
        WHERE p.product_id = %s
        GROUP BY p.product_id, c.category_name
    """, (pid,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row)


@app.route("/api/products", methods=["POST"])
@login_required(role="staff")
def create_product():
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO product (name, brand, product_type, size, description, price, category_id, image_url)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING product_id
    """, (data["name"], data.get("brand"), data.get("product_type"),
          data.get("size"), data.get("description"), data["price"],
          data.get("category_id"), data.get("image_url")))
    pid = cur.fetchone()["product_id"]
    db.commit()
    return jsonify({"product_id": pid}), 201


@app.route("/api/products/<int:pid>", methods=["PUT"])
@login_required(role="staff")
def update_product(pid):
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE product SET name=%s, brand=%s, product_type=%s, size=%s,
               description=%s, price=%s, category_id=%s, image_url=%s
        WHERE product_id=%s
    """, (data["name"], data.get("brand"), data.get("product_type"),
          data.get("size"), data.get("description"), data["price"],
          data.get("category_id"), data.get("image_url"), pid))
    db.commit()
    return jsonify({"message": "Updated"})


@app.route("/api/products/<int:pid>", methods=["DELETE"])
@login_required(role="staff")
def delete_product(pid):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM product WHERE product_id=%s", (pid,))
    db.commit()
    return jsonify({"message": "Deleted"})


@app.route("/api/categories", methods=["GET"])
def list_categories():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM category ORDER BY category_name")
    return jsonify(cur.fetchall())


# ════════════════════════════════════════════════════════════
#  SHOPPING CART
# ════════════════════════════════════════════════════════════

@app.route("/api/cart", methods=["GET"])
@login_required(role="customer")
def get_cart():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT ci.cart_item_id, ci.product_id, ci.quantity,
               p.name, p.price, p.image_url,
               (ci.quantity * p.price) AS subtotal
        FROM cart_item ci JOIN product p ON ci.product_id = p.product_id
        WHERE ci.customer_id = %s
    """, (session["user_id"],))
    items = cur.fetchall()
    total = sum(float(i["subtotal"]) for i in items)
    return jsonify({"items": items, "total": total})


@app.route("/api/cart", methods=["POST"])
@login_required(role="customer")
def add_to_cart():
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO cart_item (customer_id, product_id, quantity)
        VALUES (%s, %s, %s)
        ON CONFLICT (customer_id, product_id)
        DO UPDATE SET quantity = cart_item.quantity + EXCLUDED.quantity
        RETURNING cart_item_id
    """, (session["user_id"], data["product_id"], data.get("quantity", 1)))
    db.commit()
    return jsonify(cur.fetchone()), 201


@app.route("/api/cart/<int:item_id>", methods=["PUT"])
@login_required(role="customer")
def update_cart_item(item_id):
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE cart_item SET quantity=%s WHERE cart_item_id=%s AND customer_id=%s",
                (data["quantity"], item_id, session["user_id"]))
    db.commit()
    return jsonify({"message": "Updated"})


@app.route("/api/cart/<int:item_id>", methods=["DELETE"])
@login_required(role="customer")
def delete_cart_item(item_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM cart_item WHERE cart_item_id=%s AND customer_id=%s",
                (item_id, session["user_id"]))
    db.commit()
    return jsonify({"message": "Deleted"})


# ════════════════════════════════════════════════════════════
#  ORDERS
# ════════════════════════════════════════════════════════════

@app.route("/api/orders", methods=["POST"])
@login_required(role="customer")
def place_order():
    """Place an order from the shopping cart."""
    data = request.json
    card_id = data["card_id"]
    delivery_type = data.get("delivery_type", "standard")
    db = get_db()
    cur = db.cursor()

    # 1. Get cart items
    cur.execute("""
        SELECT ci.product_id, ci.quantity, p.price
        FROM cart_item ci JOIN product p ON ci.product_id = p.product_id
        WHERE ci.customer_id = %s
    """, (session["user_id"],))
    items = cur.fetchall()
    if not items:
        return jsonify({"error": "Cart is empty"}), 400

    # 2. Check availability (bonus)
    for item in items:
        cur.execute("SELECT COALESCE(SUM(quantity),0) AS avail FROM stock WHERE product_id=%s",
                    (item["product_id"],))
        avail = cur.fetchone()["avail"]
        if avail < item["quantity"]:
            return jsonify({"error": f"Insufficient stock for product {item['product_id']}"}), 400

    # 3. Create order
    total = sum(float(i["price"]) * i["quantity"] for i in items)
    delivery_price = 0.00 if delivery_type == "standard" else 9.99
    total += delivery_price

    cur.execute("""
        INSERT INTO orders (customer_id, card_id, total_amount)
        VALUES (%s, %s, %s) RETURNING order_id
    """, (session["user_id"], card_id, total))
    order_id = cur.fetchone()["order_id"]

    # 4. Insert order items & reduce stock
    for item in items:
        cur.execute("""
            INSERT INTO order_item (order_id, product_id, quantity, unit_price)
            VALUES (%s, %s, %s, %s)
        """, (order_id, item["product_id"], item["quantity"], item["price"]))
        # Reduce stock (from first available warehouse)
        remaining = item["quantity"]
        cur.execute("SELECT stock_id, quantity FROM stock WHERE product_id=%s AND quantity>0 ORDER BY stock_id",
                    (item["product_id"],))
        for s in cur.fetchall():
            deduct = min(remaining, s["quantity"])
            cur.execute("UPDATE stock SET quantity = quantity - %s WHERE stock_id=%s", (deduct, s["stock_id"]))
            remaining -= deduct
            if remaining <= 0:
                break

    # 5. Delivery plan
    ship_date = date.today() + timedelta(days=1)
    delivery_date = ship_date + timedelta(days=2 if delivery_type == "express" else 7)
    cur.execute("""
        INSERT INTO delivery_plan (order_id, delivery_type, delivery_price, ship_date, delivery_date)
        VALUES (%s, %s, %s, %s, %s)
    """, (order_id, delivery_type, delivery_price, ship_date, delivery_date))

    # 6. Update customer balance
    cur.execute("UPDATE customer SET balance = balance + %s WHERE customer_id=%s",
                (total, session["user_id"]))

    # 7. Clear cart
    cur.execute("DELETE FROM cart_item WHERE customer_id=%s", (session["user_id"],))

    db.commit()
    return jsonify({"order_id": order_id, "total": total}), 201


@app.route("/api/orders", methods=["GET"])
@login_required()
def list_orders():
    db = get_db()
    cur = db.cursor()
    if session["role"] == "customer":
        cur.execute("""
            SELECT o.*, d.delivery_type, d.delivery_date, d.ship_date
            FROM orders o LEFT JOIN delivery_plan d ON o.order_id = d.order_id
            WHERE o.customer_id = %s ORDER BY o.created_at DESC
        """, (session["user_id"],))
    else:
        cur.execute("""
            SELECT o.*, d.delivery_type, d.delivery_date, d.ship_date,
                   c.first_name, c.last_name, c.email
            FROM orders o
            LEFT JOIN delivery_plan d ON o.order_id = d.order_id
            JOIN customer c ON o.customer_id = c.customer_id
            ORDER BY o.created_at DESC
        """)
    return jsonify(cur.fetchall())


@app.route("/api/orders/<int:oid>", methods=["GET"])
@login_required()
def get_order(oid):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM orders WHERE order_id=%s", (oid,))
    order = cur.fetchone()
    if not order:
        return jsonify({"error": "Not found"}), 404
    cur.execute("""
        SELECT oi.*, p.name FROM order_item oi
        JOIN product p ON oi.product_id = p.product_id
        WHERE oi.order_id = %s
    """, (oid,))
    order["items"] = cur.fetchall()
    cur.execute("SELECT * FROM delivery_plan WHERE order_id=%s", (oid,))
    order["delivery"] = cur.fetchone()
    return jsonify(order)


@app.route("/api/orders/<int:oid>/status", methods=["PUT"])
@login_required(role="staff")
def update_order_status(oid):
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE orders SET status=%s WHERE order_id=%s", (data["status"], oid))
    db.commit()
    return jsonify({"message": "Status updated"})


# ════════════════════════════════════════════════════════════
#  ADDRESSES & CREDIT CARDS
# ════════════════════════════════════════════════════════════

@app.route("/api/addresses", methods=["GET"])
@login_required(role="customer")
def list_addresses():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT a.*, ca.address_type, ca.is_default
        FROM address a JOIN customer_address ca ON a.address_id = ca.address_id
        WHERE ca.customer_id = %s
    """, (session["user_id"],))
    return jsonify(cur.fetchall())


@app.route("/api/addresses", methods=["POST"])
@login_required(role="customer")
def add_address():
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO address (street, city, state, zip_code, country)
        VALUES (%s,%s,%s,%s,%s) RETURNING address_id
    """, (data["street"], data["city"], data.get("state"),
          data.get("zip_code"), data.get("country", "US")))
    aid = cur.fetchone()["address_id"]
    cur.execute("""
        INSERT INTO customer_address (customer_id, address_id, address_type, is_default)
        VALUES (%s,%s,%s,%s)
    """, (session["user_id"], aid, data.get("address_type", "both"), data.get("is_default", False)))
    db.commit()
    return jsonify({"address_id": aid}), 201


@app.route("/api/addresses/<int:aid>", methods=["PUT"])
@login_required(role="customer")
def update_address(aid):
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE address SET street=%s, city=%s, state=%s, zip_code=%s, country=%s
        WHERE address_id=%s
    """, (data["street"], data["city"], data.get("state"),
          data.get("zip_code"), data.get("country", "US"), aid))
    db.commit()
    return jsonify({"message": "Updated"})


@app.route("/api/addresses/<int:aid>", methods=["DELETE"])
@login_required(role="customer")
def delete_address(aid):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM customer_address WHERE address_id=%s AND customer_id=%s",
                (aid, session["user_id"]))
    cur.execute("DELETE FROM address WHERE address_id=%s", (aid,))
    db.commit()
    return jsonify({"message": "Deleted"})


@app.route("/api/cards", methods=["GET"])
@login_required(role="customer")
def list_cards():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT cc.*, a.street, a.city, a.state, a.zip_code
        FROM credit_card cc JOIN address a ON cc.billing_address = a.address_id
        WHERE cc.customer_id = %s
    """, (session["user_id"],))
    return jsonify(cur.fetchall())


@app.route("/api/cards", methods=["POST"])
@login_required(role="customer")
def add_card():
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO credit_card (customer_id, card_number, cardholder_name, expiry_date, billing_address, is_default)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING card_id
    """, (session["user_id"], data["card_number"], data["cardholder_name"],
          data["expiry_date"], data["billing_address"], data.get("is_default", False)))
    db.commit()
    return jsonify(cur.fetchone()), 201


@app.route("/api/cards/<int:cid>", methods=["PUT"])
@login_required(role="customer")
def update_card(cid):
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE credit_card SET card_number=%s, cardholder_name=%s, expiry_date=%s,
               billing_address=%s, is_default=%s
        WHERE card_id=%s AND customer_id=%s
    """, (data["card_number"], data["cardholder_name"], data["expiry_date"],
          data["billing_address"], data.get("is_default", False), cid, session["user_id"]))
    db.commit()
    return jsonify({"message": "Updated"})


@app.route("/api/cards/<int:cid>", methods=["DELETE"])
@login_required(role="customer")
def delete_card(cid):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM credit_card WHERE card_id=%s AND customer_id=%s",
                (cid, session["user_id"]))
    db.commit()
    return jsonify({"message": "Deleted"})


# ════════════════════════════════════════════════════════════
#  STOCK / WAREHOUSE (Staff)
# ════════════════════════════════════════════════════════════

@app.route("/api/warehouses", methods=["GET"])
@login_required(role="staff")
def list_warehouses():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT w.*, a.street, a.city, a.state,
               COALESCE(SUM(s.quantity),0) AS current_usage
        FROM warehouse w
        JOIN address a ON w.address_id = a.address_id
        LEFT JOIN stock s ON w.warehouse_id = s.warehouse_id
        GROUP BY w.warehouse_id, a.street, a.city, a.state
    """)
    return jsonify(cur.fetchall())


@app.route("/api/stock", methods=["POST"])
@login_required(role="staff")
def add_stock():
    """Add stock to a warehouse. Bonus: checks warehouse capacity."""
    data = request.json
    db = get_db()
    cur = db.cursor()

    # Bonus: check capacity
    cur.execute("SELECT capacity FROM warehouse WHERE warehouse_id=%s", (data["warehouse_id"],))
    wh = cur.fetchone()
    if wh and wh["capacity"]:
        cur.execute("SELECT COALESCE(SUM(quantity),0) AS used FROM stock WHERE warehouse_id=%s",
                    (data["warehouse_id"],))
        used = cur.fetchone()["used"]
        if used + data["quantity"] > wh["capacity"]:
            return jsonify({"error": "Exceeds warehouse capacity"}), 400

    cur.execute("""
        INSERT INTO stock (product_id, warehouse_id, quantity)
        VALUES (%s, %s, %s)
        ON CONFLICT (product_id, warehouse_id)
        DO UPDATE SET quantity = stock.quantity + EXCLUDED.quantity
        RETURNING stock_id
    """, (data["product_id"], data["warehouse_id"], data["quantity"]))
    db.commit()
    return jsonify(cur.fetchone()), 201


# ════════════════════════════════════════════════════════════
#  CUSTOMERS (Staff query)
# ════════════════════════════════════════════════════════════

@app.route("/api/customers", methods=["GET"])
@login_required(role="staff")
def list_customers():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT customer_id, email, first_name, last_name, balance, created_at FROM customer ORDER BY last_name")
    return jsonify(cur.fetchall())


# ════════════════════════════════════════════════════════════
#  RUN
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, port=5000)
