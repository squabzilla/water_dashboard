# Title

## List of tables in DB

| Table | Full retrieval | Why |
| ----- | -------------- | --- |
| `city_boundary` | Yes | 1 row, needed for whole map extent |
| `city_districts` | Yes | needed for whole boundaries, + `name` for labels |
| `hydrology` | Yes | needed for whole lake/river features, plus possible `lake_name` features |
| `watermain_pipes` | Yes | needed for whole pipe-network layer to be visible
| `watermain_breaks` | Yes | needed for whole incident map |
| `select_watermain_breaks` | Yes | shows the catastrophic Bearspawn watermain breaks |
| `select_watermain_pipes` | Yes | shows the waterpipes associated with the catastrophic Bearspawn watermain breaks |
| `weather_stations` | Yes? | unsure if I'll use, but probably harmless to include |
| `weather_daily` | No | exists for records, not spatial attribute; want filtered, non-spatial JSON |
| `weather_hourly` | No | exists for records, not spatial attribute; want filtered, non-spatial JSON |
| `weather_daily_staging` | No | staging table - exclude |
| `weather_hourly_staging` | No | staging table - exclude |

## Backend - query builder

| Function/Object | Status | Note |
| -------- | -------- | -------- |
| `ColumnCategory(StrEnum)` | Done, located in `schema_constants.py` | A high-level categorization of different internal-column types (Not PSQL types)  |
| `PG_TYPE_TO_CATEGORY` mapping | Done, located in `schema_constants.py` | Maps my PSQL column-types to internal-column types. |
| `OPERATORS_BY_COLUMN_CATEGORY` mapping | Done, located in `schema_constants.py` | Maps what kind of (internal) operation is allowed on what type of table. |
| `OPERATOR_TO_SQL_SYMBOL` mapping | Done, located in `schema_constants.py` | Maps the internal operations defined in `OPERATORS_BY_COLUMN_CATEGORY` into proper SQL operator. |
| `KNOWN_TABLES` | Done, located in `schema_constants.py` | A tuple of my defined tables. Also hey I'm intentionally using a tuple! |
| `schema_constants.py` | Done | Hey, it's the actual .py file for all the above. |
| `load_schema_registry(conn)` | Written, needs unit tests | builds `{table_1: {col_1: type, col_2: type}, table_2 {col_1: type, col_2:type} }` nested `dict`s |
| `build_where_clause(table, filters, registry)` | Claude thinks its done, still needs work | validates tables, helps builds parameterized `WHERE` clauses for PSQL |
| `FilterError` | Written | Raises my error messages. |

NOTE: the `build_where_clause` function needs to build an SQL function that grabs a `jsonb_build_object`  
that gets returned as exactly one row, and exactly one column.  
The *contents* of that single-row, single-column are a full JSON of all the data you want.  
Later, the `execute_scalar` function will execute that SQL-statement, and unwrap the JSON for Python to use.  
Remember the weird unwrapping of GeoJSONs I had to do? The `jsonb_build_object` makes those.  
Which is why I'll need to unwrap them later.

### Unit tests

- testing `load_schema_registry(conn)` on fake `dict`s
- triggering `FilterError` on bad table/column/operator
- ensuring good SQL *valid* filters

## Backend - main

| Function | Status | Note |
| -------- | ------ | ---- |
| `app = FastAPI()` skeleton | Not yet build | trivial, but required for `@app.get` to work |
| `SPATIAL_LAYER_TABLES` | Designed, not built | renamed from `ALLOWED_FULL_TABLES` to current |
| `get_full_table(table: DatabaseTables)` | Designed, not yet built | fetch from PostGIS with GET; should give `403` error if fail |
| `get_geometry_column(table)` | Not yet written | small helper to look up geometry column based on table |
| `execute_scalar(sql, params)` | Not yet written | executes SQL clause from `build_where_clause`, and unwraps the returned object |
| `TestClient` to test both endpoints | Not started | FastAPI's built-in testing tool, letting me test API routes without starting a server or listening on a port. |

NOTE: The `TestClient` function is useful from a portfolio development standpoint,  
even tho I could just as easily test on my real, locally-hosted database.