####################################################################################################
# file name: explore_weather_stations.py
# author: William Hovdestad
#
# the goal of this script is to get a list of relevant weather stations in calgary for our purposes,
# calling the api of official canadian climate data
# API = "https://api.weather.gc.ca/collections/climate-stations/items"
# Steps:
# 1. get weather stations in the calgary area
# 2. calc distance between each station and calgary tower (used as semi-arbitary POINT for Calgary),
#    and sort by said distance
# 3.  filter them to stations currently active, have hourly values, and start at/before jan 1 2000
# 4. (optional) - print data to console confirming above actually works
# 5. save our data to a txt file



####################################################################################################
### script-setup 0: project-root-setup
import os
import sys
from pathlib import Path
# set PROJECT_ROOT so libraries from cousin folders import properly
# note that I want the main directory and file is `scripts`, a sub-directory of main,
#  so I need grand-parent folder instead of simply parent-folder

# gets file-path, (hopefully) resolves relative path issues, gets grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



####################################################################################################
### script-setup 1: library imports
import geopandas as gpd # geospatial library, used for distance calculations
from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data



####################################################################################################
### section 0: global variables

# Calgary tower lat/long: 51.04488383135468, -114.06305864230913

Calgary_tower_lat = round(51.04488383135468,4)
Calgary_tower_long = round(-114.06305864230913,4)
#print(f"Calgary tower lat: {Calgary_tower_lat} long: {Calgary_tower_long}")
CALGARY = {"lat": Calgary_tower_lat, "long": Calgary_tower_long}
RADIUS_KM = 50
START_DATE = "2000-01-01"



####################################################################################################
### section 1: grab all relevant stations


# create bounding box based on lat/long coordinate, and distance from said coord
def __bbox_from_radius(lat, long, km):
    degree = km / 111 # approximate conversion to turn km into degree
    # NOTE: Explanation:
    #   The Earth is roughly 111km per degree of latitude 
    #       (Earth's circumference ~40,000km / 360 degrees)
    #   Latitude lines have constant distance between them
    #       (N-S circles whose circumference gets smaller as you move from equator, 
    #        but distance between them is constant)
    #   Longitude lines have shrinking distances between them as you move further away from equator
    #       (E/W lines that all intersect geographic north/south pole)
    #   This results in our bounding-box being inaccurate, 
    #   but works well enough for our "grab stuff from this general area" purposes
    min_x = long - degree
    min_y = lat - degree
    max_x = long + degree
    max_y = lat + degree
    return min_x, min_y, max_x, max_y


# calls the api to get all stations in general calgary area, using the `bbox_from_radius` function
def stations__fetch():
    min_x, min_y, max_x, max_y = __bbox_from_radius(CALGARY["lat"], CALGARY["long"], RADIUS_KM)

    url = "https://api.weather.gc.ca/collections/climate-stations/items"

    params = {
        "bbox": f"{min_x},{min_y},{max_x},{max_y}",
        # NOTE: bbox order is  standard order defined by the 
        # OGC (Open Geospatial Consortium) API spec that Environment Canada's API follows
        # basically, maps to west-boundary, south-boundary, east-boundary, north-boundary
        "PROV_STATE_TERR_CODE": "AB",
        "f": "json", # this line says we want it in json format
        "limit": 200,
        # NOTE: above sets the limits of results;
        # 200 is higher than Environment Canada API's default limit of 10, 
        # but low enough not to upset API
    }

    # actual API call - make request, do response.wait-for-update, return the response data
    
    # sends an HTTP GET request to the URL
    # NOTE: everything is stored in response - status code, headers, body
    response = httpx.get(url, params=params)
    # checks that status code is "200" which means everything is ok
    response.raise_for_status()
    # turn raw response body text into Python dictionary
    all_stations = response.json()
    # grab only items from "features" in said dictionary, 
    # since API returns a GeoJSON `FeatureCollection` that wraps actualy data inside "features" key
    all_stations = all_stations["features"]
    # NOTE: could also do that in one step
    # all_stations = response.json()["features"]
    return all_stations



####################################################################################################
### section 2 - calculate distance between station and calgary tower; sort stations by said distance


