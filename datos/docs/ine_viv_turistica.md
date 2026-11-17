# INE experimental: viviendas turísticas en España

Fuente: INE, estadística experimental (CC BY 4.0). Cuenta los anuncios de Airbnb, Booking y Vrbo deduplicados, no el registro oficial.
Descargadas el 2026-11-17. 13 periodos semestrales **2020M08 … 2026M05** (agosto y febrero/mayo según la edición).

## Formato

CSV **largo**, separador `;`, **UTF-8 con BOM** (la cabecera HTTP dice ISO-8859-15, pero no lo es), `\r\n`.
Números: **miles con `.`, decimales con `,`** (`341.001`, `0,99`). Periodo `AAAAMmm` (`2026M05`).
Los niveles se identifican con un código delante: `01 Andalucía`, `48 Bizkaia`, `48020 Bilbao`. Las filas de agregado dejan vacías las columnas inferiores.

| Tabla | Nivel | Columnas | Filas |
|---|---|---|---|
| 39363 | **Municipio** | Total Nacional; CCAA; Provincias; Municipios; Viviendas y plazas; Periodo; Total | 320.073 |
| 39364 | Provincia | …; Provincias; Viviendas y plazas; Periodo; Total | 2.808 |
| 39365 | Provincia (%) | …; Provincias; Periodo; Total | 936 |
| 39366 | **Municipio (%)** | …; Municipios; Periodo; Total | 106.691 |

`Viviendas y plazas` ∈ {Viviendas turísticas, Plazas, Plazas por vivienda turística}. El % es sobre el total de viviendas del municipio.
Municipios de interés (código INE de 5 dígitos): `48020 Bilbao`, `20069 Donostia/San Sebastián`, `01059 Vitoria-Gasteiz`, `08019 Barcelona`.
Une con REATE por código INE (`prov.zfill(2)+mun.zfill(3)`).
