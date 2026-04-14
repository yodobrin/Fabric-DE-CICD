-- Fabric notebook source

-- METADATA ********************

-- META {
-- META   "kernel_info": {
-- META     "name": "synapse_pyspark"
-- META   },
-- META   "dependencies": {
-- META     "lakehouse": {
-- META       "default_lakehouse": "a9adeeae-3b76-42fa-a5ab-16f510ee221a",
-- META       "default_lakehouse_name": "Lakehouse_Silver",
-- META       "default_lakehouse_workspace_id": "29cf286f-e35e-474a-8714-19263d6b1fc3",
-- META       "known_lakehouses": [
-- META         {
-- META           "id": "a9adeeae-3b76-42fa-a5ab-16f510ee221a"
-- META         }
-- META       ]
-- META     },
-- META     "environment": {}
-- META   }
-- META }

-- CELL ********************

select count(*) from dbo.t3

-- METADATA ********************

-- META {
-- META   "language": "sparksql",
-- META   "language_group": "synapse_pyspark"
-- META }

-- CELL ********************

select countryOrRegion, count(1) from dbo.t3 group by countryOrRegion

-- METADATA ********************

-- META {
-- META   "language": "sparksql",
-- META   "language_group": "synapse_pyspark"
-- META }

-- CELL ********************

select count(*) from dbo.t2

-- METADATA ********************

-- META {
-- META   "language": "sparksql",
-- META   "language_group": "synapse_pyspark"
-- META }

-- CELL ********************

select count(*) from dbo.t1

-- METADATA ********************

-- META {
-- META   "language": "sparksql",
-- META   "language_group": "synapse_pyspark"
-- META }
