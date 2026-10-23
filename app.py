import json
import re
import sqlite3
from datetime import datetime

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from database import get_connection, init_db

# Create the Flask app.
app = Flask(__name__)

CORS(app)


FREE_DELIVERY_LIMIT = 70000     # Free standard delivery from this subtotal up
STANDARD_DELIVERY_FEE = 0       # Standard delivery fee below the limit
EXPRESS_DELIVERY_FEE = 5000     # Express delivery fee
MAX_QUANTITY = 10               # Maximum of one product per cart line

ALLOWED_CATEGORIES = [
    "Foundation", "Concealer", "Primer", "Powder", "Blush",
    "Lipstick", "Lip Gloss", "Highlighter", "Eyes", "Makeup Tools",
]
ALLOWED_DELIVERY_METHODS = ["standard", "express"]
ALLOWED_PAYMENT_METHODS = ["card", "bank-transfer", "pay-on-delivery"]


def get_db():
    """Open one database connection for the current request and reuse it."""
    if "db" not in g:
        g.db = get_connection()
    return g.db


@app.teardown_appcontext
def close_db(error):
    """Flask runs this after every request. It closes the connection."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ==========================================================================
# SMALL HELPER FUNCTIONS
# ==========================================================================
def error_response(message, status_code=400):
    """Build a standard JSON error answer."""
    return jsonify({"success": False, "error": message}), status_code


def get_json_body():
    """Read the JSON sent by the frontend. Returns None if it is not valid."""
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return data
    return None


def slugify(text):
    """Turn 'Glow Highlighter' into 'glow-highlighter'."""
    text = text.lower().replace(" and ", " ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def to_whole_number(value):
    """Turn 3 or '3' into the integer 3. Returns None if it is not a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def row_to_product(row):
    """Turn a database row into a dictionary the frontend can use."""
    try:
        shades = json.loads(row["shades"])
    except ValueError:
        shades = []
    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "brand": row["brand"],
        "category": row["category"],
        "price": row["price"],
        "description": row["description"],
        "image": row["image"],
        "shades": shades,
        "stock": row["stock"],
        "in_stock": row["stock"] > 0,
    }


def find_product(db, reference):
    """Find a product by its number id (e.g. 3) or its slug (e.g. 'blush')."""
    reference = str(reference).strip()
    if reference.isdigit():
        row = db.execute("SELECT * FROM products WHERE id = ?", (int(reference),)).fetchone()
        if row:
            return row
    return db.execute("SELECT * FROM products WHERE slug = ?", (reference,)).fetchone()


def calculate_delivery_fee(subtotal, delivery_method="standard"):
    """Work out the delivery fee using the store's free-delivery rule."""
    if subtotal <= 0:
        return 0
    if delivery_method == "express":
        return EXPRESS_DELIVERY_FEE
    if subtotal >= FREE_DELIVERY_LIMIT:
        return 0
    return STANDARD_DELIVERY_FEE


# ==========================================================================
# ERROR HANDLERS (always answer with JSON, never with an HTML error page)
# ==========================================================================
@app.errorhandler(404)
def handle_not_found(error):
    return error_response("That address was not found.", 404)


@app.errorhandler(405)
def handle_wrong_method(error):
    return error_response("That request method is not allowed here.", 405)


@app.errorhandler(sqlite3.Error)
def handle_database_error(error):
    print("Database error:", error)  # Shows in the terminal to help you debug
    return error_response("A database error happened. Please try again.", 500)


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    print("Unexpected error:", error)
    return error_response("Something went wrong on the server.", 500)


# ==========================================================================
# HOME / TEST ROUTE
# ==========================================================================
@app.route("/")
def home():
    """Open http://127.0.0.1:5000 to check that the backend is running."""
    return jsonify({
        "success": True,
        "message": "Beauty Haven Store backend is running.",
        "try_this": "/api/products",
    })


