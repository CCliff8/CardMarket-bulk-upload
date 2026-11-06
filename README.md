# Cardmarket Wants List Uploader

A small local app that adds many Pokémon cards to a [Cardmarket](https://www.cardmarket.com) **wants list** in one go.
You search for the exact cards in a web UI, and the app pastes them into Cardmarket's own **Add Deck List** box
using your own logged-in Chrome. No Cardmarket API key is needed, and your password is never seen by the app.

## How it works (the actual flow)

1. **Find cards.** In the UI you search by name, optionally with a set: `charizard 151`, `gengar fossil`.
   Autocomplete shows each printing with its image, set and number. Click one to add it. You can also paste a list of
   names (`2x Umbreon ex`, one per line); names with several versions show a dropdown so you choose one.
2. **Review.** Change amounts (any number, 1–999) or remove cards. At most **150 different cards** per run.
3. **Name the list and click "Add N cards".** The name may contain letters, numbers, spaces and hyphens, 1–30
   characters (Cardmarket's own rule). If the list doesn't exist, it is created.
4. **Log in.** Your installed **Google Chrome** opens on cardmarket.com. Log in and pass the Cloudflare check yourself,
   then click **"I'm logged in — continue"** in the yellow banner in the app. (The app only attaches to Chrome after
   this click, so Cloudflare sees a normal browser.)
5. **Upload.** The app opens *Buying → My Wants → your list → Add Deck List*, pastes one line per card, and presses
   **Add to <list>**.
6. **Result.** The app shows how many cards were **added** and which were **not added**, plus Cardmarket's own
   messages. The card list then clears, ready for the next batch (the list name stays).

### Where the card data comes from
- **Cardmarket's public product catalogue** (all Pokémon singles, downloaded from `downloads.s3.cardmarket.com`,
  cached in `data/` and refreshed daily) is used for the card names and attack names Cardmarket expects.
  Pokémon cannot be added by name alone, so each line is `<amount> <name> <ability/attack names>`,
  e.g. `3 Gengar Curse Dark Mind`.
- **[TCGdex](https://tcgdex.dev)** provides the search, card images, set names and set numbers.

### Known limits
- Cardmarket's deck-list line cannot select a set. A line adds *any version with the same attacks*, not only the
  printing you picked.
- A wants list holds at most 150 entries in total on Cardmarket. The app counts only the cards of the current run,
  not what is already in the list.
- Cards missing from Cardmarket's catalogue fall back to TCGdex's attack names, which may not be accepted.
- macOS only as written: Chrome is expected at `/Applications/Google Chrome.app`.

## Setup

Requirements: Python 3.9+, Node.js, Google Chrome.

```
pip install -r requirements.txt
cd frontend && npm install
```

## Run

Two terminals:

```
python3 server.py                  # API on http://127.0.0.1:5001
cd frontend && npm run dev         # UI on  http://localhost:5173
```

Open http://localhost:5173. Use the sun/moon switch in the corner for System, Light or Dark theme.

## Command line (optional)

```
printf 'Umbreon ex\n2x Scoop Up Net\nGengar Fossil\n' | python3 bulk_watchlist.py --dry-run
python3 bulk_watchlist.py --file cards.txt --list "My list"
```

`--dry-run` only matches the names and prints the lines. Without it, Chrome opens, you log in, press Enter in
the terminal, and the added / not-added summary is printed. Names that match several versions are listed but not
sent; use the UI to choose a version.

## Files

| Path | Purpose |
|------|---------|
| `bulk_watchlist.py` | Matching, line building and the Chrome/Playwright upload (also the CLI) |
| `server.py` | Flask API used by the UI |
| `frontend/` | React (Vite) UI, plain CSS |
| `chrome_profile/` | Chrome profile used by the app, so your login is remembered (git-ignored) |
| `data/` | Cached Cardmarket product catalogue (git-ignored) |
| `debug/` | Screenshot and page HTML saved when a step fails (git-ignored) |

## Troubleshooting
- **Stuck on "Log in"**: click **"I'm logged in — continue"** in the app tab, not the Cardmarket tab.
- **Cloudflare loops**: use the Chrome window the app opened (not another browser).
- **A step failed**: look at `debug/error.png` and `debug/error.html`.
