import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import geopandas as gpd
import requests
# from shapely.geometry import shape
import psycopg
import sqlalchemy
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")
#print(env_dir)

load_dotenv(env_dir)

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
APP_TOKEN = os.getenv("APP_TOKEN")


url = r"https://data.calgary.ca/api/v3/views/erra-cqp9/query.geojson"


auth = (API_KEY, API_SECRET_KEY)
headers = {"X-App-Token": APP_TOKEN}

response = requests.get(url, auth=auth, headers=headers)
response.raise_for_status()

response_output = response.json()
#response_output = response_output["features"]
gdf = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol
#response_output['the_geom'] = response_output['the_geom'].apply(shape)
#gdf = gpd.GeoDataFrame(response_output).set_geometry('geometry')

# NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")
print(f"CRS: {gdf.crs}")

#print(gdf.head())

output_path = Path(PROJECT_ROOT) / "backend" / "data" / "calgary_boundary.geojson"

#gdf.to_file(output_path, driver="GeoJSON", index=False)


print(f"DATABASE: `calgary_watermains`; POSTGRES_USER: `{POSTGRES_USER}`; POSTGRES_PASSWORD: `{POSTGRES_PASSWORD}`")

# NOTE: `POSTGRES_DB=calgary_watermains` in podman stuff, so assume 'your_database' = 'calgary_watermains'
database_name = 'calgary_watermains'

engine_text = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:5433/{database_name}"
engine = create_engine(engine_text)


# engine = create_engine('postgresql+psycopg://username:password@localhost:5432/your_database')

#print(sqlalchemy.__version__)

gdf.to_postgis("table_name", engine, if_exists="replace", index=False)
print("done")