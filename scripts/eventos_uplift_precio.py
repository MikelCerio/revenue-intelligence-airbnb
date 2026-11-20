"""
Uplift de los grandes eventos en la ocupación y el precio hotelero de Bilbao, Donostia y Vitoria-Gasteiz (Eustat).

Eustat NO publica el precio por día: el ADR (tarifa media diaria por habitación) solo es mensual. Por eso el uplift
de precio se mide en tres partes, todas con datos públicos de la Encuesta de establecimientos turísticos receptores:

  A. Ocupación diaria de hoteles (etrm_20h, 2022-01 en adelante) en las noches de evento frente a noches de control:
     misma ciudad y día de la semana, a menos de 21 días, sin evento ni festivo (ni su víspera) y fuera de Navidad.
     Ruido de referencia (placebo): la misma comparación para noches normales.
  B. Cuánto sube el ADR cuando sube la ocupación (etrm_14h + etrm_03h, mensual desde 2015, sin 2020-2021):
     diferencias interanuales (mismo mes del año anterior), que quitan la temporada; la constante recoge la inflación.
     B2: la misma relación entre meses de un mismo año (la curva de temporada que fija los precios con antelación).
  C. Uplift directo del ADR en eventos puntuales que caen en un solo mes (finales de la UEFA en San Mamés, salida del
     Tour de Francia): diferencias en diferencias frente a las otras dos capitales y al mismo mes de otros años.
     Ruido de referencia: el mismo cálculo para todos los meses sin evento puntual.

Lectura: A × B da el uplift de precio que corresponde a la subida de ocupación de un evento recurrente (que el
mercado ya espera); C mide lo que pasó de verdad con el precio en eventos excepcionales.

Límites:
  - Son hoteles, no pisos turísticos. El patrón se parece, la intensidad no tiene por qué.
  - El ADR mensual diluye un evento de 1-3 noches en 30: el uplift de C es un mínimo, no el de la noche del evento.
  - Las fechas de 2022-2024 de las fiestas siguen reglas fijas (Aste Nagusia: sábado posterior al 15 de agosto;
    Semana Grande: sábado anterior al 15 a sábado siguiente). Jazzaldia 2022-2024 queda fuera: fechas sin confirmar.
  - Los partidos de liga solo se excluyen de los controles en 2025-2026 (no hay calendario anterior en el proyecto).

Salidas (solo agregados públicos): outputs/eventos/uplift_hotel_ocupacion.csv, uplift_hotel_placebo.csv,
uplift_adr_elasticidad.csv, uplift_adr_puntuales.csv
Uso:  python scripts/eventos_uplift_precio.py
Requisitos: pandas, numpy
"""
import csv
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
EUSTAT = sorted((RAIZ / "datos" / "raw" / "eustat_132680").glob("20*"))[-1]
SALIDA = RAIZ / "outputs" / "eventos"
CIUDADES = {"-Bilbao": "Bilbao", "-Donostia / San Sebastián": "Donostia", "-Vitoria-Gasteiz": "Vitoria-Gasteiz"}
VENTANA = 21
ANIOS_COVID = {2020, 2021}


# ---------------------------------------------------------------- eventos
def d(s):
    return date.fromisoformat(s)


def sabado_antes(dia):
    return dia - timedelta(days=(dia.weekday() - 5) % 7 or 7)


def eventos_historicos():
    """Ediciones 2022-2024 con fecha segura (regla fija o fuente comprobada)."""
    ev = []
    for y in (2022, 2023, 2024):
        quince = date(y, 8, 15)
        # (la Tamborrada y la Behobia van en sus propios bucles más abajo)
        an = quince + timedelta(days=(5 - quince.weekday()) % 7 or 7)  # sábado posterior al 15 de agosto
        ev.append((f"Aste Nagusia {y}", "Bilbao", "fiestas", an, an + timedelta(days=8)))
        sg = sabado_antes(quince)
        ev.append((f"Semana Grande Donostia {y}", "Donostia", "fiestas", sg, sg + timedelta(days=7)))
        ev.append((f"Fiestas de La Blanca {y}", "Vitoria-Gasteiz", "fiestas", date(y, 8, 4), date(y, 8, 9)))
    for y in (2022, 2023, 2024, 2025):
        ev.append((f"Tamborrada de San Sebastian {y}", "Donostia", "fiestas", date(y, 1, 19), date(y, 1, 19)))
    for y in (2022, 2023, 2024):  # Behobia: segundo domingo de noviembre
        primero = date(y, 11, 1)
        domingo = primero + timedelta(days=(6 - primero.weekday()) % 7 + 7)
        ev.append((f"Behobia-San Sebastian {y}", "Donostia", "deporte", domingo, domingo))
    bbk = {2022: ("2022-07-07", "2022-07-09"), 2023: ("2023-07-06", "2023-07-08"), 2024: ("2024-07-11", "2024-07-13")}
    zin = {2022: ("2022-09-16", "2022-09-24"), 2023: ("2023-09-22", "2023-09-30"), 2024: ("2024-09-20", "2024-09-28")}
    for y in (2022, 2023, 2024):
        ev.append((f"Bilbao BBK Live {y}", "Bilbao", "festival", d(bbk[y][0]), d(bbk[y][1])))
        ev.append((f"Festival de San Sebastian (Zinemaldia) {y}", "Donostia", "festival", d(zin[y][0]), d(zin[y][1])))
    return ev


