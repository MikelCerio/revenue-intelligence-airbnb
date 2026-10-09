# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# ## 7a dim_snapshot: ¿qué snapshots están completos?
# **Qué:** cuento anuncios y filas de calendar por snapshot y marco como incompleto el que tiene menos del 85 % de la mediana de anuncios de su ciudad.
# **Por qué:** Inside Airbnb a veces captura solo una parte; comparar un snapshot parcial con uno completo genera bajas falsas.
# **Resultado esperado:** Barcelona 2026-04-20 (7.277) y 2026-02-18 (12.786) marcados como no completos; el resto, completos.

# CELL ********************

from pyspark.sql import functions as F, Window

UMBRAL_COMPLETITUD = 0.85   # un snapshot es "completo" si tiene al menos el 85 % de la mediana de anuncios de su ciudad

base = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables"
listings = spark.read.format("delta").load(f"{base}/listings")
calendar = spark.read.format("delta").load(f"{base}/calendar")

n_list = listings.groupBy("ciudad", "snapshot_date").agg(F.countDistinct("id").alias("n_anuncios"))
n_cal = calendar.groupBy("ciudad", "snapshot_date").agg(F.count("*").alias("n_filas_calendar"))

w = Window.partitionBy("ciudad")
snap = (n_list.join(n_cal, ["ciudad", "snapshot_date"])
        .withColumn("mediana_ciudad", F.percentile_approx("n_anuncios", 0.5).over(w))
        .withColumn("ratio", F.round(F.col("n_anuncios") / F.col("mediana_ciudad"), 3))
        .withColumn("es_completo", F.col("ratio") >= UMBRAL_COMPLETITUD))

