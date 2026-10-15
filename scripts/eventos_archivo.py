"""
Archivo histórico de eventos de Euskadi (Kulturklik, Open Data Euskadi).

Por qué existe: la API solo conserva unos 5 meses hacia atrás; lo anterior se borra. Para poder cruzar
eventos con precios y demanda de meses pasados hay que guardarlos nosotros, semana a semana.

Qué hace en cada ejecución:
  1. Descarga los eventos de un rango de meses (por defecto: el mes anterior y los 12 siguientes).
  2. Normaliza (fechas en texto AAAA-MM-DD, precio mínimo y máximo, ciudad clave) y marca las fechas imposibles.
  3. Los une al archivo eventos/eventos_euskadi.csv (una fila por id de evento):
       - evento nuevo      -> primera_captura = hoy
       - evento ya visto   -> ultima_captura = hoy; si cambió nombre, fechas, hora, lugar o precio,
                              el cambio queda en eventos/eventos_cambios.csv
  4. Apunta la ejecución en eventos/capturas.csv.
Un evento con ultima_captura anterior a la última captura y fecha futura = desapareció (cancelado o retirado).

Solo datos públicos de eventos. No guarda descripciones, imágenes ni enlaces de compra.

Uso:  python scripts/eventos_archivo.py                     (mes anterior y 12 siguientes)
      python scripts/eventos_archivo.py --desde 2025-07     (rescate de lo que aún conserva la API)
Requisitos: pandas
"""
import argparse
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "eventos"
URL = "https://api.euskadi.eus/culture/events/v1.0/events/byMonth/{y}/{m}?_elements=100&_page={p}"

CAMPOS = ["id", "typeEs", "nameEs", "startDate", "endDate", "publicationDate", "openingHoursEs", "sourceNameEs",
          "sourceUrlEs", "municipalityEs", "municipalityNoraCode", "provinceNoraCode", "establishmentEs", "priceEs"]
VIGILADOS = ["nameEs", "fecha_ini", "fecha_fin", "openingHoursEs", "establishmentEs", "priceEs"]
CIUDADES = {"Bilbao": "Bilbao", "Donostia": "Donostia", "Vitoria": "Vitoria-Gasteiz"}


def pedir(url, intentos=3):
    for i in range(intentos):
        try:
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
                return json.load(r)
        except Exception as e:  # red caída o servidor ocupado: se reintenta con espera creciente
            if i == intentos - 1:
                raise
            print(f"    reintento ({e})")
            time.sleep(5 * (i + 1))


def meses(desde, hasta):
    y, m = desde
    while (y, m) <= hasta:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def descargar(desde, hasta):
    items = []
    for y, m in meses(desde, hasta):
        p, antes = 1, len(items)
        while True:
            d = pedir(URL.format(y=y, m=m, p=p))
            items += [{k: i.get(k) for k in CAMPOS} for i in d["items"]]
            if p >= d["totalPages"]:
                break
            p += 1
            time.sleep(0.15)
        print(f"  {y}-{m:02d}: {len(items) - antes} eventos")
    return pd.DataFrame(items).drop_duplicates("id")


