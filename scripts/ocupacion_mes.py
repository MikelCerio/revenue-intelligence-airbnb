"""
Ocupación aproximada por mes de Bilbao, Donostia y la costa (Gipuzkoa y Bizkaia), con datos públicos de Inside Airbnb.

Mismo método que scripts/eventos_efecto.py: una noche cuenta como ocupada si no está disponible en el calendario, y
cada noche se lee en la captura más cercana por delante (antelación de 0 a 29 días). Se quitan los pisos bloqueados
todo el año (ninguna noche libre en los 365 días de la captura). Las noches que el dueño bloquea para uso propio
cuentan como ocupadas, así que en zonas de segunda residencia (costa en agosto) la cifra puede salir algo alta.
Comparado con la encuesta de apartamentos turísticos del INE (scripts/validacion_ine.py), el calendario queda por
debajo casi todo el año, pero en la costa de Gipuzkoa se pasa en julio y agosto: ahí se resta AJUSTE_VERANO.

Salida: outputs/herramienta/ocupacion_mes.json  ->  {grupo: {"AAAA-MM": ocupación en %}}
Uso:    python scripts/ocupacion_mes.py
"""
import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
BRONZE = RAIZ / "data" / "bronze" / "euskadi"
SALIDA = RAIZ / "outputs" / "herramienta" / "ocupacion_mes.json"
SALIDA_DIA = RAIZ / "outputs" / "herramienta" / "ocupacion_dia.json"   # {grupo: {"AAAA-MM-DD": %}} para el calendario
MAX_ANTELACION = 29
MAX_ANTELACION_DIA = 45      # solo para rellenar los días que ninguna captura ve a menos de 30 días
ANTELACION_REFERENCIA = 15
# Puntos que se restan por bloqueos del dueño en verano. Costa Gipuzkoa, calendario menos INE: ago-2025 +9,7,
# jul-2026 +6,9, ago-2026 +15,8 (media +10,8). Donostia también se pasa (+8 a +10), pero menos que su margen
# por debajo el resto del año, así que se deja como está.
AJUSTE_VERANO = {"Costa Gipuzkoa": {7: 10, 8: 10}}


def ajustar(grupo, mes, valor):
    """Resta el ajuste de verano a una ocupación en % (mes = número de mes)."""
    return max(0, valor - AJUSTE_VERANO.get(grupo, {}).get(mes, 0))
COSTA = {
    "Costa Gipuzkoa": ["Hondarribia", "Pasaia", "Orio", "Zarautz", "Aia", "Getaria", "Zumaia", "Deba", "Mutriku"],
    "Costa Bizkaia": ["Ondarroa", "Lekeitio", "Ea", "Elantxobe", "Ibarrangelu", "Mundaka", "Sukarrieta", "Busturia", "Bermeo",
                      "Bakio", "Lemoiz", "Gorliz", "Plentzia", "Barrika", "Sopelana", "Getxo", "Zierbena", "Muskiz", "Santurtzi"],
}


def arreglar(s):
    """Algunos nombres de municipio llegan con la codificación rota (Ã¡ en vez de á)."""
    try:
        return s.encode("cp1252").decode("utf-8")
    except Exception:
        return s


def grupo_de(municipio):
    if municipio.startswith("Donostia"):
        return "Donostia"
    if municipio == "Bilbao":
        return "Bilbao"
    return next((g for g, ms in COSTA.items() if municipio in ms), None)


def diario(TODO):
    """Ocupación por día, corregida por antelación, para el calendario de colores.

    Cada captura ve las noches cercanas más llenas que las de 4 semanas después (han tenido más tiempo para venderse).
    Pintado tal cual, cada mes parecería más lleno al principio que al final. Se mide ese efecto por grupo (media por
    antelación de todas las capturas, que promedia la temporada) y se lleva cada noche a la antelación de referencia
    (15 días). Los días que ninguna captura ve a menos de 30 días se rellenan con la siguiente (hasta 45 días).
    """
    T = TODO.copy()
    curva = T[T.antelacion <= MAX_ANTELACION_DIA].groupby(["grupo", "antelacion"]).ocupada.mean()
    ref = {g: curva[g].loc[ANTELACION_REFERENCIA] for g in T.grupo.unique()}
    T["ajustada"] = T.ocupada - T.apply(lambda r: curva[(r.grupo, r.antelacion)] - ref[r.grupo], axis=1)
    T = T.sort_values("antelacion").drop_duplicates(["grupo", "date"])
    salida = {g: {r.date.strftime("%Y-%m-%d"): ajustar(g, r.date.month, int(round(100 * min(1, max(0, r.ajustada)))))
                  for r in G.sort_values("date").itertuples()}
              for g, G in T.groupby("grupo")}
    SALIDA_DIA.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for g in sorted(ref):
        c = curva[g]
        print(f"{g}: antelación 0 -> {100 * c.loc[0]:.0f} %, 15 -> {100 * c.loc[15]:.0f} %, 29 -> {100 * c.loc[29]:.0f} %; días: {len(salida[g])}")


def main():
    trozos = []
    for d in sorted(p for p in BRONZE.iterdir() if (p / "calendar.csv.gz").exists()):
        L = pd.read_csv(d / "listings.csv.gz", usecols=["id", "neighbourhood_cleansed", "room_type"], low_memory=False)
        L = L[L.room_type == "Entire home/apt"].copy()
        L["grupo"] = L.neighbourhood_cleansed.astype(str).map(arreglar).map(grupo_de)
        L = L.dropna(subset=["grupo"])
        C = pd.read_csv(d / "calendar.csv.gz", usecols=["listing_id", "date", "available"])
        C = C[C.listing_id.isin(L.id)].copy()
        C["ocupada"] = C.available.astype(str).str.lower().isin(["f", "false"]).astype(int)
        vivos = C.groupby("listing_id").ocupada.mean()
        C = C[C.listing_id.isin(vivos[vivos < 1].index)]
        C["date"] = pd.to_datetime(C.date)
        t0 = C.date.min()
        C = C[(C.date - t0).dt.days <= MAX_ANTELACION_DIA].merge(L[["id", "grupo"]], left_on="listing_id", right_on="id")
        n = C.groupby(["grupo", "date"]).ocupada.mean().reset_index()
        n["antelacion"] = (n.date - t0).dt.days
        trozos.append(n)
    TODO = pd.concat(trozos)
    diario(TODO)
    N = TODO[TODO.antelacion <= MAX_ANTELACION].sort_values("antelacion").drop_duplicates(["grupo", "date"])
    N["mes"] = N.date.dt.strftime("%Y-%m")
    M = N.groupby(["grupo", "mes"]).agg(occ=("ocupada", "mean"), noches=("ocupada", "size")).reset_index()
    M = M[M.noches >= 20]  # meses con pocas noches medidas (bordes de la serie) fuera
    salida = {g: {r.mes: ajustar(g, int(r.mes[5:]), round(100 * r.occ)) for r in G.itertuples()} for g, G in M.groupby("grupo")}
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    for g, meses in salida.items():
        print(g, " ".join(f"{m[2:]}:{v}" for m, v in meses.items()))


if __name__ == "__main__":
    main()
