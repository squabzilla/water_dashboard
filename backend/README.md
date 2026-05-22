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
  
`fetch_hourly.py`  
Runs-once-every-hour script, fetches latest hourly reading, inserts it, prunes old records.  
We only want hourly records for past week, to prevent overly large archive.  
  
`data`  
Folder containing GeoJSONs from above scripts.  
  
`update_psql.py`  
This script handles the logic for inserting the data from the data-gathering scripts,  
\- namely `ingest_historical.py`, `update_daily.py`, and `update_hourly.py` -  
and inserts it into psql database.  
Aside from the fact that I'll reuse that psql-insertion-logic in multiple scripts,  
it also means I can verify the API retrieval portion and database-insertion portion separately. 