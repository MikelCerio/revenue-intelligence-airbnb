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
| 4 | Hecho | Modelo gold: 4 dimensiones y 2 hechos en `lh_gold` |
| 5 | En curso | Workspace, Git, ingesta, silver, gold y modelo semántico Direct Lake con medidas y avisos; falta silver de reviews y geojson |
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

## Paso 5 (continuación), F4: silver de `listings` en PySpark

El notebook `nb_01_silver_listings` reproduce en PySpark las reglas del Paso 3 y se comprobó contra pandas con los mismos números.

- **4a Lectura.** `multiLine=True` y `escape='"'`: los textos largos traen saltos de línea dentro de comillas. Sin `multiLine` salen 10.128 filas; con él, 6.248 (como pandas). Spark lee por defecto línea a línea; pandas lo gestiona solo.
- **4b Columnas y tipos.** Las mismas 39 columnas: 15 enteros largos, 12 decimales, 4 fechas y 8 textos. Nulos idénticos a pandas.
- **4c Reglas.** `price_num` con `regexp_replace`; flags con `coalesce(..., False)` para que nunca sean `NULL` (comparar un nulo con 9999 da "desconocido", no "falso"); `t`/`f` a booleano con aserción que falla si aparece otro valor; acentos reparados con `encode`/`decode` nativos de Spark (ISO-8859-1), solo si el texto contiene `Ã`; `license` convertida en `license_status` y `exempt_type` y eliminada en la misma operación.
- **4c-4 Calidad.** Con gravedad: **bloquean** `id` duplicados y flags con nulos (`assert`); **avisan** coordenadas, rangos y fechas. Si un aviso afecta a un porcentaje alto de filas, se trataría como bloqueante.
- **4d Escritura.** Tabla Delta en `lh_silver/Tables/listings` (ruta `abfss://...`), `partitionBy("ciudad", "snapshot_date")` y `replaceWhere`: reemplaza solo la partición del snapshot, así que repetir no duplica ni toca los demás (idempotente). Un `overwrite` normal habría borrado el resto.
- **4e Parámetros y pipeline.** `CIUDAD` y `SNAPSHOT` en una celda marcada como de parámetros, con valores por defecto; el pipeline los sustituye. `pl_silver_listings`: Lookup (92) -> Filter (`ruta_fichero = data/listings.csv.gz`, 23) -> ForEach (lotes de 2) -> actividad Notebook con `@item().ciudad` y `@item().fecha`. Prueba con `take(..., 2)` y después los 23: 26 filas de salida (23 notebooks más 3) y **23 particiones** (11 de Barcelona y 12 de Euskadi).

**Comprobaciones de coherencia.** 19.325 anuncios x 365 noches = 7.053.625, y el `calendar` de ese snapshot tiene 7.053.632 filas. Barcelona pasa de 19.325 anuncios (2025-08-10) a 15.293 (2026-06-24), un descenso de ~21 %: observación a revisar, sin causa asumida.

**Errores y lecciones.**
- Un valor escrito a mano dentro de un bucle (`euskadi`, `2026-06-30` en los parámetros del notebook) habría cargado siempre el mismo snapshot con todo en verde. Dentro del bucle van `@item()`, no literales.
- En una expresión la `@` va solo al principio (`@take(activity(...), 2)`), y el `take` de prueba debe apuntar a la lista **filtrada**, no al Lookup de 92.
- Un `ForEach` con notebooks lanza una sesión de Spark por llamada: lotes bajos para no agotar la capacidad del trial.
- Variables como `destino` viven en la sesión del notebook: si se reinicia, hay que redefinirlas.

---

## Paso 5 (continuación): reconstrucción del workspace y Git

**Por qué hubo que reconstruir.** El primer workspace se creó como **"área de trabajo de aplicación de plantilla"** (casilla de las opciones avanzadas al crearlo): un tipo especial que **no admite Git** y que no se puede cambiar después. Se renombró a `revenue-intelligence-airbnb-old` y se creó uno normal. Se hizo **primero el nuevo y solo después se retira el viejo**, para no perder trabajo.

**Qué se recuperó y cómo.**
- Los datos de `lh_bronze` y `lh_silver` no se migran: se regeneran ejecutando los pipelines.
- Los notebooks se exportaron como `.ipynb` (carpeta `fabric/` del repo) y se importaron en el nuevo; al importar **recuerdan el lakehouse del workspace viejo**, así que hay que quitarlo y añadir el nuevo como predeterminado.
- Copiar y pegar actividades entre pipelines no funcionó: se recrearon a mano (están descritos más arriba).

