# Front End Overview

## Frontend stack & skeleton

React + TypeScript, MapLibre for the map layers.  
Skeleton work: routing for the five dashboard pages, a shared layout/nav, and a typed API client -  
optionally generated with `openapi-typescript` off your FastAPI OpenAPI schema,  
since you're already disciplined about typing on the backend.

## Build order (recommended, least → most risky)

1.  **Executive Overview:** 
First, because it's the lowest-risk page and proves the full round trip (browser → FastAPI → PostGIS → browser)  
before you touch anything harder. KPI cards (total breaks, date range covered, avg breaks/year)  
plus maybe one time-series chart.

2.  **Infrastructure & Incident Map:**  
The centerpiece and highest-risk page. MapLibre GeoJSON source/layer setup,  consuming the full-table endpoints for `city_boundary`,  
`city_districts`, `hydrology`, `watermain_pipes`, `watermain_breaks`, and the two highlight layers (`select_watermain_breaks`, `select_watermain_pipes`).  
Clustering at zoom-out for the point layers, popups/tooltips on click, and labeling driven by hydrology.lake_name and city_districts.name.

3.  **Precipitation/Breaks and Temperature/Breaks:**  
Mostly chart work once the data-fetching pattern from step 1 is proven:  
correlation/scatter plots and dual-axis time series, consuming date-filtered weather data.

4.  **Breaks Over Time:**  
Last, likely the simplest once the aggregation endpoint pattern is established from the other pages.

## Data-shape decisions that affect the frontend

**Server-side aggregation over client-side.**  
FastAPI returns pre-aggregated rows for charts rather than shipping years of raw breaks/weather records to the browser for React to crunch.

**Two response shapes, not one.**
  Map-consuming components (Incident Map) get `GeoJSON FeatureCollection`s.  
  Chart-consuming components (`weather_daily`/`weather_hourly`) get plain JSON arrays of `{date, value}`-style records (not GeoJSON)  
   since wrapping each row in a `Feature` just repeats the same station geometry across thousands of rows for data your charts don't treat spatially at all.