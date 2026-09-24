-- ====================================================================================================
/* A reminder of relevant context:

In my watermain-break project,
there is a table called weather_daily that has a column named LOCAL_DATE of type date,
and a column called TOTAL_PRECIPITATION of type numeric.
It's Geometry type is Point (Point) and its Geometry collumn is geometry.
(There are other columns as well, but these are the relevant ones right now.)

There is also a column called PublicWaterMain_Pipes that has a column named length of type numeric
(that I believe is tied to the geometry of the table),
and a column named diam that is of type int4
(that measures the pipe diameter in mm),
and a column called year of type int4 storing the year the pipe was built.
(There are other columns as well, but these are the relevant ones right now.)

Note that both of these tables have a CRS of EPSG:4326.

I would like to make a new table derived from these two, using a standalone SQL script.

I want the table to have as a primary key, the year;
I want this ranging from 1956 (the first year in my watermain-break project) to current year.
I would like the following columns in it: number of days in that year (to make later daily-average calculations easier),
the total rainfall of that year, and the total length of the pipelines that existed up-to and including that year
(for example. for the year 1970 I want all pipelines that have a year value of 1970 or lower).

If we can get a unit of measurement for the distance,
I'd also like the total *volume* of pipelines that existed up-to and including that year,
using the pipeline length and diam as input for the calculation of cylinder volume. */



-- ==================================================================================================================================================
-- annual_watermain_weather_summary
-- ==================================================================================================================================================
--
-- One row per calendar year, 1956 through the current year, combining:
--   - weather_daily          ("LOCAL_DATE", "TOTAL_PRECIPITATION")
--   - PublicWaterMain_Pipes  (length, diam, year)
--
-- Run the two diagnostic queries below FIRST and read the results before
-- trusting the length/volume columns this script produces.

-- --------------------------------------------------------------------------------------

-- Diagnostic 1: what unit is `length` actually stored in?
--
-- Compares the stored attribute to a length computed straight from the
-- geometry, transformed into a metric projected CRS (NAD83 / UTM zone
-- 11N -- a reasonable fit for Calgary's longitude, plenty accurate for
-- an order-of-magnitude check).
--
--   ratio ~ 1     -> length is already in metres (assumption used below)
--   ratio ~ 3.28  -> length is in feet
--   ratio ~ 1000  -> length is in km, or a mm/m mismatch the other way
--   ratio ~ 0.001 -> length is in mm

-- --------------------------------------------------------------------------------------

--  SELECT
--      SUM(length) AS stored_length_sum,
--      SUM(ST_Length(ST_Transform(geometry, 26911))) AS geometry_length_m,
--      SUM(length) / NULLIF(SUM(ST_Length(ST_Transform(geometry, 26911))), 0) AS ratio
--  FROM "PublicWaterMain_Pipes";

-- --------------------------------------------------------------------------------------

--  RESULTS:
--  stored_length_sum:   5418758.8168
--  geometry_length_m:   5419941.406824013
--  ratio:               0.9997818075998895
--  CONFIRMED: ratio is ~1, unit is m
 
-- --------------------------------------------------------------------------------------

-- Diagnostic 2: any pipes with an unknown build year?
-- These are excluded from the cumulative totals below -- know the count
-- before you trust the numbers.

-- --------------------------------------------------------------------------------------

--  SELECT count(*) AS pipes_missing_year
--  FROM "PublicWaterMain_Pipes"
--  WHERE year IS NULL;

-- --------------------------------------------------------------------------------------

--  pipes_missing_year: 0
--  CONFIRMED: no pipes with missing year, which would break code
 


-- ==================================================================================================================================================
-- Section 01: Create table (will populate later)
-- ==================================================================================================================================================

DROP TABLE IF EXISTS annual_watermain_weather_summary;

CREATE TABLE annual_watermain_weather_summary (
    year                        int4    PRIMARY KEY,
    days_in_year                int4    NOT NULL,
    is_complete_year            boolean NOT NULL,
    total_precipitation_mm      numeric,
    cumulative_pipe_length_m    numeric NOT NULL,
    cumulative_pipe_volume_m3   numeric NOT NULL
);

-- ==================================================================================================================================================
-- Section 02: populate table using following style of syntax:
-- `INSERT INTO <table> WITH (...) SELECT (...)`
--      Section 02.1 - clause:  `INSERT INTO <table>`
--      Section 02.2 - clause:  `WITH (...)`
--      Section 02.3 - clause:  `SELECT (...)`
-- ==================================================================================================================================================

/*
conceptualizing how this works:

`INSERT INTO table VALUES (...)`:
base pattern

`INSERT INTO table SELECT (...)`:
use a `SELECT` statement to generate the values, instead of explicit declaration;
usually you'd be grabbing data from a table, but could be `SELECT 1` or `SELECT 'x'` 
or - more relevantlly - SELECT generate_series(1956, ...)

`INSERT INTO table WITH (...) SELECT (..)`:
doing `WITH (...) SELECT (...) instead of `SELECT (...)` means that
the `WITH (...)` statement generates a "CTE" - and once the "CTE" is defined in code,
the `SELECT (...)` clause can reference it

CTE: "Common Table Expression"
each `name AS (query)` is a CTE - a reuseable statement,
that later code in the same SQL statement can reference

NOTE: SQL has some good back-end optimizations on how it runs,
so the order of things written in the code might be very different from how it runs,
as SQL will take the statement and do optimization BS to it, THEN run it
*/