**Git integration con GitHub.**
- Requisitos: capacidad de Fabric, el interruptor del tenant para sincronizar con GitHub, y un **token de acceso personal fine-grained** limitado a un solo repositorio con **Contents: Read and write** (Metadata de solo lectura lo añade GitHub). El token se pega solo en Fabric, nunca en chats.
- El error "las credenciales del proveedor de Git no están autorizadas" se debió a un token con **ningún permiso** (el repo seleccionado no basta: hay que añadir los permisos).
- Conexión: rama `master`, carpeta `workspace` (la carpeta `fabric/` guarda las exportaciones manuales, con otro formato). Cada elemento nuevo aparece en Control de código fuente y se confirma con un clic.

**Silver de `listings` en el workspace nuevo.** Con `pl_silver_listings` (Lookup, Filter, ForEach y Notebook) se cargaron los 23 snapshots: la tabla `listings` de `lh_silver` tiene **23 particiones**.

**Errores y lecciones.**
- Los parámetros base de la actividad Notebook estaban guardados como **texto fijo** (`euskadi`, `2026-06-30`) en vez de `@item().ciudad` y `@item().fecha`. Las dos llamadas escribían la misma partición, y una falló con `ConcurrentAppendException` mientras la otra salía "Correcto" **sin haber cargado Barcelona**. El estado no basta: se comprobó el contenido.
- La fuente de verdad es el **JSON del pipeline** (vista de código), no lo que muestra el cuadro de configuración.
- Se añadió `print("PROCESANDO:", CIUDAD, SNAPSHOT)` justo debajo de la celda de parámetros: en la instantánea de cada ejecución se ve qué valores recibió el notebook.
- Dos escrituras concurrentes sobre la misma partición provocan conflicto en Delta; sobre particiones distintas (cada snapshot la suya) no.

---

## Paso 4 (gold): modelo estrella

Silver `calendar` (23 particiones, **88.672.422 filas**, sin pérdidas respecto a bronze) y silver `listings` alimentan el gold, que se construye con el notebook `nb_10_gold_dimensiones` y se escribe en `lh_gold`.

| Tabla | Grano | Filas |
|---|---|---|
| `dim_snapshot` | un snapshot (ciudad + fecha), con `snapshot_id` = `ciudad_yyyymmdd` | 23 |
| `dim_zona` | una zona (municipio en Euskadi, barrio en Barcelona) y su grupo (provincia o distrito) | 286 |
| `dim_listing` | un anuncio, con sus atributos más recientes y `primera_vez`, `ultima_vez`, `n_snapshots` | ~34.000 |
| `dim_fecha` | un día, de 2025-07-01 a 2027-12-31 | 914 |
| `fact_listing_snapshot` | un anuncio en un snapshot (precio, flags, disponibilidad, reseñas) | 242.766 |
| `fact_calendar` | una noche de un anuncio visto desde un snapshot | 88.672.422 |

**Decisiones.**
- **Snapshots parciales.** Algunos snapshots de Inside Airbnb vienen incompletos de origen (Barcelona 2026-04-20: 7.277 anuncios frente a ~15.000; 2026-02-18: 12.786). `dim_snapshot.es_completo` los **marca** (anuncios >= 85 % de la mediana de su ciudad), no los borra, y las medidas de altas, bajas y pickup deben excluirlos. Sin ello habría bajas falsas.
- **Claves de una columna.** Las relaciones del modelo admiten una sola columna: `snapshot_id` (hechos y `dim_snapshot`), `zona_id` (`ciudad|zona`) y `listing_id`.
- **Dimensión frente a hecho.** La dimensión describe al anuncio (tipo, capacidad, zona); el hecho mide lo que cambia en cada foto (el precio de ese mes). Por eso el precio no está en `dim_listing`.
- **Antelación (`dias_antelacion`).** Precalculada en `fact_calendar` para el pickup. La captura de un snapshot dura varios días (hasta ~12), así que la fecha nominal desplaza la antelación (máximo 377). Se usa la **fecha real de captura** de cada anuncio (`calendar_last_scraped`); para los 62.780 sin ella (anuncios que están en `calendar` pero no en `listings`) se estima con la primera fecha de su calendario y se marcan con `sin_fecha_captura`. Rango resultante: -1 a 364 (el -1 es un día por la zona horaria).
- **Estrategia de escritura.** Dimensiones pequeñas derivadas: `overwrite` completo (barato y siempre coherente con silver). Hechos grandes: particionados por snapshot; hoy se reescriben enteros y queda como mejora la carga incremental con `replaceWhere`.
- **`dim_zona`.** `assert` de que cada zona pertenece a un solo grupo: si no, las sumas por grupo se duplicarían. Hay más zonas que en un solo snapshot (215 y 71) porque algunas solo aparecen en ciertos meses.
- **`dim_listing` y censura.** `primera_vez` es la primera vez que se **observa** el anuncio dentro de la ventana (agosto 2025 a junio 2026), no su fecha de alta. La rotación de Barcelona (12 % de anuncios en un solo snapshot) está inflada por los snapshots parciales.
- **`dim_fecha`.** Tabla de fechas completa y sin huecos, con comprobación de que cubre todas las fechas de `fact_calendar`.

