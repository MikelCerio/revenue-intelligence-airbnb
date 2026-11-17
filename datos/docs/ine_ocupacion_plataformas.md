# INE experimental: ocupación en alojamientos turísticos a partir de plataformas digitales

Fuente: INE, estadística experimental (CC BY 4.0), con datos de Airbnb, Booking y Expedia. Descargada el 2026-11-17.
**No hay nivel municipio**: lo más fino son los *puntos turísticos* (106, entre ellos Bilbao, Donostia/San Sebastián,
Vitoria-Gasteiz y Barcelona) y las *zonas turísticas* (p. ej. "Bilbao: Conurbacion 2024", "Pais Vasco: Costa Guipuzkoa").

## Formato

Igual que `ine_viv_turistica.md`: CSV largo, `;`, UTF-8 con BOM, miles con `.` y decimales con `,`.
Periodo `AAAAMmm` en las mensuales y `AAAA` en las anuales.

| Tabla | Periodicidad | Ámbito | Medidas |
|---|---|---|---|
| 48423 | Mensual 2018M01…2026M06 | Nacional y CCAA | Concepto turístico × Residencia |
| **48424** | Mensual | **Puntos turísticos** | Nº de alojamientos ocupados, nº de noches ocupadas, estancia media |
| 48425 | Mensual | Nacional y CCAA | Pernoctaciones × Residencia |
| **48426** | Mensual | **Puntos turísticos** | Pernoctaciones × Residencia |
| 48427 | Anual 2018…2025 | Provincias | Pernoctaciones |
| 48428 / 48429 | Anual | CCAA / **Puntos turísticos** | Alojamientos y noches ocupados |
| 48430 / 48431 | Anual | CCAA / Puntos turísticos | Pernoctaciones |
| 48432 | Anual | **Zonas turísticas** | Pernoctaciones |
| 48433 / 48434 | Anual | Nacional / CCAA | Pernoctaciones por país o continente de origen |
| 48435 / 48436 | Anual | Nacional | Por tamaño / tipo de alojamiento |

`Residencia del viajero` ∈ {Total, Residentes en España, Residentes en el Extranjero}.
`Concepto turístico` ∈ {Número de alojamientos turísticos ocupados, Número de noches ocupadas, Estancia media}.

Nota: esta serie experimental es distinta de la EOAP (Encuesta de Ocupación en Apartamentos Turísticos) que ya usa
`scripts/validacion_ine.py`. Sirve como segunda validación de la ocupación por calendario de Inside Airbnb en Bilbao y Donostia.
