# Ampliación Bilbao: oferta por distrito, ingreso estimado, costes e impuesto turístico

Qué se hace, con qué datos y cuántos, paso a paso. Todo se reproduce con `python scripts/bilbao_open_data.py`, que imprime los recuentos de cada paso. Las salidas son tablas **agregadas** en `outputs/bilbao/`; los datos crudos quedan en `data/opendata/` (fuera de Git).

> **Corrección (19/10/2026): ocupación por calendario.** Hasta ahora las noches vendidas se estimaban con las reseñas (la mitad de las estancias deja reseña, 3 noches por estancia, tope del 70 %). Comparado con fuentes comerciales de referencia (consultadas solo para comprobar, no se publican), ese método daba **entre 2 y 4 veces menos ingreso**, aunque los precios coincidían. Ahora las noches salen del **calendario público** (noches no disponibles leídas entre 0 y 29 días antes, octubre de 2025 a septiembre de 2026), que queda a unos ±10 puntos de ocupación de esas fuentes. Cambian dos conclusiones: **el turístico mediano sí supera al alquiler largo** en todos los municipios, y en Donostia los profesionales no rinden menos que los particulares. Todas las cifras de este documento ya están corregidas.
>
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
4. **P2, ingreso estimado.** Pisos completos de corta estancia (mínimo de 30 noches o menos), con al menos una reseña en 12 meses, precio y al menos 180 noches de calendario medidas: 821 pisos.
   - Noches al año = parte de las noches de octubre de 2025 a septiembre de 2026 que el calendario público da como no disponibles (cada noche leída en la captura más cercana por delante, a 0-29 días) × 365. Se descartan, en cada captura, los anuncios bloqueados todo el año.
   - Ingreso mensual = noches × precio por noche ÷ 12.
   - Se muestran la mediana y el rango intercuartílico; las celdas con menos de 10 pisos no se publican.
5. **P3, impuesto.** Impuesto por estancia = 6,50 € × personas × mínimo(noches, 6).
6. **P4, costes.** Neto del piso mediano de cada distrito con tres escenarios (sección 6).
7. **P5, comparativa.** Lo mismo por municipio: Bilbao, Donostia, la costa y Vitoria-Gasteiz.
8. **P6, tamaño del mercado.** Cada piso se compara con sus iguales (mismo distrito y capacidad: 1-2, 3-4, 5-6, 7 o más personas; solo grupos de 10 o más).

## 3. Supuestos y cómo afectan

| Supuesto | Valor | Sensibilidad |
|---|---|---|
| Noches ocupadas | No disponibles en el calendario público, a 0-29 días | Cuenta como ocupadas las noches que bloquea el dueño: puede inflar algo la ocupación, sobre todo en zonas de segunda residencia en verano |
| Estancia media | 3 noches | Solo para calcular limpiezas en los costes |
| Precio | Mediana de marzo a junio de 2026 | Sin invierno (diciembre a febrero no traen precio): en la costa, todavía algo alto |
| Tarifa del impuesto | 6,50 € por persona y noche, tope de 6 noches | Anuncios municipales y prensa de 2026; confirmar en las ordenanzas |

El ingreso es una **estimación con método conocido**, no un dato real. Se comprobó contra fuentes comerciales de referencia: el precio coincide y la ocupación queda a unos ±10 puntos.

## 4. Resultados

**P1. Pisos completos por cada 1.000 habitantes**: Ibaiondo 6,2 · Uribarri 4,6 · Abando 4,5 · Begoña 1,8 · Deustu 1,6 · Basurtu-Zorrotza 1,5 · Errekalde 1,3 · Otxarkoaga-Txurdinaga 0,4 · **Bilbao 3,1**. Inside Airbnb da 1.055 pisos completos y el registro oficial, 1.019 viviendas.

