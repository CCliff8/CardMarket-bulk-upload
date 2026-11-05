# Cardmarket Wants List Uploader

Paste card names -> they are matched on TCGdex and converted to the lines Cardmarket's
"Add Deck List" box needs (`<qty> <name> <ability/attack names>`) -> a browser you log in to
creates/opens a Wants list and pastes them -> you get a summary of added / not added.

Cardmarket cannot add a Pokémon by name alone, so each line carries its ability and attack names
(e.g. `Umbreon ex Moon Mirage Onyx`). Names with several different versions are shown for you to choose.
Limit: 150 entries per run (Cardmarket's per-list limit).

## Setup
```
pip install -r requirements.txt && python3 -m playwright install chromium
cd frontend && npm install
```

## UI
```
python3 server.py                  # 127.0.0.1:5001
cd frontend && npm run dev         # http://localhost:5173
```

## CLI
```
printf 'Umbreon ex\n2x Scoop Up Net\n' | python3 bulk_watchlist.py --dry-run
python3 bulk_watchlist.py --file cards.txt --list "My list"
```

## Cloudflare
Playwright's own Chromium is blocked by Cloudflare. The app therefore starts your real Google Chrome
(own profile in `chrome_profile/`, remote-debugging port 9222), lets you log in and pass the check normally,
and only attaches Playwright after you click "I'm logged in". Requires Google Chrome in /Applications.

## Status
Verified: name matching and line building, API, frontend build.
Verified against a real account: open list, Add Deck List, submit, and reading Cardmarket's added / not-added messages.
List names must be 1-30 characters: letters, numbers, spaces, hyphens (Cardmarket's rule).
Not verified: creating a brand-new list (the selectors come from the page HTML).
On any failure a screenshot and the page HTML are saved to `debug/`.
