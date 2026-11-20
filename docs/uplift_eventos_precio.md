# Uplift de los grandes eventos: ocupación y precio hotelero (Eustat)

Script: `scripts/eventos_uplift_precio.py` · Datos: Eustat, Encuesta de establecimientos turísticos receptores
(tablas `etrm_20h`, `etrm_14h`, `etrm_03h`, descarga del 2026-11-17) · Salidas: `outputs/eventos/uplift_*.csv`

## Qué se puede medir y qué no

Eustat publica la **ocupación hotelera por día** en las tres capitales (desde enero de 2022), pero el **ADR solo
por mes**. No existe un precio público por noche. Por eso el uplift de precio se construye en dos pasos:

1. **Cuánto sube la ocupación** la noche del evento frente a noches de control (mismo día de la semana, menos de
   21 días, sin evento, festivo ni Navidad). El ruido de una noche normal frente a sus controles es de ±7-8 puntos
   (desviación típica), así que una sola edición casi nunca es concluyente; la media de varias sí.
2. **Cuánto sube el ADR cuando sube la ocupación**, con la serie mensual 2015-2026 (sin 2020-2021).

## Resultado 1: los eventos pesan mucho más en temporada baja

| Evento (ediciones) | Ocupación de control | Subida de ocupación |
|---|---|---|
| Tamborrada, Donostia (5) | ~41 % | **+16,4 puntos** (+22 a +28 en 2023-2025) |
| Behobia, Donostia (4, noche del sábado y del domingo) | ~69 % | **+10,6 puntos** |
| Fiestas de La Blanca, Vitoria (5) | ~85 % | +7,3 |
| BBK Live, Bilbao (5) | ~84 % | +5,9 |
| Semana Grande, Donostia (5) | ~89 % | +3,8 |
| Zinemaldia, Donostia (5) | ~87 % | +1,9 |
| Aste Nagusia, Bilbao (5) | ~86 % | +1,3 (+3,3 sin 2026) |

Media de los eventos de temporada alta: **+4 puntos**; de temporada baja (control por debajo del 70 %): **+14 puntos**.
En verano los hoteles ya están al 85-90 %: el evento no puede llenar lo que ya está lleno, y la presión de la
demanda sale por el **precio**, no por la ocupación.

## Resultado 2: cuánto sube el ADR por cada 10 puntos de ocupación

| Ciudad | Mismo mes, año anterior (shock de demanda) | Entre meses del año (curva de temporada) |
|---|---|---|
| Bilbao | +5,1 % (±1,2) | +11,7 % (±0,5) |
| Donostia | +6,9 % (±1,8) | +20,7 % (±0,7) |
| Vitoria-Gasteiz | +0,6 % (±1,5) | +8,3 % (±0,6) |

La primera columna mide la reacción del precio a una demanda **inesperada** (el año sale mejor de lo previsto).
La segunda, cómo se fija el precio ante una demanda **que se espera** (la temporada): es la que se parece a un
evento conocido de antemano. Los dos números acotan el uplift.

## Uplift de precio que corresponde a cada evento (estimación)

| Tipo de evento | Ocupación | Precio hotelero (rango) |
|---|---|---|
| Fiesta o festival de verano en Bilbao o Donostia | +4 puntos | **+2 % a +8 %** de media en esas noches |
| Tamborrada (Donostia, enero) | +16 puntos | **+12 % a +36 %** |
| Behobia (Donostia, noviembre) | +11 puntos | **+7 % a +22 %** |

En verano es un **mínimo**: con los hoteles casi llenos la ocupación no puede subir más y el ajuste va al precio, que
este método no ve noche a noche.

## Eventos excepcionales: el ADR del mes no lo recoge

Finales de la UEFA en San Mamés (mayo de 2024 y 2025) y salida del Tour de Francia (julio de 2023), comparados con el
mismo mes de otros años y con las otras capitales:

| Evento | ADR del mes | Ruido de un mes normal |
|---|---|---|
| Final de la Europa League 2025 | +2,7 % | ±3,9 % |
| Final de la Champions femenina 2024 | +0,4 % | ±3,9 % |
| Salida del Tour 2023 | −1,8 % | ±3,9 % |

Dos noches entre treinta se diluyen en la media del mes: ninguno se distingue del ruido. Con datos públicos no se
puede medir el precio de una noche concreta; para eso hacen falta precios por fecha (de pago o de reservas propias).

## Límites

- Son **hoteles**, no pisos turísticos. En Inside Airbnb la Aste Nagusia sale +4,9 puntos de ocupación aproximada:
  el orden de magnitud coincide.
- Las fechas de 2022-2024 siguen reglas fijas (Aste Nagusia, Semana Grande, La Blanca, Tamborrada, Behobia) o están
  comprobadas (BBK Live, Zinemaldia, finales de la UEFA). Jazzaldia 2022-2024 queda fuera: fechas sin confirmar.
- Los datos de 2026 son provisionales en Eustat. Aste Nagusia 2026 sale −6,6: revisarlo cuando se consoliden.
- Los partidos de liga solo se excluyen de los controles en 2025-2026.
- La relación ADR-ocupación es lineal; para subidas muy grandes (Tamborrada) el rango es amplio a propósito.

Fuente: Eustat. Elaboración propia.
