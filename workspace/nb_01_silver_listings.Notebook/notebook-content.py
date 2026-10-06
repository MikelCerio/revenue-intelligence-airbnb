# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "e5b24d47-c902-4dd1-9689-6849b8f1eddc",
# META       "default_lakehouse_name": "lh_bronze",
# META       "default_lakehouse_workspace_id": "f27effa5-e197-450a-8f22-a721e757bc54",
# META       "known_lakehouses": [
# META         {
# META           "id": "e5b24d47-c902-4dd1-9689-6849b8f1eddc"
# META         }
# META       ]
# META     }
# META   }
# META }

# PARAMETERS CELL ********************

# Parámetros: el pipeline los sustituye al llamar al notebook
CIUDAD = "euskadi"
SNAPSHOT = "2026-06-30"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("PROCESANDO:", CIUDAD, SNAPSHOT)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# # nb_01_silver_listings
# **Objetivo:** leer `listings` crudos de bronze (Euskadi 2026-06-30), aplicar las reglas de silver con PySpark y validarlas; después se escribirá la tabla Delta en `lh_silver`.
# **Entrada:** `lh_bronze/Files/<ciudad>/<fecha>/listings.csv.gz`.
# **Reglas:** las acordadas en `docs/manual.md` (Paso 3); aquí se reproducen en PySpark.

# MARKDOWN ********************

# ## 4a Leer `listings` con Spark
# **Qué:** leo el CSV con y sin `multiLine`.
# **Por qué:** los textos largos traen saltos de línea dentro de comillas; sin `multiLine`, Spark cuenta cada línea como una fila nueva.
# **Resultado:** sin `multiLine` 10.128 filas; con `multiLine` 6.248 filas y 90 columnas, igual que pandas.

# CELL ********************

ruta = f"Files/{CIUDAD}/{SNAPSHOT}/listings.csv.gz"

df_mal = spark.read.option("header", True).csv(ruta)
df_bien = (spark.read
    .option("header", True)
    .option("multiLine", True)
    .option("escape", '"')
    .csv(ruta))

print("sin multiLine:", df_mal.count())
print("con multiLine:", df_bien.count(), "| columnas:", len(df_bien.columns))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4b Elegir 39 columnas y declarar los tipos
# **Qué:** me quedo con 39 columnas y las convierto a entero largo, decimal, fecha o texto.
# **Por qué:** tipos fijos entre snapshots y sin datos personales (`host_name`, descripciones).
# **Resultado:** 6.248 filas x 39 columnas. Nulos iguales a pandas: `bathrooms` 0,155, `bedrooms` 0,149, `license` 0,118, `beds` 0,115, `first_review` y `last_review` 0,101.

# CELL ********************

from pyspark.sql import functions as F

ENTERAS = ["id", "host_id", "accommodates", "availability_30", "availability_60",
    "availability_90", "availability_365", "number_of_reviews", "number_of_reviews_ltm",
    "number_of_reviews_l30d", "calculated_host_listings_count",
    "calculated_host_listings_count_entire_homes", "calculated_host_listings_count_private_rooms",
    "calculated_host_listings_count_shared_rooms", "estimated_occupancy_l365d"]
DECIMALES = ["latitude", "longitude", "bathrooms", "bedrooms", "beds", "minimum_nights",
    "maximum_nights", "review_scores_rating", "review_scores_location", "review_scores_value",
    "reviews_per_month", "estimated_revenue_l365d"]
FECHAS = ["last_scraped", "calendar_last_scraped", "first_review", "last_review"]
TEXTOS = ["neighbourhood_cleansed", "neighbourhood_group_cleansed", "property_type",
    "room_type", "price", "license", "has_availability", "host_is_superhost"]

df = df_bien.select(*(ENTERAS + DECIMALES + FECHAS + TEXTOS))
for c in ENTERAS:   df = df.withColumn(c, F.col(c).cast("long"))
for c in DECIMALES: df = df.withColumn(c, F.col(c).cast("double"))
for c in FECHAS:    df = df.withColumn(c, F.to_date(F.col(c)))

print(df.count(), len(df.columns))
nulos = df.select([F.round(F.mean(F.col(c).isNull().cast("int")), 3).alias(c) for c in df.columns])
print(nulos.toPandas().T.sort_values(0, ascending=False).head(6))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4c-1 Precio, flags y booleanos
# **Qué:** creo `price_num`, los flags `price_missing`, `price_outlier` e `is_long_stay`, y paso `t`/`f` a booleano. Si aparece otro valor, falla.
# **Por qué:** un flag debe ser `True` o `False`, nunca `NULL` (por eso el `coalesce`); un nulo no es un falso.
# **Resultado:** 572 / 1 / 264. `has_availability`: true 6.216, false 6, nulo 26. `host_is_superhost`: true 2.458, false 3.784, nulo 6.

# CELL ********************

# 1) Fallar rápido si aparece un valor que no sea t/f
for c in ["has_availability", "host_is_superhost"]:
    malos = df.filter(F.col(c).isNotNull() & ~F.col(c).isin("t", "f")).count()
    assert malos == 0, f"Valores inesperados en {c}"

# 2) Transformaciones
df = (df
    .withColumn("price_num", F.regexp_replace("price", "[$,]", "").cast("double"))
    .withColumn("price_missing", F.col("price_num").isNull())
    .withColumn("price_outlier", F.coalesce(F.col("price_num") == 9999, F.lit(False)))
    .withColumn("is_long_stay", F.coalesce(F.col("minimum_nights") >= 28, F.lit(False)))
    .withColumn("has_availability", F.when(F.col("has_availability") == "t", True).when(F.col("has_availability") == "f", False))
    .withColumn("host_is_superhost", F.when(F.col("host_is_superhost") == "t", True).when(F.col("host_is_superhost") == "f", False)))