-- =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
--      Section 02.1: `INSERT INTO <table>` clause
-- =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

INSERT INTO annual_watermain_weather_summary


-- =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
--      Section 02.2: `WITH (...)` clause
-- =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

WITH
year_series AS (
    SELECT generate_series(1956, EXTRACT(YEAR FROM CURRENT_DATE)::int) AS year
),
 
days AS (
    SELECT
        year,
        (make_date(year + 1, 1, 1) - make_date(year, 1, 1))::int AS days_in_year
        -- make_date function: MAKE_DATE(year, month, dat) e.g. MAKE_DATE(2026, 09, 23)
        -- so this grabs Jan01 of following year, - Jan01 of current year, converts result to int, that's `days_in_year`
        -- also SQL functions are case-insensitive, which bothers me, but whatever
    FROM year_series
),
 
rainfall AS (
    SELECT
        EXTRACT(YEAR FROM "LOCAL_DATE")::int AS year,
        SUM("TOTAL_PRECIPITATION") AS total_precipitation_mm
    FROM weather_daily
    GROUP BY 1
    -- `GROUP BY `` groups by first column in SELECT statement, in this case `years_series`
    -- kinda want to change it to explicitly use `years_series`
),
 
-- Pipe length/volume added per build-year, across ALL years present in
-- the data -- not restricted to 1956+. A pipe built in, say, 1930 still
-- has to count toward every year's cumulative total from 1956 onward.
pipes_by_year AS (
    SELECT
        year,
        SUM(length) AS length_added,
        SUM(pi() * POWER(diam / 2000.0, 2) * length) AS volume_added_m3
    FROM "PublicWaterMain_Pipes"
    WHERE year IS NOT NULL
    GROUP BY year
),
 
-- Running total across build-years only
-- (sparse: one row per year that actually saw new pipe construction).
pipes_cumulative AS (
    SELECT
        year,
        SUM(length_added)    OVER (ORDER BY year ROWS UNBOUNDED PRECEDING) AS cumulative_length_m,
        SUM(volume_added_m3) OVER (ORDER BY year ROWS UNBOUNDED PRECEDING) AS cumulative_volume_m3
        -- so normally you tell SQL "do the sum over the previous X rows, and possible following rows, e.g.:
        -- SELECT t, a, avg(a) OVER (ORDER BY t ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) FROM data ORDER BY t
        -- UNBOUND PRECEDING means frame's lower boundary is infinite;
        -- it's useful when calculating running-totals/cumulative metrics
    FROM pipes_by_year
)


-- =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
--      Section 02.3: `SELECT (...)` clause
-- =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

-- NOTE:
-- a *table* alias (e.g. `ys` in `FROM year_series ys`) can be referenced
-- in the SELECT list even though it's textually defined later, in
-- FROM/JOIN -- because SQL has a fixed logical processing order that's
-- different from text order: roughly FROM/JOIN, WHERE, GROUP BY, HAVING,
-- SELECT, ORDER BY. FROM/JOIN resolves first regardless of where it's
-- written, so by the time SELECT runs, the alias already exists.
--
-- this does NOT apply the same way to *column* aliases (SELECT ... AS x)
-- those are only usable in GROUP BY / ORDER BY as a Postgres-specific
-- convenience, not in WHERE or HAVING.
SELECT
    ys.year,
    d.days_in_year,
    ys.year < EXTRACT(YEAR FROM CURRENT_DATE)::int AS is_complete_year,
    r.total_precipitation_mm, -- NOTE: this is nullable, as year with no weather record is missing data - so NULL
    COALESCE(pc.cumulative_length_m, 0)  AS cumulative_pipe_length_m, -- not nullable, as year prior to pipe existing
    COALESCE(pc.cumulative_volume_m3, 0) AS cumulative_pipe_volume_m3--  means the pipe's length/volume is 0
    -- COALESCE(A, B, C,... Z, AA, AB, AC... (inf mostly) -> use A, if A NULL use B, if B NULL use C, etc
    -- basically, this helps initialize starting cumulative values to 0
FROM year_series ys
-- ALIAS: year *table* alias ys

JOIN days d
-- ALIAS: days *table* alias d
ON d.year = ys.year

LEFT JOIN rainfall r
-- ALIAS: rainfall *table* alias r
ON r.year = ys.year

-- As-of join: for each calendar year, pull the most recent cumulative
-- pipe total at or before that year. A plain equi-join on year = year
-- would only populate rows where a pipe happened to be built in that
-- exact year, leaving every other year NULL instead of carried forward,
-- and would drop pre-1956 pipes entirely.
LEFT JOIN LATERAL (
    SELECT cumulative_length_m, cumulative_volume_m3
    FROM pipes_cumulative pc
    -- pipes_cumulative *table* alias pc
    WHERE pc.year <= ys.year
    ORDER BY pc.year DESC
    LIMIT 1
) latest_pipe_totals /* everything in brackets from 222-229 is ALIAS under "latest_pipe_totals" */ ON true
-- `ON true` is the join-condition (for the join that starts on 222) - so instead of "JOIN IF <condition>" it just always joins
-- because we've done a bunch of filtering in the sub-query, we don't actually need conditions here as well
ORDER BY ys.year;