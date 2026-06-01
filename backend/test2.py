from datetime import date, datetime, timedelta, timezone

var = {"datetime": "2000-01-01T00:00:00Z/..",}

# print("today:", date.today())

# print("now:", datetime.now())

# UTC (Zero Offset): YYYY-MM-DDThh:mm:ssZ

day_minus_eight = date.today() - timedelta(days=8)

# print(day_minus_eight)

start_str = str(day_minus_eight) + "T00:00:00Z/.."


"""
import zoneinfo
from zoneinfo import ZoneInfo

# 1. Generate an aware UTC datetime object
utc_now = datetime.now(timezone.utc)

# 2. Shift the moment to the Mountain Time zone
mt_now = utc_now.astimezone(ZoneInfo("America/Edmonton"))

print("UTC Time:     ", utc_now)
print("Mountain Time:", mt_now)

#offset = mt_now.utcoffset()

#print(offset)

print(mt_now.strftime("%:z"))

#print(zoneinfo.available_timezones())

prop__ID_time = "CLIMATE_IDENTIFIER,LOCAL_DATE,LOCAL_YEAR,LOCAL_MONTH,LOCAL_DAY"
prop__temp = "MEAN_TEMPERATURE,MIN_TEMPERATURE,MAX_TEMPERATURE"
prop__precip = "TOTAL_PRECIPITATION,TOTAL_RAIN,TOTAL_SNOW"
# NOTE: my prop values are comma separated, BUT LAST ONE DOESN'T HAVE COMMA
prop__all = prop__ID_time + "," + prop__temp + "," + prop__precip

#print(f'"{prop__all}"')"""

print(start_str)