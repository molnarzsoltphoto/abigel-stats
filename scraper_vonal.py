"""
Abigél – menetrendszerűség vonalanként és szegmensenként.

20 percenként lekéri a holavonat.is járműadatát, és minden Magyarországon közlekedő
vonatról egy sort ír a havi CSV-be (data/futasok/ÉÉÉÉ-HH.csv):
  datum, ido, vonatszam, nev, szegmens, viszonylat, vonal, megallo, keses_perc

Ugyanebből frissíti a data/pontossag.json összesítőt: nap × viszonylat × szegmens
bontásban a megfigyelt vonatok száma, a menetrendszerű (≤5 perc) arány, az átlagos
és a 90. percentilis késés. Egy vonat egy napon egyszer számít: az utolsó
megfigyelt késésével (nem a végállomási, mert azt a forrás nem adja).

Csak a szabványos könyvtárat használja. A szegmens és a vonalszám a vonatnévből,
illetve a viszonylat végpontjaiból származik, közelítő besorolás.
"""

import csv
import datetime as dt
import json
import os
import re
import statistics
import urllib.request
import zoneinfo
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / "data" / "futasok"
OUT_JSON = ROOT / "data" / "pontossag.json"
URL = "https://cdn.holavonat.is/train_data_v3.json"
TZ = zoneinfo.ZoneInfo("Europe/Budapest")
KEEP_DAYS = 400
ONTIME_MIN = 5
FIELDS = ["datum", "ido", "vonatszam", "nev", "szegmens", "viszonylat", "vonal", "megallo", "keses_perc"]