**P2. Ingreso bruto mensual estimado (mediana y rango 25 % a 75 %)**: Abando 3.423 € (2.545 € a 4.281 €) · Basurtu-Zorrotza 2.929 € · Ibaiondo 2.823 € (2.202 € a 3.713 €) · Errekalde 2.611 € · Uribarri 2.558 € · Deustu 2.528 € · Begoña 1.885 € · **Bilbao 2.778 € (2.092 € a 3.741 €)**. Precio por noche mediano de Bilbao: 163 €; ocupación mediana, 58 % (unas 17,5 noches al mes). Otxarkoaga-Txurdinaga tiene solo 10 pisos activos y no se interpreta.

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
| Abando | 3.423 € | 2.025 € | 1.340 € | 2.423 € |
| Basurtu-Zorrotza | 2.929 € | 1.645 € | 1.059 € | 1.996 € |
| Ibaiondo | 2.823 € | 1.554 € | 989 € | 1.899 € |
| Errekalde | 2.611 € | 1.406 € | 884 € | 1.725 € |
| Uribarri | 2.558 € | 1.343 € | 831 € | 1.665 € |
| Deustu | 2.528 € | 1.310 € | 804 € | 1.633 € |
| Begoña | 1.885 € | 893 € | 516 € | 1.128 € |

Un propietario solo cubre los gastos fijos con unas 3 noches al mes a 163 € y necesita unas **11 noches al mes** para igualar el alquiler largo neto; el piso mediano de Bilbao hace entre 13,7 y 18,4. **El turístico mediano supera al alquiler largo en todos los distritos** (en Begoña, por poco), también con gestora salvo en Begoña.

**Límites.** El precio no incluye la tarifa de limpieza que paga el huésped: si se cobra aparte, el neto sube unos 100-130 €/mes. Se combina el ingreso mediano con las noches medianas del distrito, que no son del mismo piso. No incluye mobiliario, vacíos ni impagos del alquiler largo.

## 7. Comparativa por municipio (P5)

| Municipio | Pisos | Precio | Noches/mes | Bruto | Neto del dueño | Alquiler largo neto | Turístico ÷ largo |
|---|---|---|---|---|---|---|---|
| Donostia-San Sebastián | 921 | 323 € | 17,5 | 5.563 € | 3.701 € | 982 € | 3,77 |
| Zarautz | 136 | 208 € | 14,4 | 3.019 € | 1.768 € | 628 € | 2,82 |
| Sopelana | 40 | 202 € | 16,8 | 2.933 € | 1.658 € | 684 € | 2,42 |
| Hondarribia | 102 | 188 € | 14,5 | 2.845 € | 1.631 € | 781 € | 2,09 |
| Bilbao | 825 | 163 € | 17,5 | 2.778 € | 1.523 € | 861 € | 1,77 |
| Getxo | 96 | 163 € | 16,8 | 2.654 € | 1.438 € | 684 € | 2,10 |
| Vitoria-Gasteiz | 67 | 143 € | 19,2 | 2.578 € | 1.335 € | 701 € | 1,90 |

Alquiler largo: capitales con contratos nuevos (4.º trimestre de 2025); el resto, renta media de los contratos vigentes de su área funcional (EMAL). Bakio (2,25), Mundaka (2,38), Lekeitio (1,63) y Bermeo (1,29) también quedan por encima. **El turístico mediano gana al alquiler largo en todos los municipios**, con Donostia muy por delante (3,8 veces); antes de impuestos y sin contar el trabajo de gestionarlo.

## 8. Tamaño del mercado (P6)

De 759 pisos comparados en 16 grupos, 163 pisos con 10 o más reseñas ingresan menos que el 75 % de sus iguales: les faltan unos **188.700 € al mes** en total (mediana de 1.094 € por piso) para llegar a la mediana de su grupo. Otros 56 pisos están "baratos y llenos" (117 € frente a 155 € de sus iguales). Del total que falta, Ibaiondo, Abando y Uribarri suman el 81 %. De los que rinden poco, el 15 % tiene menos de 10 reseñas y el 40 % deja libres 270 días o más: no todos están mal gestionados.

## 8b. Donostia por distrito (P7)

Inside Airbnb trata Donostia como una sola zona, así que se usan los 7 distritos censales del INE (CUMUN 20069, 141 secciones). Cada distrito lleva el nombre de los barrios de referencia que contiene; los nombres son aproximados. Mismo método que en Bilbao: 901 pisos en 23 grupos de distrito y capacidad.

- Ingreso bruto mensual del piso mediano: de 6.785 € (Centro) y 6.666 € (Parte Vieja) a unos 5.000 € (Amara, Gros, Antiguo); Altza-Intxaurrondo, 2.893 €.
- 210 pisos con 10 o más reseñas rinden por debajo del 75 % de sus iguales: les faltan unos **467.400 € al mes** (mediana de 2.137 € por piso), unas 2,5 veces más que en Bilbao.
- 73 pisos "baratos y llenos": 226 € frente a 357 € de sus iguales.
- Con el método anterior (reseñas), sin distritos el hueco salía casi igual: no lo explica la ubicación.