**Errores y lecciones.**
- Las variables del notebook (`Window`, `destino`...) desaparecen al reiniciar la sesión: tras un reinicio, primero la celda de imports y lecturas; un notebook debe poder ejecutarse de arriba abajo.
- La fecha nominal de un snapshot no es la fecha de captura: comprobar el rango de la antelación por snapshot destapó el desfase.
- Cuando falta un dato, la reserva debe ser la mejor inferencia posible (primera fecha del calendario), no una cifra peor, y se deja un flag.
- Un recuento de silver igual al de bronze es la prueba de contenido más fuerte; los recuentos por snapshot además revelaron los parciales.

---

## Modelo semántico Direct Lake (`sm_revenue_airbnb`)

Modelo sobre las 6 tablas de `lh_gold`, **Direct Lake**: lee las tablas Delta directamente, sin copiar datos ni refresco programado.

**Relaciones** (todas muchos a uno, filtro en una sola dirección, de la dimensión al hecho): `fact_calendar` y `fact_listing_snapshot` con `dim_snapshot` por `snapshot_id`; los dos hechos con `dim_listing` por `listing_id`; `dim_listing` con `dim_zona` por `zona_id`; `fact_calendar` con `dim_fecha` por `fecha`. Verificado con una consulta que cruza dimensión y hecho: Euskadi 25.509.090 filas en 12 snapshots y Barcelona 63.163.332 en 11, iguales a los totales de silver.

**Medidas** (carpeta Revenue):
- `Ocupacion aprox 30d`: noches `available = false` entre noches totales, solo con `dias_antelacion` de 0 a 29. Una misma noche aparece en varios snapshots; mirar los 30 días siguientes a cada captura compara fotos del mismo horizonte. Es un límite superior de la ocupación real (`f` mezcla reservas, bloqueos y anuncios cerrados).
- `ADR mediano`: mediana del precio publicado, sin precios nulos, sin el valor 9999 y sin larga estancia (los flags de silver). Es precio publicado, no cobrado.
- `RevPAR aprox 30d`: ADR mediano por ocupación aproximada; indicador comparativo, no ingreso real.
- `Anuncios`: anuncios distintos en el contexto.
- Avisos (carpeta Avisos): `Nota precio` y `Nota cobertura` devuelven un texto solo cuando la selección incluye snapshots sin precio o parciales; se adaptan al filtro.

**Primeros resultados** (último snapshot completo): Barcelona 2026-06-24, ocupación 66,6 %, ADR 252 € y RevPAR aprox. 167,9 €; Euskadi 2026-06-30, 69,3 %, 199,8 € y 138,4 €. La ocupación a 30 días de Euskadi muestra la estacionalidad: 76 % en julio de 2025, 36 % en diciembre y 69 % en junio de 2026.

**Hallazgos sobre el precio.**
- **Dic 2025, ene y feb 2026: 100 % de anuncios sin precio en bronze**, en las dos ciudades (origen, no un fallo del modelo). El ADR devuelve vacío, que es más honesto que 0 (un precio de 0 € diría "gratis"; vacío dice "no se sabe"). `dim_snapshot.tiene_precio` y `pct_sin_precio` lo marcan.
- **Desde marzo 2026 aparecen columnas `price_quote_*`** con una fecha de check-in distinta en cada snapshot (de 6 a 45 días después de la captura). Hipótesis, no hecho: el precio pasa a ser la cotización de una estancia concreta, por lo que el ADR no es comparable con los meses anteriores. La mediana de Barcelona pasa de 113 € (nov) a 177 y 277 € (primavera), que no es el mercado sino, probablemente, un cambio de método. Se declara como limitación y no se compara el ADR entre ambos periodos.

**Cosas aprendidas.**
- Tras crear relaciones en un modelo Direct Lake hay que **refrescar** (reapunta a las tablas Delta, no copia datos); sin ello la consulta falla con "la relación debe recalcularse".
- Un refresco **no añade columnas nuevas** de la tabla Delta: se declaran en el modelo (`pct_sin_precio`, `tiene_precio`). En Direct Lake no hay columnas calculadas sobre tablas del lakehouse, así que lo derivado va en gold.
- La herramienta MCP de Power BI se autentica **por su cuenta** (no reutiliza la sesión abierta del navegador, por seguridad) y pide un inicio de sesión interactivo; la conexión caduca y hay que repetirla.
- 31.390 filas de `fact_calendar` (0,04 %) corresponden a anuncios que nunca aparecen en `listings`: salen como "(en blanco)" en los análisis por zona.

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