SEGMENT_RULES = [
    (r"railjet|\brj\b|eurocity|\bec\b|euronight|\ben\b|nightjet|intercity|\bic\b", "IC"),
    (r"interregio|interrégió|\bir\b|expressz|express|fast train|gyors|\bgy\b", "IR"),
    (r"hév|\bh\d", "HÉV"),
    (r"passenger|személy|regional|regionális|euroregio|\bs\d{1,3}\b|\bg\d{2}\b|\bz\d{2}\b|suburban|elővárosi|zónázó", "személy"),
]
# Végpontpárból vonalszám. Közelítő: a nagy fővonalakra, a többi üres marad.
LINE_BY_ENDPOINTS = {
    frozenset(["Budapest", "Pécs"]): "40", frozenset(["Budapest", "Dombóvár"]): "40", frozenset(["Budapest", "Nagykanizsa"]): "30",
    frozenset(["Budapest", "Székesfehérvár"]): "30a", frozenset(["Budapest", "Győr"]): "1", frozenset(["Budapest", "Hegyeshalom"]): "1",
    frozenset(["Budapest", "Sopron"]): "8", frozenset(["Budapest", "Szombathely"]): "20", frozenset(["Budapest", "Debrecen"]): "100",
    frozenset(["Budapest", "Nyíregyháza"]): "100", frozenset(["Budapest", "Záhony"]): "100", frozenset(["Budapest", "Miskolc"]): "80",
    frozenset(["Budapest", "Sátoraljaújhely"]): "80", frozenset(["Budapest", "Szeged"]): "140", frozenset(["Budapest", "Kecskemét"]): "140",
    frozenset(["Budapest", "Szolnok"]): "100a", frozenset(["Budapest", "Békéscsaba"]): "120", frozenset(["Budapest", "Lőkösháza"]): "120",
    frozenset(["Budapest", "Esztergom"]): "2", frozenset(["Budapest", "Vác"]): "70", frozenset(["Budapest", "Szob"]): "70",
    frozenset(["Budapest", "Hatvan"]): "80", frozenset(["Budapest", "Lajosmizse"]): "142", frozenset(["Budapest", "Pusztaszabolcs"]): "40a",
    frozenset(["Budapest", "Kunszentmiklós-Tass"]): "150", frozenset(["Budapest", "Kelebia"]): "150", frozenset(["Budapest", "Tapolca"]): "29",
    frozenset(["Budapest", "Keszthely"]): "29", frozenset(["Budapest", "Balatonfüred"]): "29", frozenset(["Budapest", "Veszprém"]): "20",
    frozenset(["Budapest", "Fonyód"]): "30", frozenset(["Budapest", "Siófok"]): "30", frozenset(["Budapest", "Ceglédbercel"]): "100a",
    frozenset(["Budapest", "Monor"]): "100a", frozenset(["Budapest", "Cegléd"]): "100a",
    frozenset(["Győr", "Sopron"]): "8", frozenset(["Győr", "Hegyeshalom"]): "1", frozenset(["Sopron", "Szentgotthárd"]): "21", frozenset(["Szombathely", "Celldömölk"]): "20",
    frozenset(["Kiskunhalas", "Baja"]): "154", frozenset(["Kecskemét", "Kiskunhalas"]): "152", frozenset(["Budapest", "Dunaújváros"]): "42", frozenset(["Budapest", "Martonvásár"]): "30a",
    frozenset(["Budapest", "Gödöllő"]): "80a", frozenset(["Budapest", "Sülysáp"]): "120a", frozenset(["Budapest", "Eger"]): "87", frozenset(["Budapest", "Gyöngyös"]): "85",
    frozenset(["Budapest", "Hidasnémeti"]): "90", frozenset(["Budapest", "Zalaegerszeg"]): "25", frozenset(["Budapest", "Oroszlány"]): "12", frozenset(["Kőbánya", "Lajosmizse"]): "142",
    frozenset(["Budapest", "Kosice"]): "90", frozenset(["Budapest", "Kassa"]): "90", frozenset(["Budapest", "Balatonszentgyörgy"]): "30", frozenset(["Győr", "Keszthely"]): "26",
    frozenset(["Győr", "Veszprém"]): "11", frozenset(["Dombóvár", "Gyékényes"]): "41", frozenset(["Baja", "Székesfehérvár"]): "154", frozenset(["Tapolca", "Kaposvár"]): "36",
    frozenset(["Pécs", "Tapolca"]): "36", frozenset(["Pécs", "Szombathely"]): "17", frozenset(["Hatvan", "Somoskőújfalu"]): "81", frozenset(["Szeged", "Békéscsaba"]): "135",
    frozenset(["Mezőhegyes", "Mezőtúr"]): "125", frozenset(["Szolnok", "Szentes"]): "130", frozenset(["Füzesabony", "Debrecen"]): "108", frozenset(["Pilisvörösvár", "Rákos"]): "2",
    frozenset(["Nyíregyháza", "Záhony"]): "100", frozenset(["Debrecen", "Tiszalök"]): "109", frozenset(["Békéscsaba", "Vésztő"]): "128", frozenset(["Tiborszállás", "Mátészalka"]): "115",
    frozenset(["Budapest", "Kiskunhalas"]): "150", frozenset(["Szolnok", "Debrecen"]): "100", frozenset(["Miskolc", "Nyíregyháza"]): "80", frozenset(["Budapest", "Pápa"]): "10",
    frozenset(["Székesfehérvár", "Szombathely"]): "20", frozenset(["Székesfehérvár", "Komárom"]): "5", frozenset(["Dombóvár", "Pécs"]): "40", frozenset(["Pécs", "Villány"]): "65",
    frozenset(["Pécs", "Nagykanizsa"]): "60", frozenset(["Nagykanizsa", "Szombathely"]): "17", frozenset(["Szolnok", "Békéscsaba"]): "120", frozenset(["Kecskemét", "Szeged"]): "140",
}


def city(stop_name: str) -> str:
    name = (stop_name or "").strip()
    if name.startswith("Budapest"):
        return "Budapest"
    return re.split(r"[-–,(]", name)[0].strip() or name


def segment(name: str) -> str:
    low = (name or "").lower()
    for pattern, seg in SEGMENT_RULES:
        if re.search(pattern, low):
            return seg
    return "egyéb"


def train_number(name: str) -> str:
    m = re.search(r"\b([A-Z]?\d{1,5})\b", name or "")
    return m.group(1) if m else (name or "?")[:12]


def position(v):
    pos = v.get("position") or v.get("vehiclePosition") or {}
    lat = pos.get("latitude") or pos.get("lat") or v.get("lat")
    lon = pos.get("longitude") or pos.get("lon") or pos.get("lng") or v.get("lon")
    try:
        return (float(lat), float(lon)) if lat and lon else None
    except (TypeError, ValueError):
        return None