# ==========================================================================
# PRODUCTS
# ==========================================================================
def validate_product(data):
    """
    Check product information.
    Returns (clean_product, None) if it is fine,
    or (None, "error message") if something is wrong.
    """
    name = str(data.get("name", "")).strip()
    if not name:
        return None, "Product name is required."

    category = str(data.get("category", "")).strip()
    if category not in ALLOWED_CATEGORIES:
        return None, "Category must be one of: " + ", ".join(ALLOWED_CATEGORIES) + "."

    price = data.get("price")
    if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
        return None, "Price must be a number that is 0 or more."

    stock = to_whole_number(data.get("stock", 0))
    if stock is None or stock < 0:
        return None, "Stock must be a whole number that is 0 or more."

    # Shades can be sent as a list ["Fair", "Deep"] or as text "Fair, Deep"
    shades = data.get("shades", [])
    if isinstance(shades, str):
        shades = [part.strip() for part in shades.split(",") if part.strip()]
    if not isinstance(shades, list) or not all(isinstance(s, str) for s in shades):
        return None, "Shades must be a list of text values, for example [\"Fair\", \"Deep\"]."

    return {
        "name": name,
        "brand": str(data.get("brand", "")).strip(),
        "category": category,
        "price": int(round(price)),
        "description": str(data.get("description", "")).strip(),
        "image": str(data.get("image", "")).strip(),
        "shades": [s.strip() for s in shades if s.strip()],
        "stock": stock,
    }, None