## 8c. Tipo de anfitrión (P8)

Segmentos por `calculated_host_listings_count`: particular (1 anuncio), pequeño (2 a 9) y profesional (10 o más). Un anfitrión con 10 o más anuncios suele ser una gestora, no un "gran tenedor".

| Ciudad | Segmento | Pisos | Ingreso/mes mediano | Noches/mes | % por debajo de iguales |
|---|---|---|---|---|---|
| Bilbao | Particular | 311 | 3.183 € | 18,3 | 15 % |
| Bilbao | Pequeño | 236 | 2.891 € | 17,7 | 27 % |
| Bilbao | Profesional | 212 | 2.413 € | 15,8 | 37 % |
| Donostia | Particular | 293 | 5.251 € | 18,4 | 25 % |
| Donostia | Pequeño | 223 | 5.033 € | 17,9 | 30 % |
| Donostia | Profesional | 385 | 5.937 € | 16,6 | 22 % |

En Bilbao los profesionales rinden algo menos (menos noches y precio más bajo). **En Donostia no:** cobran más (363 € frente a 270 €) y son los que más ingresan. Con el método de reseñas salían muy por debajo en las dos ciudades, porque las gestoras reciben menos reseñas por estancia y venden también por Booking y canal directo.

## 8d. Validación de la ocupación con el INE

`scripts/validacion_ine.py` compara la ocupación mensual del calendario (`outputs/herramienta/ocupacion_mes.json`, sin ajustes) con el **grado de ocupación por apartamentos** de la Encuesta de Ocupación en Apartamentos Turísticos del INE: puntos turísticos de Bilbao y Donostia (tabla 2083) y zonas turísticas Costa Bizkaia y Costa Gipuzkoa (tabla 2022). Resultado en `outputs/bilbao/validacion_ine.csv`.

| Zona | Meses | INE | Calendario | Diferencia media | Julio y agosto | Correlación |
|---|---|---|---|---|---|---|
| Bilbao | 11 | 72,4 % | 59,9 % | −12,4 pp | −9,4 pp | 0,93 |
| Donostia | 13 | 65,9 % | 59,3 % | −6,6 pp | +6,3 pp | 0,91 |
| Costa Bizkaia | 11 | 64,6 % | 53,5 % | −11,1 pp | −4,9 pp | 0,82 |
| Costa Gipuzkoa | 13 | 63,4 % | 50,5 % | −13,0 pp | +10,8 pp | 0,83 |

- **No es la misma población.** El INE mide apartamentos turísticos registrados como establecimiento (unos 650 en Bilbao), venden por todos los canales y solo cuenta los abiertos cada mes. El calendario mide pisos completos de Airbnb, también de particulares, y sigue contando los que se quedan vacíos en invierno. Por eso el INE es un techo y la diferencia crece fuera de temporada.
- **El nivel del calendario es prudente:** queda por debajo del INE en la media de todas las zonas. El ingreso estimado con él no está inflado.
- **La forma de la temporada coincide** (correlación de 0,82 a 0,93), que es lo que usan el modo tablet y el calendario de colores.
- **Excepción: julio y agosto en la costa de Gipuzkoa.** El calendario se pasa unos 11 puntos, por las noches que los dueños se guardan para veranear. `scripts/ocupacion_mes.py` resta 10 puntos en esos dos meses (`AJUSTE_VERANO`). En Donostia se pasa algo menos (+6 pp) y se deja sin ajustar.
- Faltan algunos meses del INE (por ejemplo, noviembre y diciembre en Bilbao), que no publica cuando hay pocos establecimientos.

## 9. Paso a Fabric (pendiente)

1. Subir a `lh_bronze/Files/opendata/` las fuentes públicas.
2. Notebook silver: secciones del INE de Bilbao a distritos (polígonos como texto WKT) y habitantes por distrito.
3. Notebook gold: `dim_distrito`, la asignación de cada anuncio a su distrito, el precio de referencia y las tablas `fact_oferta_distrito`, `fact_ingreso_distrito` y `param_impuesto`.
4. Modelo semántico: pisos por 1.000 habitantes, ingreso mediano y simulador del impuesto con parámetros.
5. Página de informe: Bilbao por distrito y simulador del impuesto.
