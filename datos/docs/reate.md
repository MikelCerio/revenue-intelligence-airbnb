# REATE: viviendas y habitaciones de uso turístico (Euskadi)

Registro de Empresas y Actividades Turísticas del Gobierno Vasco. Fuente: Open Data Euskadi, CC BY 4.0.
Foto del registro **vigente** (sin bajas), regenerada a diario. Perfil de la foto del 2026-11-17.

| Fichero | Registros | Campos |
|---|---|---|
| `viviendas.json` | 4.720 (Bizkaia 2.676, Gipuzkoa 1.833, Araba 211) | 20 |
| `habitaciones.json` | 736 (Bizkaia 506, Gipuzkoa 186, Araba 44) | 22 |

Formato: lista JSON de objetos, UTF-8, **todos los valores como texto** (también números y fechas).
Los campos vacíos no salen en el objeto: hay que usar `.get()`, no `[...]`.

## Campos

| Campo | Tipo real | % nulos (viv / hab) | Notas |
|---|---|---|---|
| `Nregistro` | texto | 0 / 0 | Código de registro, patrón `AAA99999` (3 letras + 5 dígitos). **Clave para cruzar con `license` de Inside Airbnb**. 2 viviendas sin código. Únicos: 4.718 / 736 |
| `FechainscripcionREATE` | fecha `DD/MM/AAAA` | 0 / 0 | Fecha de alta en el registro (desde 2016) |
| `Tipoalojamiento` | categoría | 0 / 0 | Un solo valor por fichero: "Vivienda para uso turístico" / "Habitación de vivienda particular para uso turístico" |
| `Modalidad` | categoría | ~0 / 0 | "Medio no rural" / "Medio rural" |
| `Situadaennucleorural`, `Situadaennucleourbano` | Sí/No | ~0 / 0 | Redundante con `Modalidad` |
| `Capacidad` | entero | 0 / 0 | Plazas. Moda 4 en viviendas y 2 en habitaciones |
| `Nbanos` | entero | 0,1 / 0 | Baños |
| `Superficietotalviviendasm2` | decimal | 23,7 / 35,5 | m² |
| `Nresidentesvivienda`, `Ndormitoriosresidentes`, `Ndormitoriosusuarios` | entero | solo hab. ~35 | Solo en habitaciones |
| `Codigoprovincia` | código | 0 | `01` Araba, `20` Gipuzkoa, `48` Bizkaia (sin ceros a la izquierda en algunos casos: normalizar con `zfill(2)`) |
| `Codigomunicipio` | código | 0 | Código INE de municipio **sin la provincia y sin ceros** (Bilbao = `20`). Código INE de 5 dígitos = `prov.zfill(2) + mun.zfill(3)` (Bilbao `48020`, Donostia `20069`) |
| `Municipio`, `Provincia`, `Localidad` | texto | 0 | `Municipio` tiene 188 grafías para 105 códigos (variantes bilingües): **agrupar siempre por código** |
| `Codigopostal` | texto | 0 | 5 dígitos |
| **`Direccion`** | texto | 0 | **Dato sensible.** Solo para geocodificar en silver; nunca en gold ni en salidas |
| **`Nombrecomercial`** | texto | 53 / 68 | **Sensible** (puede identificar a la persona titular o a la empresa). No publicar |
| **`Telefono`**, **`Email`**, **`Web`** | texto | 82-100 | **Datos de contacto personales.** Descartar en silver |

No hay coordenadas ni barrio: para llegar a sección o barrio hay que geocodificar `Direccion` contra el callejero (F5, portales de Bilbao).
Tampoco viene el nombre de la persona titular como campo, pero `Nombrecomercial` y los datos de contacto pueden identificarla.

## Uso previsto

- Altas por mes a partir de `FechainscripcionREATE`; bajas comparando fotos diarias por `Nregistro`.
- Oferta registrada frente a anuncios activos de Inside Airbnb por municipio, y % de anuncios con licencia que existe en REATE.
