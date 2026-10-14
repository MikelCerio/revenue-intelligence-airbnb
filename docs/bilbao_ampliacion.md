# Ampliación Bilbao: oferta por distrito, ingreso estimado e impuesto turístico

Qué se hace, con qué datos y cuántos, paso a paso. Todo se reproduce con `python scripts/bilbao_open_data.py`, que imprime los recuentos de cada paso. Las salidas son tablas **agregadas** en `outputs/bilbao/`; los datos crudos quedan en `data/opendata/` (fuera de Git).

## 1. Fuentes

| Fuente | Qué se usa | Filas usadas |
|---|---|---|
| Inside Airbnb, Euskadi, snapshot 2026-06-30 | Ubicación aproximada, tipo de alojamiento, estancia mínima, reseñas de 12 meses y precio | 1.599 anuncios en Bilbao |
| Bilbao Open Data: habitantes por distrito, sección y edad (2022) | Habitantes por sección censal | 278 secciones, 344.678 habitantes |
| Bilbao Open Data: distritos y secciones (2022) | Nombre de cada distrito | 8 distritos |
| INE: cartografía de secciones censales (1-ene-2024) | Polígonos de las secciones de Bilbao, que se unen en distritos | 273 secciones |
| Registro de viviendas de uso turístico de Euskadi | Comprobación del total de Bilbao y reparto por código postal | 1.019 viviendas en Bilbao |

No se usa el callejero de portales ni ninguna dirección. **No existe un mapa oficial de barrios de Bilbao** (el IGN llega solo a municipio y el Ayuntamiento publica la lista de barrios sin geometría), así que el nivel de análisis es el **distrito**.

## 2. Pasos

1. **Distritos.** Las 273 secciones censales del INE de Bilbao (municipio 48020) se agrupan por código de distrito y se unen en 8 polígonos, en coordenadas geográficas.
2. **Anuncios a distrito.** Cada anuncio se asigna al distrito que contiene su punto. Quedan fuera 6 de 1.599 (0,4 %). Las coordenadas de Inside Airbnb están desplazadas hasta unos 150 m a propósito, así que un anuncio junto a una frontera puede caer en el distrito vecino. Por eso solo se publican agregados.
3. **P1, oferta.** Pisos completos por distrito ÷ habitantes × 1.000.
4. **P2, ingreso estimado.** Solo pisos completos de corta estancia (mínimo de 30 noches o menos) con al menos una reseña en 12 meses y precio: 879 pisos.
   - Noches al año = reseñas de 12 meses ÷ 0,5 × máximo(3 noches, estancia mínima), con un tope del 70 % del año.
   - Ingreso mensual = noches × precio por noche ÷ 12.
   - Se muestran la mediana y el rango intercuartílico. Las celdas con menos de 10 pisos no se publican.
5. **P3, impuesto.** Impuesto por estancia = 6,50 € × personas × mínimo(noches, 6), calculado por persona y noche.

## 3. Supuestos y cómo afectan

| Supuesto | Valor | Sensibilidad |
|---|---|---|
| Estancias que dejan reseña | 50 % | Si fueran el 40 %, el ingreso subiría un 25 % |
| Estancia media | 3 noches | **Es el que más pesa:** con 2 noches el ingreso mediano de Bilbao baja a 940 €/mes; con 4, sube a 1.855 € |
| Tope de ocupación | 70 % | Lo alcanza el 13,7 % de los pisos |
| Precio | Precio publicado por noche | Es el de una cotización concreta (coincide al 100 % con `price_quote_price_per_night`), no el cobrado |
| Tarifa del impuesto | 6,50 € por persona y noche, tope de 6 noches | Recogido de prensa y anuncios municipales; confirmar en las ordenanzas publicadas |

Estos supuestos son los mismos que usa Inside Airbnb en su estimación (`estimated_revenue_l365d`), y la réplica da la misma mediana. Por eso el ingreso es una **estimación con método conocido, no un dato real**.

## 4. Resultados

