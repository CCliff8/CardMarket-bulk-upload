#!/usr/bin/env python3
"""Bulk-add Pokémon cards of a TCGdex set to a Cardmarket watchlist (Playwright)."""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

API = "https://api.tcgdex.net/v2/en"
HERE = Path(__file__).parent
PROFILE = HERE / "browser_profile"
DONE_FILE = HERE / "done.json"
CM_URL = "https://www.cardmarket.com/en/Pokemon/Products?idProduct={}"


def list_sets():
    return requests.get(f"{API}/sets", timeout=30).json()


def parse_numbers(spec):
    """'1-5,8,12' -> {'1','2','3','4','5','8','12'} (compared against localId, leading zeros ignored)."""
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(str(n) for n in range(int(a), int(b) + 1))
        elif part:
            out.add(str(int(part)))
    return out


def fetch_cards(set_id, numbers=None):
    brief = requests.get(f"{API}/sets/{set_id}", timeout=30).json()["cards"]
    if numbers:
        brief = [c for c in brief if c["localId"].lstrip("0") in numbers]

    def detail(c):
        d = requests.get(f"{API}/cards/{c['id']}", timeout=30).json()
        pid = (d.get("pricing") or {}).get("cardmarket", {}).get("idProduct")
        return {"id": c["id"], "number": c["localId"], "name": c["name"],
                "idProduct": pid, "url": CM_URL.format(pid) if pid else None}

    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(detail, brief))


def load_done():
    return set(json.loads(DONE_FILE.read_text())) if DONE_FILE.exists() else set()


def add_to_watchlist(page, url, watchlist):
    # NOTE: selectors are unverified guesses; adjust against the real Cardmarket DOM.
    page.goto(url, wait_until="domcontentloaded")
    page.locator("a[href*='Watchlist'], button:has-text('Watchlist')").first.click()
    page.get_by_text(watchlist, exact=True).first.click()
    page.wait_for_timeout(500)


def run(cards, watchlist, delay):
    from playwright.sync_api import sync_playwright

    done = load_done()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.cardmarket.com/en/Pokemon")
        input("Log in to Cardmarket in the browser window, then press Enter here... ")
        for i, c in enumerate(cards, 1):
            if c["id"] in done:
                print(f"[{i}/{len(cards)}] skip {c['id']} (already done)")
                continue
            try:
                add_to_watchlist(page, c["url"], watchlist)
                done.add(c["id"])
                DONE_FILE.write_text(json.dumps(sorted(done)))
                print(f"[{i}/{len(cards)}] added {c['id']} {c['name']}")
            except Exception as e:
                print(f"[{i}/{len(cards)}] FAILED {c['id']} {c['name']} ({page.url}): {e}")
            time.sleep(delay)
        ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list-sets", action="store_true")
    ap.add_argument("--set", help="TCGdex set id, e.g. sv03.5")
    ap.add_argument("--numbers", help="e.g. 1-5,8")
    ap.add_argument("--watchlist", help="Name of the target watchlist")
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.list_sets:
        for s in list_sets():
            print(s["id"], "-", s["name"])
        return
    if not a.set:
        ap.error("--set is required")
    cards = fetch_cards(a.set, parse_numbers(a.numbers) if a.numbers else None)
    missing = [c for c in cards if not c["url"]]
    cards = [c for c in cards if c["url"]]
    if a.dry_run:
        for c in cards:
            print(c["id"], c["name"], c["url"])
        print(f"{len(cards)} cards, {len(missing)} without Cardmarket id")
        return
    if not a.watchlist:
        ap.error("--watchlist is required unless --dry-run")
    run(cards, a.watchlist, a.delay)


if __name__ == "__main__":
    sys.exit(main())
