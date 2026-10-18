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

# Ingreso estimado = noches ocupadas × precio de referencia.
# Desde octubre de 2026 las noches salen del CALENDARIO público, no de las reseñas. El método anterior
# (la mitad de las estancias deja reseña, 3 noches por estancia, tope del 70 %) daba entre 2 y 4 veces menos
# ingreso que las fuentes comerciales de referencia, consultadas solo para comprobar; el calendario se queda
# a unos ±10 puntos de ocupación de ellas. Noche ocupada = no disponible, leída en la captura más cercana por
# delante (0 a 29 días), como scripts/ocupacion_mes.py. Incluye las noches que bloquea el dueño.
VENTANA_OCUPACION = ("2025-10-01", "2026-09-30")   # último año completo con calendario medido
MIN_NOCHES_MEDIDAS = 180   # con menos noches observadas (alta o baja a mitad de año) el piso no entra en el ingreso
ESTANCIA_MEDIA = 3         # noches por estancia, para estimar limpiezas
OCUPACION = None           # se rellena en main() con ocupacion_calendario()

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


SNAPSHOTS_PRECIO = ("2026-03-31", "2026-04-30", "2026-05-31", "2026-06-30")


def precio_referencia():
    """Precio por noche de referencia de cada anuncio: mediana de sus precios de marzo a junio de 2026.

    Desde marzo de 2026 el precio de Inside Airbnb es una cotización para fechas cercanas a la captura;
    usar solo junio sobrestimaba el ingreso anual (precios de verano). Diciembre a febrero no traen precio.
    """
    trozos = []
    for s in SNAPSHOTS_PRECIO:
        X = pd.read_csv(LISTINGS.parents[1] / s / "listings.csv.gz", usecols=["id", "price"], low_memory=False)
        X["p"] = pd.to_numeric(X.price.astype(str).str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
        trozos.append(X[(X.p > 0) & (X.p < 9999)][["id", "p"]])
    ref = pd.concat(trozos).groupby("id").p.median()
    print(f"  precio de referencia (mediana mar-jun 2026) para {len(ref)} anuncios de Euskadi")
    return ref


def ocupacion_calendario():
    """Ocupación anual de cada anuncio (0 a 1) con el calendario público de todas las capturas.

    Cada noche de VENTANA_OCUPACION se lee en la captura más cercana por delante (antelación de 0 a 29 días).
    Se descartan, en cada captura, los anuncios bloqueados los 365 días (no están en el mercado).
    Se guarda en data/opendata/ocupacion_anuncio.csv (ignorado por git) para no recalcular cada vez.
    """
    cache = DATOS / f"ocupacion_anuncio_{VENTANA_OCUPACION[0]}_{VENTANA_OCUPACION[1]}.csv"
    if cache.exists():
        s = pd.read_csv(cache, index_col=0).occ
        print(f"  ocupación por calendario (caché): {len(s)} anuncios")
        return s
    ini, fin = (pd.Timestamp(x) for x in VENTANA_OCUPACION)
    trozos = []
    for d in sorted(p for p in LISTINGS.parents[1].iterdir() if (p / "calendar.csv.gz").exists()):
        C = pd.read_csv(d / "calendar.csv.gz", usecols=["listing_id", "date", "available"])
        C["ocupada"] = C.available.astype(str).str.lower().isin(["f", "false"]).astype(int)
        C = C[C.groupby("listing_id").ocupada.transform("min") == 0]
        C["date"] = pd.to_datetime(C.date)
        C["ant"] = (C.date - C.date.min()).dt.days
        trozos.append(C[(C.ant <= 29) & C.date.between(ini, fin)][["listing_id", "date", "ocupada", "ant"]])
    N = pd.concat(trozos).sort_values("ant").drop_duplicates(["listing_id", "date"])
    g = N.groupby("listing_id").ocupada.agg(["mean", "size"])
    s = g[g["size"] >= MIN_NOCHES_MEDIDAS]["mean"].rename("occ")
    s.to_frame().to_csv(cache)
    print(f"  ocupación por calendario: {len(s)} anuncios con al menos {MIN_NOCHES_MEDIDAS} noches medidas; mediana {s.median():.0%}")
    return s


def anuncios_con_distrito(distritos):
    cols = ["id", "latitude", "longitude", "room_type", "neighbourhood_cleansed", "minimum_nights",
            "number_of_reviews_ltm", "number_of_reviews", "availability_365", "accommodates", "calculated_host_listings_count"]
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


def p2_ingreso(L, distritos, precio_ref):
    P = L[(L.room_type == "Entire home/apt") & (L.minimum_nights <= 30)].copy()
    P["precio"] = P.id.map(precio_ref)
    activos = P[(P.number_of_reviews_ltm > 0) & P.precio.notna()].copy()
    activos["noches"] = activos.id.map(OCUPACION) * 365
    activos = activos.dropna(subset=["noches"])
    print(f"  pisos de corta estancia: {len(P)}; activos con precio y calendario medido (al menos 1 reseña en 12 meses): {len(activos)}")
    activos["ingreso_mes"] = activos.noches * activos.precio / 12
    filas = []
    for cod, g in activos.groupby("cod"):
        fila = {"distrito": distritos[cod][0], "pisos_activos": len(g)}
        if len(g) >= UMBRAL_PRIVACIDAD:
            fila.update(precio_noche_mediano=round(g.precio.median()), noches_ano_mediana=round(g.noches.median()),
                        ingreso_mes_p25=round(g.ingreso_mes.quantile(.25)), ingreso_mes_mediana=round(g.ingreso_mes.median()),
                        ingreso_mes_p75=round(g.ingreso_mes.quantile(.75)))
        filas.append(fila)
    print(f"  ocupación mediana de los pisos activos: {activos.noches.median() / 365:.0%}")
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


# Modelo de costes (P4). Todo son supuestos editables; la fuente o el motivo va al lado.
# Importes mensuales por piso salvo que se indique. Sin hipoteca ni IRPF.
ESCENARIOS = {
    "propietario_solo": dict(
        comision_plataforma=0.1876,   # Airbnb solo anfitrión 15,5 % + IVA 21 % no recuperable (Rentals Scale Up, Hostaway)
        comision_gestora=0.0,
        limpieza_estancia=55.0,       # SUPUESTO: limpieza externa unas 2,5 h + lavandería y amenities (sin cifra pública en Bilbao)
        suministros=180.0,            # luz 57 + gas 43 + agua 18 (medias de hogar 2026) + internet 40 + extra por rotación 22
        comunidad=80.0, seguro=30.0, ibi_basura=40.0,  # medias de propietario en España
        software=0.0,
        mantenimiento_pct=0.03),      # SUPUESTO: reposición y pequeñas reparaciones
    "con_gestora": dict(
        comision_plataforma=0.1876, comision_gestora=0.20,  # gestoras: 15-30 % habitual (Chekin)
        limpieza_estancia=55.0, suministros=180.0, comunidad=80.0, seguro=30.0, ibi_basura=40.0,
        software=0.0, mantenimiento_pct=0.03),
    "gestora_con_escala": dict(
        comision_plataforma=0.155 * 0.7,  # SUPUESTO: 30 % de reservas directas sin comisión; con IVA deducible
        comision_gestora=0.0,
        limpieza_estancia=35.0,       # SUPUESTO: equipo propio y lavandería por volumen
        suministros=180.0, comunidad=80.0, seguro=30.0, ibi_basura=40.0,
        software=25.0,                # SUPUESTO: PMS y herramientas por piso
        mantenimiento_pct=0.02),
}
ALQUILER_LARGO_MES = 1011.1   # EMAL Gobierno Vasco: renta media de contratos nuevos en Bilbao, 4.º trimestre de 2025


def p4_costes(activos, distritos):
    """Neto mensual antes de hipoteca e impuestos del piso mediano de cada distrito, por escenario."""
    filas = []
    for cod, g in activos.groupby("cod"):
        if len(g) < UMBRAL_PRIVACIDAD:
            continue
        noches_mes = g.noches.median() / 12
        bruto = g.ingreso_mes.median()
        estancias_mes = noches_mes / ESTANCIA_MEDIA
        fila = {"distrito": distritos[cod][0], "ingreso_bruto_mes": round(bruto), "noches_mes": round(noches_mes, 1)}
        for nombre, e in ESCENARIOS.items():
            variable = bruto * (e["comision_plataforma"] + e["comision_gestora"] + e["mantenimiento_pct"]) \
                + estancias_mes * e["limpieza_estancia"]
            fijo = e["suministros"] + e["comunidad"] + e["seguro"] + e["ibi_basura"] + e["software"]
            fila[f"neto_{nombre}"] = round(bruto - variable - fijo)
        filas.append(fila)
    fijo_largo = ESCENARIOS["propietario_solo"]
    neto_largo = ALQUILER_LARGO_MES - (fijo_largo["comunidad"] + fijo_largo["seguro"] + fijo_largo["ibi_basura"])
    T = pd.DataFrame(filas).sort_values("ingreso_bruto_mes", ascending=False)
    T["neto_alquiler_largo"] = round(neto_largo)
    return T


def p5_municipios(precio_ref):
    """Bilbao frente a Donostia, la costa y Vitoria-Gasteiz: ingreso, neto del dueño y alquiler largo (EMAL 2025)."""
    largo = {  # capitales: contratos nuevos 4T 2025; resto: renta media vigente de su área funcional
        "Bilbao": 1011.1, "Donostia-San Sebastián": 1131.9, "Vitoria-Gasteiz": 851.2, "Zarautz": 778.1,
        "Hondarribia": 930.9, "Getxo": 833.9, "Sopelana": 833.9, "Bakio": 766.7, "Bermeo": 594.6,
        "Lekeitio": 594.6, "Mundaka": 594.6}
    def arreglar(s):
        try:
            return s.encode("cp1252").decode("utf-8")
        except Exception:
            return s
    L = pd.read_csv(LISTINGS, usecols=["id", "neighbourhood_cleansed", "room_type", "minimum_nights", "number_of_reviews_ltm"], low_memory=False)
    L["municipio"] = L.neighbourhood_cleansed.astype(str).map(arreglar)
    L["precio"] = L.id.map(precio_ref)
    A = L[(L.room_type == "Entire home/apt") & (L.minimum_nights <= 30) & (L.number_of_reviews_ltm > 0) & L.precio.notna()].copy()
    A["noches"] = A.id.map(OCUPACION) * 365
    A = A.dropna(subset=["noches"])
    A["ingreso_mes"] = A.noches * A.precio / 12
    e = ESCENARIOS["propietario_solo"]
    fijo = e["suministros"] + e["comunidad"] + e["seguro"] + e["ibi_basura"]
    filas = []
    for m, g in A.groupby("municipio"):
        if m not in largo or len(g) < 30:
            continue
        bruto = g.ingreso_mes.median(); noches_mes = g.noches.median() / 12
        neto = bruto * (1 - e["comision_plataforma"] - e["mantenimiento_pct"]) - noches_mes / ESTANCIA_MEDIA * e["limpieza_estancia"] - fijo
        neto_largo = largo[m] - (e["comunidad"] + e["seguro"] + e["ibi_basura"])
        filas.append(dict(municipio=m, pisos_activos=len(g), precio_noche_mediano=round(g.precio.median()), noches_mes=round(noches_mes, 1),
                          ingreso_mes_mediana=round(bruto), ingreso_mes_p25=round(g.ingreso_mes.quantile(.25)), ingreso_mes_p75=round(g.ingreso_mes.quantile(.75)),
                          neto_propietario_solo=round(neto), neto_alquiler_largo=round(neto_largo), turistico_entre_largo=round(neto / neto_largo, 2),
                          bruto_anual=round(bruto * 12), largo_bruto_anual=round(largo[m] * 12)))
    return pd.DataFrame(filas).sort_values("ingreso_mes_mediana", ascending=False)


def p6_tamano_mercado(activos, distritos):
    """Pisos que rinden por debajo de sus iguales (mismo distrito y capacidad, grupos de 10 o más)."""
    A = activos.copy()
    A["cap"] = pd.cut(A.accommodates, [0, 2, 4, 6, 99], labels=["1-2", "3-4", "5-6", "7+"])
    A["occ"] = A.noches / 365
    g = A.groupby(["cod", "cap"], observed=True)
    A["n_grupo"] = g["precio"].transform("size")
    for c in ("precio", "occ", "ingreso_mes"):
        A[c + "_q25"] = g[c].transform(lambda x: x.quantile(.25)); A[c + "_q75"] = g[c].transform(lambda x: x.quantile(.75)); A[c + "_med"] = g[c].transform("median")
    B = A[A.n_grupo >= UMBRAL_PRIVACIDAD].copy()
    B["rinde_poco"] = B.ingreso_mes < B.ingreso_mes_q25
    B["establecido"] = B.number_of_reviews >= 10
    B["barato_lleno"] = (B.occ >= B.occ_q75) & (B.precio <= B.precio_q25)
    B["falta_mes"] = np.where(B.rinde_poco, B.ingreso_mes_med - B.ingreso_mes, 0)
    rp = B[B.rinde_poco]; est = B[B.rinde_poco & B.establecido]; bl = B[B.barato_lleno]
    resumen = dict(pisos_comparados=len(B), grupos=B.groupby(["cod", "cap"], observed=True).ngroups,
                   rinden_poco=len(rp), pct_rinden_poco_pocas_resenas=round(100 * (rp.number_of_reviews < 10).mean()),
                   pct_rinden_poco_270_dias_libres=round(100 * (rp.availability_365 >= 270).mean()),
                   establecidos_rinden_poco=len(est), falta_mes_establecidos=round(est.falta_mes.sum(), -2),
                   falta_mes_establecido_mediana=round(est.falta_mes.median()), falta_mes_total=round(B.falta_mes.sum(), -2),
                   baratos_llenos=len(bl), precio_baratos_llenos=round(bl.precio.median()), precio_iguales=round(bl.precio_med.median()),
                   subida_baratos_llenos_mes=round(((bl.precio_med - bl.precio) * bl.noches / 12).sum(), -2))
    por_distrito = B.groupby("cod").agg(pisos=("precio", "size"), rinden_poco=("rinde_poco", "sum"), falta_mes=("falta_mes", "sum")).reset_index()
    por_distrito["distrito"] = por_distrito.cod.map({c: distritos[c][0] for c in distritos})
    por_distrito["falta_mes"] = por_distrito.falta_mes.round(-2)
    return resumen, por_distrito.drop(columns="cod").sort_values("falta_mes", ascending=False)


# Donostia: Inside Airbnb no la divide en barrios. Se usan los 7 distritos censales del INE y se
# nombran con los barrios conocidos que caen dentro (coordenadas aproximadas de referencia).
BARRIOS_DONOSTIA = {
    "Parte Vieja": (-1.9858, 43.3238), "Centro": (-1.9810, 43.3180), "Gros": (-1.9750, 43.3240),
    "Antiguo": (-2.0100, 43.3110), "Amara": (-1.9800, 43.3060), "Egia": (-1.9700, 43.3180),
    "Altza": (-1.9270, 43.3170), "Intxaurrondo": (-1.9500, 43.3130), "Aiete": (-2.0000, 43.3050),
    "Ibaeta": (-2.0200, 43.3060), "Igeldo": (-2.0500, 43.3150), "Loiola": (-1.9600, 43.2970),
    "Ulia": (-1.9600, 43.3260),
}


def distritos_donostia():
    a_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True).transform
    por_distrito = {}
    for sr in shapefile.Reader(str(DATOS / "ine_2024" / "SECC_CE_20240101.shp")).iterShapeRecords():
        if sr.record["CUMUN"] == "20069":
            por_distrito.setdefault(int(sr.record["CDIS"]), []).append(transform(a_wgs84, shape(sr.shape.__geo_interface__)))
    res = {}
    for cd, g in sorted(por_distrito.items()):
        geom = unary_union(g).buffer(0)
        dentro = [b for b, (x, y) in BARRIOS_DONOSTIA.items() if geom.contains(Point(x, y))]
        res[cd] = (f"{cd:02d} · " + (", ".join(dentro) if dentro else "sin barrio de referencia"), geom)
    print(f"  Donostia: {sum(len(v) for v in por_distrito.values())} secciones censales en {len(res)} distritos")
    return res