PUNTUALES = [  # (nombre, ciudad, mes AAAA-MM, primera noche, última noche)
    ("Salida del Tour de Francia", "Bilbao", "2023-07", "2023-06-29", "2023-07-01"),
    ("Final Champions League femenina (San Mamés)", "Bilbao", "2024-05", "2024-05-24", "2024-05-25"),
    ("Final Europa League (San Mamés)", "Bilbao", "2025-05", "2025-05-20", "2025-05-21"),
]


def todos_los_eventos():
    ev = eventos_historicos()
    G = pd.read_csv(RAIZ / "eventos" / "grandes_eventos.csv")
    ev += [(r.nombre, r.ciudad, r.tipo, d(r.fecha_ini), d(r.fecha_fin)) for r in G.itertuples()]
    ev += [(n, c, "puntual", d(a), d(b)) for n, c, _, a, b in PUNTUALES]
    E = pd.DataFrame(ev, columns=["evento", "ciudad", "tipo", "ini", "fin"])
    # En una carrera de domingo, quien viene de fuera duerme la noche anterior: se cuenta también esa noche.
    E.loc[E.tipo == "deporte", "ini"] = E.loc[E.tipo == "deporte", "ini"] - timedelta(days=1)
    return E


def noches_excluidas(E):
    """Noches que no valen como control: eventos (±1 día), festivos y vísperas, Navidad, partidos en casa."""
    fuera = {c: set() for c in CIUDADES.values()}
    for r in E.itertuples():
        x = r.ini - timedelta(days=1)
        while x <= r.fin + timedelta(days=1):
            fuera[r.ciudad].add(x)
            x += timedelta(days=1)
    festivos = []
    pascua = {2022: "2022-04-17", 2023: "2023-04-09", 2024: "2024-03-31", 2025: "2025-04-20", 2026: "2026-04-05"}
    for y in range(2022, 2027):
        p = d(pascua[y])
        festivos += [p - timedelta(days=3), p - timedelta(days=2), p + timedelta(days=1)]
        festivos += [date(y, m, dd) for m, dd in [(1, 1), (1, 6), (5, 1), (7, 25), (7, 31), (8, 15), (10, 12), (11, 1), (12, 6), (12, 8)]]
        festivos += [date(y, 12, 20) + timedelta(days=k) for k in range(19)]  # 20-dic a 7-ene
    for c in fuera:
        for f in festivos:
            fuera[c] |= {f, f - timedelta(days=1)}
    F = pd.read_csv(RAIZ / "eventos" / "partidos_casa_laliga.csv")
    for r in F.itertuples():
        if r.ciudad in fuera:
            fuera[r.ciudad].add(d(r.fecha))
    return fuera


# ---------------------------------------------------------------- lectura Eustat
def leer_px(nombre):
    """Tabla de Eustat en formato ancho (una columna por periodo AAAA-MM) -> largo. Une las .parteN."""
    trozos = []
    for f in sorted(EUSTAT.glob(f"PX_132680_cetr_{nombre}*.csv")):
        filas = list(csv.reader(f.open(encoding="latin-1")))
        cab = filas[0]
        nper = sum(1 for c in cab if len(c) == 7 and c[4] == "-")
        dims = cab[: len(cab) - nper]
        for r in filas[1:]:
            for per, v in zip(cab[len(dims):], r[len(dims):]):
                try:
                    trozos.append(dict(zip(dims, r[: len(dims)]), periodo=per, valor=float(v)))
                except ValueError:
                    pass  # ":" o vacío = sin dato
    return pd.DataFrame(trozos)


