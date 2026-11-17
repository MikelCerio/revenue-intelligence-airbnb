"""
Descarga completa (bronze) de dos estadísticas experimentales del INE (CC BY 4.0):

- Viviendas turísticas en España (tablas 39363-39366): viviendas, plazas y % sobre el total de
  viviendas, por municipio y nivel inferior. Se bajan enteras (todos los municipios).
- Ocupación en alojamientos turísticos a partir de plataformas digitales (48423-48436):
  alojamientos y noches ocupados, pernoctaciones; nacional, CCAA, provincias, puntos y zonas turísticas.

Guarda en datos/raw/ine_<serie>/AAAA-MM-DD/<tabla>.csv (fichero original del INE: ';', UTF-8 con BOM
aunque la cabecera HTTP diga ISO-8859-15, miles con '.', decimales con ',') y _descarga.json.  Uso: python scripts/descargar_ine.py
Cita: Fuente: INE, estadística experimental.
"""
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "datos" / "raw"
URL = "https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/{}.csv"
UA = {"User-Agent": "Mozilla/5.0 (descarga open data, proyecto de portfolio)"}
SERIES = {
    "ine_viv_turistica": {
        "pagina": "https://www.ine.es/experimental/viv_turistica/exp_viv_turistica_tablas.htm",
        "tablas": [39363, 39364, 39365, 39366],
    },
    "ine_ocupacion_plataformas": {
        "pagina": "https://www.ine.es/dynt3/inebase/es/index.htm?padre=7957",
        "tablas": list(range(48423, 48437)),  # 48423-48426 anual, 48427-48436 mensual
    },
}


def main() -> int:
    hoy = dt.date.today().isoformat()
    errores = 0
    for serie, cfg in SERIES.items():
        carpeta = RAIZ / serie / hoy
        if carpeta.exists():
            print(f"[{serie}] ya existe {hoy}, no se sobrescribe")
            continue
        carpeta.mkdir(parents=True)
        registro = {"serie": serie, "pagina": cfg["pagina"], "licencia": "CC BY 4.0 - INE",
                    "fecha_descarga": dt.datetime.now().isoformat(timespec="seconds"), "tablas": []}
        for t in cfg["tablas"]:
            url = URL.format(t)
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=300) as r:
                    datos = r.read()
                (carpeta / f"{t}.csv").write_bytes(datos)
                cabecera = datos.split(b"\n", 1)[0].decode("utf-8-sig", errors="replace").strip()
                registro["tablas"].append({"tabla": t, "url": url, "bytes": len(datos),
                                           "filas": datos.count(b"\n") - 1, "cabecera": cabecera,
                                           "sha256": hashlib.sha256(datos).hexdigest()})
                print(f"[{serie}] {t}: {len(datos):>11,} B")
            except Exception as e:
                errores += 1
                registro["tablas"].append({"tabla": t, "url": url, "error": str(e)})
                print(f"[{serie}] ERROR {t}: {e}", file=sys.stderr)
            time.sleep(0.5)
        (carpeta / "_descarga.json").write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
