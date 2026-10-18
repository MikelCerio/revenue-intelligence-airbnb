# Revenue Intelligence sobre Inside Airbnb

Proyecto de portfolio de **analítica de revenue para alquiler turístico**, construido de extremo a extremo en **Microsoft Fabric**: ingesta reproducible, arquitectura medallion (bronze, silver, gold), modelo semántico **Direct Lake** y un informe de Power BI pensado para propietarios de pocos pisos.

> **Estado:** funcionan la ingesta, silver (`listings` y `calendar`), el gold, el modelo Direct Lake y un informe de Power BI de 9 páginas. La ampliación de Bilbao y Donostia por distrito está hecha en Python ([metodología](docs/bilbao_ampliacion.md)) y pendiente de llevar a Fabric. Pendientes también: reseñas como proxy de demanda y seguridad por filas (RLS).

**[Mapa interactivo](https://mikelcerio.github.io/revenue-intelligence-airbnb/mapa/)**: ocupación, ADR y RevPAR aproximados por municipio y barrio, por temporada y con niveles de fiabilidad.

## Hallazgos principales

1. **¿Turístico o alquiler largo? Gana el turístico, con distancia según la ciudad.** El piso turístico mediano ingresa al año 4,9 veces lo que un alquiler largo en Donostia, 2,7 veces en Bilbao y 3,0 veces en Vitoria-Gasteiz (antes de gastos). Tras comisiones, limpieza y gastos fijos, un piso tipo de Abando (Bilbao) deja unos 2.000 € netos al mes frente a 861 € del alquiler largo. *(Corregido el 19/10/2026: la ocupación se mide ahora con el calendario público y no con las reseñas, que daban entre 2 y 4 veces menos ingreso. Ver [metodología](docs/bilbao_ampliacion.md).)*
2. **Mucho dinero sin capturar.** Comparando cada piso con otros de su mismo distrito y tamaño, 163 pisos de Bilbao con historial ingresan menos del 75 % de sus iguales: les faltan unos 189.000 € al mes. En Donostia son 210 pisos y unos 467.000 € al mes.
3. **El tipo de anfitrión pesa distinto en cada ciudad.** En Bilbao, el 37 % de los pisos de anfitriones con 10 o más anuncios queda por debajo de sus iguales, frente al 15 % de los particulares. En Donostia es al revés: los profesionales cobran más por noche y son los que más ingresan.
4. **Estacionalidad muy marcada.** La ocupación a 30 días de Euskadi pasa del 76 % en julio al 36 % en diciembre.

Todas las cifras son estimaciones con datos públicos (ver [Limitaciones](#limitaciones)).

## Qué responde

Con datos abiertos de **Barcelona** y **Euskadi** (23 snapshots mensuales, de julio de 2025 a junio de 2026):

- ¿Qué **ocupación aproximada** y qué **RevPAR** tiene cada ciudad y cada zona?
- ¿Cómo es la **estacionalidad**? (la ocupación a 30 días de Euskadi pasa del 76 % en julio al 36 % en diciembre)
- ¿Qué zonas tienen **muestra suficiente** (30 o más anuncios) para fiarse de su ranking?
- En **Bilbao y Donostia**, por distrito: ¿cuánto ingresa un piso, compensa frente al alquiler largo y quién rinde por debajo de pisos parecidos? Cruza Inside Airbnb con distritos censales del INE y la estadística de alquiler del Gobierno Vasco (EMAL).

## Arquitectura

```mermaid
flowchart LR
    A[Inside Airbnb<br/>CC BY 4.0] -->|Pipeline<br/>Lookup + ForEach + Copy| B[(lh_bronze<br/>ficheros crudos)]
    B -->|Notebooks PySpark| C[(lh_silver<br/>Delta limpio)]
    C -->|Notebook PySpark| D[(lh_gold<br/>modelo estrella)]
    D -->|Direct Lake| E[Modelo semántico<br/>sm_revenue_airbnb]
    E --> F[Informe Power BI]
```

| Capa | Contenido | Tamaño |
|---|---|---|
| **Bronze** | Los ficheros tal cual llegan (`Files/<ciudad>/<fecha>/`) | 92 ficheros, 2,1 GB |
| **Silver** | `listings` y `calendar` en Delta, tipados, con flags y validaciones, particionados por ciudad y snapshot | `calendar`: 88,7 M filas |
| **Gold** | `dim_snapshot`, `dim_zona`, `dim_listing`, `dim_fecha`, `fact_listing_snapshot`, `fact_calendar` | 6 tablas |
| **Modelo** | Direct Lake sobre `lh_gold`, 6 relaciones y medidas DAX | |

## Decisiones técnicas que merece la pena revisar

- **Bronze inmutable y binario.** Los ficheros se copian sin interpretar, para que un error de limpieza no destruya el original y la deriva de esquema (`listings` pasa de 79 a 90 columnas) no rompa la ingesta.
- **Pipeline parametrizado e idempotente.** Una lista de 92 elementos generada desde configuración recorre `Lookup`, `ForEach` y `Copy`. Repetir una copia sobrescribe, no duplica; los reintentos son seguros.
- **Silver limpia y marca, no elimina.** Flags (`price_missing`, `price_outlier`, `is_long_stay`) en lugar de borrar filas; booleanos que admiten "desconocido"; validaciones con gravedad (las que bloquean el notebook y las que solo avisan).
- **Escrituras por partición con `replaceWhere`.** Recargar un snapshot no toca los otros 22.
- **Privacidad por diseño.** No se cargan nombres de anfitriones, descripciones ni el texto libre de las licencias (puede contener documentos de identidad).
- **Direct Lake.** El modelo lee las tablas Delta sin copiar los 88 millones de filas.
- **Todo versionado.** Los elementos de Fabric (lakehouses, notebooks, pipelines, modelo en TMDL e informe en formato de proyecto) están en la carpeta `workspace/`.

## Hallazgos sobre los datos

Cosas que no se ven en un tutorial y que condicionan cualquier conclusión:

1. **Snapshots parciales.** Barcelona 2026-04-20 trae 7.277 anuncios frente a ~15.000 en los vecinos. `dim_snapshot.es_completo` los marca y las medidas avisan; sin ello habría bajas falsas.
2. **Tres meses sin precio.** De diciembre de 2025 a febrero de 2026, el 100 % de los anuncios no trae precio en origen. El ADR sale **vacío, no cero**: un precio de 0 € diría "gratis".
3. **El significado del precio cambia.** Desde marzo de 2026 el precio coincide con `price_quote_price_per_night`: es la cotización para fechas cercanas a la captura, así que el de junio es precio de verano e inflaba los ingresos entre un 15 y un 35 %. En la ampliación de Bilbao se usa la mediana de marzo a junio de cada anuncio, y no se compara el ADR entre antes y después.
4. **El calendario no trae precio por noche** en ningún snapshot, y "no disponible" mezcla reservas, bloqueos y anuncios cerrados: la ocupación es un **límite superior**.
5. **La fecha de un snapshot es nominal.** La captura dura varios días (hasta ~12); la antelación se calcula con la fecha real de captura de cada anuncio.
6. **Codificación rota en Euskadi** (`SebastiÃ¡n`), corregida solo en las filas afectadas.

## Cómo está organizado el repositorio

| Ruta | Qué hay |
|---|---|
| `config/` | Snapshots a descargar (`snapshots.yaml`) y la lista plana que lee el pipeline |
| `scripts/` | Descarga local a bronze y generación de la lista de trabajo |
| `notebooks/` | Exploración inicial con pandas (la evidencia de las decisiones) |
| `fabric/` | Copia exportada de los notebooks de Fabric |
| `workspace/` | Elementos de Fabric sincronizados con Git: lakehouses, notebooks, pipelines, modelo semántico e informe |
| `docs/manual.md` | Manual del proyecto: cada paso con el porqué, los errores y las lecciones |
| `docs/bilbao_ampliacion.md` | Metodología y resultados de Bilbao y Donostia por distrito |
| `docs/mapa/` | Mapa interactivo publicado en GitHub Pages |
| `scripts/bilbao_open_data.py` | Ampliación de Bilbao y Donostia, reproducible de principio a fin |
| `outputs/bilbao/` | Resultados agregados por distrito (sin anuncios individuales) |

## Reproducir

1. Crear un workspace de Fabric (con capacidad) y conectarlo a este repositorio (carpeta `workspace`).
2. Subir `config/snapshots_flat.json` a `lh_bronze/Files/config/` y ejecutar `pl_ingesta_snapshots`.
3. Ejecutar `pl_silver_listings` y `pl_silver_calendar`, y después el notebook del gold.
4. Refrescar el modelo `sm_revenue_airbnb` y abrir el informe `rp_revenue_airbnb`.

## Limitaciones

- La ocupación y el RevPAR son **aproximaciones comparativas**, no ingresos reales.
- El precio es el **publicado**, no el cobrado.
- Las zonas de Euskadi son municipios, no barrios, y no son comparables en tamaño con las de Barcelona. En Bilbao y Donostia se usan distritos censales del INE; los nombres de los distritos de Donostia son aproximados.
- Solo se publican datos agregados por zona, con un mínimo de 10 pisos por celda.
- Los datos de Inside Airbnb son una muestra pública con sus propias limitaciones de captura.

## Datos y licencia

Datos de [Inside Airbnb](https://insideairbnb.com/get-the-data/), publicados bajo licencia **Creative Commons Attribution 4.0 (CC BY 4.0)**. Este repositorio no incluye los ficheros de datos.