**P1. Pisos completos por cada 1.000 habitantes**: Ibaiondo 6,2 · Uribarri 4,6 · Abando 4,5 · Begoña 1,8 · Deustu 1,6 · Basurtu-Zorrotza 1,5 · Errekalde 1,3 · Otxarkoaga-Txurdinaga 0,4 · **Bilbao 3,1**. Comprobación: Inside Airbnb da 1.055 pisos completos en Bilbao y el registro oficial, 1.019 viviendas.

**P2. Ingreso bruto mensual estimado (mediana y rango 25 % a 75 %)**: Abando 1.640 € (675 € a 3.048 €) · Ibaiondo 1.599 € (668 € a 2.943 €) · Uribarri 1.407 € · Errekalde 1.264 € · Basurtu-Zorrotza 968 € · Deustu 904 € · Begoña 600 € · **Bilbao 1.397 € (561 € a 2.817 €)**. Otxarkoaga-Txurdinaga tiene solo 10 pisos activos y no se interpreta.

**P3. Impuesto para 2 adultos y un precio de 190 € por noche (mediana de Bilbao)**: 13 € por noche, el 6,8 % del precio, en cualquier estancia de 1 a 6 noches. Solo baja a partir de la séptima noche: 4,1 % con 10 noches y 1,4 % con 30. Con 4 adultos son 26 € por noche, el 13,7 % del precio.

## 5. Límites

- Los habitantes son de 2022; la cartografía, de 2024. Las secciones cambian poco y los distritos casan.
- Un distrito mezcla zonas muy distintas, pero no hay geometría oficial de barrios.
- Un anuncio junto a una frontera puede cambiar de distrito según cómo se dibuje la frontera: en una versión simplificada de los polígonos, un anuncio pasó de distrito y la mediana de Errekalde se movió de 1.264 € a 1.396 €. En distritos pequeños, las medianas son sensibles.
- El ingreso es bruto: no descuenta comisiones, limpieza, suministros, gestión ni impuestos.

## 6. Paso a Fabric (pendiente)

1. Subir a `lh_bronze/Files/opendata/` las tres fuentes públicas.
2. Notebook silver: secciones del INE de Bilbao a distritos (los polígonos se guardan como texto WKT) y habitantes por distrito.
3. Notebook gold: `dim_distrito` (código, nombre, habitantes, geometría), la asignación de cada anuncio a su distrito y las tablas `fact_oferta_distrito`, `fact_ingreso_distrito` y `param_impuesto`.
4. Modelo semántico: medidas de pisos por 1.000 habitantes, ingreso mediano y simulador del impuesto con parámetros (personas y noches).
5. Página de informe: Bilbao por distrito y simulador del impuesto.

## 7. Modelo de costes (P4)

Neto mensual del piso mediano de cada distrito, **antes de hipoteca e impuestos**, con tres escenarios. Todos los costes son parámetros editables en el script (`ESCENARIOS`), con su fuente o la marca SUPUESTO.

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
| Abando | 1.640 € | 825 € | 497 € | 993 € |
| Ibaiondo | 1.599 € | 765 € | 445 € | 939 € |
| Uribarri | 1.407 € | 633 € | 352 € | 784 € |
| Errekalde | 1.264 € | 549 € | 296 € | 677 € |
| Basurtu-Zorrotza | 968 € | 336 € | 142 € | 431 € |
| Deustu | 904 € | 276 € | 95 € | 368 € |
| Begoña | 600 € | 75 € | −45 € | 127 € |

Un propietario que gestiona solo su piso cubre los gastos fijos con unas 2,5 noches al mes a 190 €, pero necesita unas **9 noches al mes** para igualar el alquiler largo neto; el piso mediano de Bilbao hace entre 3,5 y 8,5 según el distrito.

**Límites.** El precio de Inside Airbnb no incluye la tarifa de limpieza que paga el huésped: si se cobra aparte, el neto sube unos 100-130 €/mes y el piso mediano del centro empata con el alquiler largo. Se combina el ingreso mediano con las noches medianas del distrito, que no son del mismo piso. No incluye mobiliario, vacíos ni impagos del alquiler largo.
