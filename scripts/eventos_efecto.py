"""
Efecto de los grandes eventos en la ocupación de Bilbao, Donostia y Vitoria-Gasteiz.

Qué mide: para cada noche de un evento, la ocupación aproximada de los pisos completos (noches NO disponibles
en el calendario de Inside Airbnb) frente a noches de control. Una noche de control es:
  - de la misma ciudad y del mismo día de la semana,
  - dentro de 21 días de la noche del evento,
  - sin evento grande, sin partido en casa y sin festivo (ni la víspera),
  - con una antelación parecida (±7 días) entre la captura y la noche, porque cuanto más cerca de la noche se
    toma la foto, más reservado aparece el calendario.
Cada noche se lee en la captura más cercana por delante (antelación de 0 a 29 días).

Límites (importantes):
  - "No disponible" mezcla reservas y bloqueos del anfitrión: es una aproximación, no ocupación real.
  - El calendario no trae precio por noche; solo se analiza demanda.
  - Los eventos pequeños (conciertos, teatro) no están en el control: pueden contaminar algunas noches.
  - Se calcula también el ruido de noches normales (placebo) para saber qué diferencias son creíbles.

Salida (solo agregados): outputs/eventos/efecto_eventos.csv y outputs/eventos/placebo.csv
Panel estable (--panel estable): solo se cuentan los pisos completos que aparecen en TODAS las capturas, para que
la composición no cambie de una noche a otra (altas y bajas de anuncios meten ruido). Vitoria-Gasteiz se descarta
en ese modo por tener muy pocos pisos estables.

Uso:  python scripts/eventos_efecto.py                    (todos los pisos de cada captura)
      python scripts/eventos_efecto.py --panel estable    (panel estable)
Requisitos: pandas, numpy
"""
from pathlib import Path

import argparse

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
BRONZE = RAIZ / "data" / "bronze" / "euskadi"
EVENTOS = RAIZ / "eventos"
SALIDA = RAIZ / "outputs" / "eventos"
MAX_ANTELACION = 29
VENTANA_CONTROL = 21
TOLERANCIA_ANTELACION = 7
MIN_CONTROLES = 2
CIUDADES = {"Bilbao": "Bilbao", "Donostia": "Donostia", "Vitoria": "Vitoria-Gasteiz"}
FESTIVOS = pd.to_datetime("""2025-07-25 2025-08-15 2025-10-12 2025-11-01 2025-12-06 2025-12-08 2025-12-25 2026-01-01
    2026-01-06 2026-03-19 2026-04-02 2026-04-03 2026-04-06 2026-05-01 2026-07-25 2026-08-15 2026-10-12""".split())


def ciudad_de(barrio):
    b = str(barrio)
    return next((v for k, v in CIUDADES.items() if b.startswith(k)), None)


def capturas():
    return sorted(p for p in BRONZE.iterdir() if (p / "calendar.csv.gz").exists() and (p / "listings.csv.gz").exists())


def ids_estables():
    """Ids de pisos completos presentes en todas las capturas (Bilbao y Donostia)."""
    conjuntos = []
    for d in capturas():
        L = pd.read_csv(d / "listings.csv.gz", usecols=["id", "neighbourhood_cleansed", "room_type"], low_memory=False)
        L = L[(L.room_type == "Entire home/apt") & L.neighbourhood_cleansed.map(ciudad_de).isin(["Bilbao", "Donostia"])]
        conjuntos.append(set(L.id))
    estables = set.intersection(*conjuntos)
    print(f"panel estable: {len(estables)} pisos presentes en las {len(conjuntos)} capturas")
    return estables


def noches_por_ciudad(estables=None):
    """Ocupación aproximada por ciudad y noche, con la antelación de la captura que la mide."""
    trozos = []
    for d in capturas():
        L = pd.read_csv(d / "listings.csv.gz", usecols=["id", "neighbourhood_cleansed", "room_type"], low_memory=False)
        L = L[L.room_type == "Entire home/apt"].assign(ciudad=lambda x: x.neighbourhood_cleansed.map(ciudad_de)).dropna(subset=["ciudad"])
        if estables is not None:
            L = L[L.id.isin(estables)]
        C = pd.read_csv(d / "calendar.csv.gz", usecols=["listing_id", "date", "available"])
        C = C[C.listing_id.isin(L.id)].merge(L[["id", "ciudad"]], left_on="listing_id", right_on="id")
        C["date"] = pd.to_datetime(C.date)
        t0 = C.date.min()
        C["ocupada"] = C.available.astype(str).str.lower().isin(["f", "false"]).astype(int)
        g = C.groupby(["ciudad", "date"]).ocupada.agg(occ="mean", pisos="size").reset_index()
        g["antelacion"] = (g.date - t0).dt.days
        g["captura"] = d.name
        trozos.append(g[g.antelacion <= MAX_ANTELACION])
    N = pd.concat(trozos).sort_values("antelacion").drop_duplicates(["ciudad", "date"]).sort_values(["ciudad", "date"])
    N["dia"] = N.date.dt.dayofweek
    return N.reset_index(drop=True)


def noches_de_eventos():
    E = pd.read_csv(EVENTOS / "grandes_eventos.csv")
    filas = []
    for r in E.itertuples():
        if r.ciudad not in CIUDADES.values():
            continue
        for d in pd.date_range(r.fecha_ini, r.fecha_fin):
            filas.append(dict(evento=r.nombre, ciudad=r.ciudad, tipo=r.tipo, date=d))
    F = pd.read_csv(EVENTOS / "partidos_casa_laliga.csv", parse_dates=["fecha"])
    for r in F.itertuples():
        filas.append(dict(evento=f"{r.equipo_local} en casa (LaLiga)", ciudad=r.ciudad, tipo="futbol", date=r.fecha))
    return pd.DataFrame(filas)


