"""
Descarga completa (bronze) de las tablas Eustat de la Encuesta de Establecimientos Turísticos
Receptores (operación 132680) vía API PX-Web: ADR, RevPAR, ocupación, entradas, pernoctaciones,
estancia media; hoteles, apartamentos, rurales y albergues; anual, mensual, por municipio y capitales.

Guarda en datos/raw/eustat_132680/AAAA-MM-DD/:  <tabla>.csv (respuesta tal cual), <tabla>.meta.json
(variables y códigos) y _descarga.json (URL, tamaño, sha256, fecha de actualización de Eustat).

Uso:  python scripts/descargar_eustat.py [--operacion 132680] [--formato csv]
Cita obligatoria: Fuente: Eustat. Instituto Vasco de Estadística.
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "datos" / "raw"
API = "https://eu.eustat.eus/bankupx/api/v1/es/DB"
UA = {"User-Agent": "Mozilla/5.0 (descarga open data, proyecto de portfolio)"}
LIMITE_CELDAS = 90_000


def get(url: str, body: dict | None = None) -> bytes:
    data = json.dumps(body).encode() if body is not None else None
    hdr = dict(UA, **({"Content-Type": "application/json"} if data else {}))
    req = urllib.request.Request(url, data=data, headers=hdr)
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--operacion", default="132680")
    ap.add_argument("--formato", default="csv")
    ap.add_argument("--solo", default="", help="ids separados por coma: completa la carpeta de hoy con esas tablas")
    args = ap.parse_args()
    solo = {s.strip() for s in args.solo.split(",") if s.strip()}
    carpeta = RAIZ / f"eustat_{args.operacion}" / dt.date.today().isoformat()
    reg_path = carpeta / "_descarga.json"
    if carpeta.exists() and not solo:
        print(f"ya existe {carpeta}, no se sobrescribe")
        return 0
    carpeta.mkdir(parents=True, exist_ok=True)

    catalogo = json.loads(get(API))
    tablas = [t for t in catalogo if f"_{args.operacion}_" in t["id"]]
    if solo:
        tablas = [t for t in tablas if t["id"].removesuffix(".px") in solo or t["id"] in solo]
    print(f"{len(tablas)} tablas de la operación {args.operacion}")
    registro = {"operacion": args.operacion, "fecha_descarga": dt.datetime.now().isoformat(timespec="seconds"),
                "licencia": "Eustat - reutilización libre citando la fuente", "tablas": []}
    if solo and reg_path.exists():  # conservar lo ya bajado y sustituir las entradas de estas tablas
        registro = json.loads(reg_path.read_text(encoding="utf-8"))
        ids = {t["id"] for t in tablas}
        registro["tablas"] = [x for x in registro["tablas"] if x["id"] not in ids]
    errores = 0
    for t in tablas:
        url = f"{API}/{t['id']}"
        base = t["id"].removesuffix(".px")
        try:
            meta = json.loads(get(url))
            (carpeta / f"{base}.meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
            celdas = 1
            for v in meta["variables"]:
                celdas *= len(v["values"])
            # La API devuelve 403 por encima de ~100.000 celdas: partir por la variable de tiempo
            tvar = next((v for v in meta["variables"] if v.get("time")), meta["variables"][-1])
            por_periodo = celdas // len(tvar["values"])
            paso = max(1, LIMITE_CELDAS // por_periodo)
            trozos = [tvar["values"][i:i + paso] for i in range(0, len(tvar["values"]), paso)]
            for n, trozo in enumerate(trozos, 1):
                consulta = {"query": [{"code": v["code"], "selection": (
                                {"filter": "item", "values": trozo} if v is tvar else {"filter": "all", "values": ["*"]})}
                                      for v in meta["variables"]],
                            "response": {"format": args.formato}}
                datos = get(url, consulta)
                nombre = f"{base}.{args.formato}" if len(trozos) == 1 else f"{base}.parte{n}.{args.formato}"
                (carpeta / nombre).write_bytes(datos)
                registro["tablas"].append({"id": t["id"], "fichero": nombre, "titulo": meta["title"],
                                           "actualizado_eustat": t.get("updated"), "url": url, "bytes": len(datos),
                                           "celdas": por_periodo * len(trozo), "periodos": [trozo[0], trozo[-1]],
                                           "sha256": hashlib.sha256(datos).hexdigest(),
                                           "variables": [v["text"] for v in meta["variables"]]})
                print(f"  {nombre}: {len(datos):>10,} B  {por_periodo * len(trozo):>8,} celdas")
                time.sleep(0.5)
        except Exception as e:  # tabla demasiado grande o error puntual: se anota y se sigue
            errores += 1
            registro["tablas"].append({"id": t["id"], "url": url, "error": str(e)})
            print(f"  ERROR {base}: {e}", file=sys.stderr)
        time.sleep(0.5)  # cortesía con el servidor (límite de peticiones por ventana)
    (carpeta / "_descarga.json").write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"errores: {errores}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
