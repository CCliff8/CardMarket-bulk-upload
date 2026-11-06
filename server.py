#!/usr/bin/env python3
"""Local Flask API wrapping bulk_watchlist.py for the React UI (127.0.0.1:5001)."""
import threading

from flask import Flask, jsonify, request
from flask_cors import CORS

import bulk_watchlist as bw

app = Flask(__name__)
CORS(app)

state = {"status": "idle", "result": None, "error": None}
login_event = threading.Event()


@app.get("/api/search")
def search():
    q = request.args.get("q", "").strip()
    return jsonify(bw.search_cards(q) if len(q) >= 2 else [])


@app.get("/api/card-line/<path:card_id>")
def card_line(card_id):
    return jsonify(text=bw.card_line_text(card_id))


@app.post("/api/resolve")
def resolve():
    return jsonify(bw.resolve_text(request.get_json()["text"]))


def worker(lines, list_name):
    try:
        state["result"] = bw.run(lines, list_name, wait_for_login)
        state["status"] = "finished"
    except Exception as e:
        state.update(status="error", error=str(e).splitlines()[0])


def wait_for_login():
    state["status"] = "waiting_login"
    login_event.wait()
    state["status"] = "running"


@app.post("/api/start")
def start():
    if state["status"] in ("starting", "waiting_login", "running"):
        return jsonify(error="already running"), 409
    d = request.get_json()
    lines = [l for l in d["lines"] if l.strip()]
    if not lines or not d.get("list"):
        return jsonify(error="lines and list name required"), 400
    if not bw.LIST_NAME_RE.match(d["list"].strip()):
        return jsonify(error="List name: 1-30 characters, letters, numbers, spaces and hyphens only."), 400
    if len(lines) > bw.MAX_ENTRIES:
        return jsonify(error=f"max {bw.MAX_ENTRIES} entries per run"), 400
    state.update(status="starting", result=None, error=None)
    login_event.clear()
    threading.Thread(target=worker, args=(lines, d["list"]), daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/logged-in")
def logged_in():
    login_event.set()
    return jsonify(ok=True)


@app.get("/api/status")
def status():
    return jsonify(state)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
