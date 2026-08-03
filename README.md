name: Vonatkésés napi scraper

on:
  schedule:
    - cron: '0 22 * * *'  # 23:00 magyar idő (UTC+1), nyáron 22:00 UTC
  workflow_dispatch:       # kézi indítás is lehetséges

jobs:
  scrape:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Python setup
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Függőségek telepítése
        run: pip install requests

      - name: Scraper futtatása
        run: python scraper.py

      - name: Adat commitálása
        run: |
          git config user.name "abigel-bot"
          git config user.email "abigel-bot@users.noreply.github.com"
          git add data/kesesi_adatok.csv
          git diff --staged --quiet || git commit -m "Napi késési adat – $(date +'%Y-%m-%d')"
          git push
