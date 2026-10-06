# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "e5b24d47-c902-4dd1-9689-6849b8f1eddc",
# META       "default_lakehouse_name": "lh_bronze",
# META       "default_lakehouse_workspace_id": "f27effa5-e197-450a-8f22-a721e757bc54",
# META       "known_lakehouses": [
# META         {
# META           "id": "e5b24d47-c902-4dd1-9689-6849b8f1eddc"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# Welcome to your new notebook
# Type here in the cell editor to add code!
import os, json

raiz = "/lakehouse/default/Files"
with open(f"{raiz}/config/snapshots_flat.json", encoding="utf-8") as f:
    lista = json.load(f)

esperadas = {(e["ciudad"], e["fecha"], e["ruta_fichero"].split("/")[-1]) for e in lista}

encontradas = set()
for ciudad in ("barcelona", "euskadi"):
    for fecha in os.listdir(f"{raiz}/{ciudad}"):
        for nombre in os.listdir(f"{raiz}/{ciudad}/{fecha}"):
            encontradas.add((ciudad, fecha, nombre))

print("esperados:", len(esperadas), "| encontrados:", len(encontradas))
print("faltan:", sorted(esperadas - encontradas))
print("sobran:", sorted(encontradas - esperadas))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
