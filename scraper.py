"""
Abigel – vonatkésés napi scraper (v2)
Lekéri a holavonat.is adatait, külön számolja a vonat (RAIL) és
összes jármű késési statisztikáit, és hozzáfűzi a CSV-hez.
Max 60 nap adatot tart meg.
"""

import requests
import csv
import os
from datetime import datetime, timezone, timedelta

DATA_DIR = "data"
CSV_PATH = os.path.join(DATA_DIR, "kesesi_adatok.csv")
MAX_DAYS = 60
HOLAVONAT_URL = "https://cdn.holavonat.is/train_data_v3.json"
HU_TZ = timezone(timedelta(hours=2))

CSV_FIELDS = [
    "datum", "ido",
    "osszes", "kesik_db", "atlag_perc", "max_perc",
    "zold_db", "sarga_db", "narancs_db", "piros_db",
    "legtobbet_keso", "legtobbet_perc",
    "tr_osszes", "tr_kesik_db", "tr_kesik_pct",
    "tr_atlag_perc", "tr_max_perc",
    "tr_legtobbet_keso", "tr_legtobbet_perc",
]


def fetch_data():
    r = requests.get(HOLAVONAT_URL, timeout=30)
    r.raise_for_status()
    return r.json()


def get_position(v):
    pos = v.get("position") or v.get("vehiclePosition") or {}
    lat = pos.get("latitude") or pos.get("lat") or v.get("lat")
    lon = pos.get("longitude") or pos.get("lon") or pos.get("lng") or v.get("lon")
    return (float(lat), float(lon)) if lat and lon else None


def in_hungary(lat, lon):
    return 45 <= lat <= 49 and 15 <= lon <= 23


def get_mode(v):
    return (v.get("trip") or {}).get("route", {}).get("mode", "").upper()


def is_rail(v):
    return get_mode(v) in ("RAIL", "SUBWAY")


def get_delay_min(v):
    stop = (v.get("stopRelationship") or {}).get("stop", {}).get("name", "")
    stoptimes = (v.get("trip") or {}).get("stoptimes") or []
    dl = next((x for x in stoptimes if (x.get("stop") or {}).get("name") == stop), None)
    if dl is None or dl.get("arrivalDelay") is None:
        return None
    return round(dl["arrivalDelay"] / 60)


def get_name(v):
    trip = v.get("trip") or {}
    return (trip.get("tripShortName") or
            (trip.get("route") or {}).get("shortName") or "?").replace("<", "").replace(">", "")


def calc_group_stats(vehicles):
    delays = []
    cnt_g = cnt_y = cnt_o = cnt_r = 0
    worst_name, worst_min = "", -1
    for v in vehicles:
        dm = get_delay_min(v)
        if dm is None:
            continue
        if dm <= 5:
            cnt_g += 1
            continue
        delays.append(dm)
        if dm <= 15:
            cnt_y += 1
        elif dm <= 60:
            cnt_o += 1
        else:
            cnt_r += 1
        if dm > worst_min:
            worst_min = dm
            worst_name = get_name(v)
    total = len(vehicles)
    late = len(delays)
    return {
        "osszes": total,
        "kesik_db": late,
        "kesik_pct": round(late / total * 100) if total else 0,
        "atlag_perc": round(sum(delays) / late) if late else 0,
        "max_perc": max(delays) if delays else 0,
        "zold_db": cnt_g, "sarga_db": cnt_y,
        "narancs_db": cnt_o, "piros_db": cnt_r,
        "legtobbet_keso": worst_name,
        "legtobbet_perc": worst_min if worst_min >= 0 else 0,
    }


def main():
    now = datetime.now(HU_TZ)
    datum = now.strftime("%Y-%m-%d")
    ido = now.strftime("%H:%M")
    print(f"[{datum} {ido}] Adatok lekérése...")
    data = fetch_data()
    vehicles = data.get("vehiclePositions") or []
    relevant = [v for v in vehicles if (p := get_position(v)) and in_hungary(*p)]
    print(f"  {len(relevant)} jármű Magyarországon")
    if not relevant:
        print("  Nincs elég adat.")
        return
    all_s = calc_group_stats(relevant)
    rail_s = calc_group_stats([v for v in relevant if is_rail(v)])
    print(f"  Összes: {all_s['osszes']}, Késik: {all_s['kesik_db']} ({all_s['kesik_pct']}%)")
    print(f"  Vonat: {rail_s['osszes']}, Késik: {rail_s['kesik_db']} ({rail_s['kesik_pct']}%), Átlag: {rail_s['atlag_perc']} perc")
    row = {
        "datum": datum, "ido": ido,
        "osszes": all_s["osszes"], "kesik_db": all_s["kesik_db"],
        "atlag_perc": all_s["atlag_perc"], "max_perc": all_s["max_perc"],
        "zold_db": all_s["zold_db"], "sarga_db": all_s["sarga_db"],
        "narancs_db": all_s["narancs_db"], "piros_db": all_s["piros_db"],
        "legtobbet_keso": all_s["legtobbet_keso"], "legtobbet_perc": all_s["legtobbet_perc"],
        "tr_osszes": rail_s["osszes"], "tr_kesik_db": rail_s["kesik_db"],
        "tr_kesik_pct": rail_s["kesik_pct"], "tr_atlag_perc": rail_s["atlag_perc"],
        "tr_max_perc": rail_s["max_perc"],
        "tr_legtobbet_keso": rail_s["legtobbet_keso"], "tr_legtobbet_perc": rail_s["legtobbet_perc"],
    }
    rows = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get("datum") != datum]
    rows.append(row)
    rows = sorted(rows, key=lambda r: r["datum"])
    cutoff = (now - timedelta(days=MAX_DAYS)).strftime("%Y-%m-%d")
    rows = [r for r in rows if r.get("datum", "") >= cutoff]
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Mentve: {CSV_PATH} ({len(rows)} nap)")


if __name__ == "__main__":
    main()
