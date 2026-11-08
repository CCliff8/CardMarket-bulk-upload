#!/usr/bin/env python3
"""Paste card names -> build Cardmarket deck-list lines -> add them to a Wants list (Playwright)."""
import argparse
import json
import re
import socket
import subprocess
import sys
import time
import unicodedata
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
CATALOG_URL = "https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_6.json"
CATALOG_FILE = HERE / "data" / "products_singles_6.json"
CATALOG_MAX_AGE = 24 * 3600
_catalog = None
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


def _cm_product_id(card):
    """Cardmarket idProduct from a TCGdex card; the pricing or cardmarket field can be null."""
    return ((card.get("pricing") or {}).get("cardmarket") or {}).get("idProduct")


def _norm(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().lower()


def _line_text(product_name):
    """Cardmarket product name 'Gengar [Curse | Dark Mind]' -> deck-list text 'Gengar Curse Dark Mind'."""
    return re.sub(r"\s+", " ", re.sub(r"[\[\]|]", " ", product_name)).strip()


def load_catalog():
    """Cardmarket's own public product catalogue (all Pokémon singles), cached for a day."""
    global _catalog
    if _catalog is None:
        if not CATALOG_FILE.exists() or time.time() - CATALOG_FILE.stat().st_mtime > CATALOG_MAX_AGE:
            CATALOG_FILE.parent.mkdir(exist_ok=True)
            r = requests.get(CATALOG_URL, timeout=120)
            r.raise_for_status()
            CATALOG_FILE.write_bytes(r.content)
        products = json.loads(CATALOG_FILE.read_text())["products"]
        by_id, by_name = {}, {}
        for p in products:
            by_id[p["idProduct"]] = p
            base = p["name"].split(" [")[0]
            by_name.setdefault(_norm(base), {}).setdefault(p["idMetacard"], p["name"])
        _catalog = {"by_id": by_id, "by_name": by_name}
    return _catalog


def _result(pairs):
    """pairs: (deck-list text, Cardmarket product name or None). `products` maps text -> product name."""
    products = {}
    for text, product in pairs:
        products.setdefault(text, product)
    options = list(products)
    return {"status": "ok" if len(options) == 1 else "ambiguous", "options": options, "products": products}


def _tcgdex_candidates(card_name, hint):
    brief = requests.get(f"{API}/cards", params={"name": f"eq:{card_name}"}, timeout=30).json()
    if not isinstance(brief, list) or not brief:
        return []
    with ThreadPoolExecutor(12) as ex:
        details = list(ex.map(lambda c: requests.get(f"{API}/cards/{c['id']}", timeout=30).json(), brief[:1000]))
    return [d for d in details if hint in d.get("set", {}).get("name", "").lower()
            or hint == d.get("set", {}).get("id", "").lower()]


def resolve_name(name):
    """Returns {'status': ok|ambiguous|not_found, 'options': [deck-list text, ...]}.
    Looks the name up in Cardmarket's own catalogue. A trailing set name or id ('Gengar Fossil',
    'Gengar (Fossil)', 'Gengar base3') is resolved through TCGdex, which knows the sets."""
    cat = load_catalog()
    name = re.sub(r"[()\[\]]", " ", name).strip()
    words = name.split()
    for k in range(len(words), 0, -1):
        card_name, hint = " ".join(words[:k]), " ".join(words[k:]).lower()
        if not hint:
            found = cat["by_name"].get(_norm(card_name))
            if found:
                return _result((_line_text(n), n) for n in found.values())
            continue
        options = []
        for d in _tcgdex_candidates(card_name, hint):
            pid = _cm_product_id(d)
            prod = cat["by_id"].get(pid)
            options.append((_line_text(prod["name"]), prod["name"]) if prod else (cm_text(d), None))
        if options:
            return _result(options)
    return {"status": "not_found", "options": [], "products": {}}


_sets = None


def set_names():
    global _sets
    if _sets is None:
        _sets = {x["id"]: x["name"] for x in requests.get(f"{API}/sets", timeout=30).json()}
    return _sets


def search_cards(query, limit=30):
    """Autocomplete: 'charizard', 'charizard 151', 'gengar fossil' -> cards with image, set and number."""
    sets = set_names()
    words = query.split()
    seen, out = set(), []
    for k in range(len(words), 0, -1):
        name, hint = " ".join(words[:k]), " ".join(words[k:]).lower()
        brief = requests.get(f"{API}/cards", params={"name": name}, timeout=30).json()
        for c in brief if isinstance(brief, list) else []:
            set_id = c["id"].rsplit("-", 1)[0]
            set_name = sets.get(set_id, set_id)
            if hint and hint not in set_name.lower() and hint != set_id.lower():
                continue
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            out.append({"id": c["id"], "name": c["name"], "number": c["localId"], "setId": set_id,
                        "setName": set_name, "image": f"{c['image']}/low.webp" if c.get("image") else None})
        if out:
            break
    return out[:limit]


def card_line(card_id):
    """Deck-list text (and Cardmarket product name) for one specific printing, via its product id."""
    d = requests.get(f"{API}/cards/{card_id}", timeout=30).json()
    prod = load_catalog()["by_id"].get(_cm_product_id(d))
    if prod:
        return {"text": _line_text(prod["name"]), "product": prod["name"]}
    return {"text": cm_text(d), "product": None}


def resolve_text(text):
    """Pasted text -> list of {raw, qty, name, status, options, line}. `line` is set when unambiguous."""
    items = []
    for raw in (l for l in text.splitlines() if l.strip()):
        qty, name = parse_line(raw)
        r = resolve_name(name)
        line = None
        if r["status"] == "ok":
            line = f"{qty} {r['options'][0]}"
        items.append({"raw": raw, "qty": qty, "name": name, **r, "line": line,
                      "product": r["products"].get(r["options"][0]) if r["status"] == "ok" else None})
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


# Card details Cardmarket lets you set on a wants entry (Bulk modification form field names).
TRI_FIELDS = ("isReverseHolo", "isFirstEd", "isSigned", "isAltered")  # values 'Y' / 'N'
CONDITIONS = {"MT": "1", "NM": "2", "EX": "3", "GD": "4", "LP": "5", "PL": "6", "PO": "7"}
LANGUAGES = {"1": "English", "2": "French", "3": "German", "4": "Spanish", "5": "Italian", "6": "S-Chinese",
             "7": "Japanese", "8": "Portuguese", "9": "Russian", "10": "Korean", "11": "T-Chinese",
             "12": "Dutch", "13": "Polish", "14": "Czech", "15": "Hungarian", "16": "Indonesian", "17": "Thai"}


def clean_details(d):
    """Keep only valid, non-empty details. Empty means 'leave as it is'."""
    d = d or {}
    out = {}
    if str(d.get("minCondition", "")) in CONDITIONS.values():
        out["minCondition"] = str(d["minCondition"])
    langs = [str(x) for x in d.get("languages") or [] if str(x) in LANGUAGES]
    if langs:
        out["languages"] = langs
    for f in TRI_FIELDS:
        if d.get(f) in ("Y", "N"):
            out[f] = d[f]
    return out


def _rowkey(text):
    return re.sub(r"[^a-z0-9]", "", _norm(text))


def _row_ids(page):
    return {c.get_attribute("data-id-want") for c in page.locator('input[name="checkWantsRow[]"]').all()}


def apply_details(page, list_url, before_ids, entries):
    """Sets condition/language/etc. on the rows added by this run, using the list's Bulk modification form.
    Entries with identical details are changed together. Returns (applied, failed)."""
    groups = {}
    for e in entries:
        d = clean_details(e.get("details"))
        if d:
            groups.setdefault(json.dumps(d, sort_keys=True), (d, []))[1].append(e)
    applied, failed = [], []
    for d, group in groups.values():
        wanted = {}
        for e in group:
            if e.get("product"):
                wanted.setdefault(_rowkey(e["product"]), []).append(e)
            else:
                failed.append({"line": e["line"], "reason": "unknown Cardmarket product name"})
        if not wanted:
            continue
        page.goto(list_url, wait_until="domcontentloaded")
        page.get_by_text("Bulk modification").first.click()
        ticked = set()
        for row in page.locator("tr[role=row]").all():
            box = row.locator('input[name="checkWantsRow[]"]')
            if not box.count() or box.get_attribute("data-id-want") in before_ids:
                continue
            key = _rowkey(row.locator("td.name a").first.inner_text())
            if key in wanted:
                box.check()
                ticked.add(key)
        for key, es in wanted.items():
            if key not in ticked:
                failed += [{"line": e["line"], "reason": "not a new row in the list (already there?)"} for e in es]
        if not ticked:
            continue
        if "minCondition" in d:
            page.locator("#minCondition").select_option(d["minCondition"])
        for f in TRI_FIELDS:
            if f in d:
                page.locator(f"#{f}").select_option(d[f])
        if "languages" in d:
            page.evaluate("""ids => { const s = document.querySelector("select[name='idLanguages[]']");
                for (const o of s.options) o.selected = ids.includes(o.value);
                s.dispatchEvent(new Event('change', {bubbles: true})); }""", d["languages"])
        page.locator('input[type=submit][form=ModifyForm]').click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)
        applied += [e["line"] for key in ticked for e in wanted[key]]
    return applied, failed


