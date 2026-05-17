# Calgary Water Main GIS Dashboard

The goal of this is to create an interactive web-based GIS dashboard to explore water main incidents in Calgary.

# Tech-Stack

## Front-End
-   [Node.js] (frontend tooling runtime)
-   [Typescript]
-   [MapLibre]
-   Other considered techs:
    -   [Vite]
    -   [React]

## Back-End
-   [Python] using [FastAPI]

## Database
-   [Podman] container of [PostGIS]

# Dashboard Structure:

## Page 1 - Executive Overview
Summary page explaning the project.

Includes our questions:
-   Where are the infrastructure incidents occurring?
-   How does seasonal rainfall correlate to infrastructure incidents?
-   How do seasonal and temperature conditions relate to infrastructure incidents?

## Page 2 - Infrastructure & Incident Map
Layers:
-   City Boundary
-   Community Boundaries
-   Water Pressure Zones
-   Water Main Incidents (I would like an API to regularly check for new water main incidents, and update the database if there are any)

This page lets the user examine water main breaks. I would like the `Water Main Incidents` layer to be regularly updated via API call.

The user can select a timeframe of incidents to look at.

This GIS visualization divides the city of Calgary by communities - however, a toggle will exist to divide it by `Water Pressure Zones` instead.

Eventually, I would like to have functionality that when you click a `Community` or `Water Pressure Zone`, the user is given information about that area.

## Page 3 - Rain & Seasonal Precipitation
Layers:
-   City Boundary
-   Community Boundaries
-   Water Main Incidents (I would like an API to regularly check for new water main incidents, and update the database if there are any)
-   Historical Rainfall (non-GIS database of previous years Rainfall by Rainfall-Gauge)
-   Current Rainfall (non-GIS database of current year Rainfall by Rainfall-Gauge - I would like API to update this daily)
-   Rainfall Gauge locations (GIS-layer containing location of all Rainfall-Gauge items, to be linked with Historical Rain and Current Rainfall)

It is worth noting that the rainfall data is only measure for the "rainy season" of Calgary, which is typically May-September.

The goal of this layer is to create some sort of interpolation of rainfall throughout the city,  
based on the average rainfall at each Rainfall Gauge location during a user-selected time period.

Hopefully we will also be able to create some visualizations examining the relationship/correlation between Water Main Incidents, and rainfall.

## Page 4 - Temperature & Seasonal Conditions
Layers:
-   City Boundary
-   Community Boundaries
-   Water Main Incidents (I would like an API to regularly check for new water main incidents, and update the database if there are any)
-   City Temperature layer

---

## Prerequisites

- On Linux/WSL2: make sure [unzip] is installed `sudo apt-get install zip unzip`
- [UV] - best package manager for Python. Install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [fnm] Install Fast-Node-Manager for Node.js - install with: `curl -o- https://fnm.vercel.app/install | bash`
- [Node.js] - we want this installed with [fnm], install with: `fnm install 24`
    - Verify the Node.js version with: `node -v # Should print "v24.15.0".`
    - Verify npm version `npm -v # Should print "11.12.1".`
- [Podman](https://podman.io/getting-started/installation) installed and running
- On Windows: [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) with Podman installed inside your Linux distribution

---

# Getting Started

The first goal was creating a ocal app that displays a map, queries FastAPI backend, fetches data by bbo, renders markers/polygons, updates on pan/zoom.

Having a very basic map shows that the project is actually feasible, and helps ensure our basic tech-stack is working.

During this step, I followed the instructions from `GettingStartedGuide.md` in order to create a proof-of-concept protoype.

(Note that the data added in this section has since been deleted, and I've updated the process for interacting with PostGIS to the one seen here.)

# Database Section: PostGIS + pgAdmin on Podman

A containerized local development environment for GIS (Geographic Information Systems) work, running PostGIS and pgAdmin using Podman.

---

## What is this?

This project sets up a self-contained environment for storing, querying, and visualizing geospatial data. Here's what each piece does:

- **PostGIS** - a PostgreSQL database with geospatial extensions. Think of it as a regular database that also understands geographic concepts like points, lines, polygons, distances, and map projections. It's the industry standard for storing and querying GIS data.
- **pgAdmin** - a web-based graphical interface for managing your PostgreSQL/PostGIS database. Instead of typing database commands in a terminal, you get a visual tool for browsing your data, running queries, and managing your database.
- **Podman** - a tool for running containers. Containers are self-contained packages that include everything an application needs to run, making it easy to set up complex software without installing it directly on your machine. Podman is similar to Docker but doesn't require a background service running as root.

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

### 2. Set up environment variables

Your database credentials are stored in a `.env` file that stays on your machine and is never committed to GitHub. Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

Open `.env` in a text editor and replace the placeholder values:

```bash
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
PGADMIN_EMAIL=your_email@example.com
PGADMIN_PASSWORD=your_password
```

### 3. Run the setup script

```bash
bash setup.sh
```

This will create the necessary folders, set the correct permissions, and start all the containers. It only needs to be run once on a new machine.

---

## Accessing the Services

| Service    | URL                        |
|------------|----------------------------|
| pgAdmin    | http://localhost:8088      |
| PostGIS    | localhost, port `5433`     |

Open pgAdmin in your browser at `http://localhost:8088` and log in with the email and password you set in `.env`.

Note that PostGIS needs port `5433` to connect to it *externally*, but uses port `5432` to connect to it *internally* (i.e. from pgAdmin)

---

## Connecting pgAdmin to PostGIS

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

---

## Managing the Containers

After the initial setup, use these commands to start and stop the environment:

```bash
# Start all containers
podman pod start postgis

# Stop all containers
podman pod stop postgis

# Check logs if something isn't working
podman logs pgadmin
podman logs postgres

# Tear down everything (your data is preserved in ./poddata)
podman pod rm --force postgis
```

---

## Notes for Windows (WSL2) Users

- Run all commands inside your WSL2 terminal, not PowerShell
- Access pgAdmin and PostGIS via `localhost` in your Windows browser
- If you have an existing PostgreSQL installation on Windows, it may already be using port `5432` — this setup uses port `5433` to avoid that conflict
- If port `8088` or `5433` are already in use, check for conflicting services with `netstat -ano | findstr :<port>` in PowerShell
- Your data is stored in `./poddata/` inside WSL2 and survives container restarts

---

## Project Structure

```
.
|-- setup.sh            # Container setup script - run this first on a new machine
|-- .env                # Your local credentials (not committed to GitHub)
|-- .env.example        # Template showing which variables are needed
|-- .gitignore
|-- README.md
|-- frontend            # folder containing all logic for front-end side of dashboard
|-- backend             # folder containing all logic for back-end side of dashboard      
|-- poddata/            # Persistent container data (not committed to GitHub)
    |-- postgres/       # PostgreSQL data files
    |-- pgadmin/        # pgAdmin session and config data
```

### Project Structure Note: needs 

---

## Security Notes

- `.env` and `poddata/` are excluded from version control via `.gitignore` - your credentials will never be accidentally committed to GitHub
- All ports are bound to `127.0.0.1` (localhost only) and are not publicly exposed
- Use strong, unique passwords in your `.env`, especially if deploying to a server
