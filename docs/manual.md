# Manual del proyecto: Revenue Intelligence sobre Inside Airbnb

Documento vivo. Cada paso se explica con la misma estructura: **qué hicimos, por qué, cómo, qué descubrimos, errores y preguntas de entrevista**. Se actualiza al cerrar cada paso.

Fuente de datos: [Inside Airbnb](https://insideairbnb.com/get-the-data/), licencia CC BY 4.0.

---

## Mapa del proyecto

```
bronze  -> ficheros crudos, intactos          data/bronze/<ciudad>/<fecha>/
silver  -> limpieza y tipado                  (Paso 3)
gold    -> modelo estrella para Power BI      (Paso 4)
Fabric  -> mismo flujo con Lakehouse+Pipeline (Paso 5)
```

| Paso | Estado | Resumen |
|---|---|---|
| 0 | Hecho | Repo, entorno Python y configuración de snapshots |
| 1 | Hecho | Descarga a bronze: 92 ficheros, 2,1 GB |
| 2 | En curso | Exploración de `listings` (Euskadi 2026-06-30) |
| 3 | Pendiente | Capa silver |
| 4 | Pendiente | Modelo gold |
| 5 | Pendiente | Migración a Fabric |
| 6 | Pendiente | Informe Power BI |

---

## Paso 0 y 1: esqueleto y descarga a bronze

**Qué hicimos.** Repo Git con `config/snapshots.yaml` (23 snapshots mensuales: 11 Barcelona y 12 Euskadi) y `scripts/02_descarga.py`, que baja 4 ficheros por snapshot.

**Por qué.**
- Las fechas viven en configuración y no en el código: añadir un snapshot es añadir una línea. En Fabric serán los parámetros de un `ForEach` del pipeline.
- La web solo enseña el último snapshot, pero el servidor guarda los mensuales. Los encontramos con peticiones `HEAD` (preguntan si existe y cuánto pesa, sin descargar). Esas URLs no están enlazadas oficialmente, así que **bajamos una vez y guardamos en bronze**.

**Decisiones de diseño del script.**
1. **Idempotente:** si el fichero existe, lo salta. Se puede relanzar tras un fallo.
2. **`.part` + renombrar:** se descarga a `fichero.part` y solo se renombra si el tamaño coincide con `Content-Length`. Nunca queda un fichero truncado con aspecto válido.
3. **Streaming por trozos de 1 MB:** no carga `reviews` (130 MB) en memoria.
4. **Bronze sin tocar:** no se descomprime ni se parsea. Si cambia una regla de limpieza, se reprocesa desde bronze.

**Reproducibilidad.** Los datos no van a Git (`.gitignore`). Lo que se versiona es script + configuración + fechas verificadas, y con eso cualquiera reconstruye bronze.

**Errores y lecciones.**
- Rutas relativas dependen del directorio de la terminal: usa rutas absolutas o ancla la raíz con un fichero (`config/snapshots.yaml`).
- `Content-Length` mide la descarga comprimida. Estimamos 2,5 GB y el `HEAD` dio 2,23 GB: medir antes vale más que estimar.
- Git necesita `user.name` y `user.email`, y el email debe coincidir con uno verificado en GitHub para que los commits cuenten en el perfil.

---

## Paso 2: exploración de `listings` (Euskadi, 2026-06-30)

**Objetivo.** Decidir qué columnas llegan a silver y qué reglas de limpieza aplicar, sobre **un solo snapshot** antes de generalizar a los 23.

**Hallazgos.**
- 6.248 anuncios y 90 columnas (42 `float64`, 30 `str`, 18 `int64`).
- **12 columnas 100 % vacías**, entre ellas `host_since`, `host_total_listings_count`, `neighbourhood` e `instant_bookable`. Una columna vacía se tipa como `float64` porque `NaN` es un float: el dtype no dice qué es la columna.
- **Hosts profesionales:** se miden con `calculated_host_listings_count` (y variantes por tipo de alojamiento), que sí viene rellena.
- **Barrio:** se usa `neighbourhood_cleansed`, no `neighbourhood`.
- **`price` es texto** con formato `"$483.00"`; 87 valores llevan coma de miles. Hay que quitar `$` y `,` antes de convertir.
- **572 precios nulos (9,2 %)**, y **no** son anuncios inactivos: 544 de los 546 nulos analizables tienen `has_availability = t`. Además, 26 filas tienen `has_availability` nulo.
- **Precio máximo 9999**, mediana 196 y media 264: sospecha de valor centinela y distribución muy asimétrica.

**Pendiente de decidir (Paso 2c).** Qué hacer con los nulos de precio y con los extremos (9999 y los menores de 20), y en qué moneda va `price` (consultar el diccionario de datos de Inside Airbnb).

**Errores y lecciones.**
- Una hipótesis plausible ("los nulos son inactivos") era falsa. Se comprueba, no se supone.
- `sort_values()` deja los `NaN` al final: `.tail()` devolvía solo `NaN`. Hacer `dropna()` antes.
- `pd.crosstab` descarta las filas con `NaN`; el total no coincidía con el número de filas.

---

## Glosario

| Término | Qué significa |
|---|---|
| **Medallion** | Arquitectura por capas: bronze (crudo), silver (limpio), gold (modelo para consumo). |
| **Lakehouse (Fabric)** | Almacén sobre OneLake con `Files/` (ficheros crudos) y `Tables/` (tablas Delta). |
| **Delta** | Formato de tabla sobre Parquet con transacciones; Direct Lake solo lee Delta. |
| **Direct Lake** | Modo del modelo semántico que lee las tablas Delta del lakehouse sin importar los datos. |
| **Idempotente** | Ejecutarlo una o varias veces deja el mismo resultado. |
| **`HEAD` (HTTP)** | Pide solo las cabeceras (existe, tamaño) sin descargar el cuerpo. |
| **Valor centinela** | Valor que sustituye a "desconocido" o "no aplicable" (9999, -1, 1900-01-01) y es indistinguible de un dato real si no se conoce la convención. |
| **ADR** | Average Daily Rate: ingresos por habitaciones entre noches vendidas. Aquí `price` es precio **publicado**, no cobrado. |
| **Ocupación** | Noches vendidas entre noches disponibles. |
| **RevPAR** | Ingresos por noche disponible = ADR x ocupación. |
| **Comp set** | Conjunto de alojamientos comparables para fijar referencias de precio y ocupación. |
| **Pickup** | Reservas acumuladas para una fecha futura entre dos momentos. Aquí se aproxima con la disponibilidad entre snapshots. |
| **Lead time** | Días entre la reserva (o la observación) y la noche de estancia. |
| **Winsorizar** | Recortar extremos a un percentil (por ejemplo p1 y p99) en vez de eliminarlos. |
| **Mediana** | Valor central; no la arrastran los extremos, a diferencia de la media. |

---

## Preguntas de entrevista (con espacio para tu respuesta)

1. ¿Por qué tres lakehouses y no uno con carpetas? Ventaja e inconveniente.
   - *Mi respuesta:*
2. Direct Lake solo funciona sobre Delta. ¿Qué pasa si se apunta a los CSV de bronze?
   - *Mi respuesta:*
3. ¿Qué parte de este repo demuestra reproducibilidad si los datos no están dentro?
   - *Mi respuesta:*
4. "No disponible" en el calendar no significa reservado. ¿Por qué?
   - *Mi respuesta:*
5. Un precio publicado de 9999 sin reseñas en 12 meses: ¿eliminar, recortar o marcar con un flag?
   - *Mi respuesta:*
6. ¿Por qué la mediana por barrio como referencia de comp set y no la media?
   - *Mi respuesta:*
7. Si `host_since` viene vacía en este snapshot, ¿cómo compruebas los otros 22 antes de descartarla?
   - *Mi respuesta:*
