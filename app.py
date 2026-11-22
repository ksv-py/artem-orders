"""Artem Orders - furniture / interior order tracking for Artem Interiors
& Constructions (Delhi). Mobile-first Flask + SQLite web app.

v1: no login (single workshop-manager view), no WhatsApp API (wa.me share
links only), no face recognition or payments. See README.md.
"""
import os
import sqlite3
from datetime import date, timedelta
from urllib.parse import quote

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, send_from_directory, url_for)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "artem_orders.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "artem-orders-dev-key")
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB per upload

STATUSES = ["New", "Cutting", "Assembly", "Polish", "Ready", "Delivered"]
ITEMS = ["Wardrobe / Almari", "Modular Kitchen", "Bed", "Dining Table",
         "TV Unit", "Door", "Other"]
WOODS = ["Teak", "Sheesham", "Plywood", "MDF", "Laminate", "Other"]

# ---------------------------------------------------------------- db helpers


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS karigars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            skill TEXT NOT NULL,
            phone TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            item TEXT NOT NULL,
            size TEXT,
            wood TEXT,
            status TEXT NOT NULL DEFAULT 'New',
            delivery_date TEXT,
            karigar_id INTEGER REFERENCES karigars(id),
            notes TEXT,
            design_photo TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            filename TEXT NOT NULL,
            caption TEXT,
            stage TEXT,
            created_at TEXT NOT NULL
        );
    """)
    db.commit()
    db.close()


def seed_db():
    """Demo seed data, only when the tables are empty. Clearly demo names
    from the reference Reel's world, not real clients."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    if db.execute("SELECT COUNT(*) FROM karigars").fetchone()[0] > 0:
        db.close()
        return
    karigars = [
        ("Raju", "Carpenter", ""),
        ("Sunil", "Carpenter", ""),
        ("Imran", "Polisher", ""),
        ("Gopal", "Helper", ""),
    ]
    db.executemany("INSERT INTO karigars (name, skill, phone) VALUES (?, ?, ?)",
                   karigars)
    today = date.today().isoformat()
    orders = [
        # customer, item, size, wood, status, delivery_date, karigar_id, notes
        ("Sharma ji", "Wardrobe / Almari", "6 ft x 7 ft", "Teak",
         "Assembly", "2026-11-28", 1, "Sliding doors, mirror on left shutter."),
        ("Verma ji", "Modular Kitchen", "10 ft x 8 ft", "Plywood",
         "Cutting", "2026-12-02", 2, "Laminate finish, soft-close hinges."),
        ("Gupta ji", "Bed", "Queen 6 ft x 6.5 ft, with storage", "Sheesham",
         "Polish", "2026-11-20", 3, "Headboard with side tables."),
        ("Mehta ji", "TV Unit", "8 ft wall unit", "MDF",
         "New", "2026-11-30", 1, "Laminate finish, LED strip lighting."),
        ("Khan ji", "Dining Table", "6-seater", "Teak",
         "New", "2026-12-05", 4, "With 6 chairs, polish to match almari."),
    ]
    for o in orders:
        db.execute(
            """INSERT INTO orders (customer_name, item, size, wood, status,
                 delivery_date, karigar_id, notes, design_photo, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?)""",
            (*o, today))
    db.commit()
    db.close()


# ---------------------------------------------------------------- helpers


def parse_date(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def order_state(order, today):
    """Return 'overdue', 'due-today', 'due-soon' or '' for an order row."""
    if order["status"] == "Delivered":
        return ""
    d = parse_date(order["delivery_date"])
    if d is None:
        return ""
    if d < today:
        return "overdue"
    if d == today:
        return "due-today"
    if d <= today + timedelta(days=7):
        return "due-soon"
    return ""


def order_dict(row, today):
    d = dict(row)
    d["state"] = order_state(row, today)
    d["karigar_name"] = None
    if row["karigar_id"]:
        k = get_db().execute("SELECT name FROM karigars WHERE id = ?",
                             (row["karigar_id"],)).fetchone()
        d["karigar_name"] = k["name"] if k else None
    return d


def wa_link(order):
    """WhatsApp share link (wa.me text link, no API). The customer picks
    the chat after tapping; photos cannot ride along in the link itself."""
    text = (
        f"Artem Interiors - Order Update\n"
        f"Customer: {order['customer_name']}\n"
        f"Item: {order['item']}"
        + (f" ({order['size']})" if order["size"] else "")
        + f"\nStatus: {order['status']}\n"
        + (f"Delivery date: {order['delivery_date']}\n"
           if order["delivery_date"] else "")
        + "Work photos are in the app, I will share them here too."
    )
    return "https://wa.me/?text=" + quote(text)


def save_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return ""
    name = secure_filename(file_storage.filename)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        return ""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, name)
    stem, i = name.rsplit(".", 1)[0], 1
    while os.path.exists(path):
        name = f"{stem}-{i}.{ext}"
        path = os.path.join(UPLOAD_DIR, name)
        i += 1
    file_storage.save(path)
    return name


# ---------------------------------------------------------------- routes


