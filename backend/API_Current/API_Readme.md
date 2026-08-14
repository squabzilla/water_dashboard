# Readme for the APIs

This document will outline the various APIs I'm retrieving data from.

There are two main kinds of data:  
- **Base Layers**, for mapping vector layers I am grabbing once. These layers I can about their (visual) shape, not really the data.
- **Database Layers**, for items I can about the data (and maybe coordinates of), but not the visual shape.

## Base Layers
- **Public Water Main**, shows the network of pipes throughout the city.  
*It's an interesting visual layer, and there's no overhead for importing it.*  
*Link:* https://data.calgary.ca/Services-and-Amenities/Public-Water-Main/w6h9-w33i/about_data
- **Hydrology**, a layer that gets me waterbodies (rivers, lakes, ponds) for the city of Calgary.  
*Link:* https://data.calgary.ca/Environment/Hydrology/47bt-eefd/about_data
- **Community District Boundaris**, showing the various communities of the city.  
*Link:* https://data.calgary.ca/Base-Maps/Community-District-Boundaries/surr-xmvs/about_data 
- **City Boundary** showing the boundary of the city itself.  
*Link:* https://data.calgary.ca/Base-Maps/City-Boundary/erra-cqp9/about_data

## Database Layers
- **WatermainBreaks**, the core feature of the dashboard.  
*Link:* https://data.calgary.ca/Environment/Water-Main-Breaks/dpcu-jr23/about_data
- **Weather**, which is its own topic.  
*Link to API docs:* https://api.weather.gc.ca/openapi  

## Files:  
Here is a list of files in the API folder:  
- `API_Readme.md`  
This file
- `base_layers.py`  
Python file that fetches my *City of Calgary* base layers.
- `waterMainBreaks_APIlogic.py`  
Python file that contains a function for the API-logic used when querying the *Water Main Breaks* API
- `waterMainBreaks_backfill.py`  
Python file that backfills my PostGIS database, with *Water Main Breaks* data from `1956-01-01` onwards.
- `waterMainBreaks_runHourly.py`  
Python file for my hourly-query of the *Water Main Breaks* data.
- `weather_APIlogic.py`  
Python file that contains the core logic for querying *MSC GeoMet* data from `https://api.weather.gc.ca/`
- `weather_daily_backfill.py`  
Python file that will backfill my **weather_data_daily** table, using data from `collections/climate-daily`
- `weather_daily_runDaily.py`  
Python file to be run every day to update my **weather_data_daily** table, using data from `collections/climate-daily`
- `weather_hourly_backfill.py`  
Python file that will backfill my **weather_data_hourly** table in my database, using data from `collections/climate-hourly`
Yes it's almost identical to `weather_hourly_runDaily.py`, no I don't care.
- `weather_hourly_runDaily.py`  
Python file to be run every day to update my **weather_data_hourly** table, using data from `collections/climate-hourly`  
Yes it's almost identical to `weather_hourly_backfill.py`, no I don't care.
- `weather_hourly_runHourly.py`
Python file to be run every *hour* to update my **weather_data_hourly** table, using data from `collections/swob-realtime`



- `weather_climate-daily.py`  
Python file that queries *MSC GeoMet* `collections/climate-daily` data.  
Will have a command-line toggle of `-b` that determines if it 
and backfills our database from `1956-01-01` onwards.
- `weather_climate-daily_runDaily.py`  
Python file that queries *MSC GeoMet* `collections/climate-daily`, and is run once-per-day to update our **weather_data_daily** table.
- `weather_climate-hourly_runDaily.py`  
Python file that queries *MSC GeoMet* `collections/climate-hourly`, and is run once-per-day to update our **weather_data_hourly** table.


I want TWO weather-data tables:  
- **weather_data_daily**
- **weather_data_hourly**

### WatermainBreaks

The earliest date for WatermainBreaks is 1956-01-01. Just for fun, I will have all the data in my DB.  
This means in the ***Backfill*** step, I will need to ensure I grab it from 1956 onwards.

This data will be stored in the **watermain_breaks** table.

Because it's possible that a WatermainBreak record could be changed after its creation (perhaps due to changing the **STATUS** or **BREAK_TYPE** value),  
I will want to run this ***Hourly*** to keep it up-to-date.  
Given that there's only a few hundred a year, I can grab the last *two-years* worth of data every hour, overwriting existing data in my DB.  
I will store this data in the **watermain_breaks_staging** table, and then merge with the main **watermain_breaks** table.  
Note that I need a *unique-column* for overwriting records. I'll merge the **BREAK_DATE** and **point** columns to make a **UNIQUE_KEY** column.

### Weather

I want TWO weather-data tables:  
- **weather_data_daily**
- **weather_data_hourly**

