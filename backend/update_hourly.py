####################################################################################################
# file name: update_hourly.py
# author: William Hovdestad
#
# The goal of this script is to retrieve hourly temperature data from the following weather station:
# STATION_NAME: CALGARY INT'L CS; CLIMATE_IDENTIFIER: 3031094;
# We only want data for the past week, meaning the most recent 7 * 24 = 168 readings.
#
# Ideally this script will be ran every hour, and update our database with the results.
# However,