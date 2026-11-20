import os
from datetime import date

import pymssql
from flask import Flask, jsonify, request

from .database import connect
from .migrate import run_migrations
from .repository import SupplyRepository
from .service import SupplyService

app = Flask(__name__)

@app.get("/")
def home():
    return jsonify({
        "service": "supplies",
        "message": "YourTurn Supplies service is running"
    })

@app.get("/health")
def health():
    version = os.environ.get("APP_VERSION", "local")
    try:
        with connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM dbo.schema_migrations")
            cursor.fetchone()
            cursor.execute("UPDATE dbo.schema_migrations SET applied_at = applied_at WHERE 1 = 0")
    except pymssql.Error:
        return jsonify(status="unavailable", db="unavailable", version=version), 503
    return jsonify(status="ok", db="ok", version=version)


def get_roommates():
    # Use the original seed roster until the Chores API is wired in.
    return [{"id": index, "name": name}
            for index, name in enumerate(("Alex", "Sam", "Jordan", "Maya"), start=1)]


@app.get("/supplies/")
def supplies_page():
    roommates = get_roommates()
    with connect() as conn:
        service = SupplyService(SupplyRepository(conn, roommates))
        return jsonify(supplies=service.overview(), roommates=roommates,
                       spending=service.monthly_spending(date.today()))


@app.post("/supplies/<int:supply_id>/bought")
def mark_bought(supply_id):
    payload = request.form or request.get_json(silent=True)
    if not hasattr(payload, "get"):
        return jsonify(error="A roommate ID and price are required."), 400
    roommate_id = payload.get("roommate_id")
    if isinstance(roommate_id, str) and roommate_id.isascii() and roommate_id.isdecimal() and len(roommate_id) <= 10:
        roommate_id = int(roommate_id)
    raw_price = payload.get("price")
    if type(roommate_id) is not int or isinstance(raw_price, bool):
        return jsonify(error="A roommate ID and price are required."), 400
    try:
        price = float(raw_price)
    except (TypeError, ValueError, OverflowError):
        return jsonify(error="Enter a valid price."), 400
    roommates = get_roommates()
    with connect() as conn:
        try:
            service = SupplyService(SupplyRepository(conn, roommates))
            service.record_purchase(supply_id, roommate_id, price, date.today())
        except ValueError as error:
            return jsonify(error=str(error)), 400
    return "", 204

if __name__ == "__main__":
    run_migrations()
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
