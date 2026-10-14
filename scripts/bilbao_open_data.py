"""
Ampliación Bilbao: oferta por distrito, ingreso estimado y simulador del impuesto turístico.

Qué hace, en orden (cada paso imprime cuántos datos usa):
  1. Descarga las fuentes públicas (habitantes y distritos de Bilbao, secciones censales
     del INE) a data/opendata/ (en .gitignore).
  2. Dibuja los 8 distritos de Bilbao uniendo las secciones censales del INE.
  3. Coloca cada anuncio de Inside Airbnb en su distrito.
  4. P1: pisos turísticos por cada 1.000 habitantes y distrito.
  5. P2: ingreso mensual estimado por distrito (mediana y rango intercuartílico).
  6. P3: impuesto turístico por estancia según noches y personas.
Solo escribe datos AGREGADOS (por distrito o por escenario) en outputs/bilbao/.
Nunca escribe direcciones, números de registro, IDs de anuncio ni datos de contacto.

Uso:  python scripts/bilbao_open_data.py
Requisitos: pandas, numpy, pyshp, shapely, pyproj
"""
import json
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
import shapefile
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform, unary_union

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "opendata"
SALIDA = RAIZ / "outputs" / "bilbao"
LISTINGS = RAIZ / "data" / "bronze" / "euskadi" / "2026-06-30" / "listings.csv.gz"

FUENTES = {
    "f3_habitantes_seccion_2022.csv": "https://www.bilbao.eus/bilbaoopendata/demografia/numero_habitantes_distrito_seccion_edad_2022.csv",
    "f4_distritos_secciones_2022.csv": "https://www.bilbao.eus/bilbaoopendata/demografia/distritos_secciones_2022.csv",
    "ine_seccionado_2024.zip": "https://www.ine.es/prodyser/cartografia/seccionado_2024.zip",
}

# Supuestos del ingreso estimado (se pueden cambiar; el resultado depende mucho de ESTANCIA_MEDIA)
TASA_RESENA = 0.5      # proporción de estancias que dejan reseña
ESTANCIA_MEDIA = 3     # noches por estancia (o la estancia mínima del piso si es mayor)
TOPE_OCUPACION = 0.70  # máximo de noches del año que se considera ocupado

# Impuesto turístico (vigor 1-ene-2027). Verificado en prensa; confirmar en las ordenanzas publicadas.
TARIFA_PISO = 6.50     # € por persona y noche, vivienda de uso turístico (Bilbao, Donostia y Vitoria-Gasteiz)
TOPE_NOCHES = 6        # noches máximas gravadas por estancia
UMBRAL_PRIVACIDAD = 10  # no se muestra ninguna celda con menos de 10 pisos


def descargar():
    DATOS.mkdir(parents=True, exist_ok=True)
    for nombre, url in FUENTES.items():
        destino = DATOS / nombre
        if destino.exists():
            continue
        print(f"  descargando {nombre} ...")
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=600) as r:
            destino.write_bytes(r.read())
    if not (DATOS / "ine_2024").exists():
        with zipfile.ZipFile(DATOS / "ine_seccionado_2024.zip") as z:
            z.extractall(DATOS / "ine_2024")


def distritos_bilbao():
    a_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True).transform
    lector = shapefile.Reader(str(DATOS / "ine_2024" / "SECC_CE_20240101.shp"))
    por_distrito = {}
    for sr in lector.iterShapeRecords():
        if sr.record["CUMUN"] == "48020":
            geom = transform(a_wgs84, shape(sr.shape.__geo_interface__))
            por_distrito.setdefault(int(sr.record["CDIS"]), []).append(geom)
    f4 = pd.read_csv(DATOS / "f4_distritos_secciones_2022.csv", sep=";", encoding="latin-1")
    nombres = dict(zip(f4.iloc[:, 1], f4.iloc[:, 0]))
    n_secc = sum(len(v) for v in por_distrito.values())
    print(f"  secciones censales INE 2024 en Bilbao: {n_secc}; distritos: {len(por_distrito)}")
    return {cd: (nombres[cd], unary_union(g).buffer(0)) for cd, g in sorted(por_distrito.items())}


def habitantes_por_distrito():
    raw = pd.read_csv(DATOS / "f3_habitantes_seccion_2022.csv", sep=";", header=None, encoding="latin-1").iloc[2:]
    secc = raw[pd.to_numeric(raw[1], errors="coerce").notna()]  # quita la fila "Total general"
    total = secc.iloc[:, 2:].apply(pd.to_numeric, errors="coerce").sum(axis=1)
    pob = total.groupby(pd.to_numeric(secc[0]).astype(int)).sum()
    print(f"  secciones con habitantes: {len(secc)}; habitantes de Bilbao (2022): {int(pob.sum())}")
    return pob.to_dict()