@app.route("/api/products", methods=["GET"])
def get_products():
    """GET /api/products  (optional: ?category=Foundation)"""
    db = get_db()
    category = request.args.get("category", "").strip()

    if category:
        rows = db.execute(
            "SELECT * FROM products WHERE LOWER(category) = LOWER(?) ORDER BY id", (category,)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM products ORDER BY id").fetchall()

    products = [row_to_product(row) for row in rows]
    return jsonify({"success": True, "count": len(products), "products": products})


@app.route("/api/products/<product_ref>", methods=["GET"])
def get_product(product_ref):
    """GET /api/products/3  or  /api/products/blush"""
    row = find_product(get_db(), product_ref)
    if row is None:
        return error_response("Product not found.", 404)
    return jsonify({"success": True, "product": row_to_product(row)})


@app.route("/api/products", methods=["POST"])
def add_product():
    """POST /api/products  (send the new product as JSON)"""
    data = get_json_body()
    if data is None:
        return error_response("Please send valid JSON product data.")

    product, problem = validate_product(data)
    if problem:
        return error_response(problem)

    db = get_db()

    # Make a unique slug. If 'blush' already exists, use 'blush-2', 'blush-3'...
    base_slug = slugify(product["name"]) or "product"
    slug = base_slug
    number = 2
    while db.execute("SELECT id FROM products WHERE slug = ?", (slug,)).fetchone():
        slug = base_slug + "-" + str(number)
        number += 1

    cursor = db.execute(
        """INSERT INTO products
           (slug, name, brand, category, price, description, image, shades, stock)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (slug, product["name"], product["brand"], product["category"],
         product["price"], product["description"], product["image"],
         json.dumps(product["shades"]), product["stock"]),
    )
    db.commit()

    row = db.execute("SELECT * FROM products WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"success": True, "message": "Product added.", "product": row_to_product(row)}), 201


@app.route("/api/products/<product_ref>", methods=["PUT"])
def update_product(product_ref):
    """PUT /api/products/3  (send only the fields you want to change)"""
    data = get_json_body()
    if data is None:
        return error_response("Please send valid JSON product data.")

    db = get_db()
    row = find_product(db, product_ref)
    if row is None:
        return error_response("Product not found.", 404)

    # Start with the current product, then replace whatever was sent.
    merged = row_to_product(row)
    for field in ["name", "brand", "category", "price", "description", "image", "shades", "stock"]:
        if field in data:
            merged[field] = data[field]

    product, problem = validate_product(merged)
    if problem:
        return error_response(problem)

    db.execute(
        """UPDATE products
           SET name = ?, brand = ?, category = ?, price = ?, description = ?,
               image = ?, shades = ?, stock = ?
           WHERE id = ?""",
        (product["name"], product["brand"], product["category"], product["price"],
         product["description"], product["image"], json.dumps(product["shades"]),
         product["stock"], row["id"]),
    )
    db.commit()

    updated = db.execute("SELECT * FROM products WHERE id = ?", (row["id"],)).fetchone()
    return jsonify({"success": True, "message": "Product updated.", "product": row_to_product(updated)})


@app.route("/api/products/<product_ref>", methods=["DELETE"])
def delete_product(product_ref):
    """DELETE /api/products/3"""
    db = get_db()
    row = find_product(db, product_ref)
    if row is None:
        return error_response("Product not found.", 404)

    db.execute("DELETE FROM cart_items WHERE product_id = ?", (row["id"],))
    db.execute("DELETE FROM products WHERE id = ?", (row["id"],))
    db.commit()
    return jsonify({"success": True, "message": "Product deleted."})


# ==========================================================================
# CART
# The browser keeps a random cart_id (in localStorage) and sends it in the
# address, so the server knows which cart belongs to which visitor.
# ==========================================================================
def check_cart_id(cart_id):
    """A cart_id may only contain letters, numbers, - and _ (max 64 chars)."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cart_id):
        return error_response("Invalid cart id.")
    return None


def build_cart_response(db, cart_id):
    """Read a cart from the database and calculate its totals."""
    rows = db.execute(
        """SELECT ci.id AS item_id, ci.shade, ci.quantity,
                  p.id AS product_id, p.slug, p.name, p.brand, p.price, p.image, p.stock
           FROM cart_items ci
           JOIN products p ON p.id = ci.product_id
           WHERE ci.cart_id = ?
           ORDER BY ci.id""",
        (cart_id,),
    ).fetchall()

    items = []
    subtotal = 0
    item_count = 0
    for row in rows:
        line_total = row["price"] * row["quantity"]
        subtotal += line_total
        item_count += row["quantity"]
        items.append({
            "item_id": row["item_id"],
            "product_id": row["product_id"],
            "slug": row["slug"],
            "name": row["name"],
            "brand": row["brand"],
            "image": row["image"],
            "shade": row["shade"],
            "price": row["price"],
            "quantity": row["quantity"],
            "line_total": line_total,
        })

    delivery_fee = calculate_delivery_fee(subtotal, "standard")
    response = {
        "success": True,
        "cart_id": cart_id,
        "items": items,
        "item_count": item_count,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": subtotal + delivery_fee,
        "free_delivery": subtotal >= FREE_DELIVERY_LIMIT,
        "free_delivery_limit": FREE_DELIVERY_LIMIT,
    }
    if not items:
        response["message"] = "Your cart is empty."
    return response


@app.route("/api/cart/<cart_id>", methods=["GET"])
def view_cart(cart_id):
    """GET /api/cart/<cart_id>  -> the cart contents, subtotal and total."""
    problem = check_cart_id(cart_id)
    if problem:
        return problem
    return jsonify(build_cart_response(get_db(), cart_id))


@app.route("/api/cart/<cart_id>/items", methods=["POST"])
def add_cart_item(cart_id):
    """POST /api/cart/<cart_id>/items  body: {product_id, shade, quantity}"""
    problem = check_cart_id(cart_id)
    if problem:
        return problem

    data = get_json_body()
    if data is None or "product_id" not in data:
        return error_response("Please send a product_id.")

    quantity = to_whole_number(data.get("quantity", 1))
    if quantity is None or quantity < 1:
        return error_response("Quantity must be a whole number of 1 or more.")

    db = get_db()
    product = find_product(db, data["product_id"])
    if product is None:
        return error_response("Product not found.", 404)

    shade = str(data.get("shade", "")).strip()[:50]

    existing = db.execute(
        "SELECT id, quantity FROM cart_items WHERE cart_id = ? AND product_id = ? AND shade = ?",
        (cart_id, product["id"], shade),
    ).fetchone()
    new_quantity = min((existing["quantity"] if existing else 0) + quantity, MAX_QUANTITY)

    if product["stock"] < 1:
        return error_response(product["name"] + " is out of stock.")
    if new_quantity > product["stock"]:
        return error_response("Only " + str(product["stock"]) + " of " + product["name"] + " left in stock.")

    if existing:
        db.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (new_quantity, existing["id"]))
    else:
        db.execute(
            "INSERT INTO cart_items (cart_id, product_id, shade, quantity) VALUES (?, ?, ?, ?)",
            (cart_id, product["id"], shade, new_quantity),
        )
    db.commit()
    return jsonify(build_cart_response(db, cart_id)), 201


@app.route("/api/cart/<cart_id>/items/<int:item_id>", methods=["PUT"])
def update_cart_item(cart_id, item_id):
    """PUT /api/cart/<cart_id>/items/<item_id>  body: {quantity}"""
    problem = check_cart_id(cart_id)
    if problem:
        return problem

    data = get_json_body()
    quantity = to_whole_number(data.get("quantity")) if data else None
    if quantity is None or quantity < 1:
        return error_response("Quantity must be a whole number of 1 or more.")

    db = get_db()
    row = db.execute(
        """SELECT ci.id, p.stock, p.name FROM cart_items ci
           JOIN products p ON p.id = ci.product_id
           WHERE ci.id = ? AND ci.cart_id = ?""",
        (item_id, cart_id),
    ).fetchone()
    if row is None:
        return error_response("Cart item not found.", 404)

    quantity = min(quantity, MAX_QUANTITY)
    if quantity > row["stock"]:
        return error_response("Only " + str(row["stock"]) + " of " + row["name"] + " left in stock.")

    db.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (quantity, item_id))
    db.commit()
    return jsonify(build_cart_response(db, cart_id))


