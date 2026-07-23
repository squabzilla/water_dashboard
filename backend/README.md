Explanation of files in backend  
  
`explore_stations.py`  
This was a python script meant to look at weather stations from the ECCC API.  
ECCC = Environment And Climate Change Canada  
API = Application Programming Interface  
  
`explore_stations_output.txt`  
The output text file containing human-readable information about the weather stations we found.  
  
`pyproject.toml` `uv.lock` `__pycache__`  
Configuration files for UV python environment.  
  
`fetch_historical.py`  
Runs-once-ever backfill script of daily weather data from 2000-01-01 to current day. Run once.  
  
`fetch_daily.py`  
Runs-once-per-day script, fetches and updates most recent daily reading (probably yesterday's.)  
  
`fetch_current.py`  
Runs-once-every-hour script, fetches latest hourly reading, inserts it, prunes old records.  
We only want hourly records for past week, to prevent overly large archive.  
  
~~`data`~~  
~~Folder containing GeoJSONs from above scripts.~~  
Nevermind, I'm not going to do this.
  
~~`update_psql.py`  ~~
~~This script handles the logic for inserting the data from the data-gathering scripts,~~  
~~\- namely `ingest_historical.py`, `update_daily.py`, and `update_hourly.py` -~~  
~~and inserts it into psql database.~~  
~~Aside from the fact that I'll reuse that psql-insertion-logic in multiple scripts,~~  
~~it also means I can verify the API retrieval portion and database-insertion portion separately. ~~  
Nevermind, the data gathering scripts will insert stuff directly.




I really ought to list the data APIs I'm querying at some point (and why)

Datasets:

Water Main Breaks (update regularly)
	Link: https://data.calgary.ca/Environment/Water-Main-Breaks/dpcu-jr23/about_data   

Public Water Main
	Link: https://data.calgary.ca/Services-and-Amenities/Public-Water-Main/w6h9-w33i/about_data

City Boundary
	Link: https://data.calgary.ca/Base-Maps/City-Boundary/erra-cqp9/about_data

Communities
	Link: https://data.calgary.ca/Base-Maps/Community-District-Boundaries/surr-xmvs/about_data

Water Pressure Zones
	Link: https://data.calgary.ca/Environment/Water-Pressure-Zones/xn3q-y49u/about_data

Current rainfall (update regularly)
	Link: https://data.calgary.ca/Environment/Current-Year-Rainfall/c7sr-67sr/about_data

Historical rainfall
	Link: https://data.calgary.ca/Environment/Historical-Rainfall/d9kv-swk3/about_data

Rainfall Gauge Locations
	Link: https://data.calgary.ca/Base-Maps/Rain-Gauge-locations/x9fe-3zah/about_data

Climate/temperature data  (update regularly)
	Link: (uh, complicated?)

Hydrology
	Link: https://data.calgary.ca/Environment/Hydrology/47bt-eefd/about_data



Data fetching scripts:  
`fetch_historical` scripts will collect historical data from 2000-01-01 to current date  
`fetch_shapes` scripts will collect one-off shapes we aren't planning to udpate, like city boundaries  
*(yes, I know city boundaries update like yearly or something, but MVP won't care about this)*
`fetch_current` scripts will be ran every 5-15 minutes (to be decided later) to keep current, up-to-date data
`fetch_daily` is useful for things to be ran daily  
\- I should make a `daily` version of all the `historical` scripts to keep them updated to current time.

Note that `fetch_historical` and `fetch_current` will overlap; we will want both historical archives, and current up-to-date data for some items.


## Fetch Historical / Daily datasets:
 - Water main breaks
 - Historical rainfall
 - Official weather data

## Fetch Shapes datasets:
 - Public Water Main
 - City Boundary
 - Communities
 - Water pressure zones
 - Rainfall Gauge locations
 - Hydrology

## Fetch Current datasets:
 - Water main breaks
 - Official Weather data
 - *(later, not part of MVP)* Current rainfall

## JSON Files
During test & development, some API data was saves as JSON file for reference.  
While these files aren't going to be used in code anywhere,  
inspecting them is often useful to better understand the data we're trying to grab.


## Railfall Data Notes
While the use of rainfall data is outside our current project scope,  
we're keeping some notes about it for future use.  

Notes:  

I'd be better off with a Bash script using say WGET to download the (hopefully compressed) CSV archive  
and then writing Python code to process that archive  
rather than using an API call  
tbh, there's a way to write Python code to download an item from a download link too  
I did that with historical population data for the NZEST project  

## Handling High Amounts of API Data
Theoretically, doing some form of pagination is  the way to handle high amounts of data via API call.  
However, in practice, as least with the Environment Canada weather data, pagination wasn't really working.  
At least, via the actual "pagination" option on the API.  
What did work was looping through all the years of the data,  
as each individual year was small enough to query by itself.  
So looping through time-periods of the data (at least for time-stamped data)  
was a much more effective-in-practice way of using pagination to handle large amounts of data via API call.