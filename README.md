# Cardmarket Wants List Uploader

A small local app that can add Pokémon cards in bulk on [Cardmarket](https://www.cardmarket.com), the best TCG marketplace in Europe.

## How to use it

1. Either find cards manually (search by name, e.g. `charizard 151`) or paste them as text.
2. Enter the name of the wants list and click **Add**.
3. You are redirected to Cardmarket (a Chrome window opens).
4. Log in.
5. Go back to the app and click **I'm logged in — continue**.
6. The cards are automatically added to the list. The app shows what was added and what was not.

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

## How it works

- Card names, images and sets come from [TCGdex](https://tcgdex.dev). Cardmarket's public product catalogue gives the exact text its "Add Deck List" box expects (e.g. `Gengar Curse Dark Mind`).
- The app opens your own Chrome so you log in yourself. Your password is never seen by the app.
- After you click continue, it opens your wants list (creating it if needed), pastes the cards into **Add Deck List** and reads Cardmarket's reply.

**Limits:** up to 150 different cards per run, and Cardmarket cannot pick a set from the text, so it adds any version with the same attacks. List names: letters, numbers, spaces and hyphens, up to 30 characters.
