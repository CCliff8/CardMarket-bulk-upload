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

## Status
Verified: name matching and line building, API, frontend build.
Not verified: the Cardmarket browser steps (open/create list, paste, read the result messages).
On any failure a screenshot and the page HTML are saved to `debug/`.
