import httpx
from dateutil.parser import parse

# Calgary tower lat/long: 51.04488383135468, -114.06305864230913

Calgary_tower_lat = round(51.04488383135468,4)
Calgary_tower_long = round(-114.06305864230913,4)
#print(f"Calgary tower lat: {Calgary_tower_lat} long: {Calgary_tower_long}")
CALGARY = {"lat": Calgary_tower_lat, "long": Calgary_tower_long}
RADIUS_KM = 50
START_DATE = "2000-01-01"

# create bounding box based on lat/long coordinate, and distance from said coord
def bbox_from_radius(lat, long, km):
    degree = km / 111 # approximate conversion to turn km into degree
    # NOTE: Explanation:
    #   The Earth is roughly 111km per degree of latitude - Earth's circumference ~40,000km / 360 degrees
    #   Latitude lines have constant distance between them
    #       (N-S circles whose circumference gets smaller as you move from equator, but distance between them is constant)
    #   Longitude lines have shrinking distances between them as you move further away from equator
    #       (E/W lines that all intersect geographic north/south pole)
    #   This results in our bounding-box being inaccurate, 
    #   but works well enough for our "grab stuff from this general area" purposes
    min_x = long - degree
    min_y = lat - degree
    max_x = long + degree
    max_y = lat + degree
    return min_x, min_y, max_x, max_y

def fetch_stations():
    min_x, min_y, max_x, max_y = bbox_from_radius(CALGARY["lat"], CALGARY["long"], RADIUS_KM)

    url = "https://api.weather.gc.ca/collections/climate-stations/items"

    params = {
        "bbox": f"{min_x},{min_y},{max_x},{max_y}",
        # NOTE: bbox order is  standard order defined by the OGC (Open Geospatial Consortium) API spec that Environment Canada's API follows
        # basically, maps to west-boundary, south-boundary, east-boundary, north-boundary
        "PROV_STATE_TERR_CODE": "AB",
        "f": "json", # this line says we want it in json format
        "limit": 200,
        # NOTE: sets limits of results - 200 is higher than Environment Canada API's default limit of 10, but low enough not to upset API
    }

    # actual API call - make request, do response.wait-for-update, return the response data
    response = httpx.get(url, params=params)
    response.raise_for_status()
    return response.json()["features"]


# confirms station was used this year - the exact date of "2026-01-01" is somewhat arbitrary,
#  but a station used as of Jan 1, current year, is likely stuff active
def is_active(station):
    last_date = station["properties"].get("LAST_DATE", "") # `.get()` syntax: `.get({KEY}, {return-value-if-key-not-found})`
    is_active = last_date >= "2026-01-01" 
    # `last_date >= "2026-01-01"` is TRUE if `last_date` after 2026-01-01, and FALSE if it's not
    # then we set `is_active` to the result of that boolean expression
    # NOTE: string comparison orders them alphabetically, so A < M < Z, 
    # but in YYYY-MM-DD format, string sorting and date sorting produce same result
    return is_active # return the boolean value


# confirms station has hourly results
def has_hourly(station):
    has_hourly_data = station["properties"].get("HAS_HOURLY_DATA", "")
    has_hourly_boolean = has_hourly_data == "Y" # `has_hourly_boolean` will be True if value is "Y", otherwise False
    return has_hourly_boolean # return the boolean value


# confirms stations daily-values starts prior to 2000
def valid_daily_start(station):
    datetime_START_DATE = parse(START_DATE) # turns `START_DATE` into proper datetime variable
    station_first_date = station["properties"].get("DLY_FIRST_DATE", "") # `.get()` syntax: `.get({KEY}, {return-value-if-key-not-found})`
    try: # a try-block, to see if the `station_first_date` can be converted to datetime NOTE: confirmed that `parse` gives error with invalid datetime format
        datetime_station_first_date = parse(station_first_date) # attempt to turn `station_first_date` into a datetime
        if datetime_station_first_date > datetime_START_DATE: return False # return False if station_first_date comes after START_DATE
        return True # return True - only occurs if `daily_start` can be converted to date, and occurs prior to start_time
    except:
        return False # returns False if the "HLY_FIRST_DATE" can't be converted to datetime


# filters for stations that are active as of this year, has hourly data, and first daily date is prior to 2000-01-01
# we're assuming that stations active at start of year are still active, and that active stations with hourly data have it for -checks notes- past week
def filter_stations(all_stations):
    results = []
    for station in all_stations:
        if not is_active(station): continue # skip if we don't get TRUE for `is_active(station)`
        if not has_hourly(station): continue # skip if we don't get TRUE for `has_hourly(station)`
        if not valid_daily_start(station): continue # skip if we don't get TRUE for `valid_daily_start(station)`
        results.append(station)
    return results


# call our functions lol
stations = fetch_stations()
filtered = filter_stations(stations)
# stations = filter_2(stations)
# print(f"\nExample station:\n{stations[0]}\n") # prints raw JSON of first station, to make sure it looks good
print(f"{len(stations)} total stations, {len(filtered)} after filtering")

# print(f"\nExample station:\n{stations[0]}\n") # prints raw JSON of first station, to make sure it looks good

print("\nValid stations:")
for s in filtered:
    #print(s["properties"]["STATION_NAME"], s["properties"]["CLIMATE_IDENTIFIER"], "\n", s)
    print(s["properties"]["STATION_NAME"], s["properties"]["CLIMATE_IDENTIFIER"])
    print(f"Custom `is_active`         check: {is_active(s)};\tLAST_DATE: {s["properties"]["LAST_DATE"]}")
    print(f"Custom `has_hourly`        check: {has_hourly(s)};\tHAS_HOURLY_DATA: {s["properties"]["HAS_HOURLY_DATA"]}")
    print(f"Custom `valid_daily_start` check: {valid_daily_start(s)};\tDLY_FIRST_DATE: {s["properties"]["DLY_FIRST_DATE"]}")
    print("")