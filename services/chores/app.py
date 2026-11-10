import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/")
def home():
    return jsonify({
        "service": "chores",
        "message": "YourTurn Chores service is running"
    })

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "chores"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)