def ocupacion_diaria():
    T = leer_px("etrm_20h")
    T = T[(T.variable == "Grado de ocupación por habitaciones") & (T.origen == "Total") & (T["día del mes"] != "Total")]
    T = T[T["ámbitos territoriales"].isin(CIUDADES)]
    T["ciudad"] = T["ámbitos territoriales"].map(CIUDADES)
    T["fecha"] = pd.to_datetime(T.periodo + "-" + T["día del mes"].str.zfill(2), errors="coerce")
    return T.dropna(subset=["fecha"]).set_index(["ciudad", "fecha"]).valor.sort_index()


def mensual():
    A = leer_px("etrm_14h")
    A = A[A.iloc[:, 1].isin(CIUDADES) & A.iloc[:, 0].str.startswith("Tarifa")]
    A = A.assign(ciudad=A.iloc[:, 1].map(CIUDADES)).set_index(["ciudad", "periodo"]).valor.rename("adr")
    O = leer_px("etrm_03h")
    O = O[(O.variable == "Grado de ocupación por habitaciones") & O["zona geográfica"].isin(CIUDADES)
          & (O["categoría"] == "Total") & (O["día de la semana"] == "Total")]
    O = O.assign(ciudad=O["zona geográfica"].map(CIUDADES)).set_index(["ciudad", "periodo"]).valor.rename("occ")
    M = pd.concat([A, O], axis=1).dropna().reset_index()
    M["anio"] = M.periodo.str[:4].astype(int)
    M["mes"] = M.periodo.str[5:].astype(int)
    return M[~M.anio.isin(ANIOS_COVID)]


# ---------------------------------------------------------------- A. ocupación diaria
def control(S, ciudad, dia, fuera):
    xs = [dia + timedelta(days=7 * k) for k in range(-3, 4) if k != 0]
    vals = [S.get((ciudad, pd.Timestamp(x))) for x in xs if x not in fuera[ciudad] and abs((x - dia).days) <= VENTANA]
    vals = [v for v in vals if v is not None and not np.isnan(v)]
    return (np.mean(vals), len(vals)) if len(vals) >= 2 else (None, 0)


def parte_a(S, E, fuera):
    filas = []
    ultimo = S.index.get_level_values(1).max().date()
    for r in E.itertuples():
        x = r.ini
        while x <= r.fin:
            occ = S.get((r.ciudad, pd.Timestamp(x)))
            if occ is not None and x <= ultimo:
                c, n = control(S, r.ciudad, x, fuera)
                if c is not None:
                    filas.append(dict(evento=r.evento, ciudad=r.ciudad, tipo=r.tipo, fecha=x, occ=occ, ctrl=c, n_ctrl=n))
            x += timedelta(days=1)
    R = pd.DataFrame(filas)
    R["dif_pp"] = R.occ - R.ctrl
    T = (R.groupby(["evento", "ciudad", "tipo"])
         .agg(noches=("fecha", "size"), ocupacion_evento=("occ", "mean"), ocupacion_control=("ctrl", "mean"), dif_pp=("dif_pp", "mean"))
         .round(1).reset_index().sort_values(["ciudad", "evento"]))
    # placebo: todas las noches normales frente a sus controles
    P = []
    for (c, f), v in S.items():
        x = f.date()
        if x not in fuera[c]:
            ctrl, _ = control(S, c, x, fuera)
            if ctrl is not None:
                P.append(dict(ciudad=c, dif_pp=v - ctrl))
    P = pd.DataFrame(P).groupby("ciudad").dif_pp.agg(noches="size", media="mean", desviacion="std",
                                                      p5=lambda s: s.quantile(.05), p95=lambda s: s.quantile(.95)).round(1)
    return T, P.reset_index()