# function to calculate distance betewen two sets of lat/long coordinates
# NOTE: assuming default lat/long CRS of 'EPSG:4326', 
# NOTE: assuming desired output CRS is 'EPSG:3776' for use in City-of-Calgary-area
# NOTE: this function is deliberately very GENERIC because I'll probably want to re-use it later
# NOTE: make sure it's "EPSG", not "ESPG"
def __calc_distance(lat_1, long_1, lat_2, long_2, distance_crs='EPSG:3776'):
    # NOTE: X = long, Y = lat
    point_1, point_2 = Point(long_1, lat_1), Point(long_2, lat_2)
    # NOTE: `Point` Attributes: x, y, z, m - float

    # turn points into geodataframes - default CRS for points will be EPSG 4326, so set them to that
    df_1 = gpd.GeoDataFrame({'geometry': [point_1]}, crs='EPSG:4326')
    df_2 = gpd.GeoDataFrame({'geometry': [point_2]}, crs='EPSG:4326')

    # NOTE: default geojson crs is EPSG 4326 - but that has distance in degrees,
    # so a distance calculation gives me degrees, not km
    # EPSG3776 seems like best CRS for Calgary area, and gives distance in km
    df_1 = df_1.to_crs(distance_crs)
    df_2 = df_2.to_crs(distance_crs)

    # calculate distance
    series_distance = df_1.distance(df_2)
    dist_val = round(series_distance[0],3)
    dist_unit = df_1.crs.axis_info[0].unit_name
    dist_dict = {"value":dist_val, "unit":dist_unit}
    return dist_dict


# function to calculates distance between single station and calgary tower
# (which is used as semi-arbitrary "point" location of city of calgary)
def __calc_station_distance(single_station):
    # NOTE: X = long, Y = lat
    stn_lat =  single_station["geometry"]["coordinates"][1]
    stn_long = single_station["geometry"]["coordinates"][0]
    # NOTE: coordinates are [lon, lat] in GeoJSON

    city_lat =  CALGARY["lat"]
    city_long = CALGARY["long"]
    distance = __calc_distance(stn_lat, stn_long, city_lat, city_long)
    return distance


# calculates distance between calgary tower and ALL stations, 
# and adds that to each individual station's json
def stations__distance_calc(all_stations):
    for single_station in all_stations:
        distance = __calc_station_distance(single_station)
        single_station["properties"]["distance_km"] = float(round(distance["value"]/1000, 2)) 
        # NOTE: putting the "distance_km" attribute under "properties"
    all_stations.sort(key=lambda station: station["properties"]["distance_km"])
    return all_stations
    # NOTE:
    # a valid use for lambda! since the .sort() method takes a function as an argument,
    # it's easier to write the `lambda` function of `station: station["properties"]["distance_km"]`
    # that will, given a station, get us the specific distance value we want from the station
    # technically we could write a separate function and call it pass it to key, but that's tedious
    # this implementation of .sort() also makes it very flexible while being easy to implement
    # I'm now starting to understand why lambda exists



####################################################################################################
### section 3 - filter stations


# function that confirms an individual station was used this year
# NOTE:
# the exact date of "2026-01-01" is somewhat arbitrary, 
# but a station used as of Jan 1, current year, is likely still an active station
def __is_active(station):

    last_date = station["properties"].get("LAST_DATE", "")
    # `.get()` syntax: `.get({KEY}, {return-value-if-key-not-found})`
    
    is_active = last_date >= "2026-01-01" 
    # `last_date >= "2026-01-01"` is TRUE if `last_date` is at least 2026-01-01, else its FALSE
    # then we set `is_active` to the result of that boolean expression
    # NOTE: string comparison orders them alphabetically, so A < M < Z, 
    # but in YYYY-MM-DD format, string sorting and date sorting produce same result
    return is_active # return the boolean value


# function that confirms an individual station has hourly results
def __has_hourly(station):
    has_hourly_data = station["properties"].get("HAS_HOURLY_DATA", "")
    has_hourly_boolean = has_hourly_data == "Y"
    # `has_hourly_boolean` will be True if value is "Y", otherwise False
    return has_hourly_boolean # return the boolean value