def normalizar(E, hoy):
    E = E.copy()
    E["id"] = E["id"].astype(str)
    E["fecha_ini"] = E.startDate.astype(str).str[:10]
    E["fecha_fin"] = E.endDate.astype(str).str[:10]
    E["fecha_publicacion"] = E.publicationDate.astype(str).str[:10]
    ini = pd.to_datetime(E.fecha_ini, errors="coerce")
    fin = pd.to_datetime(E.fecha_fin, errors="coerce")
    # Fechas imposibles (años 0226, 2014…): se conservan marcadas, nunca se borran en silencio.
    E["fecha_valida"] = ini.notna() & fin.notna() & (fin >= ini) & ini.dt.year.between(hoy.year - 2, hoy.year + 3)
    nums = E.priceEs.fillna("").astype(str).apply(lambda s: [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", s)])
    E["precio_min"] = [min(n) if n else (0.0 if "gratis" in str(s).lower() else None) for n, s in zip(nums, E.priceEs)]
    E["precio_max"] = [max(n) if n else (0.0 if "gratis" in str(s).lower() else None) for n, s in zip(nums, E.priceEs)]
    # El origen entrega acentos rotos: la ciudad se reconoce por el principio del nombre.
    E["ciudad_clave"] = E.municipalityEs.fillna("").apply(
        lambda s: next((v for k, v in CIUDADES.items() if s.startswith(k)), "Otro"))
    return E.drop(columns=["startDate", "endDate", "publicationDate"])


def unir(nuevos, hoy):
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / "eventos_euskadi.csv"
    hoy_s = hoy.isoformat()
    cambios = []
    if ruta.exists():
        M = pd.read_csv(ruta, dtype={"id": str}, keep_default_na=False, na_values=[""]).set_index("id")
    else:
        M = pd.DataFrame()
    N = nuevos.set_index("id")
    comunes = N.index.intersection(M.index) if len(M) else []
    for i in comunes:
        for c in VIGILADOS:
            a, b = M.at[i, c], N.at[i, c]
            if not (pd.isna(a) and pd.isna(b)) and str(a) != str(b):
                cambios.append(dict(id=i, fecha_captura=hoy_s, campo=c, antes=a, despues=b))
    N["ultima_captura"] = hoy_s
    if len(M):
        N["primera_captura"] = [M.at[i, "primera_captura"] if i in comunes else hoy_s for i in N.index]
        N["n_capturas"] = [int(M.at[i, "n_capturas"]) + 1 if i in comunes else 1 for i in N.index]
        resto = M.loc[M.index.difference(N.index)]  # no vistos hoy: se conservan tal cual
        Z = pd.concat([resto, N.reindex(columns=M.columns)])
    else:
        N["primera_captura"], N["n_capturas"] = hoy_s, 1
        Z = N
    Z = Z.sort_values(["fecha_ini", "ciudad_clave"])
    Z.reset_index().to_csv(ruta, index=False, encoding="utf-8")
    if cambios:
        C = pd.DataFrame(cambios)
        f = SALIDA / "eventos_cambios.csv"
        C.to_csv(f, mode="a", header=not f.exists(), index=False, encoding="utf-8")
    nuevos_ids = len(N.index.difference(M.index)) if len(M) else len(N)
    return len(Z), nuevos_ids, len(cambios)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", help="AAAA-MM; por defecto, el mes anterior")
    ap.add_argument("--meses-adelante", type=int, default=12)
    a = ap.parse_args()
    hoy = date.today()
    d = tuple(int(x) for x in a.desde.split("-")) if a.desde else ((hoy.year, hoy.month - 1) if hoy.month > 1 else (hoy.year - 1, 12))
    h_m = hoy.month - 1 + a.meses_adelante
    hasta = (hoy.year + h_m // 12, h_m % 12 + 1)
    print(f"Captura del {hoy}: {d[0]}-{d[1]:02d} a {hasta[0]}-{hasta[1]:02d}")
    E = normalizar(descargar(d, hasta), hoy)
    print(f"  descargados: {len(E)}; con fecha imposible: {(~E.fecha_valida).sum()}")
    total, nuevos, cambios = unir(E, hoy)
    fila = pd.DataFrame([dict(fecha=hoy.isoformat(), desde=f"{d[0]}-{d[1]:02d}", hasta=f"{hasta[0]}-{hasta[1]:02d}",
                              descargados=len(E), nuevos=nuevos, cambios=cambios, total_archivo=total)])
    f = SALIDA / "capturas.csv"
    fila.to_csv(f, mode="a", header=not f.exists(), index=False)
    print(f"Listo. Archivo: {total} eventos ({nuevos} nuevos, {cambios} cambios detectados) en {SALIDA}")


if __name__ == "__main__":
    main()
