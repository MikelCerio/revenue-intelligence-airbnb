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
| 2 | Hecho | Exploración de `listings` y `calendar`; reglas de silver definidas |
| 3 | Parte 1 hecha | Silver de `listings` (Euskadi 2026-06-30) en local; los 23 snapshots se harán en Fabric con PySpark |
| 4 | Pendiente | Modelo gold |
| 5 | En curso | Workspace, lakehouses y pipeline de ingesta (F1 a F3); faltan silver, gold y modelo |
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
- **Extremos de precio.** Mediana 196 y media 264 (cola derecha). Solo **1 anuncio a 9999**: centinela probable, con impacto de ~1,8 en la media. Lo que pesa son los **87 anuncios con precio >= 1000** (casas enteras de 6 a 15 plazas, con reseñas recientes): parecen reales y coinciden con los 87 precios con coma de miles.
- **Precios bajos (15 con precio < 20).** Todos son habitaciones privadas con `minimum_nights` >= 31. Son **larga estancia**, no alquiler turístico.
- **Nulos de precio según disponibilidad.** 281 (49 %) con `availability_365 = 0` (cerrados: no hay precio que mostrar), 230 (40 %) con >= 30 días libres y sin precio (posible problema de captura, es una hipótesis) y 61 en zona gris. `has_availability` es un indicador débil; el útil es `availability_365`. Las 26 filas con `has_availability` nulo tienen todas el precio nulo.
- **`price_quote_price_per_night`** es una copia numérica de `price`: coincide en el 100 % de las filas con precio. Sirve para validar el parseo, no es una fuente independiente ni rellena nulos.
- **Larga estancia.** `minimum_nights` >= 28 en 264 anuncios (4,2 %), 219 de ellos con precio. Mediana de precio 95,52 frente a 199,80 del resto. El 47 % de los anuncios exige 2 o más noches. 2 anuncios no tienen `minimum_nights`.

**Reglas propuestas para silver (pendientes de validar).**
1. `price_num` numérico, conservando el texto original y validado contra `price_quote_price_per_night`.
2. Flags en lugar de borrar: `price_missing`, `price_outlier` (el 9999 y lo que decidamos) e `is_long_stay` (`minimum_nights` >= 28, umbral configurable).
3. Silver **limpia y marca**, no elimina ni imputa. Las exclusiones de negocio (por ejemplo, larga estancia fuera del comp set) van en gold o en las medidas.
4. ADR de referencia con **mediana** por barrio.

**Moneda.** El diccionario de datos de Inside Airbnb indica "local currency": `price` va en la moneda local (euros en España) y el `$` es solo formato.

**Pendiente (fuera del Paso 2).** Medir la larga estancia por zona y explorar `reviews`.

**Errores y lecciones.**
- Una hipótesis plausible ("los nulos son inactivos") era falsa. Se comprueba, no se supone.
- `sort_values()` deja los `NaN` al final: `.tail()` devolvía solo `NaN`. Hacer `dropna()` antes.
- `pd.crosstab` descarta las filas con `NaN`; el total no coincidía con el número de filas.
- Un indicador débil (`has_availability`, casi siempre `t`) llevó a una conclusión incompleta sobre los nulos de precio; `availability_365` la corrigió. Antes de fiarte de una columna, mira cómo se reparte.
- Un `.ipynb` guarda las salidas junto al código: no se commitea tal cual en un repo público.

---

## Paso 2 (continuación): `calendar` y deriva de esquema

**Grano.** El grano responde a "¿qué representa una fila?". En `calendar` de un snapshot es **un anuncio en una noche**. Al apilar snapshots hay que añadir `snapshot_date`: la misma noche aparece una vez por cada snapshot que la ve. Contar filas sin filtrar esa columna cuenta la misma noche varias veces; y comparar esa misma noche entre snapshots es, justamente, el pickup.

**Tamaño.** Euskadi 2026-06-30: 2.281.585 filas y 116 MB en memoria. Estimación de los 23 snapshots apilados: del orden de **100 millones de filas**, demasiado para pandas y adecuado para Spark y Delta.

**Hallazgos (Euskadi 2026-06-30).**
- 5 columnas: `listing_id`, `date`, `available`, `minimum_nights`, `maximum_nights`. **Sin precio.**
- `available`: 50,4 % `t` y 49,6 % `f`. `f` mezcla reservado, bloqueado por el propietario y anuncio cerrado, así que no es ocupación.
- 6.251 anuncios en `calendar` frente a 6.248 en `listings`: 3 huérfanos con IDs muy altos (anuncios nuevos entre ambos scrapes). Ningún anuncio de `listings` falta en `calendar`.
- No hay una fecha de captura única: la ventana empieza entre 06-30 y 07-03 según el anuncio, y se captura anuncio a anuncio. Para el pickup hay que usar la fecha real (`calendar_last_scraped`), no la nominal.
- Un anuncio tiene una ventana de 335 días; el resto, 365.

