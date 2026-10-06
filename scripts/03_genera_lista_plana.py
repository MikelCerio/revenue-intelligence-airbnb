"""Genera config/snapshots_flat.json a partir de config/snapshots.yaml.

Es una lista plana de elementos {ciudad, ruta, fecha, ruta_fichero}, uno por fichero a descargar.
El pipeline de Fabric la lee con una actividad Lookup y la recorre con un unico ForEach
(Fabric no permite un ForEach dentro de otro).

Uso:
    python scripts/03_genera_lista_plana.py
"""
import json
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
cfg = yaml.safe_load((RAIZ / "config" / "snapshots.yaml").read_text(encoding="utf-8"))

plana = [
    {"ciudad": ciudad, "ruta": datos["ruta"], "fecha": fecha, "ruta_fichero": fichero}
    for ciudad, datos in cfg["ciudades"].items()
    for fecha in datos["fechas"]
    for fichero in cfg["ficheros"]
]

salida = RAIZ / "config" / "snapshots_flat.json"
salida.write_text(json.dumps(plana, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(len(plana), "elementos ->", salida)
