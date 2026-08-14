Making this a .txt because I can't be bothered with formatting MarkDown right now

But GODS I need a doc just overviewing what weather data I want so I can review it

`weather_data_daily` cols:
    - CLIMATE_IDENTIFIER
    - LOCAL_DATE
    - MEAN_TEMPERATURE
    - MIN_TEMPERATURE
    - MAX_TEMPERATURE
    - TOTAL_PRECIPITATION
    - TOTAL_RAIN
    - TOTAL_SNOW

`weather_data_hourly_ cols:
    - CLIMATE_IDENTIFIER
    - UTC_DATE
    - LOCAL_DATE
    - TEMP
    - PRECIP_AMOUNT
    - RELATIVE_HUMIDITY
    - WINDCHILL
    - WIND_DIRECTION
    - WIND_SPEED
    - WEATHER_ENG_DESC


class DailyWeatherCols(StrEnum):
    station_name = "STATION_NAME"
    climate_identifier = "CLIMATE_IDENTIFIER"
    local_date = "LOCAL_DATE"
    mean_temperature = "MEAN_TEMPERATURE"
    min_temperature = "MIN_TEMPERATURE"
    max_temperature = "MAX_TEMPERATURE"
    total_precipitation = "TOTAL_PRECIPITATION"
    total_rain = "TOTAL_RAIN"
    total_snow = "TOTAL_SNOW"

class HourlyWeatherCols(StrEnum):
    climate_identifier = "CLIMATE_IDENTIFIER"
    utc_date = "UTC_DATE"
    local_date = "LOCAL_DATE"
    temp = "TEMP"
    precip_amount = "PRECIP_AMOUNT"
    relative_humidity = "RELATIVE_HUMIDITY"
    windchill = "WINDCHILL"
    wind_direction = "WIND_DIRECTION"
    wind_speed = "WIND_SPEED"
    weather_eng_desc = "WEATHER_ENG_DESC"