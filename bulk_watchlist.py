#!/usr/bin/env python3
"""Paste card names -> build Cardmarket deck-list lines -> add them to a Wants list (Playwright)."""
import argparse
import re
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

API = "https://api.tcgdex.net/v2/en"
HERE = Path(__file__).parent
PROFILE = HERE / "chrome_profile"
DEBUG = HERE / "debug"
WANTS_URL = "https://www.cardmarket.com/en/Pokemon/Wants"
MAX_ENTRIES = 150
MAX_CANDIDATES = 40
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CDP_PORT = 9222


def _port_open():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", CDP_PORT)) == 0


def start_chrome():
    """Start the real Chrome as a normal browser (no automation flags, so Cloudflare accepts it).
    Playwright only attaches to it afterwards. Uses its own profile so your login is remembered."""
    if _port_open():
        return
    subprocess.Popen([CHROME, f"--remote-debugging-port={CDP_PORT}", f"--user-data-dir={PROFILE}",
                      "--no-first-run", "--no-default-browser-check", "https://www.cardmarket.com/en/Pokemon"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if _port_open():
            return
        time.sleep(0.5)
    raise RuntimeError("Chrome did not start with remote debugging")


def parse_line(line):
    """'3x Charizard ex' / '3 Charizard ex' / 'Charizard ex' -> (3, 'Charizard ex')."""
    m = re.match(r"^\s*(\d+)\s*x?\s+(.+?)\s*$", line, re.I)
    return (int(m.group(1)), m.group(2)) if m else (1, line.strip())


def cm_text(card):
    """Name + ability names + attack names, the form Cardmarket needs for Pokémon cards."""
    parts = [card["name"]]
    parts += [a["name"] for a in card.get("abilities") or []]
    parts += [a["name"] for a in card.get("attacks") or []]
    return " ".join(parts)


def _fetch_details(brief, limit):
    with ThreadPoolExecutor(12) as ex:
        return list(ex.map(lambda c: requests.get(f"{API}/cards/{c['id']}", timeout=30).json(), brief[:limit]))


def _by_name(name):
    brief = requests.get(f"{API}/cards", params={"name": f"eq:{name}"}, timeout=30).json()
    return brief if isinstance(brief, list) else []


def resolve_name(name):
    """Returns {'status': ok|ambiguous|not_found, 'options': [cardmarket text, ...]}.
    Accepts a trailing set name/id too: 'Gengar Fossil', 'Gengar (Fossil)', 'Gengar base3'."""
    name = re.sub(r"[()\[\]]", " ", name).strip()
    words = name.split()
    # Try the whole text as a card name first, then shorter names with the rest as a set hint.
    for k in range(len(words), 0, -1):
        card_name, hint = " ".join(words[:k]), " ".join(words[k:]).lower()
        brief = _by_name(card_name)
        if not brief:
            continue
        details = _fetch_details(brief, 1000 if hint else MAX_CANDIDATES)
        if hint:
            details = [d for d in details if hint in d.get("set", {}).get("name", "").lower()
                       or hint == d.get("set", {}).get("id", "").lower()]
            if not details:
                continue
        options = list(dict.fromkeys(cm_text(d) for d in details))
        return {"status": "ok" if len(options) == 1 else "ambiguous", "options": options}
    return {"status": "not_found", "options": []}


def resolve_text(text):
    """Pasted text -> list of {raw, qty, name, status, options, line}. `line` is set when unambiguous."""
    items = []
    for raw in (l for l in text.splitlines() if l.strip()):
        qty, name = parse_line(raw)
        r = resolve_name(name)
        line = None
        if r["status"] == "ok":
            line = f"{qty} {r['options'][0]}"
        items.append({"raw": raw, "qty": qty, "name": name, **r, "line": line})
    return items


def _save_debug(page, tag):
    DEBUG.mkdir(exist_ok=True)
    page.screenshot(path=str(DEBUG / f"{tag}.png"), full_page=True)
    (DEBUG / f"{tag}.html").write_text(page.content())


LIST_NAME_RE = re.compile(r"^[A-Za-z0-9 \-]{1,30}$")  # Cardmarket's own rule for wants-list names


def _list_card(page, list_name):
    title = page.locator("h3.card-title").filter(has_text=re.compile(f"^\\s*{re.escape(list_name)}\\s*$", re.I))
    return page.locator("div.card").filter(has=title)


def open_or_create_list(page, list_name):
    if not LIST_NAME_RE.match(list_name):
        raise ValueError("List name: 1-30 characters, letters, numbers, spaces and hyphens only.")
    page.goto(WANTS_URL, wait_until="domcontentloaded")
    if not _list_card(page, list_name).count():
        page.locator("input[name=wlName]").fill(list_name)
        page.locator("button.newList-btn").click()
        page.wait_for_load_state("domcontentloaded")
        page.goto(WANTS_URL, wait_until="domcontentloaded")
    href = _list_card(page, list_name).first.get_by_text("View / Edit List").locator("xpath=ancestor-or-self::a").get_attribute("href")
    page.goto("https://www.cardmarket.com" + href, wait_until="domcontentloaded")


def add_decklist(page, list_name, lines):
    """Pastes `lines` into the list's Add Deck List page. Returns the result dict."""
    open_or_create_list(page, list_name)
    page.get_by_text(re.compile(r"add deck ?list", re.I)).first.click()
    page.wait_for_load_state("domcontentloaded")
    page.locator("textarea").first.fill("\n".join(lines))
    page.locator("button").filter(has_text=re.compile(r"add to", re.I)).last.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)
    _save_debug(page, "after_submit")
    alerts = [a.inner_text() for a in page.locator(".alert").all()]
    bad = " ".join(a for a, el in zip(alerts, page.locator(".alert").all())
                   if re.search(r"danger|error", el.get_attribute("class") or ""))
    failed = [l for l in lines if re.sub(r"^\d+x?\s+", "", l, flags=re.I).lower() in bad.lower()]
    return {"added": [l for l in lines if l not in failed], "not_added": failed, "messages": alerts}


def run(lines, list_name, wait_for_login):
    from playwright.sync_api import sync_playwright

    start_chrome()
    wait_for_login()  # you log in and pass Cloudflare first; we attach only afterwards
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        page = browser.contexts[0].pages[0]
        try:
            return add_decklist(page, list_name, lines)
        except Exception:
            _save_debug(page, "error")
            raise
        finally:
            browser.close()  # detaches only; your Chrome window stays open


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="text file with one card per line (default: stdin)")
    ap.add_argument("--list", dest="list_name", help="Wants list name (created if missing)")
    ap.add_argument("--dry-run", action="store_true", help="only resolve names, do not open the browser")
    a = ap.parse_args()

    text = Path(a.file).read_text() if a.file else sys.stdin.read()
    items = resolve_text(text)
    ok = [i for i in items if i["line"]]
    for i in items:
        print(f"[{i['status']}] {i['raw']!r}" + (f" -> {i['line']}" if i["line"] else
              f" options: {i['options'][:5]}" if i["options"] else ""))
    if len(ok) > MAX_ENTRIES:
        sys.exit(f"{len(ok)} entries; the limit is {MAX_ENTRIES} per run.")
    if a.dry_run or not ok:
        return
    if not a.list_name:
        ap.error("--list is required unless --dry-run")
    res = run([i["line"] for i in ok], a.list_name,
              lambda: input("Log in to Cardmarket in the browser window, then press Enter... "))
    print(f"\nAdded: {len(res['added'])}  Not added: {len(res['not_added'])}")
    for l in res["not_added"]:
        print("  not added:", l)
    print("Cardmarket said:", *res["messages"], sep="\n  ")
    print(f"Unresolved names (never sent): {[i['raw'] for i in items if not i['line']]}")


if __name__ == "__main__":
    main()