**Deriva de esquema (los 23 snapshots).**
- `calendar` tiene **7 columnas** (incluidas `price` y `adjusted_price`) hasta Barcelona 2026-01-18 y Euskadi 2025-09-29, y **5** a partir de ahí. Pero en los 9 snapshots que tienen esas columnas **`price` y `adjusted_price` están 100 % vacías** (comprobado en los 9: 0 % informado). El precio por noche **no existe en ningún snapshot**; el único precio disponible es el de `listings`.
- `listings` tiene 79, 85 o 90 columnas según el snapshot (aparecen `price_quote_*` y `hosts_time_as_host_*`).
- Consecuencia: silver no puede asumir un esquema fijo. Debe **declarar el schema a mano**, tolerar columnas ausentes y registrar qué snapshot trae qué.

**Errores y lecciones.**
- Generalicé "el calendar no tiene precio" desde un solo snapshot. Antes de afirmar algo del conjunto, se comprueba en el conjunto.
- Luego corregí al revés: vi columnas `price` en los `calendar` antiguos y supuse que traían datos. Estaban vacías. **Que una columna exista no significa que tenga datos**: se mide el % de valores informados.

---

## Cierre del Paso 2: columnas útiles y reglas para silver

**Columnas útiles para revenue.**

| Grupo | Columnas |
|---|---|
| Precio | `price` (de `listings`, texto con `$` y comas; la moneda es local) |
| Disponibilidad | `available` (de `calendar`), `availability_30/60/90/365` |
| Demanda | `number_of_reviews_ltm`, `reviews_per_month` |
| Segmentación (comp set) | `room_type`, `property_type`, `accommodates`, `bedrooms`, `neighbourhood_cleansed`, `minimum_nights` |
| Host | `host_id`, `calculated_host_listings_count` y sus variantes |
| Solo contraste | `estimated_occupancy_l365d`, `estimated_revenue_l365d` (modelo de Inside Airbnb, no se usan como métrica propia) |

**RevPAR aproximado.** `price` de `listings` x proporción de noches `f` de `calendar`, con `calendar` agregado primero al grano de `listings`. La ocupación es un **límite superior** (`f` mezcla reservas, bloqueos y anuncios cerrados) y el precio es el publicado. Sirve para comparar, no como ingreso real.

**Prototipo (Euskadi 2026-06-30).** De 6.248 anuncios quedan 5.454 en la base: se pierden 572 sin precio, 266 de larga estancia o sin dato y 1 con precio 9999, con solapes. Solo 25 de 206 zonas tienen 30 o más anuncios; con menos, la mediana no es fiable.

**Unidad geográfica.** En Euskadi `neighbourhood_cleansed` contiene **municipios**, no barrios (Donostia 1.316 anuncios, Gorliz 31). No son comparables en tamaño. En gold conviene una `dim_zona` con su nivel, y el comp set se define por zona + tipo de alojamiento + capacidad, no solo por geografía.

**Reglas de silver.**
1. Declarar el schema a mano y tolerar columnas ausentes (`listings` tiene 79, 85 o 90 columnas según el snapshot).
2. Detectar las columnas 100 % vacías por snapshot y no cargarlas, registrándolo.
3. `price_num`: quitar `$` y `,`, conservar el texto original y validar contra `price_quote_price_per_night` cuando exista.
4. Flags en lugar de borrar: `price_missing`, `price_outlier` (precio 9999) e `is_long_stay` (`minimum_nights` >= 28, umbral configurable).
5. Reparar la codificación de los textos con `Ã` (Euskadi: 1.692 filas y 20 nombres de zona; Barcelona no está afectada).
6. En `calendar`: añadir `snapshot_date`, usar la fecha real de captura y conservar los huérfanos marcándolos.
7. Agregar `calendar` al grano de `listings` antes de unir.
8. Silver limpia y marca; no imputa ni elimina. Las exclusiones de negocio van en gold.

**Por qué cada capa.** Bronze guarda el dato tal cual llega, sin tocarlo (por eso los acentos rotos se arreglan en silver y no en bronze). Silver limpia y da tipos. Gold modela para consumo.

---

## Paso 3, parte 1: silver de `listings` (Euskadi 2026-06-30)

Es la **especificación** de silver: las reglas se escriben y se prueban aquí con un snapshot y se aplicarán a los 23 en Fabric con PySpark. Evidencia en `notebooks/02_exploracion.ipynb`.

