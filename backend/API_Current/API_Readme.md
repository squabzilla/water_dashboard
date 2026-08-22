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
- `base_city_layers.py`  
Python file that fetches my *City of Calgary* base layers.
- `waterMainBreaks_backfill.py`  
Python file that backfills my PostGIS database, with *Water Main Breaks* data from `1956-01-01` onwards.
- `waterMainBreaks_checkAPI.py`  
Python file for that queries the *Water Main Breaks* data for any updates, by checking the `:created_at` meta-data from Socrata.
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
- `weather_stations.py`  
Python file to fetch our selected weather stations, and put them in our SQL database



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
- LOCAL_YEAR
- MEAN_TEMPERATURE
- MAX_TEMPERATURE
- MIN_TEMPERATURE
- TOTAL_PRECIPITATION
- MIN_REL_HUMIDITY
- MAX_REL_HUMIDITY
- SNOW_ON_GROUND
- HEATING_DEGREE_DAYS
- COOLING_DEGREE_DAYS

Remember that I want to query data from stations `3031094`, `3031092`, and `3031093`.  
I have these stations listed here in their *source-of-truth* priority order (see [Weather-Stations](#weather-stations) for more detail on this.)  
This means if I have multiple records on the same date, I want to use data from station `3031094` if possible,  
followed by station `3031092`, and finally station `3031093`.

As mentioned in the [WatermainBreaks section](#watermainbreaks), the earliest date for WatermainBreaks is 1956-01-01.  
This means during the ***Backfill*** section, I want to grab daily records from 1956-01-01 onwards.

I also want to retrieve data from this API ***Daily*** to keep it up-to-date, grabbing the last 30 calendar days of data, and *overwriting* existing data in my DB.  
Note that this involves querying my data, storing it in a **weather_data_daily_staging** table, and *then* merging it with the main table.

***Note about included and omitted columns:***

##### Daily-Weather: Included and Omitted Columns

The goal of the data-pipeline is to have all relevant data for a deep analysis of **Temperature and Watermain-breaks**,  
even if some (or all) of that analysis ultimately ends up outside of the project scope.  
It is easier to include extra data in the data-pipeline *from the beginning*,  
then it is to modify the pipeline to include new data in the future.

***Included columns:***  
`STATION_NAME` - useful meta-data.  
`CLIMATE_IDENTIFIER` - useful meta-data.  
`LOCAL_DATE` - we want the date of a weather-reading.  
`LOCAL_YEAR` - makes it easy to filter data by year when retrieving api data.  
`MEAN_TEMPERATURE` - basic temperature information.  
`MAX_TEMPERATURE` - basic temperature information.  
`MIN_TEMPERATURE` - basic temperature information.  
`TOTAL_PRECIPITATION` - basic temperature information.  
`MIN_REL_HUMIDITY` - humidity might be relevant for a detailed analysis of watermain-breaks and weather.  
`MAX_REL_HUMIDITY` - humidity might be relevant for a detailed analysis of watermain-breaks and weather.  
`SNOW_ON_GROUND` - standing snow can insulate soil and slow frost penetration,  
while bare/thin snow cover in extreme cold lets frost penetrate deeper and faster.  
Frost penetration could be very related to watermain-breaks.  
`HEATING_DEGREE_DAYS` - a standard derived metric for heating demand, and heating demand is potentially related to watermain-breaks.  
`COOLING_DEGREE_DAYS` - a standard derived metric for cooling demand;  
while maybe not related to watermain-breaks, it'd feel inconsistent to have `HEATING_DEGREE_DAYS` without `COOLING_DEGREE_DAYS`.

**Omitted Columns:***  
`TOTAL_RAIN`, `TOTAL_SNOW`.

The daily `TOTAL_RAIN` and `TOTAL_SNOW` because they're very complicated to deal with.
Stations that support daily `TOTAL_RAIN` and `TOTAL_SNOW` do not have hourly `PRECIP_AMOUNT` values;
conversely, stations that have hourly `PRECIP_AMOUNT` values do not have daily `TOTAL_RAIN` and `TOTAL_SNOW` values.

Because of this, and because the values recorded by different stations are slightly inconsistent with each other,
the sum of a day's hourly `PRECIP_AMOUNT` will often be inconsistent with the sum of that day's `TOTAL_RAIN` and `TOTAL_SNOW` values,
even tho both of those should - in theory - be equal to the total daily `TOTAL_PRECIPITATION` value.
(This also means that a given day's `TOTAL_PRECIPITATION` value will not be consistent with both
said day's `TOTAL_RAIN` + `TOTAL_SNOW` sum, AND the sum of said day's hourly `PRECIP_AMOUNT` values.)

Thus, it's easier to remove it.

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
- LOCAL_YEAR
- TEMP
- PRECIP_AMOUNT
- RELATIVE_HUMIDITY
- STATION_PRESSURE
- WIND_SPEED
- WIND_DIRECTION
- DEW_POINT_TEMP

The **climate-hourly** API is the best data-source for this, but doesn't include the most recent, real-time data.  
It is only updated once-per-day, and typically lacks data for the past couple days.
Thus we will supplement this with data from the **swob-realtime** API.

***NOTE: WE WILL ONLY BE USING STATION `3031094` FOR THE HOURLY-WEATHER-DATA***  
The reason for the other two stations is when retrieving data from before our **Primary** source-of-truth, STATION `3031094`, was active.  
However, for the most recent data, STATION `3031094` is active and has data formatted in the way most suitable for our needs.  
To grab data from STATIONS `3031092` and `3031093` in *addition* to `3031094`, we would need to first restructure   
the hourly-weather-data from `3031092` and `3031093` to match the hourly-weather-data structure from STATION `3031094`.

The **weather_data_hourly** Table is based on the columns from the **climate-hourly** API.  
Below is a table comparing items from the **weather_data_hourly** table, the **climate-hourly** API, and the **swob-realtime** API.  
*(Note that columns for the* **weather_data_hourly** *table were based on the* **climate-hourly** *API, so there's a 1-1 match there.)*  
| **weather_data_hourly** table | **climate-hourly** API | **swob-realtime** API     | **swob-realtime** unit-of-measurement |
|-------------------------------|------------------------|---------------------------|---------------------------------------|
| STATION_NAME                  | STATION_NAME           | stn_nam-value             | stn_nam-uom                           |
| CLIMATE_IDENTIFIER            | CLIMATE_IDENTIFIER     | clim_id-value             | clim_id-uom                           |
| LOCAL_DATE                    | LOCAL_DATE             | *calc from* date_tm-value | date_tm-uom                           |
| UTC_DATE                      | UTC_DATE               | date_tm-value             | date_tm-uom                           |
| LOCAL_YEAR                    | LOCAL_YEAR             | *calc from* date_tm-value | date_tm-uom                           |
| TEMP                          | TEMP                   | avg_air_temp_pst1hr       | avg_air_temp_pst1hr-uom               |
| PRECIP_AMOUNT                 | PRECIP_AMOUNT          | pcpn_amt_pst1hr           | pcpn_amt_pst1hr-uom                   |
| RELATIVE_HUMIDITY             | RELATIVE_HUMIDITY      | avg_rel_hum_pst1hr        | avg_rel_hum_pst1hr-uom                |
| STATION_PRESSURE              | STATION_PRESSURE       | stn_pres                  | stn_pres-uom                          |
| WIND_SPEED                    | WIND_SPEED             | avg_wnd_spd_10m_pst1hr    | avg_wnd_spd_10m_pst1hr-uom            |
| WIND_DIRECTION                | WIND_DIRECTION         | avg_wnd_dir_10m_pst1hr    | avg_wnd_dir_10m_pst1hr_1-uom          |
| DEW_POINT_TEMP                | DEW_POINT_TEMP         | avg_dwpt_temp_pst1hr      | avg_dwpt_temp_pst1hr-uom              |

- STATION_NAME
- CLIMATE_IDENTIFIER
- LOCAL_DATE
- UTC_DATE
- LOCAL_YEAR
- TEMP
- PRECIP_AMOUNT
- RELATIVE_HUMIDITY
- STATION_PRESSURE
- WIND_SPEED
- WIND_DIRECTION
- DEW_POINT_TEMP



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

##### Hourly-Weather: Included and Omitted Columns


#### Unused Weather Data

There are a few weather items that have been striked out, like so: ~~striked-out example~~.  
These are items that were up for consideration, but have been removed from our project (at least for the time being).  
We will explain the decision to remove them from the current scope of the project below:

***Daily-Weather: MIN_REL_HUMIDITY, MAX_REL_HUMIDITY, TOTAL_RAIN, TOTAL_SNOW***

***Hourly-Weather: RELATIVE_HUMIDITY***

Items removed:

***Daily-Weather: MIN_REL_HUMIDITY, MAX_REL_HUMIDITY***  
***Hourly-Weather: RELATIVE_HUMIDITY***  

Explanation:

In order to look at humidity, we would want to see *average* daily humidity in the daily weather;  
however, this data only has *minimum* and *maximum* humidity, not average.  
While using the central point between *minimum* and *maximum* is an option,  
there is a possibility that a strong change in humidity either early or late in the day  
results in the centre between *minimum* and *maximum* not being an accurate measure of center.  

While average-daily-precipitation could be computed from the hourly data,  
the process of computing daily-weather values from hourly-weather values  
is outside the initial scope of this project.  

However, it is worth noting that this represents an area for future potential work  
once the M.V.P. project has been completed.  

Items removed:
***Daily-Weather: TOTAL_RAIN, TOTAL_SNOW***

Explanation:

The weather stations that support **TOTAL_RAIN** and **TOTAL_SNOW**  
(in addition to **TOTAL_PRECIPITATION**)  
do not have hourly precipitation data.  
Conversely, stations that *have* hourly precipitation data  
do not have daily **TOTAL_RAIN** and **TOTAL_SNOW** data.

In order for *daily-rainfall* and *daily-snowfall* data to match *daily-precipitation* data,  
we need to collect all of them from the same weather station.  
However, this means that *hourly-precipitation* and *daily-precipitation*  
come from mis-matched stations, meaning there will often be a discrepancy between  
the sum of the *hourly-precipitation* data, and the *daily-precipitation* data.  
Thus, the simplest choice was to remove the **TOTAL_RAIN** and **TOTAL_SNOW** measures  
from our API-calls.