@app.route("/api/cart/<cart_id>/items/<int:item_id>", methods=["DELETE"])
def remove_cart_item(cart_id, item_id):
    """DELETE /api/cart/<cart_id>/items/<item_id>"""
    problem = check_cart_id(cart_id)
    if problem:
        return problem

    db = get_db()
    cursor = db.execute("DELETE FROM cart_items WHERE id = ? AND cart_id = ?", (item_id, cart_id))
    db.commit()
    if cursor.rowcount == 0:
        return error_response("Cart item not found.", 404)
    return jsonify(build_cart_response(db, cart_id))


@app.route("/api/cart/<cart_id>", methods=["PUT"])
def replace_cart(cart_id):
    """
    PUT /api/cart/<cart_id>  body: {"items": [{product_id, shade, quantity}, ...]}
    Replaces the whole cart. The frontend uses this to keep the server cart
    the same as its localStorage cart with a single request.
    """
    problem = check_cart_id(cart_id)
    if problem:
        return problem

    data = get_json_body()
    if data is None or not isinstance(data.get("items"), list):
        return error_response("Please send a list called items.")

    db = get_db()
    cleaned = {}  # (product_id, shade) -> quantity
    for entry in data["items"]:
        if not isinstance(entry, dict) or "product_id" not in entry:
            return error_response("Each item needs a product_id.")
        product = find_product(db, entry["product_id"])
        if product is None:
            return error_response("Product not found: " + str(entry["product_id"]), 404)
        quantity = to_whole_number(entry.get("quantity", 1))
        if quantity is None or quantity < 1:
            return error_response("Each quantity must be a whole number of 1 or more.")
        shade = str(entry.get("shade", "")).strip()[:50]
        key = (product["id"], shade)
        cleaned[key] = min(cleaned.get(key, 0) + quantity, MAX_QUANTITY)

    db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
    for (product_id, shade), quantity in cleaned.items():
        db.execute(
            "INSERT INTO cart_items (cart_id, product_id, shade, quantity) VALUES (?, ?, ?, ?)",
            (cart_id, product_id, shade, quantity),
        )
    db.commit()
    return jsonify(build_cart_response(db, cart_id))


@app.route("/api/cart/<cart_id>", methods=["DELETE"])
def clear_cart(cart_id):
    """DELETE /api/cart/<cart_id>  -> empties the cart."""
    problem = check_cart_id(cart_id)
    if problem:
        return problem
    db = get_db()
    db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
    db.commit()
    return jsonify(build_cart_response(db, cart_id))


# ==========================================================================
# ORDERS
# ==========================================================================
def format_order_number(order_id):
    """Order id 7 becomes 'BH00007'."""
    return "BH" + str(order_id).zfill(5)


def validate_order_details(data):
    """Check the customer, address and payment details. Returns an error text or None."""
    required = [
        ("customer_name", "your name"),
        ("email", "your email address"),
        ("phone", "your phone number"),
        ("address_line1", "your street address"),
        ("city", "your city"),
        ("state", "your state"),
    ]
    for field, label in required:
        if not str(data.get(field, "")).strip():
            return "Please enter " + label + "."

    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(data["email"]).strip()):
        return "Please enter a valid email address."

    phone_digits = re.sub(r"\D", "", str(data["phone"]))
    if len(phone_digits) < 10:
        return "Please enter a valid phone number."

    if data.get("delivery_method") not in ALLOWED_DELIVERY_METHODS:
        return "Please choose a delivery method (standard or express)."
    if data.get("payment_method") not in ALLOWED_PAYMENT_METHODS:
        return "Please choose a payment method (card, bank-transfer or pay-on-delivery)."
    return None