The weather data comes from  **Environment And Climate Change Canada** *MSC GeoMet - GeoMet-OGC-API, (link:* https://api.weather.gc.ca/ *)*.  
There are three main sub-items I want to retrieve:  
- **climate-daily** *link:* https://api.weather.gc.ca/openapi#/climate-daily 
- **climate-hourly** *link:* https://api.weather.gc.ca/openapi#/climate-hourly 
- **swob-realtime** *link:* https://api.weather.gc.ca/openapi#/swob-realtime 

The table **weather_data_daily** will use the **climate-daily** data from the *MSC GeoMet - GeoMet-OGC-API*.  
See the [Daily-Weather](#daily-weather) section for more detail.  

The table **weather_data_hourly** will use both the **climate-hourly** and **swob-realtime** from the *MSC GeoMet - GeoMet-OGC-API*.  
See the [Hourly-Weather](#hourly-weather) section for more detail.

I will need to select specific *weather-stations* to retrieve data from this API.  
The particulars of which *weather-stations* to use was determined during exploratory analysis, and the results are explained in the [next section](#weather-stations).

#### Weather-Stations

During exploratory analysis, I determined THREE stations I want to use as a source-of-truth for my weather-data:  
| STATION_NAME | CLIMATE_IDENTIFIER | DLY_FIRST_DATE | DLY_LAST_DATE | HLY_FIRST_DATE | HLY_LAST_DATE | source-of-truth |
| ------------ | ------------------ | ---------------| ------------- | -------------- | ------------- | --------------- |
| CALGARY INT'L CS | 3031094 | 1999-05-01 | *(current)* | 2008-12-22 | *(current)* | **Primary** |
| CALGARY INTL A | 3031092 | 2012-07-12 | *(current)* | 2012-07-09 | *(current)* | **Secondary** |
| CALGARY INT'L A | 3031093 | 1881-10-01 | 2012-07-11 | 1953-01-01 | 2012-07-12 | **Tertiary** |

I will use the **CLIMATE_IDENTIFIER** values when referencing these stations in my code.  

I want TWO main databases: **weather_data_daily** and **weather_data_hourly**. I also want a **weather_stations** to store meta-data about these tables.  

For  **weather_data_daily** and **weather_data_hourly**, I want my table to store ONE record per day/hour, respectively.  
This means that if multiple stations have data at the same *date-time*, I need reduce it to one single record.  
I reduce (potentially) overlapping data by ranking these stations, as the **Primary**, **Secondary**, and **Tertiary** source-of-truth. *(See table.)*  
To clarify, this means I will only use data from the **Primary** *source-of-truth* if available, followed by the **Secondary** and lastly the **Tertiary** *source-of-truth*.

#### Daily-Weather

I want to fill the **weather_data_daily** table, querying the following API:  
https://api.weather.gc.ca/openapi#/climate-daily  

I want to retrieve the following *properties* when querying the API:  
- STATION_NAME
- CLIMATE_IDENTIFIER
- LOCAL_DATE
- MEAN_TEMPERATURE
- MAX_TEMPERATURE
- MIN_TEMPERATURE
- TOTAL_PRECIPITATION
- TOTAL_RAIN
- TOTAL_SNOW

Remember that I want to query data from stations `3031094`, `3031092`, and `3031093`.  
I have these stations listed here in their *source-of-truth* priority order (see [Weather-Stations](#weather-stations) for more detail on this.)  
This means if I have multiple records on the same date, I want to use data from station `3031094` if possible,  
followed by station `3031092`, and finally station `3031093`.

As mentioned in the [WatermainBreaks section](#watermainbreaks), the earliest date for WatermainBreaks is 1956-01-01.  
This means during the ***Backfill*** section, I want to grab daily records from 1956-01-01 onwards.

I also want to retrieve data from this API ***Daily*** to keep it up-to-date, grabbing the last 30 calendar days of data, and *overwriting* existing data in my DB.  
Note that this involves querying my data, storing it in a **weather_data_daily_staging** table, and *then* merging it with the main table.

Some code Claude made to merge stations by priority - while I don't want to just *blindly* use Claude code, it's a useful starting point:

```
import pandas as pd

# Lower number = higher priority
STATION_PRIORITY = {
    "3031094": 1,  # primary
    "3031092": 2,  # secondary
    "3031093": 3,  # tertiary
}

def merge_stations_by_priority(
    dfs: list[pd.DataFrame],
    date_col: str = "local_date",
    station_col: str = "CLIMATE_IDENTIFIER",
) -> pd.DataFrame:
    combined = pd.concat(dfs, ignore_index=True)
    combined["_priority"] = combined[station_col].map(STATION_PRIORITY)

    if combined["_priority"].isna().any():
        unknown = combined.loc[combined["_priority"].isna(), station_col].unique()
        raise ValueError(f"No priority mapping for station id(s): {unknown}")

    merged = (
        combined
        .sort_values([date_col, "_priority"])
        .drop_duplicates(subset=date_col, keep="first")
        .drop(columns="_priority")
        .sort_values(date_col)
        .reset_index(drop=True)
    )
    return merged
```

#### Hourly-Weather

I want to fill the **weather_data_hourly** Table with hourly data from the past *two-weeks*.

I will need to query the following ***two** APIs to retrieve this data:
- **climate-hourly** *link:* https://api.weather.gc.ca/openapi#/climate-hourly 
- **swob-realtime** *link:* https://api.weather.gc.ca/openapi#/swob-realtime 

First, let's explain the columns that will be in our **weather_data_hourly** table:  
- STATION_NAME
- CLIMATE_IDENTIFIER
- LOCAL_DATE
- UTC_DATE
- TEMP
- PRECIP_AMOUNT

The **climate-hourly** API is the best data-source for this, but doesn't include the most recent, real-time data.  
It is only updated once-per-day, and typically lacks data for the past couple days.
Thus we will supplement this with data from the **swob-realtime** API.

***NOTE: WE WILL ONLY BE USING STATION `3031094` FOR THE HOURLY-WEATHER-DATA***  
The reason for the other two stations is when retrieving data from before our **Primary** source-of-truth, STATION `3031094`, was active.  
However, for the most recent data, STATION `3031094` is active and has data formatted in the way most suitable for our needs.  
Plus, the hourly queries to the **swob-realtime** API potentially grab 72 hours of per-minute data, up to 4320 records.  
We don't want to multiply this by three stations, plus the two other stations don't have **swob-realtime** in our preferred format.  

The **weather_data_hourly** Table is based on the columns from the **climate-hourly** API.  
Below is a table comparing items from the **weather_data_hourly** table, the **climate-hourly** API, and the **swob-realtime** API.  
*(Note that columns for the* **weather_data_hourly** *table were based on the* **climate-hourly** *API, so there's a 1-1 match there.)*  
| **weather_data_hourly** table | **climate-hourly** API | **swob-realtime** API |
|------------------------------ | ---------------------- | --------------------- |
| STATION_NAME | STATION_NAME | stn_nam-value |
| CLIMATE_IDENTIFIER | CLIMATE_IDENTIFIER | clim_id-value |
| UTC_DATE | UTC_DATE | date_tm-value |
| LOCAL_DATE | LOCAL_DATE | *will need be be calculated from* date_tm-value |
| TEMP | TEMP | avg_air_temp_pst1hr |
| PRECIP_AMOUNT | PRECIP_AMOUNT | pcpn_amt_pst1hr |

For the ***Backfill*** step, we will retrieve records for the past two weeks, and export them to our database as a new table.

We will also run an API call to the **climate-hourly** API on a ***Daily*** basis.  
We will retrieve records for the past two weeks during this API call.
During this, records older than two weeks will be deleted, and conflicts on the date-time values will favour new data over old data.

While the ***Backfill*** and ***Daily*** API call are almost identical, we will still have separate scripts for each for clarity.


We will also run an API call to the **swob-realtime** API on an ***Hourly*** basis.  
I want to run this 2 minutes *past* the top of the hour tho.  
Please remember to only query STATION `3031094` for this.

Once we retrieve this data, we will need to filter it to only *on-the-hour* records (where the **minute** is `00`).  
I can do a "nearest-neighbour" approach, where I filter it to the *nearest* result to the top of the hour.  
However, if I do this, I need to modify the `date_tm-value` so that the minutes are changed to `00`.  

Here's some code Claude wrote to filter to just top-of-hour.  
While I don't want to just *blindly* follow Claude code, it's a useful starting point:

```
def nearest_to_hour(
    df: pd.DataFrame,
    datetime_col: str = "date_tm",
    tolerance_minutes: int = 5,
) -> pd.DataFrame:
    """
    Keep the report nearest each top-of-hour, within tolerance.
    Since avg_air_temp_pst1hr and pcpn_amt_pst1hr are already 1hr
    aggregates from ECCC, this just selects the report representing
    each hour - no further aggregation needed.
    """
    df = df.sort_values(datetime_col).set_index(datetime_col)
    hourly_index = pd.date_range(
        df.index.min().floor("h"), df.index.max().ceil("h"), freq="h"
    )
    result = df.reindex(
        hourly_index, method="nearest", tolerance=pd.Timedelta(minutes=tolerance_minutes)
    )
    return result.reset_index().rename(columns={"index": datetime_col})
```
