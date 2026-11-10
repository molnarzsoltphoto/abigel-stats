"""
Abigél – vágányzár-gyűjtő.

Letölti a mavcsoport.hu vágányzár-oldalát, kinyeri a táblázatokat, és
data/vaganyzar.json-ba írja: vonal, viszonylat, kezdet/vég (nyers és ISO), leírás, link.
A Havaria térkép és az Abigél Vágányzár oldal ebből olvas, böngészős CORS-proxy nélkül.
Ha a letöltés vagy a feldolgozás hibázik, az előző JSON megmarad (nem ír üreset).
Csak a szabványos könyvtárat használja.
"""

import datetime as dt
import html
import json
import re
import sys
import urllib.request
import zoneinfo
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "vaganyzar.json"
SRC = "https://www.mavcsoport.hu/mav-szemelyszallitas/belfoldi-utazas/vaganyzar"
TZ = zoneinfo.ZoneInfo("Europe/Budapest")
HU = {"január": 1, "február": 2, "március": 3, "április": 4, "május": 5, "június": 6, "július": 7, "augusztus": 8, "szeptember": 9, "október": 10, "november": 11, "december": 12}


def hu_date(s):
    m = re.search(r"(\d{4})\.\s*([a-záéíóöőúüű]+)\s*(\d{1,2})\.", (s or "").lower().replace("\xa0", " "))
    if not m or m.group(2) not in HU:
        return None
    try:
        return dt.date(int(m.group(1)), HU[m.group(2)], int(m.group(3))).isoformat()
    except ValueError:
        return None


class Tables(HTMLParser):
    """Táblázatok soronként, cellánként szöveg + első link; a táblázat előtti rövid szöveg a viszonylat."""

    def __init__(self):
        super().__init__()
        self.tables, self.cur, self.row, self.cell, self.href = [], None, None, None, None
        self.recent_text = []  # a legutóbbi blokk-szövegek (viszonylat-címhez)
        self.in_table = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.in_table += 1
            self.cur = {"heading": next((t for t in reversed(self.recent_text) if t and len(t) < 120 and "érvényesség" not in t.lower()), "Vágányzár"), "rows": []}
        elif tag == "tr" and self.cur is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell, self.href = [], None
        elif tag == "a" and self.cell is not None and not self.href:
            h = a.get("href", "")
            self.href = ("https://www.mavcsoport.hu" + h) if h.startswith("/") else h
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.row is not None and self.cell is not None:
            self.row.append({"text": re.sub(r"\s+", " ", "".join(self.cell)).strip(), "href": self.href})
            self.cell = None
        elif tag == "tr" and self.cur is not None and self.row is not None:
            if self.row:
                self.cur["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.cur is not None:
            self.tables.append(self.cur)
            self.cur = None
            self.in_table -= 1
        elif tag in ("p", "h1", "h2", "h3", "h4", "strong", "div") and not self.in_table:
            self.recent_text = self.recent_text[-8:]

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
        elif not self.in_table:
            t = re.sub(r"\s+", " ", data).strip()
            if t:
                self.recent_text.append(t)


def route_from_desc(desc):
    m = re.search(r"\b([A-ZÁÉÍÓÖŐÚÜŰ][\w.-]+(?:\s[\w.-]+){0,2})\s+(?:–|-)\s+([A-ZÁÉÍÓÖŐÚÜŰ][\w.-]+(?:\s[\w.-]+){0,2})(?:\s+(?:–|-)\s+([A-ZÁÉÍÓÖŐÚÜŰ][\w.-]+))?\s+(?:vasútvonal|vonal|között)", desc or "")
    if m:
        return " – ".join(x for x in m.groups() if x)
    m = re.search(r"\b([A-ZÁÉÍÓÖŐÚÜŰ][\w.-]+)\s+és\s+([A-ZÁÉÍÓÖŐÚÜŰ][\w.-]+)\s+között", desc or "")
    return f"{m.group(1)} – {m.group(2)}" if m else ""


def parse(html_text):
    p = Tables()
    p.feed(html_text)
    out = []
    for t in p.tables:
        per_row_heading = len(t["rows"]) <= 8  # kis táblánál a tábla előtti cím a viszonylat; nagy, összevont táblánál nem
        for row in t["rows"]:
            if len(row) < 3 or "érvényesség" in " ".join(c["text"] for c in row).lower():
                continue
            line, start, end = row[0]["text"], row[1]["text"], row[2]["text"]
            desc_cell = row[3] if len(row) > 3 else row[-1]
            if not line or not (hu_date(start) or hu_date(end)):
                continue
            desc = desc_cell["text"]
            out.append({
                "line": line, "route": (t["heading"].strip("* ") if per_row_heading else route_from_desc(desc)) or "", "startRaw": start, "endRaw": end,
                "start": hu_date(start), "end": hu_date(end), "desc": desc.replace("Térképes információ a vágányzárról", "").strip(), "link": desc_cell["href"] or "",
            })
    return out


def main():
    req = urllib.request.Request(SRC, headers={"User-Agent": "Mozilla/5.0 (compatible; AbigelVaganyzar/1.0)", "Accept-Language": "hu"})
    with urllib.request.urlopen(req, timeout=40) as r:
        text = r.read().decode("utf-8", "replace")
    items = parse(html.unescape(text) if "&lt;table" in text else text)
    if len(items) < 3:
        print(f"Csak {len(items)} tétel – gyanús, az előző JSON marad.", file=sys.stderr)
        sys.exit(1)
    now = dt.datetime.now(TZ)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"frissitve": now.isoformat(), "forras": SRC, "tetelek": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} vágányzár mentve.")


if __name__ == "__main__":
    main()