@app.route("/")
def index():
    db = get_db()
    today = date.today()
    rows = db.execute(
        "SELECT * FROM orders ORDER BY delivery_date ASC").fetchall()
    orders = [order_dict(r, today) for r in rows]
    in_progress = [o for o in orders if o["status"] != "Delivered"]
    delivered = [o for o in orders if o["status"] == "Delivered"]
    overdue = [o for o in orders if o["state"] == "overdue"]
    due_week = [o for o in orders
                if o["state"] in ("due-today", "due-soon")
                and o["status"] != "Delivered"]
    karigars = db.execute("SELECT * FROM karigars ORDER BY name").fetchall()
    workload = []
    for k in karigars:
        jobs = [o for o in in_progress if o["karigar_id"] == k["id"]]
        workload.append({"karigar": k, "jobs": jobs})
    return render_template("index.html", orders=orders,
                           in_progress=len(in_progress),
                           delivered=len(delivered), overdue=overdue,
                           due_week=due_week, workload=workload,
                           today=today)


@app.route("/orders")
def order_list():
    db = get_db()
    today = date.today()
    rows = db.execute(
        "SELECT * FROM orders ORDER BY delivery_date ASC").fetchall()
    orders = [order_dict(r, today) for r in rows]
    return render_template("orders.html", orders=orders, today=today)


@app.route("/orders/new", methods=["GET", "POST"])
def order_new():
    db = get_db()
    if request.method == "POST":
        customer = request.form.get("customer_name", "").strip()
        item = request.form.get("item", "Other")
        if not customer:
            flash("Customer name is needed.")
            return redirect(url_for("order_new"))
        design_photo = save_upload(request.files.get("design_photo"))
        db.execute(
            """INSERT INTO orders (customer_name, item, size, wood, status,
                 delivery_date, karigar_id, notes, design_photo, created_at)
               VALUES (?, ?, ?, ?, 'New', ?, ?, ?, ?, ?)""",
            (customer, item,
             request.form.get("size", "").strip(),
             request.form.get("wood", "Other"),
             request.form.get("delivery_date", "").strip() or None,
             request.form.get("karigar_id") or None,
             request.form.get("notes", "").strip(),
             design_photo, date.today().isoformat()))
        db.commit()
        flash("Order added.")
        return redirect(url_for("order_list"))
    karigars = db.execute("SELECT * FROM karigars ORDER BY name").fetchall()
    return render_template("order_form.html", items=ITEMS, woods=WOODS,
                           statuses=STATUSES, karigars=karigars)


@app.route("/orders/<int:order_id>")
def order_detail(order_id):
    db = get_db()
    today = date.today()
    row = db.execute("SELECT * FROM orders WHERE id = ?",
                     (order_id,)).fetchone()
    if row is None:
        abort(404)
    order = order_dict(row, today)
    photos = db.execute(
        "SELECT * FROM photos WHERE order_id = ? ORDER BY id DESC",
        (order_id,)).fetchall()
    karigars = db.execute("SELECT * FROM karigars ORDER BY name").fetchall()
    return render_template("order_detail.html", order=order, photos=photos,
                           karigars=karigars, statuses=STATUSES,
                           wa_link=wa_link(order), today=today)


@app.route("/orders/<int:order_id>/status", methods=["POST"])
def order_status(order_id):
    db = get_db()
    status = request.form.get("status", "")
    karigar_id = request.form.get("karigar_id") or None
    if status not in STATUSES:
        flash("Unknown status.")
        return redirect(url_for("order_detail", order_id=order_id))
    cur = db.execute("UPDATE orders SET status = ?, karigar_id = ? "
                     "WHERE id = ?", (status, karigar_id, order_id))
    if cur.rowcount == 0:
        abort(404)
    db.commit()
    flash(f"Status updated to {status}.")
    return redirect(url_for("order_detail", order_id=order_id))


@app.route("/orders/<int:order_id>/photo", methods=["POST"])
def order_photo(order_id):
    db = get_db()
    row = db.execute("SELECT id FROM orders WHERE id = ?",
                     (order_id,)).fetchone()
    if row is None:
        abort(404)
    filename = save_upload(request.files.get("photo"))
    if not filename:
        flash("Please choose a photo (png, jpg, jpeg, webp or gif).")
        return redirect(url_for("order_detail", order_id=order_id))
    db.execute(
        """INSERT INTO photos (order_id, filename, caption, stage, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (order_id, filename,
         request.form.get("caption", "").strip(),
         request.form.get("stage", "").strip(),
         date.today().isoformat()))
    db.commit()
    flash("Progress photo added.")
    return redirect(url_for("order_detail", order_id=order_id))


@app.route("/karigars", methods=["GET", "POST"])
def karigar_list():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        skill = request.form.get("skill", "").strip()
        if not name or not skill:
            flash("Karigar name and skill are needed.")
            return redirect(url_for("karigar_list"))
        db.execute("INSERT INTO karigars (name, skill, phone) "
                   "VALUES (?, ?, ?)",
                   (name, skill, request.form.get("phone", "").strip()))
        db.commit()
        flash("Karigar added.")
        return redirect(url_for("karigar_list"))
    today = date.today()
    karigars = db.execute("SELECT * FROM karigars ORDER BY name").fetchall()
    workload = []
    for k in karigars:
        rows = db.execute(
            "SELECT * FROM orders WHERE karigar_id = ? "
            "AND status != 'Delivered' ORDER BY delivery_date ASC",
            (k["id"],)).fetchall()
        workload.append({"karigar": k,
                         "jobs": [order_dict(r, today) for r in rows]})
    return render_template("karigars.html", workload=workload)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    init_db()
    seed_db()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
