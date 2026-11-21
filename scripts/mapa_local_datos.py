"""
Datos agregados para el mapa local de Bilbao y Donostia (docs/mapa-local/).

Dos capas, siempre agregadas (regla del proyecto: nada a nivel de anuncio o anfitrión):
  - Distritos (8 en Bilbao, 7 en Donostia; secciones censales del INE 2024 unidas por distrito).
  - Hexágonos de unos 400 m de lado a lado (radio 230 m, en UTM 30N / EPSG:25830). Un hexágono solo aparece si
    tiene 10 o más pisos completos; sus precios e ingresos, solo si tiene 10 o más pisos activos.
Cada piso de Inside Airbnb (junio de 2026) cae en su distrito y hexágono por sus coordenadas, que Inside Airbnb
desplaza hasta unos 150 m: por eso no se baja de 400 m.

Métricas, con el mismo método que scripts/bilbao_open_data.py:
  - pisos completos, pisos por 1.000 habitantes (solo Bilbao: padrón municipal por distrito), % de habitaciones
  - pisos activos (corta estancia, al menos una reseña en 12 meses, precio y calendario medido)
  - precio por noche mediano (mediana de marzo a junio de 2026 de cada piso)
  - ocupación mediana (noches no disponibles del calendario público, octubre de 2025 a septiembre de 2026)
  - ingreso bruto mensual p25 / mediana / p75 y cuántas veces el alquiler largo de la ciudad (EMAL 2025)
  - % de pisos de gestores profesionales (10 o más anuncios)

Salida: outputs/mapa_local/datos.json (se incrusta en docs/mapa-local/index.html)
Uso:  python scripts/mapa_local_datos.py
Requisitos: pandas, numpy, shapely, pyshp, pyproj
"""
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import Point, mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bilbao_open_data as b  # noqa: E402

RAIZ = b.RAIZ
SALIDA = RAIZ / "outputs" / "mapa_local"
MIN = b.UMBRAL_PRIVACIDAD
RADIO_HEX = 230  # metros: unos 400 m de lado a lado
ALQUILER_LARGO = {"Bilbao": 1011.1, "Donostia": 1131.9}  # EMAL, contratos nuevos 4T 2025 (€/mes)
A_UTM = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True).transform
A_WGS = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True).transform
# Recintos y referencias públicas (coordenadas aproximadas, solo para orientarse en el mapa)
RECINTOS = [
    ("Bilbao", "San Mamés", "Fútbol y grandes finales", 43.2641, -2.9494),
    ("Bilbao", "Bilbao Arena (Miribilla)", "Conciertos y baloncesto", 43.2534, -2.9256),
    ("Bilbao", "Palacio Euskalduna", "Congresos y ópera", 43.2669, -2.9450),
    ("Bilbao", "Kobetamendi", "BBK Live", 43.2600, -2.9745),
    ("Bilbao", "Museo Guggenheim", "Referencia turística", 43.2687, -2.9340),
    ("Bilbao", "Casco Viejo", "Referencia turística", 43.2580, -2.9235),
    ("Donostia", "Kursaal", "Conciertos, congresos y Zinemaldia", 43.3243, -1.9783),
    ("Donostia", "Reale Arena (Anoeta)", "Fútbol", 43.3014, -1.9736),
    ("Donostia", "Illunbe", "Conciertos y deporte", 43.2985, -1.9755),
    ("Donostia", "La Concha", "Referencia turística", 43.3180, -1.9860),
    ("Donostia", "Parte Vieja", "Referencia turística", 43.3236, -1.9849),
]
COLS = ["id", "latitude", "longitude", "room_type", "neighbourhood_cleansed", "minimum_nights", "number_of_reviews_ltm",
        "accommodates", "calculated_host_listings_count"]


# ---------------------------------------------------------------- hexágonos
def hex_de(x, y, s=RADIO_HEX):
    """Coordenadas axiales del hexágono (punta arriba) que contiene el punto UTM."""
    cx = (math.sqrt(3) / 3 * x - y / 3) / s
    cz = (2 / 3 * y) / s
    cy = -cx - cz
    rx, ry, rz = round(cx), round(cy), round(cz)
    dx, dy, dz = abs(rx - cx), abs(ry - cy), abs(rz - cz)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def poligono_hex(q, r, s=RADIO_HEX):
    cx, cy = s * math.sqrt(3) * (q + r / 2), s * 1.5 * r
    esquinas = [(cx + s * math.cos(math.radians(60 * i - 30)), cy + s * math.sin(math.radians(60 * i - 30))) for i in range(6)]
    return [[round(c, 5) for c in A_WGS(x, y)] for x, y in esquinas + esquinas[:1]]


def redondea(geom):
    return json.loads(json.dumps(mapping(geom)), parse_float=lambda v: round(float(v), 5))


# ---------------------------------------------------------------- métricas
def metricas(g_todos, g_activos, ciudad, habitantes=None):
    completos = g_todos[g_todos.room_type == "Entire home/apt"]
    m = {"pisos": int(len(completos)),
         "habitaciones_pct": round(100 * (g_todos.room_type != "Entire home/apt").mean()) if len(g_todos) else None}
    if habitantes:
        m["por_1000_hab"] = round(1000 * len(completos) / habitantes, 1)
        m["habitantes"] = int(habitantes)
    if len(completos) >= MIN:
        m["profesional_pct"] = round(100 * (completos.calculated_host_listings_count >= 10).mean())
    m["activos"] = int(len(g_activos))
    if len(g_activos) >= MIN:
        a = g_activos
        m.update(precio=round(a.precio.median()), ocupacion=round(100 * a.occ.median()),
                 ingreso_p25=round(a.ingreso.quantile(.25)), ingreso=round(a.ingreso.median()), ingreso_p75=round(a.ingreso.quantile(.75)),
                 veces_largo=round(a.ingreso.median() / ALQUILER_LARGO[ciudad], 1))
    return m


