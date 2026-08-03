"""
Abigél – vonatkésés napi scraper
Lekéri a holavonat.is adatait, kiszámolja a késési statisztikákat,
és hozzáfűzi a data/kesesi_adatok.csv fájlhoz.
Max 60 nap adatot tart meg.
"""

import requests
import csv
import os
import json
from datetime import datetime, timezone, timedelta

DATA_DIR = "data"
CSV_PATH = os.path.join(DATA_DIR, "kesesi_adatok.csv")
MAX_DAYS = 60
HOLAVONAT_URL = "https://cdn.holavonat.is/train_data_v3.json"

HU_TZ = timezone(timedelta(hours=2))  # CEST (nyári idő); télen +1

CSV_FIELDS = [
    "datum",           # YYYY-MM-DD
    "ido",             # HH:MM (lekérés időpontja)
    "osszes",          # összes jármű a térképen
    "kesik_db",        # késő járatok száma (>0 perc)
    "kesik_pct",       # késési arány %
    "atlag_perc",      # átlagos késés percben (csak késők között)
    "max_perc",        # maximális késés
    "zold_db",         # 0-5 perc
    "sarga_db",        # 6-15 perc
    "narancs_db",      # 16-60 perc
    "piros_db",        # 60+ perc
    "legtobbet_keso",  # legtöbbet késő járat neve
    "legtobbet_perc",  # legtöbbet késő járat késése percben
]


def fetch_data():
    r = requests.get(HOLAVONAT_URL, timeout=30)
    r.raise_for_status()
    return r.json()


def get_position(v):
    pos = v.get("position") or v.get("vehiclePosition") or {}
    lat = pos.get("latitude") or pos.get("lat")
    lon = pos.get("longitude") or pos.get("lon") or pos.get("lng")
    if not lat and v.get("lat"):
        lat, lon = v.get("lat"), v.get("lon")
    return (float(lat), float(lon)) if lat and lon else None


def in_hungary(lat, lon):
    return 45 <= lat <= 49 and 15 <= lon <= 23


def calc_stats(vehicles):
    relevant = []
    for v in vehicles:
        pos = get_position(v)
        if not pos:
            continue
        lat, lon = pos
        if not in_hungary(lat, lon):
            continue
        relevant.append(v)

    total = len(relevant)
    if total == 0:
        return None

    delays = []
    cnt_g = cnt_y = cnt_o = cnt_r = 0
    worst_name = ""
    worst_min = -1

    for v in relevant:
        stop = (v.get("stopRelationship") or {}).get("stop", {}).get("name", "")
        stoptimes = (v.get("trip") or {}).get("stoptimes") or []
        dl = next((x for x in stoptimes if (x.get("stop") or {}).get("name") == stop), None)

        if dl is None or dl.get("arrivalDelay") is None:
            continue

        delay_min = round(dl["arrivalDelay"] / 60)

        if delay_min <= 0:
            cnt_g += 1
            continue

        delays.append(delay_min)

        if delay_min <= 5:
            cnt_g += 1
        elif delay_min <= 15:
            cnt_y += 1
        elif delay_min <= 60:
            cnt_o += 1
        else:
            cnt_r += 1

        if delay_min > worst_min:
            worst_min = delay_min
            trip = v.get("trip") or {}
            worst_name = (
                trip.get("tripShortName")
                or (trip.get("route") or {}).get("shortName")
                or "?"
            ).replace("<", "").replace(">", "")

    late_count = len(delays)
    late_pct = round(late_count / total * 100) if total else 0
    avg_delay = round(sum(delays) / late_count) if late_count else 0
    max_delay = max(delays) if delays else 0

    return {
        "osszes": total,
        "kesik_db": late_count,
        "kesik_pct": late_pct,
        "atlag_perc": avg_delay,
        "max_perc": max_delay,
        "zold_db": cnt_g,
        "sarga_db": cnt_y,
        "narancs_db": cnt_o,
        "piros_db": cnt_r,
        "legtobbet_keso": worst_name,
        "legtobbet_perc": worst_min if worst_min >= 0 else 0,
    }


def load_existing():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def prune_old(rows):
    cutoff = (datetime.now(HU_TZ) - timedelta(days=MAX_DAYS)).strftime("%Y-%m-%d")
    return [r for r in rows if r.get("datum", "") >= cutoff]


def save(rows):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    now = datetime.now(HU_TZ)
    datum = now.strftime("%Y-%m-%d")
    ido = now.strftime("%H:%M")

    print(f"[{datum} {ido}] Adatok lekérése...")
    data = fetch_data()
    vehicles = data.get("vehiclePositions") or []
    print(f"  {len(vehicles)} jármű az adatban")

    stats = calc_stats(vehicles)
    if not stats:
        print("  Nem sikerült statisztikát számolni – nincs elég adat.")
        return

    print(f"  Összes: {stats['osszes']}, Késik: {stats['kesik_db']} ({stats['kesik_pct']}%), Átlag: {stats['atlag_perc']} perc, Max: {stats['max_perc']} perc")

    rows = load_existing()
    # Ha már van mai adat, felülírjuk
    rows = [r for r in rows if r.get("datum") != datum]
    rows.append({"datum": datum, "ido": ido, **stats})
    rows = sorted(rows, key=lambda r: r["datum"])
    rows = prune_old(rows)

    save(rows)
    print(f"  Mentve: {CSV_PATH} ({len(rows)} nap)")


if __name__ == "__main__":
    main()