def get_order_items_from_request(db, data):
    """
    Get the list of things being ordered. They come either from the "items"
    list in the request, or from the saved server cart (if cart_id is sent).
    Returns a list of (product_row, shade, quantity).
    """
    entries = data.get("items")
    if not isinstance(entries, list) or len(entries) == 0:
        cart_id = str(data.get("cart_id", "")).strip()
        entries = []
        if cart_id:
            rows = db.execute(
                "SELECT product_id, shade, quantity FROM cart_items WHERE cart_id = ?", (cart_id,)
            ).fetchall()
            entries = [{"product_id": r["product_id"], "shade": r["shade"], "quantity": r["quantity"]} for r in rows]

    if len(entries) == 0:
        return None, "Your cart is empty."

    lines = []
    for entry in entries:
        if not isinstance(entry, dict) or "product_id" not in entry:
            return None, "Each ordered item needs a product_id."
        product = find_product(db, entry["product_id"])
        if product is None:
            return None, "Product not found: " + str(entry["product_id"])
        quantity = to_whole_number(entry.get("quantity", 1))
        if quantity is None or quantity < 1 or quantity > MAX_QUANTITY:
            return None, "Quantity for " + product["name"] + " must be between 1 and " + str(MAX_QUANTITY) + "."
        lines.append((product, str(entry.get("shade", "")).strip()[:50], quantity))
    return lines, None


@app.route("/api/orders", methods=["POST"])
def create_order():
    """POST /api/orders  -> records a new order (no real payment is taken)."""
    data = get_json_body()
    if data is None:
        return error_response("Please send valid JSON order data.")

    problem = validate_order_details(data)
    if problem:
        return error_response(problem)

    db = get_db()
    lines, problem = get_order_items_from_request(db, data)
    if problem:
        return error_response(problem)

    # Check stock. Add up the quantity per product first (a product could
    # appear twice with different shades).
    wanted = {}
    for product, shade, quantity in lines:
        wanted[product["id"]] = wanted.get(product["id"], 0) + quantity
    for product, shade, quantity in lines:
        if wanted[product["id"]] > product["stock"]:
            return error_response(
                "Sorry, only " + str(product["stock"]) + " of " + product["name"] + " left in stock."
            )

    # The SERVER works out the prices from the database.
    # We never trust prices sent by the browser.
    subtotal = sum(product["price"] * quantity for product, shade, quantity in lines)
    delivery_fee = calculate_delivery_fee(subtotal, data["delivery_method"])
    total = subtotal + delivery_fee

    cursor = db.execute(
        """INSERT INTO orders
           (customer_name, email, phone, address_line1, address_line2, city, state,
            postal_code, delivery_method, payment_method, notes,
            subtotal, delivery_fee, total, status, order_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(data["customer_name"]).strip(), str(data["email"]).strip(),
            str(data["phone"]).strip(), str(data["address_line1"]).strip(),
            str(data.get("address_line2", "")).strip(), str(data["city"]).strip(),
            str(data["state"]).strip(), str(data.get("postal_code", "")).strip(),
            data["delivery_method"], data["payment_method"],
            str(data.get("notes", "")).strip(),
            subtotal, delivery_fee, total, "Pending",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    order_id = cursor.lastrowid

    for product, shade, quantity in lines:
        db.execute(
            """INSERT INTO order_items
               (order_id, product_id, product_name, shade, unit_price, quantity, line_total)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (order_id, product["id"], product["name"], shade,
             product["price"], quantity, product["price"] * quantity),
        )
        db.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product["id"]))

    # If the order was linked to a server cart, empty that cart.
    cart_id = str(data.get("cart_id", "")).strip()
    if cart_id:
        db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))

    db.commit()  # Save everything together, or nothing if an error happened

    return jsonify({
        "success": True,
        "message": "Order placed successfully.",
        "order_id": order_id,
        "order_number": format_order_number(order_id),
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
        "status": "Pending",
    }), 201


@app.route("/api/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    """GET /api/orders/7  -> the order and the products in it."""
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        return error_response("Order not found.", 404)

    item_rows = db.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    items = [{
        "product_id": r["product_id"],
        "product_name": r["product_name"],
        "shade": r["shade"],
        "unit_price": r["unit_price"],
        "quantity": r["quantity"],
        "line_total": r["line_total"],
    } for r in item_rows]

    return jsonify({
        "success": True,
        "order": {
            "id": order["id"],
            "order_number": format_order_number(order["id"]),
            "customer_name": order["customer_name"],
            "email": order["email"],
            "phone": order["phone"],
            "address": {
                "line1": order["address_line1"],
                "line2": order["address_line2"],
                "city": order["city"],
                "state": order["state"],
                "postal_code": order["postal_code"],
            },
            "delivery_method": order["delivery_method"],
            "payment_method": order["payment_method"],
            "notes": order["notes"],
            "subtotal": order["subtotal"],
            "delivery_fee": order["delivery_fee"],
            "total": order["total"],
            "status": order["status"],
            "order_date": order["order_date"],
            "items": items,
        },
    })



init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)