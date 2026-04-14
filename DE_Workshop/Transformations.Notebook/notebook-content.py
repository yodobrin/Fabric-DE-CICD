# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "a9adeeae-3b76-42fa-a5ab-16f510ee221a",
# META       "default_lakehouse_name": "Lakehouse_Silver",
# META       "default_lakehouse_workspace_id": "29cf286f-e35e-474a-8714-19263d6b1fc3",
# META       "known_lakehouses": [
# META         {
# META           "id": "a9adeeae-3b76-42fa-a5ab-16f510ee221a"
# META         },
# META         {
# META           "id": "1a3f128d-8687-4aea-b559-8e9b77df5d06"
# META         }
# META       ]
# META     },
# META     "environment": {}
# META   }
# META }

# CELL ********************

# MAGIC %%sql
# MAGIC 
# MAGIC create table dbo.t1 using DELTA as (
# MAGIC     select * from t2 full outer join t3 limit 10000
# MAGIC ) 

# METADATA ********************

# META {
# META   "language": "sparksql",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# MAGIC %%sql
# MAGIC 
# MAGIC optimize dbo.t1 vorder

# METADATA ********************

# META {
# META   "language": "sparksql",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# MAGIC %%sql
# MAGIC 
# MAGIC select age, countryOrRegion, count(1) as total from dbo.t1 group by age, countryOrRegion sort by 3 desc

# METADATA ********************

# META {
# META   "language": "sparksql",
# META   "language_group": "synapse_pyspark"
# META }
