# Auditoría de fiabilidad de las comparaciones por zona

**Pregunta:** ¿a partir de cuántos anuncios tiene sentido comparar una zona con otra?
**Datos:** snapshots de junio de 2026 (Barcelona 2026-06-24, Euskadi 2026-06-30), nivel de anuncio, y la serie mensual por zona del modelo semántico.
**Método:** intervalos de confianza al 95 % por *bootstrap* (400 remuestreos de anuncios dentro de cada zona) para la ocupación (media) y el ADR (mediana); estabilidad mes a mes de la ocupación por tramo de tamaño.

## 1. Cuántos anuncios tiene cada zona

| | Barcelona (70 zonas) | Euskadi (207 zonas) |
|---|---|---|
| Zonas con ≥ 30 anuncios | 47 | 29 |
| Anuncios cubiertos con ese corte | 98 % | 81 % |
| Mediana de anuncios por zona | — | 6 |
| Zonas con ≥ 100 anuncios | 26 | 7 |

En Euskadi la mitad de las zonas tiene 6 anuncios o menos: cualquier cifra suya es anecdótica.

## 2. Margen de error (mitad del intervalo al 95 %)

| Anuncios en la zona | Ocupación (puntos) | ADR (% sobre la mediana) |
|---|---|---|
| 3–5 | ±18 | ±37–52 % |
| 6–10 | ±15–20 | ±24–56 % |
| 11–20 | ±12–18 | ±32–36 % |
| 21–30 | ±11–15 | ±21–35 % |
| 31–50 | ±7–12 | ±17–28 % |
| 51–100 | ±6–8 | ±13–20 % |
| más de 100 | ±3 | ±6–7 % |

Con el corte actual (≥ 30 anuncios): ocupación ±6,0 puntos de mediana (el 10 % peor, ±9,9) y ADR ±12,6 % (el 10 % peor, ±32,9 %).

## 3. Estabilidad mes a mes

Cambio absoluto de la ocupación de una zona entre dos snapshots consecutivos (mediana / percentil 90):

| Anuncios | Barcelona | Euskadi |
|---|---|---|
| ≤ 5 | 11,7 / 46,8 puntos | 13,3 / 44,7 |
| 6–10 | 9,2 / 19,0 | 10,7 / 29,3 |
| 21–30 | 6,4 / 13,1 | 8,0 / 28,0 |
| 31–50 | 6,7 / 13,0 | 6,8 / 28,3 |
| más de 100 | 5,0 / 10,1 | 6,2 / 16,0 |

Hasta unos 30 anuncios, la ocupación de una zona salta varios puntos de un mes a otro por puro azar de la muestra.

## 4. ¿Se pueden distinguir unas zonas de otras?

Proporción de pares de zonas cuyos intervalos de ocupación **no se solapan** (diferencia real, no ruido):

| Corte | Pares distinguibles |
|---|---|
| ≥ 10 anuncios | 27 % |
| ≥ 30 anuncios | 26 % |
| ≥ 50 anuncios | 24 % |
| ≥ 100 anuncios | 28 % |

Solo una de cada cuatro comparaciones entre zonas muestra una diferencia de ocupación fiable, aunque la muestra sea grande. La ocupación es parecida entre muchas zonas, así que los rankings detallados sobreinterpretan diferencias pequeñas. Para el ADR, con ≥ 30 anuncios *con precio válido* se distingue el 46 % de los pares, y con ≥ 50, el 60 %.

## 5. Hallazgos que cambian el diseño

1. **El corte de 30 anuncios mide el tamaño equivocado para el ADR.** El ADR usa solo anuncios con precio válido, de corta estancia y sin valor centinela. De las zonas con ≥ 30 anuncios, 17 (13 en Barcelona, 4 en Euskadi) tienen menos de 30 con precio válido; por ejemplo, la Marina de Port tiene 62 anuncios pero solo 9 con precio, y su ADR tiene un margen de ±53 %.
2. **La ocupación individual es muy polarizada.** El 35 % de los anuncios de Barcelona y el 18 % de los de Euskadi están al 0 % o al 100 % en los 30 días: la media esconde dos grupos (cerrados/bloqueados y llenos), y la desviación entre anuncios (0,34 y 0,29) es enorme.
3. **Los intervalos asumen anuncios independientes** y no corrigen que "no disponible" no equivale a reservado; son un mínimo de la incertidumbre real.
4. **Barcelona 2026-06-24 usa 15.293 anuncios con ocupación, pero solo 8.511 tienen precio válido** (la mayoría del resto son estancias largas): el ADR de Barcelona describe poco más de la mitad del parque.

## 6. Recomendación

| Nivel | Condición | Cómo mostrarlo |
|---|---|---|
| Fiable | ≥ 100 anuncios (y ≥ 50 con precio para el ADR) | cifra normal |
| Aceptable | 50–99 | cifra con "±" |
| Orientativo | 30–49 | cifra atenuada, sin posición de ranking |
| No mostrar | < 30 | agrupar en "otras zonas" o dejar vacío |

Además: aplicar un corte propio al ADR sobre los anuncios con precio válido, mostrar rangos de posición en vez de puestos exactos, y no afirmar que una zona "gana" a otra si la diferencia de ocupación es menor que ~2 × su margen.

## Límites de esta auditoría

- Un solo snapshot a nivel de anuncio por ciudad (junio de 2026) para los intervalos; la estabilidad mes a mes usa los 12 meses.
- No hay verdad externa con la que contrastar la ocupación: se mide precisión (ruido), no exactitud (sesgo).
- Los datos de calendario de Inside Airbnb mezclan reservas, bloqueos y anuncios cerrados.