snap.orderBy("ciudad", "snapshot_date").show(30, False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7b Guardar dim_snapshot en lh_gold
# **Qué:** escribo la tabla `dim_snapshot` en Delta, con un `overwrite` completo.
# **Por qué:** es una dimensión pequeña derivada de silver; reescribirla entera es barato y la mantiene siempre al día.
# **Resultado esperado:** 23 filas, 2 con `es_completo = false` (Barcelona 2026-02-18 y 2026-04-20).

# CELL ********************

destino_gold = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_gold.Lakehouse/Tables/dim_snapshot"

(snap.select("ciudad", "snapshot_date", "n_anuncios", "n_filas_calendar", "mediana_ciudad", "ratio", "es_completo")
     .write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(destino_gold))

spark.read.format("delta").load(destino_gold).orderBy("ciudad", "snapshot_date").show(30, False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7c dim_zona
# **Qué:** una fila por zona con su grupo (provincia en Euskadi, distrito en Barcelona) y una clave `zona_id`; falla si una zona aparece en más de un grupo.
# **Por qué:** es la jerarquía para comparar comp sets por provincia, municipio o barrio; la clave de una columna permite la relación con los hechos.
# **Resultado esperado:** Euskadi 3 grupos y ~207 zonas; Barcelona 10 grupos y ~69 zonas (pueden variar por snapshot).

# CELL ********************

zonas = (listings.select("ciudad",
                         F.col("neighbourhood_group_cleansed").alias("grupo"),
                         F.col("neighbourhood_cleansed").alias("zona"))
         .where(F.col("zona").isNotNull())
         .distinct()
         .withColumn("zona_id", F.concat_ws("|", "ciudad", "zona")))

n_filas = zonas.count()
n_zonas = zonas.select("zona_id").distinct().count()
print("filas:", n_filas, "| zonas únicas:", n_zonas)
assert n_filas == n_zonas, "Hay zonas asignadas a más de un grupo"

zonas.groupBy("ciudad").agg(F.countDistinct("grupo").alias("grupos"), F.count("*").alias("zonas")).show()

destino_zona = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_gold.Lakehouse/Tables/dim_zona"
zonas.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(destino_zona)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7d dim_listing
# **Qué:** una fila por anuncio con sus atributos del snapshot más reciente, y las fechas de primera y última aparición.
# **Por qué:** una dimensión describe al anuncio; lo que cambia cada mes (precio, disponibilidad) va en una tabla de hechos. Primera y última aparición permiten medir altas y bajas.
# **Resultado esperado:** `listing_id` único; decenas de miles de anuncios por ciudad.

# CELL ********************

w_id = Window.partitionBy("id")
w_ult = Window.partitionBy("id").orderBy(F.col("snapshot_date").desc())

dim_listing = (listings
    .withColumn("primera_vez", F.min("snapshot_date").over(w_id))
    .withColumn("ultima_vez", F.max("snapshot_date").over(w_id))
    .withColumn("n_snapshots", F.count("*").over(w_id))
    .withColumn("rn", F.row_number().over(w_ult))
    .where("rn = 1")
    .select(F.col("id").alias("listing_id"), "ciudad",
            F.concat_ws("|", "ciudad", "neighbourhood_cleansed").alias("zona_id"),
            "host_id", "room_type", "property_type", "accommodates", "bedrooms", "beds", "bathrooms",
            "latitude", "longitude", "license_status", "exempt_type", "host_is_superhost",
            "calculated_host_listings_count", "primera_vez", "ultima_vez", "n_snapshots"))

n_filas = dim_listing.count()
assert n_filas == dim_listing.select("listing_id").distinct().count(), "listing_id duplicado"
dim_listing.groupBy("ciudad").agg(F.count("*").alias("anuncios"),
                                  F.round(F.avg("n_snapshots"), 1).alias("snapshots_medios"),
                                  F.sum((F.col("n_snapshots") == 1).cast("int")).alias("en_un_solo_snapshot")).show()

destino_listing = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_gold.Lakehouse/Tables/dim_listing"
dim_listing.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(destino_listing)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7e fact_listing_snapshot y clave snapshot_id
# **Qué:** escribo la tabla de hechos con lo que cambia en cada snapshot (precio, flags, disponibilidad, reseñas) y añado `snapshot_id` a `dim_snapshot`.
# **Por qué:** `snapshot_id` es una clave de una sola columna, necesaria para relacionar hechos y dimensión en el modelo; la dimensión describe, el hecho mide.
# **Resultado esperado:** 242.766 filas en el hecho (suma de anuncios de los 23 snapshots) y 23 en `dim_snapshot`; clave (listing_id, snapshot_id) única.

# CELL ********************

def con_snapshot_id(d):
    return d.withColumn("snapshot_id", F.concat_ws("_", "ciudad", F.date_format("snapshot_date", "yyyyMMdd")))

fact_ls = con_snapshot_id(listings).select(
    F.col("id").alias("listing_id"), "snapshot_id",
    "price_num", "price_missing", "price_outlier", "is_long_stay",
    "minimum_nights", "availability_30", "availability_60", "availability_90", "availability_365",
    "number_of_reviews", "number_of_reviews_ltm", "reviews_per_month", "review_scores_rating")

n_filas = fact_ls.count()
assert n_filas == fact_ls.select("listing_id", "snapshot_id").distinct().count(), "clave (listing_id, snapshot_id) duplicada"

destino_fls = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_gold.Lakehouse/Tables/fact_listing_snapshot"
fact_ls.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(destino_fls)

# dim_snapshot con la misma clave
snap2 = con_snapshot_id(snap).select("snapshot_id", "ciudad", "snapshot_date", "n_anuncios",
                                     "n_filas_calendar", "mediana_ciudad", "ratio", "es_completo")
snap2.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(destino_gold)
print("fact_listing_snapshot:", n_filas, "filas | dim_snapshot:", snap2.count(), "filas")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7f fact_calendar
# **Qué:** escribo la noche de cada anuncio por snapshot, con `snapshot_id` y `dias_antelacion` (días entre el snapshot y esa noche), particionada por snapshot.
# **Por qué:** es la tabla de hechos que alimenta ocupación y pickup; precalcular la antelación evita restar fechas en 88 millones de filas dentro de cada medida.
# **Resultado esperado:** 88.672.422 filas y 23 snapshots; antelación entre 0 y unos 365 días.

# CELL ********************

fact_cal = (con_snapshot_id(calendar)
    .select("listing_id", "snapshot_id", F.col("date").alias("fecha"), "available", "minimum_nights",
            F.datediff("date", "snapshot_date").alias("dias_antelacion")))

destino_fc = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_gold.Lakehouse/Tables/fact_calendar"
(fact_cal.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
         .partitionBy("snapshot_id").save(destino_fc))

c = spark.read.format("delta").load(destino_fc)
print("filas:", c.count(), "| snapshots:", c.select("snapshot_id").distinct().count())
c.agg(F.min("dias_antelacion").alias("min_dias"), F.max("dias_antelacion").alias("max_dias")).show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

c.groupBy("snapshot_id").agg(F.min("dias_antelacion").alias("min_dias"),
                             F.max("dias_antelacion").alias("max_dias")).orderBy(F.desc("max_dias")).show(30, False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7f-2 Antelación con la fecha real de captura
# **Qué:** recalculo `dias_antelacion` restando la fecha de captura de cada anuncio (`calendar_last_scraped`) en vez de la fecha nominal del snapshot; si falta, uso la nominal y lo marco con `sin_fecha_captura`.
# **Por qué:** la captura de un snapshot dura varios días (hasta ~12 en algunos); con la fecha nominal el pickup tendría un error de esa magnitud.
# **Resultado esperado:** 88.672.422 filas; antelación máxima ≈ 365 en todos los snapshots; pocas filas sin fecha de captura (los anuncios huérfanos).

# CELL ********************

fecha_captura = (con_snapshot_id(listings)
    .select(F.col("id").alias("listing_id"), "snapshot_id", F.col("calendar_last_scraped").alias("fecha_captura")))

fact_cal = (con_snapshot_id(calendar)
    .join(F.broadcast(fecha_captura), ["listing_id", "snapshot_id"], "left")
    .select("listing_id", "snapshot_id", F.col("date").alias("fecha"), "available", "minimum_nights",
            F.datediff("date", F.coalesce("fecha_captura", "snapshot_date")).alias("dias_antelacion"),
            F.col("fecha_captura").isNull().alias("sin_fecha_captura")))

(fact_cal.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
         .partitionBy("snapshot_id").save(destino_fc))

c = spark.read.format("delta").load(destino_fc)
print("filas:", c.count(), "| sin fecha de captura:", c.filter("sin_fecha_captura").count())
c.groupBy("snapshot_id").agg(F.min("dias_antelacion").alias("min_dias"),
                             F.max("dias_antelacion").alias("max_dias")).orderBy(F.desc("max_dias")).show(30, False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7f-3 Reserva para anuncios sin fecha de captura
# **Qué:** cuando un anuncio de `calendar` no está en `listings`, estimo su fecha de captura con la primera fecha de su propio calendario; el flag `sin_fecha_captura` lo deja marcado.
# **Por qué:** la fecha nominal desplazaba la antelación hasta 12 días en esos casos; el calendario siempre empieza el día de la captura.
# **Resultado esperado:** 88.672.422 filas; 62.780 sin fecha de captura (flag); antelación entre -1 y 364.

# CELL ********************

primera_fecha = (con_snapshot_id(calendar)
    .groupBy("listing_id", "snapshot_id").agg(F.min("date").alias("primera_fecha")))

fact_cal = (con_snapshot_id(calendar)
    .join(F.broadcast(fecha_captura), ["listing_id", "snapshot_id"], "left")
    .join(F.broadcast(primera_fecha), ["listing_id", "snapshot_id"], "left")
    .select("listing_id", "snapshot_id", F.col("date").alias("fecha"), "available", "minimum_nights",
            F.datediff("date", F.coalesce("fecha_captura", "primera_fecha")).alias("dias_antelacion"),
            F.col("fecha_captura").isNull().alias("sin_fecha_captura")))

(fact_cal.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
         .partitionBy("snapshot_id").save(destino_fc))

c = spark.read.format("delta").load(destino_fc)
print("filas:", c.count(), "| sin fecha de captura:", c.filter("sin_fecha_captura").count())
c.agg(F.min("dias_antelacion").alias("min_dias"), F.max("dias_antelacion").alias("max_dias")).show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7g dim_fecha
# **Qué:** una fila por día de 2025-07-01 a 2027-12-31, con año, mes, trimestre, día de la semana y fin de semana; falla si alguna fecha de `fact_calendar` no está.
# **Por qué:** el modelo necesita una tabla de fechas completa y sin huecos para agrupar y comparar periodos.
# **Resultado esperado:** 914 filas y 0 fechas sin cubrir.

# CELL ********************

dim_fecha = (spark.sql("SELECT explode(sequence(to_date('2025-07-01'), to_date('2027-12-31'), interval 1 day)) AS fecha")
    .withColumn("anio", F.year("fecha"))
    .withColumn("mes", F.month("fecha"))
    .withColumn("anio_mes", F.date_format("fecha", "yyyy-MM"))
    .withColumn("trimestre", F.quarter("fecha"))
    .withColumn("dia_semana_iso", F.expr("weekday(fecha) + 1"))
    .withColumn("es_finde", F.expr("weekday(fecha) >= 5")))

faltan = c.select("fecha").distinct().join(dim_fecha, "fecha", "left_anti").count()
assert faltan == 0, f"Hay {faltan} fechas de fact_calendar que no están en dim_fecha"

destino_fecha = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_gold.Lakehouse/Tables/dim_fecha"
dim_fecha.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(destino_fecha)
print("dim_fecha:", dim_fecha.count(), "filas | fechas de fact_calendar sin cubrir:", faltan)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7h dim_snapshot con disponibilidad de precio
# **Qué:** añado `pct_sin_precio` y `tiene_precio` (menos del 50 % de anuncios sin precio) a `dim_snapshot`.
# **Por qué:** en dic-2025, ene-2026 y feb-2026 el precio no viene de origen; el informe debe poder avisarlo en vez de mostrar un ADR vacío sin explicación.
# **Resultado esperado:** `tiene_precio = false` en los 6 snapshots de dic a feb (3 por ciudad); `true` en los demás.

# CELL ********************

precio = (listings.groupBy("ciudad", "snapshot_date")
          .agg(F.round(F.avg(F.col("price_missing").cast("int")), 4).alias("pct_sin_precio")))

snap3 = (con_snapshot_id(snap).join(precio, ["ciudad", "snapshot_date"])
         .withColumn("tiene_precio", F.col("pct_sin_precio") < 0.5)
         .select("snapshot_id", "ciudad", "snapshot_date", "n_anuncios", "n_filas_calendar",
                 "mediana_ciudad", "ratio", "es_completo", "pct_sin_precio", "tiene_precio"))
snap3.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(destino_gold)
snap3.orderBy("ciudad", "snapshot_date").show(30, False)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7i dim_snapshot con temporada
# **Qué:** añado `temporada` (invierno, primavera, verano, otoño) y `temporada_orden` a `dim_snapshot`, según el mes del snapshot.
# **Por qué:** permite al informe comparar la ocupación por estación. La ocupación mira los 30 días siguientes a la captura, así que la estación del snapshot es una aproximación de la estación de las noches medidas. Con 12 meses de datos hay una sola vez cada estación: se compara entre estaciones, no entre años.
# **Resultado esperado:** 23 filas; dic-feb = invierno, mar-may = primavera, jun-ago = verano, sep-nov = otoño. `temporada_orden` va de 1 (primavera) a 4 (invierno) para ordenar de forma natural.

# CELL ********************

mes = F.month("snapshot_date")
snap4 = (snap3
         .withColumn("temporada", F.when(mes.isin(12, 1, 2), "invierno")
                                   .when(mes.isin(3, 4, 5), "primavera")
                                   .when(mes.isin(6, 7, 8), "verano")
                                   .otherwise("otoño"))
         .withColumn("temporada_orden", F.when(mes.isin(3, 4, 5), 1)
                                         .when(mes.isin(6, 7, 8), 2)
                                         .when(mes.isin(9, 10, 11), 3)
                                         .otherwise(4)))
assert snap4.count() == 23 and snap4.filter(F.col("temporada").isNull()).count() == 0
snap4.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(destino_gold)
snap4.orderBy("ciudad", "snapshot_date").select("ciudad", "snapshot_date", "temporada", "temporada_orden").show(30, False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