def p7_donostia(precio_ref):
    """Donostia por distrito: oferta, ingreso estimado y tamaño del mercado, con el mismo método que Bilbao."""
    dist = distritos_donostia()
    L = pd.read_csv(LISTINGS, usecols=["id", "latitude", "longitude", "room_type", "neighbourhood_cleansed", "minimum_nights",
                                       "number_of_reviews_ltm", "number_of_reviews", "availability_365", "accommodates",
                                       "calculated_host_listings_count"], low_memory=False)
    L = L[L.neighbourhood_cleansed.astype(str).str.startswith("Donostia")].copy()
    cods = list(dist); arbol = STRtree([dist[c][1] for c in cods])
    L["cod"] = [(lambda h: cods[h[0]] if len(h) else None)(arbol.query(Point(x, y), predicate="within")) for x, y in zip(L.longitude, L.latitude)]
    print(f"  anuncios de Donostia: {len(L)}; fuera de los distritos: {L.cod.isna().sum()}")
    L["precio"] = L.id.map(precio_ref)
    A = L[(L.room_type == "Entire home/apt") & (L.minimum_nights <= 30) & (L.number_of_reviews_ltm > 0) & L.precio.notna() & L.cod.notna()].copy()
    A["noches"] = A.id.map(OCUPACION) * 365
    A = A.dropna(subset=["noches"])
    A["ingreso_mes"] = A.noches * A.precio / 12
    oferta = L[L.room_type == "Entire home/apt"].groupby("cod").size()
    filas = []
    for cod, g in A.groupby("cod"):
        fila = {"distrito": dist[cod][0], "pisos_completos": int(oferta.get(cod, 0)), "pisos_activos": len(g)}
        if len(g) >= UMBRAL_PRIVACIDAD:
            fila.update(precio_noche_mediano=round(g.precio.median()), ingreso_mes_p25=round(g.ingreso_mes.quantile(.25)),
                        ingreso_mes_mediana=round(g.ingreso_mes.median()), ingreso_mes_p75=round(g.ingreso_mes.quantile(.75)))
        filas.append(fila)
    t_ingreso = pd.DataFrame(filas).sort_values("ingreso_mes_mediana", ascending=False)
    resumen, por_distrito = p6_tamano_mercado(A, {c: (dist[c][0], None) for c in dist})
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"cod": c, "distrito": n}, "geometry": mapping(g.simplify(0.0001))} for c, (n, g) in dist.items()]}
    (SALIDA / "donostia_distritos.geojson").write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    return t_ingreso, resumen, por_distrito, A


