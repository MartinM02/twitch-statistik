#!/usr/bin/env python3
"""Misst einmal die deutschen League-of-Legends-Streams auf Twitch,
haengt das Ergebnis an lol_streams.csv an und schreibt die Auswertung
in die README.md. Wird automatisch von GitHub Actions aufgerufen."""

import csv
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
CLIENT_SECRET = os.environ["TWITCH_CLIENT_SECRET"]

GAME_ID = "21779"          # League of Legends
LANGUAGE = "de"
ZEITZONE = ZoneInfo("Europe/Berlin")
CSV_DATEI = Path("lol_streams.csv")
README = Path("README.md")


def get_token() -> str:
    r = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
              "grant_type": "client_credentials"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def messe(token: str) -> tuple[int, int]:
    """Zaehlt aktuelle deutsche LoL-Streams und summiert deren Zuschauer."""
    headers = {"Client-Id": CLIENT_ID, "Authorization": f"Bearer {token}"}
    params = {"game_id": GAME_ID, "language": LANGUAGE, "first": 100}
    streams = zuschauer = 0
    while True:
        r = requests.get("https://api.twitch.tv/helix/streams",
                         headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        streams += len(data["data"])
        zuschauer += sum(s["viewer_count"] for s in data["data"])
        cursor = data.get("pagination", {}).get("cursor")
        if not cursor:
            return streams, zuschauer
        params["after"] = cursor


def zahl(n: float) -> str:
    """1234567 -> '1.234.567' (deutsche Schreibweise)"""
    return f"{round(n):,}".replace(",", ".")


def komma(n: float) -> str:
    """3.7 -> '3,7'"""
    return f"{n:.1f}".replace(".", ",")


def readme_schreiben() -> None:
    zeilen = list(csv.DictReader(CSV_DATEI.open()))
    pro_stunde: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for z in zeilen:
        t = datetime.fromisoformat(z["zeitpunkt"])
        pro_stunde[t.hour].append((int(z["streams"]), int(z["zuschauer"])))

    tabelle = [
        "| Uhrzeit | Ø Streams | Ø Zuschauer | Zuschauer pro Stream |",
        "|--------:|----------:|------------:|---------------------:|",
    ]
    ergebnisse = []
    for stunde in sorted(pro_stunde):
        werte = pro_stunde[stunde]
        s = sum(v[0] for v in werte) / len(werte)
        zu = sum(v[1] for v in werte) / len(werte)
        ratio = zu / s if s else 0.0
        ergebnisse.append((stunde, s, zu, ratio))
        tabelle.append(f"| {stunde}:00 | {zahl(s)} | {zahl(zu)} | {komma(ratio)} |")

    wenigste = min(ergebnisse, key=lambda e: e[1])
    beste = max(ergebnisse, key=lambda e: e[3])
    erste = datetime.fromisoformat(zeilen[0]["zeitpunkt"])
    letzte = datetime.fromisoformat(zeilen[-1]["zeitpunkt"])

    hinweis = ""
    if len(zeilen) < 96:
        hinweis = ("\n> Noch wenig Daten gesammelt - die Werte werden mit "
                   "jedem Tag aussagekraeftiger.\n")

    md = f"""# Deutsche League-of-Legends-Streams auf Twitch

Letzte Messung: **{letzte:%d.%m.%Y, %H:%M} Uhr** - {zahl(int(zeilen[-1]["streams"]))} Streams, {zahl(int(zeilen[-1]["zuschauer"]))} Zuschauer
{hinweis}
## Empfehlung

- **Wenigste Konkurrenz:** {wenigste[0]}:00 Uhr (Ø {zahl(wenigste[1])} Streams)
- **Bestes Zuschauer-pro-Stream-Verhaeltnis:** {beste[0]}:00 Uhr (Ø {komma(beste[3])} Zuschauer pro Stream)

## Durchschnitt pro Stunde (deutsche Zeit)

{chr(10).join(tabelle)}

---
_{len(zeilen)} Messungen im Abstand von ca. 15 Minuten, Zeitraum {erste:%d.%m.%Y} bis {letzte:%d.%m.%Y}. Alle Zeiten in deutscher Zeit._
"""
    README.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    token = get_token()
    streams, zuschauer = messe(token)
    neu = not CSV_DATEI.exists()
    with CSV_DATEI.open("a", newline="") as f:
        w = csv.writer(f)
        if neu:
            w.writerow(["zeitpunkt", "streams", "zuschauer"])
        w.writerow([datetime.now(ZEITZONE).isoformat(timespec="seconds"),
                    streams, zuschauer])
    readme_schreiben()
    print(f"OK: {streams} Streams, {zuschauer} Zuschauer")