def ciudad(nombre, distritos, L, precio_ref, ocup, pob=None):
    sel = L.neighbourhood_cleansed.astype(str)
    C = L[(sel == "Bilbao") if nombre == "Bilbao" else sel.str.startswith("Donostia")].copy()
    cods = list(distritos)
    arbol = STRtree([distritos[c][1] for c in cods])
    C["cod"] = [(lambda h: cods[h[0]] if len(h) else None)(arbol.query(Point(x, y), predicate="within"))
                for x, y in zip(C.longitude, C.latitude)]
    C = C.dropna(subset=["cod"])
    xy = [A_UTM(x, y) for x, y in zip(C.longitude, C.latitude)]
    C["hex"] = [hex_de(x, y) for x, y in xy]
    C["precio"] = C.id.map(precio_ref)
    C["occ"] = C.id.map(ocup)
    A = C[(C.room_type == "Entire home/apt") & (C.minimum_nights <= 30) & (C.number_of_reviews_ltm > 0)].dropna(subset=["precio", "occ"]).copy()
    A["ingreso"] = A.occ * 365 * A.precio / 12
    print(f"{nombre}: {len(C)} anuncios en distritos, {int((C.room_type == 'Entire home/apt').sum())} pisos completos, {len(A)} activos")

    feats = []
    for c, (dn, geom) in distritos.items():
        m = metricas(C[C.cod == c], A[A.cod == c], nombre, (pob or {}).get(c))
        nombre_d = dn if "·" in dn else dn.title()
        # Rótulo donde están los pisos (media de 10 o más), no en el centro del polígono: en Donostia algunos
        # distritos tienen grandes zonas rurales y el centro geométrico cae en el monte.
        pc = C[(C.cod == c) & (C.room_type == "Entire home/apt")]
        rp = (pc.latitude.mean(), pc.longitude.mean()) if len(pc) >= MIN else (geom.representative_point().y, geom.representative_point().x)
        m["etiqueta"] = [round(rp[0], 4), round(rp[1], 4)]
        feats.append({"type": "Feature", "properties": {"nombre": nombre_d, **m}, "geometry": redondea(geom.simplify(0.00015))})
    hexes = []
    nombres = {c: (dn if "·" in dn else dn.title()) for c, (dn, _) in distritos.items()}
    for h, g in C.groupby("hex"):
        if (g.room_type == "Entire home/apt").sum() < MIN:
            continue
        m = metricas(g, A[A.hex == h], nombre)
        anillo = poligono_hex(*h)
        cx, cy = np.mean([p[0] for p in anillo[:-1]]), np.mean([p[1] for p in anillo[:-1]])
        dentro = arbol.query(Point(cx, cy), predicate="within")
        m = {"distrito": nombres[cods[dentro[0]]] if len(dentro) else nombres[g.cod.mode()[0]], **m}
        hexes.append({"type": "Feature", "properties": m, "geometry": {"type": "Polygon", "coordinates": [anillo]}})
    resumen = metricas(C, A, nombre, sum(pob.values()) if pob else None)
    print(f"  {len(hexes)} hexágonos publicados (de {C.hex.nunique()} con algún anuncio); "
          f"cubren {sum(f['properties']['pisos'] for f in hexes)} de {resumen['pisos']} pisos completos")
    centro = A_WGS(*np.mean(xy, axis=0))
    return {"centro": [round(centro[1], 4), round(centro[0], 4)], "resumen": resumen, "alquiler_largo": ALQUILER_LARGO[nombre],
            "distritos": {"type": "FeatureCollection", "features": feats}, "hexagonos": {"type": "FeatureCollection", "features": hexes},
            "recintos": [dict(nombre=n, uso=u, lat=la, lon=lo) for c, n, u, la, lo in RECINTOS if c == nombre]}


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    precio_ref = b.precio_referencia()
    ocup = b.ocupacion_calendario()
    L = pd.read_csv(b.LISTINGS, usecols=COLS, low_memory=False)
    datos = {
        "Bilbao": ciudad("Bilbao", b.distritos_bilbao(), L, precio_ref, ocup, b.habitantes_por_distrito()),
        "Donostia": ciudad("Donostia", b.distritos_donostia(), L, precio_ref, ocup),
        "meta": dict(generado=date.today().isoformat(), anuncios="Inside Airbnb, Euskadi, 30-jun-2026",
                     precio="mediana de marzo a junio de 2026 de cada piso",
                     ocupacion="calendario público, octubre de 2025 a septiembre de 2026 (noches no disponibles)",
                     alquiler_largo="EMAL 2025, Gobierno Vasco (contratos nuevos)", minimo=MIN, hex_m=round(RADIO_HEX * math.sqrt(3)),
                     fuentes=["Inside Airbnb (CC BY 4.0)", "INE, secciones censales 2024", "Bilbao Open Data, padrón 2022",
                              "EMAL, Gobierno Vasco", "mapa base: Esri y colaboradores de OpenStreetMap"]),
    }
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    f = SALIDA / "datos.json"
    f.write_text(texto, encoding="utf-8")
    web = RAIZ / "docs" / "mapa-local" / "datos.js"  # la página lo carga con <script src>: funciona también sin servidor
    web.parent.mkdir(parents=True, exist_ok=True)
    web.write_text("window.DATOS = " + texto + ";\n", encoding="utf-8")
    print(f"Listo: {f} y {web} ({f.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
