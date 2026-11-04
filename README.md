# Cardmarket Bulk Watchlist

Bulk-add Pokémon cards of a set to a Cardmarket watchlist using Playwright browser automation.
Card data comes from TCGdex. You log in manually in the opened browser; the session is kept in `browser_profile/`.

## Setup
```
pip install -r requirements.txt && python3 -m playwright install chromium
cd frontend && npm install
```

## UI
```
python3 server.py                  # terminal 1 (127.0.0.1:5001)
cd frontend && npm run dev         # terminal 2 -> http://localhost:5173
```

## CLI
```
python3 bulk_watchlist.py --list-sets
python3 bulk_watchlist.py --set sv03.5 --numbers 1-5 --dry-run
python3 bulk_watchlist.py --set sv03.5 --watchlist "My list"
```

## Status
Verified: card fetching, dry run, API, frontend build.
Not verified: the Cardmarket click step (`add_to_watchlist()` selectors are guesses).
Test with one card and a throwaway watchlist first.