def anuncios_con_distrito(distritos):
    cols = ["latitude", "longitude", "room_type", "neighbourhood_cleansed", "minimum_nights",
            "number_of_reviews_ltm", "price"]
    L = pd.read_csv(LISTINGS, usecols=cols, low_memory=False)
    L = L[L.neighbourhood_cleansed == "Bilbao"].copy()
    cods = list(distritos)
    arbol = STRtree([distritos[c][1] for c in cods])
    L["cod"] = [(lambda h: cods[h[0]] if len(h) else None)(arbol.query(Point(x, y), predicate="within"))
                for x, y in zip(L.longitude, L.latitude)]
    print(f"  anuncios de Inside Airbnb en Bilbao: {len(L)}; fuera de los 8 distritos: {L.cod.isna().sum()}")
    return L


def p1_oferta(L, distritos, pob):
    pisos = L[L.room_type == "Entire home/apt"].groupby("cod").size()
    T = pd.DataFrame({"distrito": [distritos[c][0] for c in distritos],
                      "habitantes": [int(pob[c]) for c in distritos],
                      "pisos_completos": [int(pisos.get(c, 0)) for c in distritos]}, index=list(distritos))
    T["pisos_por_1000_hab"] = (1000 * T.pisos_completos / T.habitantes).round(1)
    return T.sort_values("pisos_por_1000_hab", ascending=False)


def p2_ingreso(L, distritos):
    P = L[(L.room_type == "Entire home/apt") & (L.minimum_nights <= 30)].copy()
    P["precio"] = pd.to_numeric(P.price.astype(str).str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
    activos = P[(P.number_of_reviews_ltm > 0) & P.precio.notna() & (P.precio < 9999)].copy()
    print(f"  pisos de corta estancia: {len(P)}; activos con precio (al menos 1 reseña en 12 meses): {len(activos)}")
    noches = activos.number_of_reviews_ltm / TASA_RESENA * np.maximum(ESTANCIA_MEDIA, activos.minimum_nights)
    activos["noches"] = np.minimum(noches, TOPE_OCUPACION * 365)
    activos["ingreso_mes"] = activos.noches * activos.precio / 12
    filas = []
    for cod, g in activos.groupby("cod"):
        fila = {"distrito": distritos[cod][0], "pisos_activos": len(g)}
        if len(g) >= UMBRAL_PRIVACIDAD:
            fila.update(precio_noche_mediano=round(g.precio.median()), noches_ano_mediana=round(g.noches.median()),
                        ingreso_mes_p25=round(g.ingreso_mes.quantile(.25)), ingreso_mes_mediana=round(g.ingreso_mes.median()),
                        ingreso_mes_p75=round(g.ingreso_mes.quantile(.75)))
        filas.append(fila)
    tope = (activos.noches >= TOPE_OCUPACION * 365 - 0.01).mean()
    print(f"  pisos que tocan el tope del {TOPE_OCUPACION:.0%} de ocupación: {tope:.1%}")
    return pd.DataFrame(filas).sort_values("ingreso_mes_mediana", ascending=False), activos


def p3_impuesto(precio_noche):
    filas = []
    for personas in (1, 2, 4):
        for noches in (1, 2, 3, 4, 5, 6, 7, 10, 14, 30):
            por_estancia = TARIFA_PISO * personas * min(noches, TOPE_NOCHES)
            por_noche = por_estancia / noches
            filas.append(dict(personas=personas, noches=noches, impuesto_estancia=round(por_estancia, 2),
                              impuesto_por_noche=round(por_noche, 2), pct_sobre_precio=round(100 * por_noche / precio_noche, 1)))
    return pd.DataFrame(filas)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    print("1. Descarga"); descargar()
    print("2. Distritos"); distritos = distritos_bilbao()
    print("3. Habitantes"); pob = habitantes_por_distrito()
    print("4. Anuncios"); L = anuncios_con_distrito(distritos)
    print("5. P1 oferta"); t1 = p1_oferta(L, distritos, pob); print(t1.to_string(index=False))
    print("6. P2 ingreso"); t2, activos = p2_ingreso(L, distritos); print(t2.to_string(index=False))
    precio = activos.precio.median()
    print(f"7. P3 impuesto (precio por noche mediano de Bilbao: {precio:.0f} EUR)"); t3 = p3_impuesto(precio)
    print(t3[t3.personas == 2].to_string(index=False))
    t1.to_csv(SALIDA / "p1_oferta_distrito.csv", index=False)
    t2.to_csv(SALIDA / "p2_ingreso_distrito.csv", index=False)
    t3.to_csv(SALIDA / "p3_impuesto_escenarios.csv", index=False)
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"cod": c, "distrito": n}, "geometry": mapping(g.simplify(0.0001))}
        for c, (n, g) in distritos.items()]}
    (SALIDA / "bilbao_distritos.geojson").write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    print(f"Listo. Salidas agregadas en {SALIDA}")


if __name__ == "__main__":
    main()
