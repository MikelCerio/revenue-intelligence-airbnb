"""
Partidos de LaLiga 2025-26 en casa del Athletic (Bilbao) y la Real Sociedad (Donostia).

Fuente: football-data.co.uk (CSV público de resultados). Solo liga: faltan Copa del Rey y competiciones europeas.
Salida: eventos/partidos_casa_laliga.csv (fecha, hora, ciudad, equipo_local, rival)

Uso:  python scripts/futbol_laliga.py
Requisitos: pandas
"""
from pathlib import Path

import pandas as pd

URL = "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"
LOCALES = {"Ath Bilbao": ("Bilbao", "Athletic Club"), "Sociedad": ("Donostia", "Real Sociedad")}
SALIDA = Path(__file__).resolve().parents[1] / "eventos" / "partidos_casa_laliga.csv"

d = pd.read_csv(URL, encoding="utf-8-sig", usecols=["Date", "Time", "HomeTeam", "AwayTeam"])
d = d[d.HomeTeam.isin(LOCALES)].copy()
d["fecha"] = pd.to_datetime(d.Date, format="%d/%m/%Y").dt.date
d["ciudad"] = d.HomeTeam.map(lambda t: LOCALES[t][0])
d["equipo_local"] = d.HomeTeam.map(lambda t: LOCALES[t][1])
d = d.rename(columns={"Time": "hora", "AwayTeam": "rival"})[["fecha", "hora", "ciudad", "equipo_local", "rival"]]
d.sort_values("fecha").to_csv(SALIDA, index=False, encoding="utf-8")
print(f"{len(d)} partidos en casa guardados en {SALIDA}")