| Subpaso | Qué hace |
|---|---|
| 3.1 | Elegir 39 columnas (las 38 presentes en los 23 snapshots, más `price_quote_price_per_night`) y declarar los tipos a mano |
| 3.2 | Reparar acentos, `price_num` y flags |
| 3.3a | `has_availability` y `host_is_superhost` a booleano |
| 3.3b | `license` a categorías |
| 3.4 | Comprobaciones de calidad |
| 3.5 | Guardar en Parquet |

**3.1 Selección y tipos.** Se dejan fuera las 12 columnas vacías, los datos personales (`host_name`, descripciones, URLs) y `amenities`. Tipos: 15 `Int64` (enteros que admiten nulos), 12 `float64`, 8 `string` y 4 fechas. Los IDs de anuncios nuevos (~1,47 x 10^18) caben en `int64`, pero se corromperían en JavaScript o Excel.

**3.2 Flags y precio.** `price_num` a partir de `price` (conservando el original), más tres flags **sin nulos**: `price_missing` (572), `price_outlier` (precio 9999: 1) e `is_long_stay` (`minimum_nights` >= 28, umbral configurable: 264). Los acentos de las zonas se reparan solo si el texto contiene `Ã`, re-decodificando con `latin-1`.

**3.3a Booleanos.** `t`/`f` pasan a `boolean` (verdadero, falso y desconocido). Si aparece otro valor, la conversión **falla** y el mensaje dice columna y valor. Los nulos se quedan como nulos: los 26 de `has_availability` no tienen precio y 23 no tienen reseñas (anuncios nuevos); los 6 de `host_is_superhost` son de 2 hosts nuevos capturados el último día. Un nulo es "aún no se sabe", no `f`. El porcentaje de superhosts (39,4 %) se calcula sobre los 6.242 con dato.

**3.3b Licencias.** `license` mezcla un formato estructurado, textos libres y, a veces, posibles datos personales. Se convierte en `license_status` (`con_registro` 4.179, `exento` 1.232, `sin_dato` 738, `texto_libre` 99) y `exempt_type` (tourist apartment, rural tourism accommodation, hotel, hostel, seasonal rental...). **El texto original no se escribe en silver** (minimización de datos); sigue en bronze. El tipo de exento sirve para segmentar el comp set.

**3.4 Calidad.** 9 comprobaciones, todas a 0: ids únicos, coordenadas en Euskadi, `accommodates` > 0, disponibilidad coherente, precio > 0, fechas de reseñas coherentes, reseñas de 12 meses <= totales y flags sin nulos. En producción cada regla lleva una gravedad: **bloquea** (un `id` duplicado infla todas las medidas) o **avisa** (unas pocas coordenadas fuera de rango son un error local), con umbral: si falla un porcentaje alto de filas, también bloquea.

**3.5 Parquet.** `data/silver/listings/ciudad=euskadi/snapshot_date=2026-06-30/listings.parquet`: 6.248 filas, 46 columnas, 449 KB, sin `license`. Se conservan los tipos (booleanos, fechas, enteros con nulos), cosa que un CSV perdería. La carpeta por `ciudad` y `snapshot_date` es una **partición al estilo Hive**: el motor solo lee las carpetas que la consulta necesita (poda de particiones) y se puede recargar un único snapshot sin tocar los demás.

**Errores y lecciones.**
- `price_outlier` salió con 572 nulos: comparar un nulo con 9999 da "desconocido", no "falso". El test de regresión no lo vio porque `.sum()` ignora los nulos. Se añadió la comprobación "flags sin nulos".
- Corregir el código no corrige el fichero ya escrito: hay que **reprocesar**. Por eso el pipeline debe poder repetirse sin duplicar (idempotencia).
- Probar la reparación de acentos con todos los valores afectados, no con uno: `cp1252` fallaba en `Álava`.
- Un indicador débil (`has_availability`) puede llevar a una conclusión incompleta; mirar cómo se reparte antes de fiarse.

**Siguiente.** Pasar a Fabric: workspace, tres lakehouses, pipeline parametrizado y notebooks PySpark que apliquen estas reglas a los 23 snapshots.

---

## Paso 5 (Fabric): workspace, lakehouses e ingesta

**F1 Workspace.** `revenue-intelligence-airbnb` con el flujo de tareas **Medallón** (un mapa visual: no crea elementos, solo los organiza). La licencia Pro de partida era una prueba de Power BI y no daba capacidad de Fabric; la capacidad de prueba de Fabric se activó desde el perfil ("Iniciar la versión de prueba"). **Licencia y capacidad son cosas distintas**: la licencia es por usuario (publicar y compartir) y la capacidad es el cómputo del workspace (necesaria para lakehouses, notebooks y pipelines). La prueba caduca hacia 2026-12-03, así que el código y el modelo van a Git.

**F2 Lakehouses.** `lh_bronze`, `lh_silver` y `lh_gold`, sin esquemas. **Files** guarda ficheros crudos (bronze) y **Tables** guarda tablas Delta registradas (silver y gold); Direct Lake solo lee Delta de `Tables`. Cada lakehouse crea un **endpoint SQL** de solo lectura sobre sus tablas.

