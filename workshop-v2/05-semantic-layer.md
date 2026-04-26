# Module 5: Update the Semantic Model & Report

> **User Story:** *As an Analytics Engineer, I want to expose t5 in the semantic model and add a visual to the report, so that business users see the new KPI without any downtime or data refresh issues.*

**Duration:** 25 minutes | **Persona:** Analytics Engineer | **Depends on:** Module 4

## Context

Table `t5` exists in Silver but isn't visible to report consumers yet. You need to add it to the semantic model (TMDL) and optionally update the report.

## Exercise 1: Understand the Semantic Model Structure (5 min)

Examine the TMDL files:

```
DE_Workshop/MySemanticModel.SemanticModel/
├── .platform                          # Item metadata
├── definition.pbism                   # Model project file
└── definition/
    ├── database.tmdl                  # Database settings
    ├── expressions.tmdl               # Data source (SQL endpoint connection)
    ├── model.tmdl                     # Table references
    └── tables/
        └── t1.tmdl                    # Column definitions for t1
```

Key files:
- `model.tmdl` — declares which tables the model exposes (currently only `ref table t1`)
- `tables/t1.tmdl` — column-level definitions, data types, lineage tags
- `expressions.tmdl` — the SQL endpoint connection string (has placeholder GUIDs)

> **Reference:** [Semantic Model Definition](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/semantic-model-definition)

## Exercise 2: Add t5 to the Model (10 min)

### Step 1: Add table reference

Edit `DE_Workshop/MySemanticModel.SemanticModel/definition/model.tmdl`:

```
ref table t1

ref table t5
```

### Step 2: Create the table definition

Create `DE_Workshop/MySemanticModel.SemanticModel/definition/tables/t5.tmdl`:

```
table t5
	lineageTag: c7a1d2e3-f4b5-4c6d-8e9f-0a1b2c3d4e5f
	sourceLineageTag: [dbo].[t5]

	column AGE
		dataType: int64
		formatString: 0
		sourceProviderType: bigint
		lineageTag: d8b2e3f4-a5c6-4d7e-9f0a-1b2c3d4e5f6a
		sourceLineageTag: AGE
		summarizeBy: none
		sourceColumn: AGE

		annotation SummarizationSetBy = User

	column BMI
		dataType: double
		sourceProviderType: float
		lineageTag: f0d4a5b6-c7e8-4f9a-1b2c-3d4e5f6a7b8c
		sourceLineageTag: BMI
		summarizeBy: none
		sourceColumn: BMI

		annotation SummarizationSetBy = User

	column countryOrRegion
		dataType: string
		sourceProviderType: varchar(8000)
		lineageTag: a1e5b6c7-d8f9-4a0b-2c3d-4e5f6a7b8c9d
		sourceLineageTag: countryOrRegion
		summarizeBy: none
		sourceColumn: countryOrRegion

		annotation SummarizationSetBy = User

	column holidayName
		dataType: string
		sourceProviderType: varchar(8000)
		lineageTag: b2f6c7d8-e9a0-4b1c-3d4e-5f6a7b8c9d0e
		sourceLineageTag: holidayName
		summarizeBy: none
		sourceColumn: holidayName

		annotation SummarizationSetBy = User

	column created_timestamp
		dataType: dateTime
		formatString: General Date
		sourceProviderType: timestamp
		lineageTag: c3a7d8e9-f0b1-4c2d-4e5f-6a7b8c9d0e1f
		sourceLineageTag: created_timestamp
		summarizeBy: none
		sourceColumn: created_timestamp

		annotation SummarizationSetBy = User

	partition t5 = entity
		mode: directLake
		source
			entityName: t5
			schemaName: dbo
			expressionSource: DatabaseQuery

	annotation PBI_ResultType = Table
```

> **Note:** `lineageTag` values must be unique GUIDs. Generate new ones for your tables.

## Exercise 3: Deploy the Model Update (5 min)

Semantic model updates work through Git Integration — the TMDL files are fully versioned.

```bash
# Commit the TMDL changes
git add DE_Workshop/MySemanticModel.SemanticModel/
git commit -m "feat: add t5 table to semantic model"
git push
```

In Fabric:
1. **Source Control** → "1 incoming change" → **Update all**
2. Fabric applies the TMDL change — the semantic model now includes t5

> **Note:** If Git Integration fails to apply the model (e.g., capacity throttled), fall back to SDK:
> ```bash
> python3 bootstrap.py deploy-item --on-exists update --item semantic_model ...
> ```

## Exercise 4: Verify in Fabric (5 min)

1. Open `MySemanticModel` in the Fabric portal
2. Check that **t5** appears as a table alongside **t1**
3. Open `MyReport` — if you add a new visual, you should see t5 columns available (AGE, BMI, countryOrRegion, holidayName, created_timestamp)

## Checkpoint

- [ ] `model.tmdl` has `ref table t5`
- [ ] `tables/t5.tmdl` exists with column definitions
- [ ] Semantic model in Fabric shows t5 as a table
- [ ] You can explain: TMDL format, lineage tags, DirectLake partitions

## Key Takeaway

> The semantic model is versioned as TMDL text files — fully diffable, reviewable in a PR, and deployable via Git or SDK. Adding a table to the model doesn't affect existing tables or reports. The report automatically sees new tables when the model is refreshed.
>
> **Further reading:**
> - [TMDL Overview](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview)
> - [Update Item Definition API](https://learn.microsoft.com/en-us/rest/api/fabric/core/items/update-item-definition)
> - [Semantic Model Definition Structure](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/semantic-model-definition)