# 3) Test de regresión contra pandas
df.agg(F.sum(F.col("price_missing").cast("int")).alias("price_missing"),
       F.sum(F.col("price_outlier").cast("int")).alias("price_outlier"),
       F.sum(F.col("is_long_stay").cast("int")).alias("is_long_stay")).show()
df.groupBy("has_availability").count().show()
df.groupBy("host_is_superhost").count().show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4c-2 Reparar acentos rotos
# **Qué:** re-decodifico con ISO-8859-1 los nombres de zona que contienen `Ã`.
# **Por qué:** Euskadi trae texto UTF-8 mal codificado; solo se toca lo roto, no lo correcto.
# **Resultado:** 0 nombres con `Ã`; provincias Guipúzcoa, Vizcaya y Álava con sus acentos.

# CELL ********************

for c in ["neighbourhood_cleansed", "neighbourhood_group_cleansed"]:
    reparado = F.decode(F.encode(F.col(c), "ISO-8859-1"), "UTF-8")
    df = df.withColumn(c, F.when(F.col(c).contains("Ã"), reparado).otherwise(F.col(c)))

print("con Ã restantes:", df.filter(F.col("neighbourhood_cleansed").contains("Ã")).count())
df.select("neighbourhood_group_cleansed").distinct().show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4c-3 Licencias a categorías
# **Qué:** creo `license_status` y `exempt_type`, y elimino `license`.
# **Por qué:** segmentar el comp set y no arrastrar texto libre con posibles datos personales.
# **Resultado:** `con_registro` 4.179, `exento` 1.232, `sin_dato` 738, `texto_libre` 99.

# CELL ********************

lic = F.col("license")
exento = F.trim(F.regexp_extract(lic, "Exempt - ([^<]+)", 1))

df = (df
    .withColumn("license_status",
        F.when(lic.isNull(), "sin_dato")
         .when(lic.contains("Exempt"), "exento")
         .when(lic.contains("Basque Country - Regional") | lic.contains("Spain - National"), "con_registro")
         .otherwise("texto_libre"))
    .withColumn("exempt_type", F.when(exento != "", exento))
    .drop("license"))

df.groupBy("license_status").count().show()
df.groupBy("exempt_type").count().orderBy(F.desc("count")).show()
print("license sigue en el DataFrame:", "license" in df.columns)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4c-4 Comprobaciones de calidad con gravedad
# **Qué:** cuento las filas que incumplen 9 reglas de sentido común. Las bloqueantes (ids únicos y flags sin nulos) detienen el notebook; las de aviso solo se muestran.
# **Por qué:** un `id` repetido o un flag nulo contaminan todo lo posterior; un dato fuera de rango suele ser un error local.
# **Resultado esperado:** 0 en las dos listas (igual que el silver de pandas).

# CELL ********************

def n(cond):
    return df.filter(cond).count()

bloquean = {
    "id duplicados": df.count() - df.select("id").distinct().count(),
    "flags con nulos": n(F.col("price_missing").isNull() | F.col("price_outlier").isNull() | F.col("is_long_stay").isNull()),
}
avisan = {
    "latitud fuera de 42-44": n(F.col("latitude").isNull() | ~F.col("latitude").between(42, 44)),
    "longitud fuera de -4 a -1": n(F.col("longitude").isNull() | ~F.col("longitude").between(-4, -1)),
    "accommodates <= 0": n(F.col("accommodates") <= 0),
    "availability_30 > availability_365": n(F.col("availability_30") > F.col("availability_365")),
    "precio <= 0": n(F.col("price_num") <= 0),
    "first_review > last_review": n(F.col("first_review") > F.col("last_review")),
    "reseñas 12m > totales": n(F.col("number_of_reviews_ltm") > F.col("number_of_reviews")),
}
print("BLOQUEAN:", bloquean)
print("AVISAN  :", avisan)
assert all(v == 0 for v in bloquean.values()), f"Validación bloqueante fallida: {bloquean}"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4d Escribir la tabla Delta en `lh_silver`
# **Qué:** añado `ciudad` y `snapshot_date` y escribo `Tables/listings` en Delta, particionada por ciudad y fecha.
# **Por qué:** `replaceWhere` reemplaza solo la partición de este snapshot, así que repetir la escritura no duplica y no toca los otros snapshots (idempotente).
# **Resultado esperado:** euskadi / 2026-06-30 / 6.248 filas, también tras ejecutarla dos veces.

# CELL ********************

salida = (df
    .withColumn("ciudad", F.lit(CIUDAD))
    .withColumn("snapshot_date", F.to_date(F.lit(SNAPSHOT))))

destino = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables/listings"

(salida.write.format("delta")
    .mode("overwrite")
    .option("replaceWhere", f"ciudad = '{CIUDAD}' AND snapshot_date = '{SNAPSHOT}'")
    .partitionBy("ciudad", "snapshot_date")
    .save(destino))

spark.read.format("delta").load(destino).groupBy("ciudad", "snapshot_date").count().show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

destino = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables/listings"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

spark.read.format("delta").load(destino).groupBy("ciudad", "snapshot_date").count().orderBy("ciudad", "snapshot_date").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************


# CELL ********************

destino = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables/listings"
spark.read.format("delta").load(destino).groupBy("ciudad", "snapshot_date").count().orderBy("ciudad", "snapshot_date").show(30)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

destino = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables/listings"
spark.read.format("delta").load(destino).groupBy("ciudad", "snapshot_date").count().orderBy("ciudad", "snapshot_date").show(30)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

dest_l = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables/listings"
spark.read.format("delta").load(dest_l).groupBy("ciudad", "snapshot_date").count().orderBy("ciudad", "snapshot_date").show(30)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
