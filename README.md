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

## Menetrendszerűség vonalanként (új, 2026-11)

`scraper_vonal.py` 20 percenként fut (`.github/workflows/pontossag.yml`), minden közlekedő vonatról egy sort ír a `data/futasok/ÉÉÉÉ-HH.csv` fájlba, és frissíti a `data/pontossag.json` összesítőt (nap × viszonylat × szegmens: vonatszám, menetrendszerű arány ≤5 perc, átlagos és 90. percentilis késés). Az Abigél Termékfejlesztés → Menetrendszerűség füle ezt olvassa. Korlátok: a késés a vonat utolsó megfigyelt értéke a napon, nem a végállomási; a szegmens (IC, IR, személy, HÉV) és a vonalszám a vonatnévből és a végpontokból becsült. Adat a bekapcsolás napjától gyűlik, visszamenőleg nincs.