def record(v, now):
    trip = v.get("trip") or {}
    route = trip.get("route") or {}
    if (route.get("mode") or "").upper() not in ("RAIL", "SUBWAY"):
        return None
    pos = position(v)
    if not pos or not (45 <= pos[0] <= 49 and 15 <= pos[1] <= 23):
        return None
    name = re.sub(r"<[^>]+>", "", trip.get("tripShortName") or route.get("shortName") or route.get("longName") or "?").strip()
    stop = ((v.get("stopRelationship") or {}).get("stop") or {}).get("name", "")
    times = trip.get("stoptimes") or []
    here = next((x for x in times if (x.get("stop") or {}).get("name") == stop), None)
    delay = here.get("arrivalDelay") if here else None
    if delay is None:
        return None
    first = ((times[0].get("stop") or {}).get("name") if times else "") or ""
    last = ((times[-1].get("stop") or {}).get("name") if times else "") or trip.get("tripHeadsign") or ""
    a, b = city(first), city(last)
    if not first and not last:  # nincs megállólista: a név „IC TOKAJ” jellegű, viszonylat ismeretlen
        a = b = ""
    ends = sorted([a, b], key=lambda x: (x != "Budapest", x))  # irányfüggetlen: Budapest elöl, különben ABC
    relation = f"{ends[0]} – {ends[1]}" if a and b and a != b else (route.get("longName") or a or b or "ismeretlen")
    return {
        "datum": now.strftime("%Y-%m-%d"), "ido": now.strftime("%H:%M"), "vonatszam": train_number(name), "nev": name[:60],
        "szegmens": "HÉV" if (route.get("mode") or "").upper() == "SUBWAY" and "hév" in name.lower() else segment(name),
        "viszonylat": relation[:80], "vonal": LINE_BY_ENDPOINTS.get(frozenset([a, b]), ""), "megallo": stop[:60], "keses_perc": round(delay / 60),
    }


def append_runs(rows, now):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{now:%Y-%m}.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)
    return path


def aggregate(now):
    """Nap × viszonylat × szegmens; vonatonként az utolsó megfigyelés a napon."""
    last_seen = {}  # (datum, vonatszam, viszonylat) -> rekord
    cutoff = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for path in sorted(RUNS_DIR.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["datum"] < cutoff:
                    continue
                last_seen[(r["datum"], r["vonatszam"], r["viszonylat"])] = r
    groups = defaultdict(list)
    for (datum, _, rel), r in last_seen.items():
        try:
            d = int(r["keses_perc"])
        except ValueError:
            continue
        groups[(datum, rel, r["szegmens"], r.get("vonal", ""))].append(d)
    days = []
    for (datum, rel, seg, line), delays in sorted(groups.items()):
        n = len(delays)
        ontime = sum(1 for d in delays if d <= ONTIME_MIN)
        late = [d for d in delays if d > ONTIME_MIN]
        srt = sorted(delays)
        days.append({
            "datum": datum, "viszonylat": rel, "szegmens": seg, "vonal": line, "vonatok": n,
            "menetrendszeru_pct": round(100 * ontime / n, 1), "atlag_keses_percben": round(statistics.mean(late), 1) if late else 0,
            "p90_keses": srt[min(n - 1, int(0.9 * (n - 1)))], "max_keses": srt[-1],
        })
    OUT_JSON.write_text(json.dumps({
        "frissitve": now.isoformat(), "menetrendszeru_kuszob_perc": ONTIME_MIN, "megjegyzes": "Utolsó megfigyelt késés vonatonként és naponta, 20 perces mintavétellel; nem végállomási érték. Szegmens (IC, IR, személy, HÉV) és vonalszám a névből/végpontokból, közelítő.",
        "napok": days,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(days)


def main():
    now = dt.datetime.now(TZ)
    req = urllib.request.Request(URL, headers={"User-Agent": "AbigelStats/2.0 (+punctuality)"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.loads(resp.read())
    rows = [r for v in (data.get("vehiclePositions") or []) if (r := record(v, now))]
    if not rows:
        print("Nincs rögzíthető vonat.")
        return
    path = append_runs(rows, now)
    groups = aggregate(now)
    print(f"{now:%Y-%m-%d %H:%M}: {len(rows)} vonat → {path.name}; összesítő: {groups} nap×viszonylat×szegmens sor")


if __name__ == "__main__":
    main()
