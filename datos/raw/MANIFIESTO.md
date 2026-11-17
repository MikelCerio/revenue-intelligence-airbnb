# Manifiesto de datos brutos (bronze)

Originales intactos. **Esta carpeta está en `.gitignore`**: REATE y Alojamientos llevan direcciones,
nombres comerciales, teléfonos y emails. Nunca publicar a nivel de vivienda o titular; agregar.
Cada carpeta `AAAA-MM-DD/` trae un `_descarga.json` con URL, bytes y sha256 de cada fichero.

| Fuente | Carpeta | Script | URL comprobada (2026-11-17) | Formato | Tamaño | Licencia / cita |
|---|---|---|---|---|---|---|
| REATE viviendas uso turístico | `reate/2026-11-17/viviendas.{json,xlsx}` | `scripts/descargar_reate.py` | `https://opendata.euskadi.eus/contenidos/ds_recursos_turisticos/habitaciones_viviendas_turisti/opendata/viviendas.json` (también `.xlsx`, `.xml`, `.jsonp`) | JSON (lista de objetos, UTF-8), XLSX | 2,68 MB + 0,56 MB · 4.720 registros | CC BY 4.0 · Gobierno Vasco, Open Data Euskadi |
| REATE habitaciones en vivienda particular | `reate/2026-11-17/habitaciones.{json,xlsx}` | idem | `.../habitaciones_viviendas_turisti/opendata/habitaciones.json` | JSON, XLSX | 0,46 MB + 0,10 MB · 736 registros | CC BY 4.0 · Gobierno Vasco |
| Alojamientos turísticos de Euskadi | `alojamientos_euskadi/2026-11-17/alojamientos.{json,xlsx,geojson}` | idem | `https://opendata.euskadi.eus/contenidos/ds_recursos_turisticos/alojamiento_de_euskadi/opendata/alojamientos.json` | JSON, XLSX, GeoJSON | 2,76 + 0,55 + 2,24 MB · 1.482 establecimientos | CC BY 4.0 · Gobierno Vasco |
| Eustat, Establecimientos Turísticos Receptores (op. 132680) | `eustat_132680/2026-11-17/` (62 tablas, 3 partidas en `.parteN`) | `scripts/descargar_eustat.py` | API PX-Web `https://eu.eustat.eus/bankupx/api/v1/es/DB/PX_132680_*.px` | CSV ancho (`,`, **ISO-8859-1**) + `.meta.json` | ~5,4 MB | Fuente: Eustat. Reutilización libre citando la fuente |
| INE experimental, viviendas turísticas | `ine_viv_turistica/2026-11-17/` (39363-39366) | `scripts/descargar_ine.py` | `https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/<tabla>.csv` | CSV largo (`;`, **UTF-8 con BOM**) | 39,4 MB | CC BY 4.0 · INE |
| INE experimental, ocupación en plataformas | `ine_ocupacion_plataformas/2026-11-17/` (48423-48436) | idem | idem | CSV largo (`;`, UTF-8 con BOM) | 12,0 MB | CC BY 4.0 · INE |
| Inside Airbnb Bilbao/Euskadi/Barcelona | ya en `data/bronze/` (no se duplica) | `scripts/02_descarga.py` | insideairbnb.com/get-the-data | CSV.gz | — | CC BY 4.0 · Inside Airbnb |

## Frecuencia y cómo repetir

- **REATE y Alojamientos: a diario.** El portal se regenera cada madrugada (`Last-Modified` 06:20). El fichero es una foto del registro vigente, sin histórico: la serie de altas y bajas solo existe si se guarda una foto por día. El script nunca sobrescribe un día ya descargado.
- **Eustat:** mensual (las tablas `etrm_*` se actualizaron el 22-10 y el 16-11-2026); las anuales `etrt_*` en febrero.
- **INE viviendas turísticas:** semestral (13 periodos, 2020M08…2026M05). **Ocupación en plataformas:** mensual hasta 2026M06; anual 2018-2025.

**Programado:** tarea de Windows `RevenueIntelligence-REATE-diario`, a diario a las 08:00 (si el PC está apagado,
se ejecuta al encenderlo). Lanza `scripts/descargar_reate_diario.cmd` y escribe el log en `datos/raw/_logs/reate.log`.
Quitarla: `Unregister-ScheduledTask -TaskName RevenueIntelligence-REATE-diario`.

```
python scripts/descargar_reate.py      # diario
python scripts/descargar_eustat.py     # mensual; --solo <id,...> completa la carpeta del día
python scripts/descargar_ine.py        # mensual
```

## Incidencias al descargar

- Eustat devuelve **HTTP 403 por encima de ~100.000 celdas** por consulta. `etrm_03h`, `etrm_04h` y `etrm_20h` se bajaron en dos trozos por periodo (`.parte1.csv`, `.parte2.csv`): hay que concatenarlos en silver.
- La URL `kml` de Alojamientos (turismo.euskadi.net) es un visor antiguo; no se descarga.
- El INE manda la cabecera `charset=ISO-8859-15`, pero los ficheros son UTF-8 con BOM. Leer con `encoding="utf-8-sig"`.
- `data/ine/vut_municipios.csv` (ya existente) es la misma tabla 39363 bajada antes: en adelante, usar la foto con fecha de aquí.

## Diccionarios

En `datos/docs/`: `reate.md`, `alojamientos_euskadi.md`, `eustat_132680.md`, `ine_viv_turistica.md` e `ine_ocupacion_plataformas.md`.
