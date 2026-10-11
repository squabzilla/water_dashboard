# List of Pages for Dashboard

1.  Executive Overview
2.  Infrastructure & Incident Map
3.  Breaks Over Time (add graph-builder later, not as MVP)
4.  Analyzing Precipitation and Watermain Breaks
5.  Analyzing Weather and Watermain breaks

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

3.  **Breaks Over Time:**  
Likely the simplest once the aggregation endpoint pattern is established from the other pages.  
I mean I want a graph-builder eventually, but not as part of MVP.

4.  **Precipitation/Breaks:**  
NOTE: This is no longer part of MVP.  
Mostly chart work once the data-fetching pattern from step 1 is proven:  
correlation/scatter plots and dual-axis time series, consuming date-filtered weather data.

4.  **Temperature/Breaks:**  
NOTE: This is no longer part of MVP.  
This requires setup, where I make a new table with each break,  
(hmm, old-break-table needs some UID to link them, why doesn't OG data have one...)  
and add columns for weather characteristic  
So like a column for weather 9 days before, 8 days before, 7, etc...  
With all sorts of different attributes like rain, air pressure, temperature...  
Could find some interesting results here. The SQL alone will be a nightmare.  
This is definitely a LATER thing, but it's still interesting...  

## Data-shape decisions that affect the frontend

**Server-side aggregation over client-side.**  
FastAPI returns pre-aggregated rows for charts rather than shipping years of raw breaks/weather records to the browser for React to crunch.

**Two response shapes, not one.**
  Map-consuming components (Incident Map) get `GeoJSON FeatureCollection`s.  
  Chart-consuming components (`weather_daily`/`weather_hourly`) get plain JSON arrays of `{date, value}`-style records (not GeoJSON)  
   since wrapping each row in a `Feature` just repeats the same station geometry across thousands of rows for data your charts don't treat spatially at all.