**F3 Ingesta (`pl_ingesta_snapshots`).**
- Conexión HTTP anónima a `data.insideairbnb.com`. Actividad **Copy data en formato binario** a `lh_bronze/Files/<ciudad>/<fecha>/`: el fichero llega idéntico y no se interpreta (si se convirtiera a Delta aquí, la deriva de esquema podría romper la carga y se perdería el original).
- Parámetros (todos de tipo Cadena): `ciudad`, `ruta`, `fecha` y `ruta_fichero` (lleva `data/` o `visualisations/`). Contenido dinámico: URL relativa con `concat`, y el nombre de archivo con `last(split(...))`. **Prueba de sensibilidad**: cambiar solo `ruta_fichero` a `visualisations/neighbourhoods.geojson` hizo aparecer ese fichero; repetir la copia sobrescribe, no duplica (idempotente).
- Lista de trabajo: `scripts/03_genera_lista_plana.py` genera `config/snapshots_flat.json` (92 elementos = 23 snapshots x 4 ficheros) a partir de `config/snapshots.yaml`, y se sube a `lh_bronze/Files/config/`. La actividad **Lookup** `lk_lista_snapshots` la lee con "solo la primera fila" desmarcado (devuelve `count: 92`).
- **ForEach** `fe_snapshots` sobre `@activity('lk_lista_snapshots').output.value`, no secuencial y con 4 lotes (para no saturar el servidor ajeno). Fabric no permite un ForEach dentro de otro, por eso la lista es plana. Dentro, `copy_snapshot_file` usa `item().ciudad`, `item().fecha`... en vez de `pipeline().parameters`.
- Prueba con `take(..., 3)`: apareció `barcelona/2025-08-10` con `calendar`, `listings` y `reviews`.

**Cierre de F3.** Sin el `take`, el pipeline ejecutó los 92 en 9 min 38 s (94 filas de salida: Lookup, ForEach y 92 copias) con estado Correcto. Un ForEach se marca como fallido si falla cualquier vuelta, así que Correcto implica las 92. Como el estado no basta, se verificó el **contenido** con el notebook `nb_00_verifica_bronze` (Python en Fabric, con `lh_bronze` como lakehouse predeterminado, ruta `/lakehouse/default/Files`): compara el **conjunto esperado** (leído de `snapshots_flat.json`) con el **encontrado** (`os.listdir`) y resultó `esperados: 92 | encontrados: 92`, `faltan: []`, `sobran: []`. Comparar conjuntos dice **cuál** falta o sobra, cosa que un simple recuento no detecta (un faltante y un sobrante se compensan).

**Errores y lecciones.**
- Un `pipeline().parameters.X` dentro del ForEach habría escrito los 92 ficheros en la misma carpeta, sobrescribiéndose, y el pipeline habría salido en verde: un **fallo silencioso**. Se comprueba el resultado, no solo el estado.
- Los reintentos son seguros porque la copia es idempotente (sobrescribe); con "añadir filas" podrían duplicar.
- El editor de expresiones avisó de un tipo en `last(split(...))` y **Evaluar expresión** lo dio por bueno: manda la evaluación, y se confirma con Validar y con una ejecución.
- Un fichero ausente devuelve 403; dentro de un ForEach no tumba las otras vueltas, pero deja el conjunto marcado como fallido.

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
| **Grano** | Qué representa exactamente una fila de una tabla. En `fact_calendar` con snapshots apilados: anuncio + noche + snapshot. |
| **Deriva de esquema** | La fuente cambia columnas con el tiempo sin avisar (`listings` pasa de 79 a 90 columnas). |
| **Flag** | Columna que marca un caso (por ejemplo `price_outlier`) en lugar de borrar la fila. |
| **Mojibake** | Texto con codificación rota (`SebastiÃ¡n` en vez de `Sebastián`). |
| **Validación de datos** | Comprobación automática antes de seguir (por ejemplo, precio parseado frente a `price_quote`); si falla, el pipeline para y avisa o marca. |
| **Parquet** | Formato columnar que conserva los tipos y comprime mucho; es la base de Delta en Fabric. |
| **Partición Hive** | Carpetas por valor de columna (`ciudad=euskadi/snapshot_date=2026-06-30/`); el motor lee solo las que necesita (poda de particiones). |
| **Minimización de datos** | No cargar lo que no se necesita, sobre todo datos personales (privacy by design). |
| **Fallar rápido** | Detener el proceso ante un valor inesperado, con un mensaje claro, en vez de convertirlo en silencio. |
| **Boolean nullable** | Tipo con tres estados: verdadero, falso y desconocido. |

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