# ---------------------------------------------------------------- B. elasticidad ADR-ocupación
def ajuste(x, y):
    X = np.column_stack([np.ones_like(x), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b
    ee = np.sqrt(res @ res / (len(y) - 2) / ((x - x.mean()) ** 2).sum())
    return b[1], ee, np.corrcoef(x, y)[0, 1], len(y)


def parte_b(M):
    puntual = {(c, m) for _, c, m, _, _ in PUNTUALES}
    filas = []
    for c, g in M.groupby("ciudad"):
        g = g[[(c, p) not in puntual for p in g.periodo]].set_index(["anio", "mes"]).sort_index()
        prev = g.rename(index=lambda a: a + 1, level=0)
        j = g.join(prev, rsuffix="_ant", how="inner")
        x, y = (j.occ - j.occ_ant).values, np.log(j.adr / j.adr_ant).values
        b, ee, r, n = ajuste(x, y)
        filas.append(dict(ciudad=c, metodo="interanual (mismo mes, año anterior)", pct_adr_por_10pp=round(100 * (np.exp(10 * b) - 1), 1),
                          ee_pct=round(1000 * ee, 1), r=round(r, 2), meses=n))
        # entre meses de un mismo año: quita el nivel de cada año (inflación, recuperación)
        h = g.reset_index()
        h["ly"] = np.log(h.adr) - h.groupby("anio").adr.transform(lambda s: np.log(s).mean())
        h["ox"] = h.occ - h.groupby("anio").occ.transform("mean")
        b, ee, r, n = ajuste(h.ox.values, h.ly.values)
        filas.append(dict(ciudad=c, metodo="temporada (entre meses del mismo año)", pct_adr_por_10pp=round(100 * (np.exp(10 * b) - 1), 1),
                          ee_pct=round(1000 * ee, 1), r=round(r, 2), meses=n))
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- C. eventos puntuales (diferencias en diferencias)
def did(M, ciudad, periodo):
    mes = int(periodo[5:])
    anio = int(periodo[:4])
    puntual = {m for _, _, m, _, _ in PUNTUALES}
    out = {}
    for c in CIUDADES.values():
        g = M[(M.ciudad == c) & (M.mes == mes)].set_index("anio")
        if anio not in g.index:
            return None
        # resto de años con el mismo mes, sin meses de evento puntual; se corrige el nivel del año con su media anual
        nivel = M[M.ciudad == c].groupby("anio").adr.apply(lambda s: np.log(s).mean())
        la = np.log(g.adr) - nivel.reindex(g.index)
        otros = [a for a in g.index if a != anio and f"{a}-{mes:02d}" not in puntual]
        if len(otros) < 3:
            return None
        out[c] = (la[anio] - la[otros].mean(), g.occ[anio] - g.occ[otros].mean())
    otras = [c for c in CIUDADES.values() if c != ciudad]
    adr = out[ciudad][0] - np.mean([out[c][0] for c in otras])
    occ = out[ciudad][1] - np.mean([out[c][1] for c in otras])
    return 100 * (np.exp(adr) - 1), occ


def parte_c(M):
    filas = []
    for n, c, m, _, _ in PUNTUALES:
        r = did(M, c, m)
        if r:
            filas.append(dict(evento=n, ciudad=c, mes=m, uplift_adr_pct=round(r[0], 1), uplift_occ_pp=round(r[1], 1)))
    puntual = {m for _, _, m, _, _ in PUNTUALES}
    ruido = [did(M, "Bilbao", p) for p in M[M.ciudad == "Bilbao"].periodo if p not in puntual]
    ruido = np.array([r[0] for r in ruido if r])
    filas.append(dict(evento="Ruido: meses de Bilbao sin evento puntual (desviación típica)", ciudad="Bilbao", mes=f"{len(ruido)} meses",
                      uplift_adr_pct=round(float(ruido.std(ddof=1)), 1), uplift_occ_pp=None))
    return pd.DataFrame(filas)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    E = todos_los_eventos()
    fuera = noches_excluidas(E)
    S = ocupacion_diaria()
    print(f"Ocupación diaria Eustat: {S.index.get_level_values(1).min().date()} a {S.index.get_level_values(1).max().date()}")
    A, P = parte_a(S, E[E.tipo != "puntual"], fuera)
    Ap, _ = parte_a(S, E[E.tipo == "puntual"], fuera)
    A = pd.concat([A, Ap])
    M = mensual()
    B = parte_b(M)
    C = parte_c(M)
    A.to_csv(SALIDA / "uplift_hotel_ocupacion.csv", index=False, encoding="utf-8")
    P.to_csv(SALIDA / "uplift_hotel_placebo.csv", index=False, encoding="utf-8")
    B.to_csv(SALIDA / "uplift_adr_elasticidad.csv", index=False, encoding="utf-8")
    C.to_csv(SALIDA / "uplift_adr_puntuales.csv", index=False, encoding="utf-8")
    pd.set_option("display.width", 200)
    print("\nA. Ocupación hotelera en noches de evento (puntos frente a noches de control)\n", A.to_string(index=False))
    print("\nRuido de noches normales\n", P.to_string(index=False))
    print("\nB. Cuánto sube el ADR por cada 10 puntos de ocupación\n", B.to_string(index=False))
    print("\nC. Eventos puntuales: ADR del mes frente a otros años y otras capitales\n", C.to_string(index=False))


if __name__ == "__main__":
    main()
