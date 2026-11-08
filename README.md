# Cardmarket Wants List Uploader

A small local app that can add Pokémon cards in bulk on [Cardmarket](https://www.cardmarket.com), the best TCG marketplace in Europe.

## How to use it

1. Either find cards manually (search by name, e.g. `charizard 151`) or paste them as text.
2. Optionally set card details (condition, language, reverse holo, first edition, signed, altered) for all cards or for single cards.
3. Enter the name of the wants list and click **Add**.
4. You are redirected to Cardmarket (a Chrome window opens).
5. Log in.
6. Go back to the app and click **I'm logged in — continue**.
7. The cards are automatically added to the list. The app shows what was added and what was not.

## Setup

```
pip install -r requirements.txt
cd frontend && npm install
```

Run it in two terminals:

```
python3 server.py                  # terminal 1
cd frontend && npm run dev         # terminal 2
```

Then open http://localhost:5173.

## Dependencies

- Python 3.9+ with `requests`, `flask`, `flask-cors` and `playwright` (installed by `requirements.txt`)
- Node.js (for the React front-end)
- Google Chrome, installed in `/Applications` (macOS)
