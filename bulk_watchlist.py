#!/usr/bin/env python3
"""Paste card names -> build Cardmarket deck-list lines -> add them to a Wants list (Playwright)."""
import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

API = "https://api.tcgdex.net/v2/en"
HERE = Path(__file__).parent
PROFILE = HERE / "browser_profile"
DEBUG = HERE / "debug"
WANTS_URL = "https://www.cardmarket.com/en/Pokemon/Wants"
MAX_ENTRIES = 150
MAX_CANDIDATES = 40


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


def resolve_name(name):
    """Returns {'status': ok|ambiguous|not_found, 'options': [cardmarket text, ...]}."""
    brief = requests.get(f"{API}/cards", params={"name": f"eq:{name}"}, timeout=30).json()
    if not isinstance(brief, list) or not brief:
        return {"status": "not_found", "options": []}
    with ThreadPoolExecutor(8) as ex:
        details = list(ex.map(lambda c: requests.get(f"{API}/cards/{c['id']}", timeout=30).json(),
                              brief[:MAX_CANDIDATES]))
    options = list(dict.fromkeys(cm_text(d) for d in details))
    return {"status": "ok" if len(options) == 1 else "ambiguous", "options": options}


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


def open_or_create_list(page, list_name):
    page.goto(WANTS_URL, wait_until="domcontentloaded")
    title = page.get_by_text(list_name, exact=True)
    if title.count():
        card = page.locator("div").filter(has=title).filter(has=page.get_by_text("View / Edit List")).last
        card.get_by_text("View / Edit List").first.click()
    else:
        page.locator("input[type=text]").first.fill(list_name)
        page.get_by_text(re.compile(r"add list", re.I)).first.click()
        page.wait_for_load_state("domcontentloaded")
        page.get_by_text(list_name, exact=True).first.click()
    page.wait_for_load_state("domcontentloaded")


def add_decklist(page, list_name, lines):
    """Pastes `lines` into the list's Add Deck List page. Returns the result dict."""
    open_or_create_list(page, list_name)
    page.get_by_text(re.compile(r"add deck ?list", re.I)).first.click()
    page.wait_for_load_state("domcontentloaded")
    page.locator("textarea").first.fill("\n".join(lines))
    page.get_by_role("button", name=re.compile(r"^\s*add to", re.I)).click()
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

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto("https://www.cardmarket.com/en/Pokemon")
            wait_for_login()
            return add_decklist(page, list_name, lines)
        except Exception:
            _save_debug(page, "error")
            raise
        finally:
            ctx.close()


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
