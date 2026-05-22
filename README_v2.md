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

***NOTE***:  
The original proof-of-concept front-end was created using `Step 8` through `Step 11` from `proof_of_concept.md`.  
Given how tiny and limited in scope the proof-of-concept front-end was, we have decided to remove it entirely.  
The front-end will be recreated once the database portion of the backend is complete,  
and we are actually in a position to incorporate our planned features into our front-end dashboard.  
Note that the original proof-of-concept front-end still exists in the `git` history,  
and can also be recreated using the previously mentioned `Step 8` through `Step 11` from `proof_of_concept.md`.  
In addition, the frontend `README.md` and `.gitignore` are still being kept for potential future reference.

## Back-End
-   [Python] using [FastAPI]

## Database
-   [Podman] container of [PostGIS], managed by [Podman Quadlets] via systemd

# Dashboard Structure:

## Page 1 - Executive Overview
Summary page explaining the project.

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

It is worth noting that the rainfall data is only measured for the "rainy season" of Calgary, which is typically May-September.

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

- On Linux/WSL2: make sure [unzip] is installed: `sudo apt-get install zip unzip`
- [UV] - best package manager for Python. Install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [fnm] Install Fast-Node-Manager for Node.js - install with: `curl -o- https://fnm.vercel.app/install | bash`
- [Node.js] - we want this installed with [fnm], install with: `fnm install 24`
    - Verify the Node.js version with: `node -v # Should print "v24.15.0".`
    - Verify npm version: `npm -v # Should print "11.12.1".`
- [Podman](https://podman.io/getting-started/installation) installed and running
- On WSL2: systemd must be enabled. Add the following to `/etc/wsl.conf` inside your WSL2 distro, then run `wsl --shutdown` from PowerShell and reopen WSL2:
    ```ini
    [boot]
    systemd=true
    ```

---

# Getting Started

The first goal was creating a local app that displays a map, queries the FastAPI backend, fetches data by bbox, renders markers/polygons, and updates on pan/zoom.

Having a very basic map shows that the project is actually feasible, and helps ensure our basic tech-stack is working.

During this step, I followed the instructions from `GettingStartedGuide.md` in order to create a proof-of-concept prototype.

(Note that the data added in this section has since been deleted, and the database setup has been fully replaced with the Quadlet-based approach described below.)

---

# Database Section: PostGIS on Podman (Quadlets)

A containerized local development environment for GIS (Geographic Information Systems) work, running PostGIS using Podman Quadlets managed by systemd.

---

## What is this?

This project sets up a self-contained environment for storing and querying geospatial data. Here's what each piece does:

- **PostGIS** - a PostgreSQL database with geospatial extensions. Think of it as a regular database that also understands geographic concepts like points, lines, polygons, distances, and map projections. It's the industry standard for storing and querying GIS data.
- **Podman** - a tool for running containers. Containers are self-contained packages that include everything an application needs to run, making it easy to set up complex software without installing it directly on your machine. Podman is similar to Docker but doesn't require a background service running as root.
- **Podman Quadlets** - a Podman feature that manages containers as systemd services, giving you automatic startup on boot, restart on failure, and proper service lifecycle management — all defined declaratively in configuration files stored in this repo.

For database administration, connect directly using pgAdmin or psql on your host machine via `localhost:5433`.

---

## How the database infrastructure works

Instead of a shell script that manually runs `podman run`, this project uses **Podman Quadlets** — declarative configuration files that tell systemd how to manage the container as a proper service.

The Quadlet files live in `database/quadlets/` in this repo:
- `postgres.container` — defines the PostGIS container: image, port, volume, environment, healthcheck
- `postgres-data.volume` — defines the named volume for persistent storage

`deploy.sh` symlinks these files into `~/.config/containers/systemd/` where Podman Quadlets expects to find them, then starts the service via systemd. The data itself is stored in a named Podman volume (`postgres-data`) on your host machine, completely separate from the repo folder — it persists across container restarts and survives even if the container is removed.

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

### 2. Set up environment variables

Your database credentials are stored in a `.env` file that lives outside the repo and is never committed to GitHub. Create it at the required location:

```bash
mkdir -p ~/.config/water_dashboard
cp .env.example ~/.config/water_dashboard/.env
nano ~/.config/water_dashboard/.env
```

Fill in your own values:

```bash
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
```

### 3. Run the deploy script

```bash
chmod +x deploy.sh
./deploy.sh
```

This will validate your `.env`, symlink the Quadlet files into the correct systemd location, and start the PostGIS service. It is safe to re-run — use it for both first-time setup and subsequent updates after a `git pull`.

### 4. (Server only) Enable boot persistence

If deploying to a server (e.g. a DigitalOcean Droplet), run this once to keep the service running after you log out:

```bash
sudo loginctl enable-linger $USER
```

This is not needed on a local WSL2 development machine.

---

## Accessing PostGIS

PostGIS is available at `localhost:5433`. Connect using any Postgres client (pgAdmin, psql, DBeaver, etc.):

| Setting  | Value               |
|----------|---------------------|
| Host     | `localhost`         |
| Port     | `5433`              |
| Database | `calgary_watermains`|
| Username | your `POSTGRES_USER`|
| Password | your `POSTGRES_PASSWORD`|

**Note for WSL2 users:** connect via `localhost:5433` from either your WSL2 terminal or your Windows-side client — both work.

---

## Managing the service

```bash
# Check service status and recent logs
systemctl --user status postgres.service

# View full logs
journalctl --user -xeu postgres.service

# Restart the service (e.g. after a git pull + deploy.sh)
systemctl --user restart postgres.service

# Stop the service and disable boot persistence (preserves all data)
./stop_deployment.sh

# Verify PostGIS is healthy and accepting connections
podman exec -it postgres pg_isready -d calgary_watermains

# Connect to the database directly
podman exec -it postgres psql -U your_username -d calgary_watermains
```

---

## Notes for Windows (WSL2) Users

- Run all commands inside your WSL2 terminal, not PowerShell
- Systemd must be enabled in WSL2 (see Prerequisites above)
- If you have an existing PostgreSQL installation on Windows, it may already be using port `5432` — this setup uses port `5433` to avoid that conflict
- Connect to PostGIS via `localhost:5433` from both WSL2 and Windows-side clients
- All container data is stored in a named Podman volume (`~/.local/share/containers/storage/volumes/systemd-postgres-data/`) inside WSL2 and survives container restarts

---

## Project Structure

```
.
├── deploy.sh               # First-time setup and update script — run this on any new machine
├── stop_deployment.sh      # Stops service and disables boot persistence, preserves data
├── .env.example            # Template showing which variables are needed (never commit .env itself)
├── .gitignore
├── README.md
├── database/
│   └── quadlets/           # Podman Quadlet configuration files (managed by systemd)
│       ├── postgres.container
│       └── postgres-data.volume
├── frontend/               # All front-end logic for the dashboard
└── backend/                # All back-end logic for the dashboard
```

**Note:** The `.env` file lives at `~/.config/water_dashboard/.env` on each machine — outside the repo, never committed to GitHub.  
The Postgres data volume lives at `~/.local/share/containers/storage/volumes/systemd-postgres-data/` — also outside the repo.

---

## Security Notes

- `.env` is stored outside the repo entirely (`~/.config/water_dashboard/.env`) and is never committed to GitHub
- All ports are bound to `127.0.0.1` (localhost only) and are not publicly exposed
- The named Podman volume is managed by the container runtime and is not accessible from the public internet
- Use strong, unique passwords in your `.env`, especially if deploying to a server
