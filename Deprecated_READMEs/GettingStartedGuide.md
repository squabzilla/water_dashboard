Absolutely. Here’s the cleanest way to get from **empty folder → working local mapping dashboard** without overengineering it.

Goal:

```txt id="07d0r9"
Browser map
    ↓
FastAPI backend
    ↓
PostGIS database
```

Where:

* the frontend requests map data by bounding box (`bbox`)
* FastAPI queries PostGIS
* MapLibre renders results
* everything runs locally

This establishes the architecture correctly from day one.

---

# Step 0 — Install Core Tools

You’ll want:

## Required

* Python 3.12+
* Node.js 20+
* Docker Desktop (or Podman)

---

# Step 1 — Create Project Structure

```txt id="7u8n8q"
mapping-dashboard/
├── backend/
├── frontend/
└── README.md
```

---

# Step 2 — Start PostGIS

This is the only thing I’d containerize initially.

From project root:

```bash id="6bqav7"
docker run --name postgis \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=gis \
  -p 5432:5432 \
  -d postgis/postgis
```

---

# Step 3 — Create Backend

## Initialize FastAPI Project

```bash id="ydoylv"
cd backend

uv init
uv add fastapi uvicorn psycopg[binary] sqlalchemy geoalchemy2
```

---

# Step 4 — Create `main.py`

`backend/main.py`

```python id="jlwmuh"
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
```

---

# Step 5 — Create Database Table

Connect to database:

```bash id="wws8sk"
docker exec -it postgis psql -U postgres -d gis
```

Then run:

```sql id="a2w7e2"
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name TEXT,
    geom GEOMETRY(Point, 4326)
);

CREATE INDEX locations_geom_idx
ON locations
USING GIST (geom);
```

---

# Step 6 — Insert Sample Data

Still inside `psql`:

```sql id="14v2vg"
INSERT INTO locations (name, geom)
VALUES
(
    'Downtown Calgary',
    ST_SetSRID(ST_MakePoint(-114.0719, 51.0447), 4326)
),
(
    'Calgary Tower',
    ST_SetSRID(ST_MakePoint(-114.0631, 51.0447), 4326)
),
(
    'University of Calgary',
    ST_SetSRID(ST_MakePoint(-114.1329, 51.0784), 4326)
);
```

Exit:

```sql id="w8fexq"
\q
```

---

# Step 7 — Run Backend

```bash id="vvb33p"
uv run fastapi dev main.py
```

Backend now runs on:

```txt id="7jqjlwm"
http://127.0.0.1:8000
```

Test:

```txt id="r0dcx4"
http://127.0.0.1:8000/features?minx=-115&miny=50&maxx=-113&maxy=52
```

You should get GeoJSON.

---

# Step 8 — Create Frontend

Open new terminal:

```bash id="s3hhdr"
cd frontend

npm create vite@latest . -- --template react-ts

npm install
npm install maplibre-gl
```

---

# Step 9 — Add MapLibre CSS

Edit:

`frontend/src/main.tsx`

Add:

```ts id="jlwm74"
import 'maplibre-gl/dist/maplibre-gl.css'
```

---

# Step 10 — Replace `App.tsx`

`frontend/src/App.tsx`

```tsx id="u0hks4"
import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'

export default function App() {
  const mapContainer = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!mapContainer.current) return

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://demotiles.maplibre.org/style.json',
      center: [-114.0719, 51.0447],
      zoom: 10,
    })

    map.on('load', async () => {
      const bounds = map.getBounds()

      const response = await fetch(
        `http://127.0.0.1:8000/features?minx=${bounds.getWest()}&miny=${bounds.getSouth()}&maxx=${bounds.getEast()}&maxy=${bounds.getNorth()}`
      )

      const data = await response.json()

      map.addSource('locations', {
        type: 'geojson',
        data,
      })

      map.addLayer({
        id: 'locations-layer',
        type: 'circle',
        source: 'locations',
        paint: {
          'circle-radius': 6,
          'circle-color': '#ff0000',
        },
      })
    })

    return () => map.remove()
  }, [])

  return (
    <div
      ref={mapContainer}
      style={{
        width: '100vw',
        height: '100vh',
      }}
    />
  )
}
```

---

# Step 11 — Run Frontend

```bash id="jlwmxw"
npm run dev
```

Open:

```txt id="sdjlwm"
http://localhost:5173
```

You should now see:

* working interactive map
* points from PostGIS
* FastAPI backend
* bbox-based querying

That’s your first real scalable GIS milestone.

---

# Why This Setup Is Correct

You already avoided:

* Leaflet bottlenecks
* loading giant GeoJSON upfront
* frontend/database coupling
* proprietary mapping APIs

And you already established:

* spatial indexing
* viewport queries
* scalable API patterns
* GPU rendering

This is a genuinely solid foundation.

---

# Immediate Next Improvements

After this works:

## 1. Reload Features On Move

Add:

```ts id="jlwmjh"
map.on('moveend', loadFeatures)
```

instead of loading once.

---

## 2. Add Clustering

MapLibre supports this directly.

---

## 3. Add Spatial Filtering

Example:

```txt id="8psjlwm"
?category=restaurants
```

---

## 4. Add Proper Layers

* polygons
* lines
* heatmaps
* labels

---

## 5. Add Vector Tiles Later

Only once:

* datasets grow
* GeoJSON becomes too large
* performance degrades

At that point:

* Martin
* PMTiles
* vector tile generation

become worthwhile.
