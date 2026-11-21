import json
import os
from datetime import date
from time import perf_counter
from urllib.error import URLError
from urllib.request import urlopen

import pymssql
from flask import Flask, g, jsonify, request

from .database import connect
from .migrate import run_migrations
from .repository import SupplyRepository
from .service import SupplyService

app = Flask(__name__)


@app.before_request
def start_request_timer():
    g.started_at = perf_counter()


@app.after_request
def finish_request(response):
    origin = request.headers.get("Origin")
    response.vary.add("Origin")
    if origin and origin == os.environ.get("UI_ORIGIN"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    duration_ms = (perf_counter() - g.started_at) * 1000
    print(f"{request.method} {request.path} {response.status_code} {duration_ms:.1f}ms", flush=True)
    return response

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
    base_url = os.environ.get("CHORES_SERVICE_URL")
    if not base_url:
        return []
    try:
        with urlopen(base_url.rstrip("/") + "/roommates", timeout=2) as response:
            return json.load(response)
    except (URLError, OSError, ValueError):
        return []


@app.get("/supplies/")
def supplies_page():
    roommates = get_roommates()
    with connect() as conn:
        service = SupplyService(SupplyRepository(conn, roommates))
        return jsonify(supplies=service.overview(), roommates=roommates,
                       spending=service.monthly_spending(date.today()),
                       warning=None if roommates else "Roommate information is temporarily unavailable.")


@app.get("/supplies/spending")
def spending():
    with connect() as conn:
        repository = SupplyRepository(conn, [])
        return jsonify(repository.spent_since(date.today().replace(day=1).isoformat()))


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
    if not roommates:
        return jsonify(error="Roommate information is unavailable. Try again shortly."), 503
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
