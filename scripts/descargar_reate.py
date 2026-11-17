"""
Foto diaria (bronze) de los registros turísticos de Euskadi (Open Data Euskadi, CC BY 4.0).

- REATE viviendas y habitaciones de vivienda particular para uso turístico
- Alojamientos turísticos de Euskadi (hoteles, pensiones, apartamentos, rurales, campings, albergues)

Guarda los originales sin tocar en datos/raw/<fuente>/AAAA-MM-DD/ y deja un _descarga.json
con URL, tamaño, sha256 y Last-Modified de cada fichero. Si la carpeta del día ya existe, no
sobrescribe nada (la serie histórica es la suma de fotos).

Uso:  python scripts/descargar_reate.py [--formatos json,xlsx]
Ojo: contienen nombres de titulares y direcciones. datos/raw/ está en .gitignore; no publicar.
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "datos" / "raw"
BASE = "https://opendata.euskadi.eus/contenidos/ds_recursos_turisticos"
FUENTES = {
    "reate": {
        "viviendas": f"{BASE}/habitaciones_viviendas_turisti/opendata/viviendas",
        "habitaciones": f"{BASE}/habitaciones_viviendas_turisti/opendata/habitaciones",
    },
    "alojamientos_euskadi": {
        "alojamientos": f"{BASE}/alojamiento_de_euskadi/opendata/alojamientos",
    },
}
EXTRA = {"alojamientos_euskadi": ["geojson"]}  # solo este dataset publica geojson
UA = {"User-Agent": "Mozilla/5.0 (descarga open data, proyecto de portfolio)"}


def bajar(url: str, destino: Path) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        datos = r.read()
        cab = dict(r.headers)
    destino.write_bytes(datos)
    return {
        "url": url,
        "fichero": destino.name,
        "bytes": len(datos),
        "sha256": hashlib.sha256(datos).hexdigest(),
        "last_modified": cab.get("Last-Modified"),
        "content_type": cab.get("Content-Type"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--formatos", default="json,xlsx")
    args = ap.parse_args()
    formatos = [f.strip() for f in args.formatos.split(",") if f.strip()]
    hoy = dt.date.today().isoformat()
    errores = 0

    for fuente, ficheros in FUENTES.items():
        carpeta = RAIZ / fuente / hoy
        if carpeta.exists():
            print(f"[{fuente}] ya existe {carpeta.name}, no se sobrescribe")
            continue
        carpeta.mkdir(parents=True)
        registro = {"fuente": fuente, "fecha_descarga": dt.datetime.now().isoformat(timespec="seconds"),
                    "licencia": "CC BY 4.0 - Gobierno Vasco, Open Data Euskadi", "ficheros": []}
        for nombre, url_base in ficheros.items():
            for ext in formatos + EXTRA.get(fuente, []):
                url = f"{url_base}.{ext}"
                try:
                    info = bajar(url, carpeta / f"{nombre}.{ext}")
                    registro["ficheros"].append(info)
                    print(f"[{fuente}] {nombre}.{ext}: {info['bytes']:,} B")
                except Exception as e:  # una URL caída no debe tumbar el resto
                    errores += 1
                    registro["ficheros"].append({"url": url, "error": str(e)})
                    print(f"[{fuente}] ERROR {url}: {e}", file=sys.stderr)
        (carpeta / "_descarga.json").write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
