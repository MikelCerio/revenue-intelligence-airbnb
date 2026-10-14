# Ampliación Bilbao: oferta por distrito, ingreso estimado, costes e impuesto turístico

Qué se hace, con qué datos y cuántos, paso a paso. Todo se reproduce con `python scripts/bilbao_open_data.py`, que imprime los recuentos de cada paso. Las salidas son tablas **agregadas** en `outputs/bilbao/`; los datos crudos quedan en `data/opendata/` (fuera de Git).

> **Corrección (14/10/2026).** La primera versión usaba el precio del snapshot de junio de 2026. Desde marzo de 2026 ese precio es una cotización para fechas cercanas a la captura, así que en junio son precios de verano e inflaban el año entre un 15 % y un 35 %. Ahora el precio de cada piso es la **mediana de sus precios de marzo a junio de 2026**. Las cifras de este documento ya están corregidas.

## 1. Fuentes

| Fuente | Qué se usa | Filas usadas |
|---|---|---|
| Inside Airbnb, Euskadi, snapshots de marzo a junio de 2026 | Ubicación aproximada, tipo de alojamiento, capacidad, estancia mínima, reseñas y precio | 1.599 anuncios en Bilbao (junio) |
| Bilbao Open Data: habitantes por distrito, sección y edad (2022) | Habitantes por sección censal | 278 secciones, 344.678 habitantes |
| Bilbao Open Data: distritos y secciones (2022) | Nombre de cada distrito | 8 distritos |
| INE: cartografía de secciones censales (1-ene-2024) | Polígonos de las secciones de Bilbao, que se unen en distritos | 273 secciones |
| Registro de viviendas de uso turístico de Euskadi | Comprobación del total de Bilbao | 1.019 viviendas en Bilbao |
| Gobierno Vasco, EMAL 2025 | Renta del alquiler largo | Capitales y áreas funcionales |

No se usa el callejero de portales ni ninguna dirección. **No existe un mapa oficial de barrios de Bilbao** (el IGN llega solo a municipio y el Ayuntamiento publica la lista de barrios sin geometría), así que el nivel de análisis es el **distrito**.

## 2. Pasos

1. **Distritos.** Las 273 secciones censales del INE de Bilbao (municipio 48020) se agrupan por código de distrito y se unen en 8 polígonos.
2. **Anuncios a distrito.** Cada anuncio se asigna al distrito que contiene su punto. Quedan fuera 6 de 1.599 (0,4 %). Las coordenadas de Inside Airbnb están desplazadas hasta unos 150 m a propósito; por eso solo se publican agregados.
3. **P1, oferta.** Pisos completos por distrito ÷ habitantes × 1.000.
4. **P2, ingreso estimado.** Pisos completos de corta estancia (mínimo de 30 noches o menos), con al menos una reseña en 12 meses y precio: 895 pisos.
   - Noches al año = reseñas de 12 meses ÷ 0,5 × máximo(3 noches, estancia mínima), con un tope del 70 % del año.
   - Ingreso mensual = noches × precio por noche ÷ 12.
   - Se muestran la mediana y el rango intercuartílico; las celdas con menos de 10 pisos no se publican.
5. **P3, impuesto.** Impuesto por estancia = 6,50 € × personas × mínimo(noches, 6).
6. **P4, costes.** Neto del piso mediano de cada distrito con tres escenarios (sección 6).
7. **P5, comparativa.** Lo mismo por municipio: Bilbao, Donostia, la costa y Vitoria-Gasteiz.
8. **P6, tamaño del mercado.** Cada piso se compara con sus iguales (mismo distrito y capacidad: 1-2, 3-4, 5-6, 7 o más personas; solo grupos de 10 o más).

## 3. Supuestos y cómo afectan

| Supuesto | Valor | Sensibilidad |
|---|---|---|
| Estancias que dejan reseña | 50 % | Si fueran el 40 %, el ingreso subiría un 25 % |
| Estancia media | 3 noches | **Es el que más pesa:** con 2 noches el ingreso baja un tercio; con 4 sube un tercio |
| Tope de ocupación | 70 % | Lo alcanza el 13,5 % de los pisos |
| Precio | Mediana de marzo a junio de 2026 | Sin invierno (diciembre a febrero no traen precio): en la costa, todavía algo alto |
| Tarifa del impuesto | 6,50 € por persona y noche, tope de 6 noches | Anuncios municipales y prensa de 2026; confirmar en las ordenanzas |

El ingreso es una **estimación con método conocido** (el de Inside Airbnb), no un dato real.

## 4. Resultados

**P1. Pisos completos por cada 1.000 habitantes**: Ibaiondo 6,2 · Uribarri 4,6 · Abando 4,5 · Begoña 1,8 · Deustu 1,6 · Basurtu-Zorrotza 1,5 · Errekalde 1,3 · Otxarkoaga-Txurdinaga 0,4 · **Bilbao 3,1**. Inside Airbnb da 1.055 pisos completos y el registro oficial, 1.019 viviendas.

**P2. Ingreso bruto mensual estimado (mediana y rango 25 % a 75 %)**: Abando 1.481 € (609 € a 2.635 €) · Ibaiondo 1.415 € (589 € a 2.648 €) · Uribarri 1.268 € · Errekalde 1.013 € · Basurtu-Zorrotza 823 € · Deustu 740 € · Begoña 511 € · **Bilbao 1.188 € (488 € a 2.417 €)**. Precio por noche mediano de Bilbao: 163 €. Otxarkoaga-Txurdinaga tiene solo 10 pisos activos y no se interpreta.

**P3. Impuesto para 2 adultos**: 13 € por noche, el **8 %** del precio mediano de Bilbao, en cualquier estancia de 1 a 6 noches. Baja a partir de la séptima: 4,8 % con 10 noches y 1,6 % con 30. Con 4 adultos, el 16 %.

