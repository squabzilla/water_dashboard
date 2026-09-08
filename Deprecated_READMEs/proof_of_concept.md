# Step 0 - Install Core Tools
Want:
- Python 3.12+
- Node.js 20+
- Podman

Setup stuff I did:
Install UV
`curl -LsSf https://astral.sh/uv/install.sh | sh`
initialize UV environment
`uv init`
open up this readme:
`code README.md`
Install "Node.js" for linux using "fnm" (which is FastNodeManager)

### make sure 'unzip' is installed on linux I guess???
`sudo apt-get install zip unzip`

### Download and install fnm:
`curl -o- https://fnm.vercel.app/install | bash`

### Download and install Node.js:
`fnm install 24`

### Verify the Node.js version:
`node -v # Should print "v24.15.0".`

### Verify npm version:
`npm -v # Should print "11.12.1".`

#### install Podman, that's what I want to use for PostGreSQL -shrug-
#### Ubuntu 20.10 and newer
sudo apt-get update
sudo apt-get -y install podman

# Step 1 - Create Project Structure
mapping-dashboard/
|-- backend/
|-- frontend/
|-- README.md

# Step 2 - Start PostGIS
Probably the only thing to containerize initially.

NOTE: Possibly useful links about this:
https://www.riannek.de/2025/how-to-use-postgis-in-podman/

https://reubenliengaard.github.io/docs/geospatial-analysis/setting-up-a-postgis-database-server#create-a-pod


#### get podman to run PostGreSQL
```bash
podman pod create --name postgis \
  -p 127.0.0.1:5433:5432 \
  -p 127.0.0.1:8088:80

podman run -d --pod postgis --name postgres \
  -e POSTGRES_USER=gisuser \
  -e POSTGRES_PASSWORD=mypassword \
  -v ./poddata/postgres:/var/lib/postgresql/data:Z \
  docker.io/postgis/postgis

podman run -d --pod postgis --name pgadmin \
  --user 5050:5050 \
  -e PGADMIN_DEFAULT_EMAIL=mail@example.com \
  -e PGADMIN_DEFAULT_PASSWORD=SuperSecret \
  -v ./poddata/pgadmin:/var/lib/pgadmin:Z \
  docker.io/dpage/pgadmin4
```

# Step 3 - Create Backend
Initialize FastAPI Project
```bash
cd backend
uv init --app
uv add fastapi --extra standard
uv add fastapi fastapi[standard] uvicorn psycopg[binary] sqlalchemy geoalchemy2 pandas geopandas
```

# Step 4 - Create `main.py`

``` Python
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

# Step 5 - Connect pgAdmin to PostGIS
When you first open pgAdmin you'll need to register your PostGIS database as a server:

1. Right-click **Servers** in the left panel -> **Register** -> **Server**
2. Under the **General** tab, give it a name (e.g. `PostGIS Local`)
3. Under the **Connection** tab, enter:
   - **Host**: `localhost`
   - **Port**: `5432` *(the internal container port - not `5433`)*
   - **Username**: the value of `POSTGRES_USER` from your `.env`
   - **Password**: the value of `POSTGRES_PASSWORD` from your `.env`
4. Click **Save**

You should now see your database appear in the left panel and can start creating tables and loading geospatial data.

# Step 6 - Load Data

Demo version:

Still inside `psql`
``` SQL
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

Exit SQL
``` SQL
\q
```
***NOTE:***

In the final version, I want to replace this entire with API calls to different APIs to load data into our PostGIS database.

# Step 7 - Run Backend
``` Bash
uv run fastapi dev main.py
```

# Step 8 - Create Frontend
```Bash
cd frontend
npm install
npm create vite@latest . -- --template react-ts
npm install
npm install maplibre-gl
```

# Step 9 - Add MapLibre CSS
Edit:
`frontend/src/main.tsx`
Add:
```Typescript
import 'maplibre-gl/dist/maplibre-gl.css'
```

# Step 10 Replace `App.tsx`

`frontend/src/App.tsx`

NOTE: I kept the original `App.tsx` as `deprecated_App.tsx` just in case

```Typescript
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

# Step 11 - Run Frontend
```Bash
npm run dev
```