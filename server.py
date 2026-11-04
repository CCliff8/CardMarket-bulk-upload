#!/usr/bin/env python3
"""Local Flask API wrapping bulk_watchlist.py for the React UI (127.0.0.1:5001)."""
import json
import threading
import time

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS  # noqa: F401  (optional, see below)

import bulk_watchlist as bw

app = Flask(__name__)
CORS(app)

state = {"status": "idle", "total": 0, "index": 0, "log": [], "logged_in": False, "stop": False}
login_event = threading.Event()


def log(msg):
    state["log"].append(msg)
    print(msg)


@app.get("/api/sets")
def sets():
    return jsonify(bw.list_sets())


@app.get("/api/sets/<set_id>/cards")
def cards(set_id):
    try:
        brief = requests.get(f"{bw.API}/sets/{set_id}", timeout=30).json()["cards"]
    except Exception as e:
        return jsonify(error=str(e)), 502
    full = bw.fetch_cards(set_id)
    by_id = {c["id"]: c for c in full}
    for b in brief:
        c = by_id.get(b["id"], {})
        c["image"] = f"{b['image']}/low.webp" if b.get("image") else None
    return jsonify(full)


def worker(cards, watchlist, delay):
    from playwright.sync_api import sync_playwright

    done = bw.load_done()
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(str(bw.PROFILE), headless=False)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://www.cardmarket.com/en/Pokemon")
            state["status"] = "waiting_login"
            log("Log in in the browser window, then click 'I'm logged in'.")
            login_event.wait()
            state["status"] = "running"
            for i, c in enumerate(cards, 1):
                if state["stop"]:
                    log("Stopped.")
                    break
                state["index"] = i
                if c["id"] in done:
                    log(f"skip {c['name']} (already done)")
                    continue
                try:
                    bw.add_to_watchlist(page, c["url"], watchlist)
                    done.add(c["id"])
                    bw.DONE_FILE.write_text(json.dumps(sorted(done)))
                    log(f"added {c['id']} {c['name']}")
                except Exception as e:
                    log(f"FAILED {c['id']} {c['name']} ({page.url}): {str(e).splitlines()[0]}")
                time.sleep(delay)
            ctx.close()
    except Exception as e:
        log(f"ERROR: {e}")
    state["status"] = "finished"


@app.post("/api/start")
def start():
    if state["status"] in ("running", "waiting_login", "starting"):
        return jsonify(error="already running"), 409
    d = request.get_json()
    cs = [c for c in d["cards"] if c.get("url")]
    state.update(status="starting", total=len(cs), index=0, log=[], stop=False)
    login_event.clear()
    threading.Thread(target=worker, args=(cs, d["watchlist"], float(d.get("delay", 3))), daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/logged-in")
def logged_in():
    login_event.set()
    return jsonify(ok=True)


@app.post("/api/stop")
def stop():
    state["stop"] = True
    login_event.set()
    return jsonify(ok=True)


@app.get("/api/status")
def status():
    return jsonify({k: v for k, v in state.items() if k != "stop"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
