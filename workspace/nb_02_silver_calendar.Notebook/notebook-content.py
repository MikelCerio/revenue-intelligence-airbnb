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

# MARKDOWN ********************

# # nb_02_silver_calendar
# **Objetivo:** leer `calendar` crudo de bronze, aplicar las reglas de silver con PySpark y escribir la tabla Delta `calendar` en `lh_silver`, particionada por ciudad y snapshot.
# **Entrada:** `lh_bronze/Files/<ciudad>/<fecha>/calendar.csv.gz`. **Grano:** un anuncio en una noche, visto desde un snapshot.

# MARKDOWN ********************


# MARKDOWN ********************

# ## Parámetros del notebook
# **Qué:** `CIUDAD` y `SNAPSHOT` por defecto; el pipeline los sustituye al llamar al notebook.
# **Por qué:** el mismo notebook procesa cualquier snapshot.

# PARAMETERS CELL ********************

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

# ## 5a Leer `calendar` con Spark
# **Qué:** leo el CSV y miro filas y columnas.
# **Resultado:** 2.281.585 filas y 5 columnas, igual que pandas.

# CELL ********************

ruta = f"Files/{CIUDAD}/{SNAPSHOT}/calendar.csv.gz"
df = spark.read.option("header", True).csv(ruta)
print(df.count(), df.columns)
df.show(3)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 5b Tipos y reglas de silver
# **Qué:** me quedo con las 5 columnas comunes, fijo los tipos y paso `available` de `t`/`f` a booleano; falla si aparece otro valor.
# **Por qué:** los `calendar` antiguos traen `price` y `adjusted_price` vacías; con las 5 columnas todos los snapshots tienen el mismo esquema.
# **Resultado esperado:** fechas de 2026-06-30 a 2027-07-02, 6.251 anuncios; `available`: true 1.149.871 y false 1.131.714.

# CELL ********************

from pyspark.sql import functions as F

df = (df.select("listing_id", "date", "available", "minimum_nights", "maximum_nights")
        .withColumn("listing_id", F.col("listing_id").cast("long"))
        .withColumn("date", F.to_date("date"))
        .withColumn("minimum_nights", F.col("minimum_nights").cast("int"))
        .withColumn("maximum_nights", F.col("maximum_nights").cast("int")))

malos = df.filter(F.col("available").isNotNull() & ~F.col("available").isin("t", "f")).count()
assert malos == 0, "Valores inesperados en available"
df = df.withColumn("available", F.when(F.col("available") == "t", True).when(F.col("available") == "f", False))

df.printSchema()
df.agg(F.min("date"), F.max("date"), F.countDistinct("listing_id")).show()
df.groupBy("available").count().show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 5c Comprobaciones de calidad con gravedad
# **Qué:** cuento filas que incumplen reglas. Las bloqueantes (clave duplicada, `available` o claves nulos) detienen el notebook; las de aviso solo se muestran.
# **Por qué:** una noche duplicada infla la ocupación; un dato fuera de rango suele ser un error local.
# **Resultado esperado:** 0 en las bloqueantes. Las de aviso pueden no ser 0: si no lo son, se anota.

# CELL ********************

def n(cond):
    return df.filter(cond).count()

bloquean = {
    "(listing_id, date) duplicados": df.count() - df.select("listing_id", "date").distinct().count(),
    "available nulo": n(F.col("available").isNull()),
    "date o listing_id nulos": n(F.col("date").isNull() | F.col("listing_id").isNull()),
}
avisan = {
    "minimum_nights < 1": n(F.col("minimum_nights") < 1),
    "maximum_nights < minimum_nights": n(F.col("maximum_nights") < F.col("minimum_nights")),
    "fecha anterior al snapshot": n(F.col("date") < F.to_date(F.lit(SNAPSHOT))),
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

# ## 5d Escribir la tabla Delta `calendar` en `lh_silver`
# **Qué:** añado `ciudad` y `snapshot_date` y escribo `Tables/calendar` en Delta, particionada por ciudad y fecha.
# **Por qué:** `replaceWhere` reemplaza solo la partición de este snapshot, así que repetir no duplica ni toca los demás (idempotente).
# **Resultado esperado:** euskadi / 2026-06-30 / 2.281.585 filas, también tras ejecutarla dos veces.

# CELL ********************

salida = (df
    .withColumn("ciudad", F.lit(CIUDAD))
    .withColumn("snapshot_date", F.to_date(F.lit(SNAPSHOT))))

destino = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables/calendar"

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

destino = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables/calendar"
spark.read.format("delta").load(destino).groupBy("ciudad", "snapshot_date").count().orderBy("ciudad", "snapshot_date").show(30)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

destino = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables/calendar"
spark.read.format("delta").load(destino).groupBy("ciudad", "snapshot_date").count().orderBy("ciudad", "snapshot_date").show(30)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

destino = "abfss://revenue-intelligence-airbnb@onelake.dfs.fabric.microsoft.com/lh_silver.Lakehouse/Tables/calendar"
df_c = spark.read.format("delta").load(destino)
df_c.groupBy("ciudad", "snapshot_date").count().orderBy("ciudad", "snapshot_date").show(30)
print("particiones:", df_c.select("ciudad", "snapshot_date").distinct().count(), "| filas totales:", df_c.count())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