def controles(N, excluidas, ciudad, fecha, dia, antelacion):
    """Ocupación media de las noches de control de una noche dada, y cuántas son."""
    M = N[(N.ciudad == ciudad) & (N.dia == dia) & ((N.date - fecha).abs() <= pd.Timedelta(days=VENTANA_CONTROL))
          & (N.date != fecha) & ((N.antelacion - antelacion).abs() <= TOLERANCIA_ANTELACION)]
    M = M[[(c, d) not in excluidas for c, d in zip(M.ciudad, M.date)]]
    return (M.occ.mean(), len(M)) if len(M) >= MIN_CONTROLES else (np.nan, len(M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", choices=["todos", "estable"], default="todos")
    sufijo = "_panel_estable" if ap.parse_args().panel == "estable" else ""
    SALIDA.mkdir(parents=True, exist_ok=True)
    N = noches_por_ciudad(ids_estables() if sufijo else None)
    print(f"noches con ocupación medida: {len(N)} ({N.date.min().date()} a {N.date.max().date()})")
    EV = noches_de_eventos()
    if sufijo:
        EV = EV[EV.ciudad != "Vitoria-Gasteiz"]
    excluidas = set(zip(EV.ciudad, EV.date))
    for ciudad in CIUDADES.values():
        for f in FESTIVOS:
            excluidas |= {(ciudad, f), (ciudad, f - pd.Timedelta(days=1))}
    idx = N.set_index(["ciudad", "date"])

    filas = []
    for r in EV.itertuples():
        if (r.ciudad, r.date) not in idx.index:
            continue
        n = idx.loc[(r.ciudad, r.date)]
        ctrl, k = controles(N, excluidas, r.ciudad, r.date, r.date.dayofweek, n.antelacion)
        if np.isnan(ctrl):
            continue
        filas.append(dict(evento=r.evento, ciudad=r.ciudad, tipo=r.tipo, date=r.date, occ=n.occ, ctrl=ctrl, antelacion=n.antelacion, pisos=n.pisos))
    R = pd.DataFrame(filas)
    R["dif_pp"] = (R.occ - R.ctrl) * 100
    cobertura = EV.groupby("evento").size().rename("noches_totales")

    def resumen(g):
        return pd.Series(dict(ciudad=g.ciudad.iloc[0], tipo=g.tipo.iloc[0], noches=len(g), ocupacion_evento=round(100 * g.occ.mean(), 1),
                              ocupacion_control=round(100 * g.ctrl.mean(), 1), dif_pp=round(g.dif_pp.mean(), 1),
                              antelacion_dias=round(g.antelacion.mean())))
    T = R.groupby("evento")[["ciudad", "tipo", "occ", "ctrl", "dif_pp", "antelacion"]].apply(resumen).join(cobertura).reset_index()
    T["cobertura"] = (T.noches / T.noches_totales).round(2)
    grandes = T[T.tipo != "futbol"].sort_values("dif_pp", ascending=False)
    print("\nGRANDES EVENTOS (diferencia de ocupación frente a noches de control, en puntos)")
    print(grandes.drop(columns="tipo").to_string(index=False))

    # Fútbol: se agrupa por ciudad porque cada partido es una sola noche (muy ruidosa por separado)
    Rf = R[R.tipo == "futbol"]
    ff = Rf.groupby("ciudad").agg(partidos=("date", "size"), ocupacion_evento=("occ", "mean"), ocupacion_control=("ctrl", "mean"), dif_pp=("dif_pp", "mean"),
                                  dif_mediana=("dif_pp", "median"))
    ff["ocupacion_evento"] *= 100; ff["ocupacion_control"] *= 100
    print("\nPARTIDOS EN CASA (todos los partidos de liga juntos)"); print(ff.round(1).to_string())
    Rf2 = Rf.assign(finde=Rf.date.dt.dayofweek.isin([4, 5, 6]))
    print("\nPartidos en casa: fin de semana frente a entre semana (diferencia media, pp)")
    print(Rf2.groupby(["ciudad", "finde"]).dif_pp.agg(["size", "mean"]).round(1).to_string())

    # Placebo: la misma diferencia para noches SIN evento; da la medida del ruido
    ruido = []
    for (c, d), n in idx.iterrows():
        if (c, d) in excluidas:
            continue
        ctrl, k = controles(N, excluidas, c, d, d.dayofweek, n.antelacion)
        if not np.isnan(ctrl):
            ruido.append(dict(ciudad=c, date=d, dif_pp=(n.occ - ctrl) * 100))
    P = pd.DataFrame(ruido)
    pl = P.groupby("ciudad").dif_pp.agg(noches="size", media="mean", desviacion="std", p5=lambda x: x.quantile(.05), p95=lambda x: x.quantile(.95)).round(1)
    print("\nRUIDO (noches sin evento: diferencia frente a su control, en puntos)"); print(pl.to_string())

    T.to_csv(SALIDA / f"efecto_eventos{sufijo}.csv", index=False, encoding="utf-8")
    pl.reset_index().to_csv(SALIDA / f"placebo{sufijo}.csv", index=False, encoding="utf-8")
    print(f"\nListo. Salidas agregadas en {SALIDA}")


if __name__ == "__main__":
    main()
