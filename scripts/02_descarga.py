"""Descarga snapshots de Inside Airbnb a la capa bronze.

Lee config/snapshots.yaml y guarda cada fichero tal cual (sin tocarlo) en
data/bronze/<ciudad>/<fecha>/<fichero>. Es idempotente: lo ya descargado se salta.

Uso:
    python scripts/02_descarga.py --dry-run
    python scripts/02_descarga.py --ciudad euskadi --fecha 2026-06-30 --fichero listings.csv.gz
    python scripts/02_descarga.py
"""
import argparse
import sys
import time
from pathlib import Path

import requests
import yaml

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config" / "snapshots.yaml"
BRONZE = RAIZ / "data" / "bronze"
TROZO = 1024 * 1024  # 1 MB por lectura: nunca cargamos un fichero entero en memoria
HEADERS = {"User-Agent": "revenue-intelligence-portfolio (CC BY 4.0, uso academico)"}


def cargar_config():
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def trabajos(cfg, ciudad=None, fecha=None, fichero=None):
    """Genera (ciudad, fecha, ruta_remota, url) para cada fichero a bajar."""
    for nombre, datos in cfg["ciudades"].items():
        if ciudad and nombre != ciudad:
            continue
        for f in datos["fechas"]:
            if fecha and f != fecha:
                continue
            for rel in cfg["ficheros"]:
                if fichero and Path(rel).name != fichero:
                    continue
                url = f"{cfg['base_url']}/{datos['ruta']}/{f}/{rel}"
                yield nombre, f, rel, url


def descargar(url, destino, reintentos=3):
    """Baja a destino.part y renombra al terminar. Devuelve 'ok' | 'saltado'."""
    if destino.exists():
        return "saltado"
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".part")

    for intento in range(1, reintentos + 1):
        try:
            with requests.get(url, stream=True, timeout=60, headers=HEADERS) as r:
                r.raise_for_status()
                esperado = int(r.headers.get("Content-Length", 0))
                with open(parcial, "wb") as out:
                    for trozo in r.iter_content(TROZO):
                        out.write(trozo)
            if esperado and parcial.stat().st_size != esperado:
                raise IOError(f"tamano {parcial.stat().st_size} != esperado {esperado}")
            parcial.replace(destino)  # el fichero final solo aparece si esta completo
            return "ok"
        except (requests.RequestException, IOError) as e:
            print(f"    intento {intento}/{reintentos} fallo: {e}")
            time.sleep(2 * intento)
    parcial.unlink(missing_ok=True)
    raise RuntimeError(f"no se pudo descargar {url}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--ciudad")
    ap.add_argument("--fecha")
    ap.add_argument("--fichero", help="solo este nombre, p.ej. listings.csv.gz")
    ap.add_argument("--dry-run", action="store_true", help="HEAD: comprueba existencia y tamano, no descarga")
    args = ap.parse_args()

    cfg = cargar_config()
    lista = list(trabajos(cfg, args.ciudad, args.fecha, args.fichero))
    if not lista:
        sys.exit("Ningun trabajo coincide con los filtros.")

    total_bytes = 0
    for i, (ciudad, fecha, rel, url) in enumerate(lista, 1):
        destino = BRONZE / ciudad / fecha / Path(rel).name
        etiqueta = f"[{i}/{len(lista)}] {ciudad}/{fecha}/{Path(rel).name}"
        if args.dry_run:
            r = requests.head(url, timeout=30, headers=HEADERS)
            mb = int(r.headers.get("Content-Length", 0)) / 1e6
            total_bytes += mb * 1e6
            print(f"{etiqueta}  HTTP {r.status_code}  {mb:.1f} MB")
        else:
            estado = descargar(url, destino)
            print(f"{etiqueta}  {estado}")

    if args.dry_run:
        print(f"\nTotal a descargar: {total_bytes / 1e9:.2f} GB en {len(lista)} ficheros")


if __name__ == "__main__":
    main()