def add_decklist(page, list_name, entries):
    """Pastes the entries' lines into the list's Add Deck List page, then applies any card details.
    entries: [{'line': '1 Gengar Curse Dark Mind', 'product': 'Gengar [Curse | Dark Mind]', 'details': {...}}]"""
    lines = [e["line"] for e in entries]
    open_or_create_list(page, list_name)
    list_url = page.url
    before_ids = _row_ids(page)
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
    added = [l for l in lines if l not in failed]
    result = {"added": added, "not_added": failed, "messages": alerts, "details_applied": [], "details_failed": []}
    to_detail = [e for e in entries if e["line"] in added]
    if any(clean_details(e.get("details")) for e in to_detail):
        result["details_applied"], result["details_failed"] = apply_details(page, list_url, before_ids, to_detail)
        _save_debug(page, "after_details")
    return result


def run(entries, list_name, wait_for_login):
    from playwright.sync_api import sync_playwright

    start_chrome()
    wait_for_login()  # you log in and pass Cloudflare first; we attach only afterwards
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        page = browser.contexts[0].pages[0]
        try:
            return add_decklist(page, list_name, entries)
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
    res = run([{"line": f"{i['qty']} {i['options'][0]}", "product": i["product"]} for i in ok], a.list_name,
              lambda: input("Log in to Cardmarket in the browser window, then press Enter... "))
    print(f"\nAdded: {len(res['added'])}  Not added: {len(res['not_added'])}")
    for l in res["not_added"]:
        print("  not added:", l)
    print("Cardmarket said:", *res["messages"], sep="\n  ")
    print(f"Unresolved names (never sent): {[i['raw'] for i in items if not i['line']]}")


if __name__ == "__main__":
    main()
