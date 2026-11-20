import os
from datetime import date

import pymssql
from flask import Flask, jsonify, request

from .database import connect
from .migrate import run_migrations
from .repository import ChoreRepository
from .service import ChoreService

app = Flask(__name__)

@app.get("/")
def home():
    return jsonify({
        "service": "chores",
        "message": "YourTurn Chores service is running"
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


@app.get("/chores/")
def chores_page():
    with connect() as conn:
        service = ChoreService(ChoreRepository(conn))
        today = date.today()
        return jsonify(chores=service.overview(today), roommates=service.roommates(),
                       stats=service.monthly_stats(today))


@app.get("/roommates")
def roommates():
    with connect() as conn:
        return jsonify(ChoreRepository(conn).list_roommates())


@app.post("/chores/<int:chore_id>/done")
def mark_done(chore_id):
    payload = request.form or request.get_json(silent=True)
    roommate_id = payload.get("roommate_id") if hasattr(payload, "get") else None
    if isinstance(roommate_id, str) and roommate_id.isascii() and roommate_id.isdecimal() and len(roommate_id) <= 10:
        roommate_id = int(roommate_id)
    if type(roommate_id) is not int:
        return jsonify(error="A roommate ID is required."), 400
    with connect() as conn:
        try:
            ChoreService(ChoreRepository(conn)).mark_done(chore_id, roommate_id, date.today())
        except ValueError as error:
            return jsonify(error=str(error)), 400
    return "", 204

if __name__ == "__main__":
    run_migrations()
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
