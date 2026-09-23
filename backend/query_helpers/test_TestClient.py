"""
file name: test_TestClient.py
author: William Hovdestad

Purpose: actually test that all that the running-APP actually works
to be completed when I have the mental bandwidth to learn testing

Claude gave me some code, I need to actually look over it and make sure I understand it...
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
from fastapi.testclient import TestClient
from backend.backend_main import app



########################################################################################################################
### now the testing logic

client = TestClient(app)


def test_full_table_rejects_non_spatial_table():
    response = client.get("/api/tables/weather_daily/full")
    assert response.status_code == 403

def test_full_table_returns_feature_collection():
    response = client.get("/api/tables/city_boundary/full")
    assert response.status_code == 200
    assert response.json()["type"] == "FeatureCollection"

def test_query_rejects_bad_filter():
    response = client.get("/api/tables/watermain_breaks/query?nonsense_column__eq=x")
    assert response.status_code == 400

def test_query_with_valid_filter():
    response = client.get("/api/tables/watermain_breaks/query?status=active")
    assert response.status_code == 200
    assert response.json()["type"] == "FeatureCollection"

def test_invalid_table_returns_422():
    response = client.get("/api/tables/not_a_real_table/full")
    assert response.status_code == 422

def test_query_with_no_matches_returns_empty_feature_collection():
    response = client.get("/api/tables/watermain_breaks/query?status__eq=nonexistent_status")
    assert response.status_code == 200
    assert response.json() == {"type": "FeatureCollection", "features": []}

def test_summary_returns_full_history_with_no_dates():
    response = client.get("/api/summary")
    assert response.status_code == 200
    body = response.json()
    assert "total_breaks" in body and "avg_breaks_per_year" in body

def test_summary_rejects_malformed_date():
    response = client.get("/api/summary?start_date=not-a-date")
    assert response.status_code == 422  # caught by the `date` type annotation, not FilterError

def test_summary_with_date_range_matching_no_rows():
    response = client.get("/api/summary?start_date=1900-01-01&end_date=1900-01-02")
    assert response.status_code == 200
    body = response.json()
    assert body["total_breaks"] == 0