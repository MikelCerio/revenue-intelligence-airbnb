"""
Datos agregados para la herramienta "¿Vendo por debajo o por encima?" (versión 1).

Genera outputs/herramienta/datos.json con SOLO datos públicos y agregados:
  - Precio de referencia de pisos parecidos (mismo distrito y capacidad): p25, mediana y p75.
    Solo se publican grupos de 10 o más pisos (regla de privacidad del proyecto).
  - Índice de precio por fecha de captura (cuánto se mueve la cotización respecto a su referencia de primavera).
  - Eventos con fechas y fuente: calendario curado, partidos de liga en casa y grandes recintos de Kulturklik.
  - Efecto medido de los eventos en la ocupación aproximada (outputs/eventos/efecto_eventos.csv).
  - Alquiler largo de referencia (EMAL, Gobierno Vasco).
No incluye IDs de anuncio, anfitriones, direcciones ni datos de ninguna empresa.

Uso:  python scripts/herramienta_datos.py
Requisitos: pandas, numpy, shapely, pyshp, pyproj (los mismos que bilbao_open_data.py)
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from shapely import STRtree
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bilbao_open_data as b  # noqa: E402

RAIZ = b.RAIZ
SALIDA = RAIZ / "outputs" / "herramienta"
CAPACIDADES = ["1-2", "3-4", "5-6", "7+"]
CORTES = [0, 2, 4, 6, 99]
MIN_PISOS = b.UMBRAL_PRIVACIDAD
SNAPSHOTS_INDICE = ["2026-03-31", "2026-04-30", "2026-05-31", "2026-06-30", "2026-07-26", "2026-08-31", "2026-09-25"]
ALQUILER_LARGO = {"Bilbao": 1011.1, "Donostia": 1131.9}  # EMAL, contratos nuevos 4T 2025
# Costa: cada municipio es una "zona"; los eventos que se le muestran son los de la capital de su provincia.
COSTA = {
    "Costa Gipuzkoa": ("Donostia", ["Hondarribia", "Pasaia", "Orio", "Zarautz", "Aia", "Getaria", "Zumaia", "Deba", "Mutriku"]),
    "Costa Bizkaia": ("Bilbao", ["Ondarroa", "Lekeitio", "Ea", "Elantxobe", "Ibarrangelu", "Mundaka", "Sukarrieta", "Busturia", "Bermeo",
                                 "Bakio", "Lemoiz", "Gorliz", "Plentzia", "Barrika", "Sopelana", "Getxo", "Zierbena", "Muskiz", "Santurtzi"]),
}
ALQUILER_COSTA = {"Zarautz": 778.1, "Hondarribia": 930.9, "Getxo": 833.9, "Sopelana": 833.9, "Bakio": 766.7,  # EMAL 2025: renta media
                  "Bermeo": 594.6, "Lekeitio": 594.6, "Mundaka": 594.6}                                     # vigente de su área funcional
RECINTOS = r"\bBEC\b|Bizkaia Arena|Kursaal|San Mam|Anoeta|Reale Arena|Bilbao Arena"  # sin Euskalduna: mucha programacion local y clasica
LISTINGS_BASE = RAIZ / "data" / "bronze" / "euskadi"


def arreglar_texto(s):
    """Algunos nombres de municipio llegan con la codificación rota (Ã¡ en vez de á)."""
    try:
        return s.encode("cp1252").decode("utf-8")
    except Exception:
        return s


def listings(snapshot, cols):
    return pd.read_csv(LISTINGS_BASE / snapshot / "listings.csv.gz", usecols=cols, low_memory=False)


def precio_de(df):
    p = pd.to_numeric(df.price.astype(str).str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
    return p.where((p > 0) & (p < 9999))


def asignar_distrito(L, distritos):
    cods = list(distritos)
    arbol = STRtree([distritos[c][1] for c in cods])
    L = L.copy()
    L["cod"] = [(lambda h: cods[h[0]] if len(h) else None)(arbol.query(Point(x, y), predicate="within"))
                for x, y in zip(L.longitude, L.latitude)]
    return L.dropna(subset=["cod"])


def grupos_precio(A, distritos):
    """Cuantiles de precio por distrito y capacidad, con el mínimo de pisos por grupo."""
    A = A.copy()
    A["cap"] = pd.cut(A.accommodates, CORTES, labels=CAPACIDADES)

    def cuantiles(g):
        return dict(n=int(len(g)), p25=round(g.precio.quantile(.25)), med=round(g.precio.median()), p75=round(g.precio.quantile(.75)))

    res = {"distritos": {}, "ciudad": {}}
    for c, g in A.groupby("cod"):
        nombre = distritos[c][0]
        por = {cap: cuantiles(h) for cap, h in g.groupby("cap", observed=True) if len(h) >= MIN_PISOS}
        if len(g) >= MIN_PISOS:
            por["todas"] = cuantiles(g)
        if por:
            res["distritos"][nombre] = por
    for cap, h in A.groupby("cap", observed=True):
        if len(h) >= MIN_PISOS:
            res["ciudad"][cap] = cuantiles(h)
    res["ciudad"]["todas"] = cuantiles(A)
    return res


def indice_temporada(ids_ref, ciudad_ids):
    """Mediana del cociente entre el precio de cada captura y la referencia (mediana mar-jun) de cada piso."""
    filas = {c: [] for c in ciudad_ids}
    for s in SNAPSHOTS_INDICE:
        L = listings(s, ["id", "price"])
        L["p"] = precio_de(L)
        L = L.dropna(subset=["p"])
        doy = pd.Timestamp(s).dayofyear
        for c, ids in ciudad_ids.items():
            g = L[L.id.isin(ids)]
            r = (g.p.values / ids_ref.reindex(g.id).values)
            r = r[np.isfinite(r)]
            if len(r) >= 50:
                filas[c].append([doy, round(float(np.median(r)), 3), int(len(r))])
    return filas


def limpia_nombre(s):
    """Quita el prefijo 'Entradas' y la fecha entre paréntesis que Kulturklik añade al final del nombre."""
    s = re.sub(r"^\s*Entradas\s+", "", str(s).strip('"'), flags=re.I)
    s = re.sub(r"\s*\((?=[^)]*\d)[^)]*\)\s*$", "", s)
    return s.replace('"', "").strip(" -")[:70]


def eventos(hoy):
    G = pd.read_csv(RAIZ / "eventos" / "grandes_eventos.csv")
    G = G[G.ciudad.isin(["Bilbao", "Donostia"])]
    lista = [dict(nombre=r.nombre, ciudad=r.ciudad, tipo=r.tipo, ini=r.fecha_ini, fin=r.fecha_fin, estado=r.estado, fuente=r.fuente_url)
             for r in G.itertuples()]
    F = pd.read_csv(RAIZ / "eventos" / "partidos_casa_laliga.csv")
    lista += [dict(nombre=f"{r.equipo_local} - {r.rival}", ciudad=r.ciudad, tipo="futbol", ini=r.fecha, fin=r.fecha, estado="liga",
                   fuente="https://www.football-data.co.uk/spainm.php") for r in F.itertuples()]
    K = pd.read_csv(RAIZ / "eventos" / "eventos_euskadi.csv", dtype={"id": str}, keep_default_na=False)
    K = K[(K.fecha_valida.astype(str) == "True") & K.ciudad_clave.isin(["Bilbao", "Donostia"])
          & K.establishmentEs.astype(str).str.contains(RECINTOS, regex=True) & (K.fecha_ini >= hoy.isoformat())
          & K.typeEs.isin(["Concierto", "Festival", "Deporte", "Feria", "Congreso"])
          & ~K.nameEs.astype(str).str.contains("CANCELAD", case=False)
          & ~(K.typeEs.isin(["Feria", "Congreso"]) & ~K.establishmentEs.astype(str).str.contains(r"\bBEC\b|Bizkaia Arena"))]
    lista += [dict(nombre=limpia_nombre(r.nameEs), ciudad=r.ciudad_clave, tipo="recinto", ini=r.fecha_ini, fin=r.fecha_fin,
                   estado="agenda", recinto=r.establishmentEs, fuente=r.sourceUrlEs if isinstance(r.sourceUrlEs, str) else "")
              for r in K.itertuples()]
    return sorted(lista, key=lambda e: e["ini"])


def efectos():
    T = pd.read_csv(RAIZ / "outputs" / "eventos" / "efecto_eventos.csv")
    G = T[(T.tipo != "futbol") & T.ciudad.isin(["Bilbao", "Donostia"])]
    por_evento = {r.evento: dict(dif_pp=r.dif_pp, noches=int(r.noches), cobertura=float(r.cobertura)) for r in G.itertuples()}
    por_tipo = {}
    for (c, t), g in G.groupby(["ciudad", "tipo"]):
        por_tipo[f"{c}|{t}"] = dict(dif_pp=round(float(g.dif_pp.mean()), 1), eventos=int(len(g)))
    P = pd.read_csv(RAIZ / "outputs" / "eventos" / "placebo.csv")
    ruido = {r.ciudad: float(r.desviacion) for r in P.itertuples()}
    return dict(por_evento=por_evento, por_tipo=por_tipo, global_pp=round(float(G.dif_pp.mean()), 1), global_ee=round(float(G.dif_pp.std(ddof=1) / np.sqrt(len(G))), 1),
                n_eventos=int(len(G)), ruido_pp=ruido)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    b.descargar()
    precio_ref = b.precio_referencia()
    dist = {"Bilbao": b.distritos_bilbao(), "Donostia": b.distritos_donostia()}
    cols = ["id", "latitude", "longitude", "room_type", "neighbourhood_cleansed", "minimum_nights", "number_of_reviews_ltm", "accommodates"]
    L = pd.read_csv(b.LISTINGS, usecols=cols, low_memory=False)
    datos = {"ciudades": {}, "estacional": {}}
    ids_ciudad = {}
    for ciudad, d in dist.items():
        sel = L.neighbourhood_cleansed.astype(str).str.startswith(ciudad)
        A = L[sel & (L.room_type == "Entire home/apt") & (L.minimum_nights <= 30) & (L.number_of_reviews_ltm > 0)].copy()
        A["precio"] = A.id.map(precio_ref)
        A = asignar_distrito(A.dropna(subset=["precio"]), d)
        datos["ciudades"][ciudad] = dict(**grupos_precio(A, d), alquiler_largo=ALQUILER_LARGO[ciudad], pisos=int(len(A)))
        ids_ciudad[ciudad] = set(A.id)
        print(f"{ciudad}: {len(A)} pisos activos con precio; distritos con datos: {len(datos['ciudades'][ciudad]['distritos'])}")
    L["municipio"] = L.neighbourhood_cleansed.astype(str).map(arreglar_texto)
    for costa, (capital, municipios) in COSTA.items():
        A = L[L.municipio.isin(municipios) & (L.room_type == "Entire home/apt") & (L.minimum_nights <= 30) & (L.number_of_reviews_ltm > 0)].copy()
        A["precio"] = A.id.map(precio_ref)
        A = A.dropna(subset=["precio"])
        A["cod"] = A.municipio
        G = grupos_precio(A, {m: (m, None) for m in municipios})
        datos["ciudades"][costa] = dict(**G, alquiler_largo=None, capital=capital, pisos=int(len(A)),
                                        alquiler_distrito={m: v for m, v in ALQUILER_COSTA.items() if m in G["distritos"]})
        ids_ciudad[costa] = set(A.id)
        print(f"{costa}: {len(A)} pisos activos con precio; municipios con datos: {len(G['distritos'])}")
    datos["estacional"] = indice_temporada(precio_ref, ids_ciudad)
    hoy = date.today()
    datos["eventos"] = eventos(hoy)
    datos["efectos"] = efectos()
    datos["meta"] = dict(generado=hoy.isoformat(), snapshot_precios="2026-03-31 a 2026-06-30 (mediana de cada piso)",
                         fuentes=["Inside Airbnb (CC BY 4.0)", "INE, secciones censales 2024", "Kulturklik (Open Data Euskadi)", "EMAL, Gobierno Vasco"])
    (SALIDA / "datos.json").write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Listo: {SALIDA / 'datos.json'} ({(SALIDA / 'datos.json').stat().st_size / 1024:.0f} KB; {len(datos['eventos'])} eventos)")


if __name__ == "__main__":
    main()
