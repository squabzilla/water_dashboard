"""
file name: test_TestClient.py
author: William Hovdestad

Purpose: actually test that all that the running-APP actually works
to be completed when I have the mental bandwidth to learn testing

Claude gave me some code, I need to actually look over it and make sure I understand it...

USAGE:
uv run pytest
uv run pytest -v # (line-by-line report)
uv run pytest <filename.py>
uv run pytest <filename.py>::<test_function_name>

TODO: update my class definitions with my new tables...
"""


########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets great grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# get path for environment so I can load it later



########################################################################################################################
### script-setup 2: library imports
import pytest
from fastapi.testclient import TestClient

# custom modules!
from data_pipeline.helper.helper_SQL_tables import DatabaseTables, DailyWeatherCols
from backend.backend_main import app



########################################################################################################################
### now the testing logic

# client = TestClient(app)

@pytest.fixture # this decorator tells pytest to run this code before every test, to set it up
def client():
    with TestClient(app) as c:
        yield c
    # yield means the function stays in its current state -
    # basically, it's ready to run more code "under" the `with` clause
    # think of the `with` clause similar to `with open(file) as f:`, where "with" handles opening/closing of the "opened-object"
    # NOTE: by default, pytest closes the connection after running a test function, but I could decorate it with:
    # @pytest.fixture(scope="module")
    # to keep it open for all tests; however, this means results from one test could "leak" into another test

# while the decorator of our `client` function means pytest runs that code before testing our function,
# the function doesn't know what any of that is unless we pass it the information
def test_full_table_rejects_non_spatial_table(client):
    response = client.get(f"/api/tables/{DatabaseTables.weather_daily}/full")
    assert response.status_code == 403

def test_full_table_returns_feature_collection(client):
    response = client.get(f"/api/tables/{DatabaseTables.city_boundary}/full")
    assert response.status_code == 200
    assert response.json()["type"] == "FeatureCollection"

def test_query_rejects_non_spatial_table(client):
    response = client.get(f"/api/tables/{DatabaseTables.weather_daily_staging}/query?{DailyWeatherCols.dwc_local_year}=2000")
    assert response.status_code == 403

def test_query_rejects_bad_filter(client):
    response = client.get(f"/api/tables/{DatabaseTables.watermain_breaks}/query?nonsense_column__eq=x")
    assert response.status_code == 400

def test_query_with_valid_filter(client):
    response = client.get(f"/api/tables/{DatabaseTables.watermain_breaks}/query?status=active")
    assert response.status_code == 200
    assert response.json()["type"] == "FeatureCollection"

def test_invalid_table_returns_422(client):
    response = client.get("/api/tables/not_a_real_table/full")
    assert response.status_code == 422

def test_query_with_no_matches_returns_empty_feature_collection(client):
    response = client.get(f"/api/tables/{DatabaseTables.watermain_breaks}/query?status__eq=nonexistent_status")
    assert response.status_code == 200
    assert response.json() == {"type": "FeatureCollection", "features": []}

### summary tables

def test_summary_returns_full_history_with_no_dates(client):
    # confirms that our summary returns the whole table if we don't specify the date-range we want
    response = client.get("/api/summary")
    assert response.status_code == 200
    body = response.json()
    assert "total_breaks" in body and "avg_breaks_per_year" in body
    assert body["total_breaks"] > 0  # confirm we actually HAVE data

def test_summary_rejects_malformed_date(client):
    response = client.get("/api/summary?start_date=not-a-date")
    assert response.status_code == 422  # caught by the `date` type annotation, not FilterError

def test_summary_with_date_range_matching_no_rows(client):
    response = client.get("/api/summary?start_date=1900-01-01&end_date=1900-01-02")
    assert response.status_code == 200
    body = response.json()
    assert body["total_breaks"] == 0



########################################################################################################################
### adding testing for newly-added endpoint 4: annual-watermain-summary
# NOTE: 
# This endpoint returns a SELECT statement that combines two separate tables together.
# There is no actual table in my database for "annual-watermain-summary", that name is defined in Endpoint 4's SQL code

def test_annual_summary_returns_full_range_with_no_year_filters(client):
    response = client.get("/api/annual-watermain-summary")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0 # confirm we actually HAVE data
    assert "break_count" in body[0] and "total_precipitation_mm" in body[0]

def test_annual_summary_merges_fields_from_both_tables(client):
    response = client.get("/api/annual-watermain-summary")
    body = response.json()
    assert len(body) > 0 # confirm we actually HAVE data
    for year_record in body:
        assert set(year_record.keys()) == {
            "calendar_year", "days_in_year", "break_count",
            "is_complete_year", "total_precipitation_mm",
            "cumulative_pipe_length_m", "cumulative_pipe_volume_m3",
        }

def test_annual_summary_with_year_range_matching_nothing(client):
    response = client.get("/api/annual-watermain-summary?start_year=1800&end_year=1801")
    assert response.status_code == 200
    assert response.json() == []

def test_annual_summary_rejects_non_integer_year(client):
    response = client.get("/api/annual-watermain-summary?start_year=not-a-year")
    assert response.status_code == 422