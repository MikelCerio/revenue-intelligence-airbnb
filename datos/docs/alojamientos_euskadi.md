# Alojamientos turísticos de Euskadi

Hoteles, pensiones, apartamentos, rurales, agroturismos, albergues y campings con origen en REATE, en la versión
del portal de turismo. Fuente: Open Data Euskadi, CC BY 4.0. Diario. Foto del 2026-11-17: **1.482 establecimientos**, 50 campos.
Ficheros: `alojamientos.json` (lista de objetos), `alojamientos.geojson` (los mismos campos en `properties`), `alojamientos.xlsx`.
**No incluye viviendas de uso turístico** (están en `reate.md`).

## Campos útiles

| Campo | Notas |
|---|---|
| `signatura` | Código de registro (1.461 únicos). Clave estable |
| `documentName` | Nombre del establecimiento (es un negocio, no una persona) |
| `lodgingType` | Hoteles 338, Pensiones 330, Casas Rurales 298, Apartamentos 223, Agroturismos 158, Albergues 86, Campings 28, Hotel-Apartamento 21 |
| `category` | Estrellas `1`-`5`; `S` = sin categoría / no aplica (554); `T`, `P` = códigos propios de campings y apartamentos (pendiente confirmar) |
| `capacity` | Plazas (texto → entero) |
| `latwgs84`, `lonwgs84` | Coordenadas WGS84 (texto → float). 0 % nulos. `latitudelongitude` = lo mismo junto |
| `municipality`, `municipalitycode` | 215 nombres para 136 códigos (bilingües): agrupar por código |
| `territory`, `territorycode` | Gipuzkoa 676, Bizkaia 571, Araba 235 |
| `marks` | Marca turística: "Montes y Valles vascos", "Costa Vasca", "Bilbao", "San Sebastián", "Vitoria-Gasteiz", "Rioja Alavesa"… (puede ser una lista separada por comas) |
| `postalCode` | 1 % nulos (`postalcode` en minúscula casi vacío: ignorar) |
| `qualityAssurance`, `room`, `restaurant`, `productClub`, `surfing`… | Marcas de servicio, casi siempre vacías |
| `physical`, `visual`, `auditive`, `intellectual`, `organic` | Accesibilidad por tipo |
| `tourismEmail`, `web`, `friendlyUrl`, `physicalUrl`, `dataXML`, `metadataXML` | Contacto y enlaces. Descartar en silver |

Campos 100 % vacíos: `accesibility`, `accesibilityIconDescription`, `phone`, `address`, `importance`, `placename`, `email`, `webpage`.

## Uso previsto

Oferta hotelera y reglada por municipio y tipo para comparar con viviendas turísticas (REATE) e Inside Airbnb, y mapa de competencia por zona.