# confirms stations daily-values goes back to at least January 01, 2000
# NOTE:
# also handles error-checking, as the "try-except" logic means 
# it returns `False` if we can't turn the "DLY_FIRST_DATE" into a proper datetime variable
def __valid_daily_start(station):
    # turn `START_DATE` into proper datetime variable
    datetime_START_DATE = parse(START_DATE)

    # use `.get()` to grab values from json
    # `.get()` syntax: `.get({KEY}, {return-value-if-key-not-found})` - built-in-error handling
    station_first_date = station["properties"].get("DLY_FIRST_DATE", "") 

    # use a try-block, to see if the `station_first_date` can be converted to datetime
    try: # NOTE: confirmed that `parse` gives error with invalid datetime format
        # attempt to turn `station_first_date` into a datetime
        datetime_station_first_date = parse(station_first_date) 
        
        # return False if station_first_date comes after START_DATE
        if datetime_station_first_date > datetime_START_DATE: return False 
        
        # return True - only occurs if `daily_start` can be converted to date, 
        # AND occurs at-or-prior-to start_time
        return True
    
    except: # what happens if we can't convert "HLY_FIRST_DATE" to datetime?
        return False # returns False if the "HLY_FIRST_DATE" can't be converted to datetime


# uses above functions to filters for stations that are: 
# active as of this year, has hourly data, and first daily date is prior to 2000-01-01
# we're assuming that stations active at start of year are still active, 
# and that active stations with hourly data have it for -checks notes- past week
def stations__filter(all_stations):
    results = []
    for station in all_stations:
        if not __is_active(station): continue # skip if we don't get TRUE for `is_active(station)`
        if not __has_hourly(station): continue # skip if we don't get TRUE for `has_hourly(station)`
        if not __valid_daily_start(station): continue # skip if we don't get TRUE for `valid_daily_start(station)`
        results.append(station)
    return results



####################################################################################################
### section 4 - actually call and use our functions to select, sort, and filter stations,
###             and print output to console


# actually call our functions lol
stations = stations__fetch()
stations = stations__distance_calc(stations)
filtered = stations__filter(stations)


# see what an example station looks like
print("")
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("~~~ START EXAMPLE STATION ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
for s in stations:
    print(s)
    break
print("~~~ END EXAMPLE STATION ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("")


# test that our distance sorting worked out fine
print("")
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("~~~ START TESTING DISTANCE SORT ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
for s in stations:
    print(f"STATION_NAME: {s["properties"]["STATION_NAME"]}; DISTANCE: {s["properties"]["distance_km"]}")
print("~~~ END TESTING DISTANCE SORT ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("")



####################################################################################################
### step 5.1 - save our data as human-readable output


# create output list so we can save our output to text
output_data_list = []

# manually create starting lines of output, so that:
# `starting_line_1` and `starting_line_2`  will be start of output
# NOTE: `f.writelines()` doesn't automatically add newlinews, hence me adding them to the strings
starting_line_1 = f"{len(stations)} total stations, {len(filtered)} after filtering\n\n"
starting_line_2 = "Valid stations:\n"
output_data_list.extend([starting_line_1, starting_line_2])

# filter through stations, adding relevant station lines to `output_data_list`
for s in filtered:
    station_delimiter_newline = "\n"
    station_line_1 = f"STATION_NAME: {s["properties"]["STATION_NAME"]}; CLIMATE_IDENTIFIER: {s["properties"]["CLIMATE_IDENTIFIER"]};\n"
    station_line_2 = f"Custom `is_active`         check: {__is_active(s)}; LAST_DATE: {s["properties"]["LAST_DATE"]};\n"
    station_line_3 = f"Custom `has_hourly`        check: {__has_hourly(s)}; HAS_HOURLY_DATA: {s["properties"]["HAS_HOURLY_DATA"]};\n"
    station_line_4 = f"Custom `valid_daily_start` check: {__valid_daily_start(s)}; DLY_FIRST_DATE: {s["properties"]["DLY_FIRST_DATE"]};\n"
    output_data_list.extend([station_delimiter_newline, station_line_1, station_line_2, station_line_3, station_line_4])
    # break

# write data to .txt file
output_txt = Path(PROJECT_ROOT) / "backend" / "test_data" / "weather_stations_output.txt"
with open(output_txt, "w") as f:
    f.writelines(output_data_list)


print("")
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("~~~ OUTPUT DATA START ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
for line in output_data_list:
    print(line, end="") # since the newline-char is already included in `line`, we don't want print to automatically add a newline as well
print("~~~ OUTPUT DATA END ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("")

####################################################################################################
### step 5.2 - save our data as json, to make output data easier to use in the future
output_json = Path(PROJECT_ROOT) / "backend" / "test_data" / "weather_stations.json"
with open(output_json, "w") as f:
    json.dump(filtered, f, indent=2)