def p8_segmentos(A_bilbao, A_donostia):
    """Particulares, pequeños y profesionales: cuánto rinden y cuántos quedan por debajo de sus iguales."""
    filas = []
    for ciudad, A in (("Bilbao", A_bilbao), ("Donostia", A_donostia)):
        A = A.copy()
        A["segmento"] = pd.cut(A.calculated_host_listings_count, [0, 1, 9, 10**6], labels=["particular (1)", "pequeño (2-9)", "profesional (10+)"])
        A["cap"] = pd.cut(A.accommodates, [0, 2, 4, 6, 99], labels=["1-2", "3-4", "5-6", "7+"])
        g = A.groupby(["cod", "cap"], observed=True)
        A["n_grupo"] = g["ingreso_mes"].transform("size"); A["q25"] = g["ingreso_mes"].transform(lambda x: x.quantile(.25))
        B = A[A.n_grupo >= UMBRAL_PRIVACIDAD]
        for s, h in B.groupby("segmento", observed=True):
            filas.append(dict(ciudad=ciudad, segmento=s, pisos=len(h), ingreso_mes_mediana=round(h.ingreso_mes.median()),
                              precio_noche_mediano=round(h.precio.median()), noches_mes=round(h.noches.median() / 12, 1),
                              pct_por_debajo_de_iguales=round(100 * (h.ingreso_mes < h.q25).mean())))
    return pd.DataFrame(filas)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    print("1. Descarga"); descargar()
    print("2. Distritos"); distritos = distritos_bilbao()
    print("3. Habitantes"); pob = habitantes_por_distrito()
    print("4. Anuncios"); L = anuncios_con_distrito(distritos)
    print("5. P1 oferta"); t1 = p1_oferta(L, distritos, pob); print(t1.to_string(index=False))
    print("6. P2 ingreso"); precio_ref = precio_referencia()
    global OCUPACION
    OCUPACION = ocupacion_calendario()
    t2, activos = p2_ingreso(L, distritos, precio_ref); print(t2.to_string(index=False))
    precio = activos.precio.median()
    print(f"7. P3 impuesto (precio por noche mediano de Bilbao: {precio:.0f} EUR)"); t3 = p3_impuesto(precio)
    print(t3[t3.personas == 2].to_string(index=False))
    print("8. P4 costes: neto mensual del piso mediano (antes de hipoteca e impuestos)")
    t4 = p4_costes(activos, distritos); print(t4.to_string(index=False))
    e = ESCENARIOS["propietario_solo"]
    fijo = e["suministros"] + e["comunidad"] + e["seguro"] + e["ibi_basura"]
    margen_noche = precio * (1 - e["comision_plataforma"] - e["mantenimiento_pct"]) - e["limpieza_estancia"] / ESTANCIA_MEDIA
    print(f"  propietario solo: cubre los gastos fijos ({fijo:.0f} EUR/mes) con {fijo / margen_noche:.1f} noches al mes "
          f"a {precio:.0f} EUR; igualar el alquiler largo neto exige {(t4.neto_alquiler_largo.iloc[0] + fijo) / margen_noche:.1f} noches")
    t4.to_csv(SALIDA / "p4_costes_distrito.csv", index=False)
    print("9. P5 Bilbao frente a Donostia, la costa y Vitoria-Gasteiz")
    t5 = p5_municipios(precio_ref); print(t5.to_string(index=False)); t5.to_csv(SALIDA / "p5_comparativa_municipios.csv", index=False)
    print("10. P6 tamaño del mercado (pisos por debajo de sus iguales)")
    r6, t6 = p6_tamano_mercado(activos, distritos); print(r6); print(t6.to_string(index=False))
    t6.to_csv(SALIDA / "p6_tamano_mercado_distrito.csv", index=False)
    print("11. P7 Donostia por distrito")
    t7, r7, t7b, A_don = p7_donostia(precio_ref); print(t7.to_string(index=False)); print(r7); print(t7b.to_string(index=False))
    t7.to_csv(SALIDA / "p7_donostia_ingreso_distrito.csv", index=False); t7b.to_csv(SALIDA / "p7_donostia_tamano_mercado.csv", index=False)
    (SALIDA / "p7_donostia_resumen.json").write_text(json.dumps({k: (int(v) if isinstance(v, (np.integer,)) else float(v) if isinstance(v, (np.floating,)) else v) for k, v in r7.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("12. P8 tipo de anfitrión")
    t8 = p8_segmentos(activos, A_don); print(t8.to_string(index=False)); t8.to_csv(SALIDA / "p8_tipo_anfitrion.csv", index=False)
    (SALIDA / "p6_tamano_mercado_resumen.json").write_text(json.dumps({k: (float(v) if isinstance(v, (np.floating,)) else int(v) if isinstance(v, (np.integer,)) else v) for k, v in r6.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
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