## 5. Límites

- Habitantes de 2022 y cartografía de 2024; los distritos casan.
- Un anuncio junto a una frontera puede cambiar de distrito según cómo se dibuje: en distritos pequeños, las medianas son sensibles.
- El ingreso es bruto: los costes se tratan en la sección 6.

## 6. Modelo de costes (P4)

Neto mensual del piso mediano de cada distrito, **antes de hipoteca e impuestos**. Todos los costes son parámetros editables en el script (`ESCENARIOS`), con su fuente o la marca SUPUESTO.

| Concepto | Propietario solo | Con gestora | Gestora con escala | Fuente |
|---|---|---|---|---|
| Comisión de plataforma | 18,76 % | 18,76 % | 10,9 % | Airbnb solo anfitrión 15,5 % + IVA no recuperable; con escala, 30 % de reservas directas (SUPUESTO) |
| Comisión de gestora | — | 20 % | — | Rango habitual 15-30 % |
| Limpieza por estancia | 55 € | 55 € | 35 € | SUPUESTO (no hay cifra pública en Bilbao) |
| Suministros | 180 €/mes | 180 €/mes | 180 €/mes | Medias de hogar 2026 + internet + rotación |
| Comunidad, seguro, IBI y basura | 150 €/mes | 150 €/mes | 150 €/mes | Medias de propietario |
| Software | — | — | 25 €/mes | SUPUESTO |
| Mantenimiento | 3 % | 3 % | 2 % | SUPUESTO |

Alquiler largo de referencia: 1.011,1 €/mes (EMAL, contratos nuevos de Bilbao, 4.º trimestre de 2025), menos comunidad, seguro e IBI = **861 €/mes netos**.

| Distrito | Bruto | Propietario solo | Con gestora | Gestora con escala |
|---|---|---|---|---|
| Abando | 1.481 € | 701 € | 404 € | 854 € |
| Ibaiondo | 1.415 € | 621 € | 338 € | 779 € |
| Uribarri | 1.268 € | 524 € | 271 € | 662 € |
| Errekalde | 1.013 € | 357 € | 154 € | 461 € |
| Basurtu-Zorrotza | 823 € | 223 € | 58 € | 304 € |
| Deustu | 740 € | 143 € | −5 € | 222 € |
| Begoña | 511 € | 6 € | −97 € | 50 € |

Un propietario solo cubre los gastos fijos con unas 3 noches al mes a 163 €, pero necesita unas **11 noches al mes** para igualar el alquiler largo neto; el piso mediano de Bilbao hace entre 3,5 y 8,5. **El turístico mediano no supera al alquiler largo en ningún distrito**; en Abando, una gestora con escala empata.

**Límites.** El precio no incluye la tarifa de limpieza que paga el huésped: si se cobra aparte, el neto sube unos 100-130 €/mes. Se combina el ingreso mediano con las noches medianas del distrito, que no son del mismo piso. No incluye mobiliario, vacíos ni impagos del alquiler largo.

## 7. Comparativa por municipio (P5)

| Municipio | Pisos | Precio | Noches/mes | Bruto | Neto del dueño | Alquiler largo neto | Turístico ÷ largo |
|---|---|---|---|---|---|---|---|
| Donostia-San Sebastián | 969 | 321 € | 7,5 | 2.426 € | 1.430 € | 982 € | 1,46 |
| Bilbao | 895 | 163 € | 7,0 | 1.188 € | 471 € | 861 € | 0,55 |
| Sopelana | 44 | 204 € | 4,8 | 1.020 € | 379 € | 684 € | 0,55 |
| Getxo | 100 | 164 € | 5,0 | 894 € | 278 € | 684 € | 0,41 |
| Hondarribia | 107 | 188 € | 4,0 | 822 € | 240 € | 781 € | 0,31 |
| Zarautz | 142 | 211 € | 3,5 | 727 € | 175 € | 628 € | 0,28 |
| Vitoria-Gasteiz | 80 | 149 € | 4,5 | 682 € | 121 € | 701 € | 0,17 |

Alquiler largo: capitales con contratos nuevos (4.º trimestre de 2025); el resto, renta media de los contratos vigentes de su área funcional (EMAL). Bakio, Bermeo, Lekeitio y Mundaka quedan entre 0 y 0,15. **Donostia es el único municipio donde el turístico mediano gana claramente al alquiler largo.**

## 8. Tamaño del mercado (P6)

De 820 pisos comparados en 16 grupos, 119 pisos con 10 o más reseñas ingresan menos que el 75 % de sus iguales: les faltan unos **113.100 € al mes** en total (mediana de 960 € por piso) para llegar a la mediana de su grupo. Otros 52 pisos están "baratos y llenos" (114 € frente a 156 € de sus iguales). Del total que falta, Ibaiondo, Abando y Uribarri suman el 88 %. De los que rinden poco, el 43 % tiene menos de 10 reseñas y el 43 % deja libres 270 días o más: no todos están mal gestionados.

## 9. Paso a Fabric (pendiente)

1. Subir a `lh_bronze/Files/opendata/` las fuentes públicas.
2. Notebook silver: secciones del INE de Bilbao a distritos (polígonos como texto WKT) y habitantes por distrito.
3. Notebook gold: `dim_distrito`, la asignación de cada anuncio a su distrito, el precio de referencia y las tablas `fact_oferta_distrito`, `fact_ingreso_distrito` y `param_impuesto`.
4. Modelo semántico: pisos por 1.000 habitantes, ingreso mediano y simulador del impuesto con parámetros.
5. Página de informe: Bilbao por distrito y simulador del impuesto.
