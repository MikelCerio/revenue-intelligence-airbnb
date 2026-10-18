"""
Validación de la ocupación por calendario contra la Encuesta de Ocupación en Apartamentos Turísticos del INE (EOAP).

El INE mide los apartamentos turísticos registrados como establecimiento (todos los canales de venta, solo los
abiertos ese mes); el calendario de Inside Airbnb mide pisos completos anunciados en Airbnb, también los de
particulares. No es la misma población: el INE sirve de techo y para comprobar la forma de la temporada.

Compara el "grado de ocupación por apartamentos" de Bilbao y Donostia (puntos turísticos, tabla 2083) y de la costa
de Bizkaia y Gipuzkoa (zonas turísticas, tabla 2022) con outputs/herramienta/ocupacion_mes.json, al que se le
devuelve el ajuste de verano para comparar el calendario tal cual.

Salida: outputs/bilbao/validacion_ine.csv
Uso:    python scripts/validacion_ine.py
"""
import json
import urllib.request
from pathlib import Path

import pandas as pd

from ocupacion_mes import AJUSTE_VERANO

RAIZ = Path(__file__).resolve().parents[1]
CALENDARIO = RAIZ / "outputs" / "herramienta" / "ocupacion_mes.json"
CACHE = RAIZ / "data" / "ine"
SALIDA = RAIZ / "outputs" / "bilbao" / "validacion_ine.csv"
API = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{}?nult=36"
ZONAS = {"Bilbao": ("2083", "Bilbao."), "Donostia": ("2083", "Donostia/San Sebasti"),
         "Costa Bizkaia": ("2022", "Costa Bizkaia"), "Costa Gipuzkoa": ("2022", "Costa Guipuzkoa")}


def tabla(t):
    f = CACHE / f"eoap_{t}.json"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_bytes(urllib.request.urlopen(API.format(t), timeout=120).read())
    return json.loads(f.read_text(encoding="utf-8"))


def medida(nombre):
    if "fin de semana" in nombre:
        return "ine_finde"
    if "ocupación por apartamentos" in nombre:
        return "ine_ocupacion"
    if "apartamentos estimados" in nombre:
        return "apartamentos_ine"
    return None


def main():
    filas = []
    for g, (t, clave) in ZONAS.items():
        for s in tabla(t):
            n = s["Nombre"]
            if clave not in n or "Total categor" not in n or not medida(n):
                continue
            filas += [{"grupo": g, "mes": f"{d['Anyo']}-{d['FK_Periodo']:02d}", "medida": medida(n), "valor": d["Valor"]}
                      for d in s["Data"] if d["Valor"] is not None]
    I = pd.DataFrame(filas).pivot_table(index=["grupo", "mes"], columns="medida", values="valor").reset_index()
    cal = json.loads(CALENDARIO.read_text(encoding="utf-8"))
    I["calendario"] = [cal.get(g, {}).get(m) for g, m in zip(I.grupo, I.mes)]
    I = I.dropna(subset=["calendario"])
    I["calendario"] += [AJUSTE_VERANO.get(g, {}).get(int(m[5:]), 0) for g, m in zip(I.grupo, I.mes)]   # sin el ajuste
    I["diferencia"] = I.calendario - I.ine_ocupacion
    I = I[["grupo", "mes", "ine_ocupacion", "ine_finde", "apartamentos_ine", "calendario", "diferencia"]].round(1)
    I.to_csv(SALIDA, index=False)
    for g, x in I.groupby("grupo"):
        ver = x[x.mes.str[5:].isin(["07", "08"])]
        print(f"{g}: {len(x)} meses, INE {x.ine_ocupacion.mean():.1f} %, calendario {x.calendario.mean():.1f} %, "
              f"diferencia {x.diferencia.mean():+.1f} pp (julio-agosto {ver.diferencia.mean():+.1f}), "
              f"correlación {x.ine_ocupacion.corr(x.calendario):.2f}")


if __name__ == "__main__":
    main()
