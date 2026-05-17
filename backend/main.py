from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text


DATABASE_URL = "postgresql+psycopg://postgres:password@localhost:5432/gis"

engine = create_engine(DATABASE_URL)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/features")
def get_features(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
):
    query = text("""
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', json_agg(features.feature)
        )
        FROM (
            SELECT json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(geom)::json,
                'properties', json_build_object(
                    'name', name
                )
            ) AS feature
            FROM locations
            WHERE geom && ST_MakeEnvelope(
                :minx, :miny, :maxx, :maxy, 4326
            )
        ) AS features;
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {
            "minx": minx,
            "miny": miny,
            "maxx": maxx,
            "maxy": maxy,
        })

        geojson = result.scalar()

    return geojson
