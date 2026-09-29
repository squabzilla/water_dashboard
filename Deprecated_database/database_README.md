# Database Infrastructure

This document explains how the database infrastructure pieces fit together — what each file does, why it exists, and how they interact at runtime.

---

## File inventory

### In the repo (`database/`)

| File | Purpose |
|------|---------|
| `config.sh` | Non-secret configuration: DB name, host, port, container name |
| `quadlets/postgres.container` | Defines the PostGIS container as a systemd service |
| `quadlets/postgres-data.volume` | Defines the named volume for persistent storage |

### On your machine (outside the repo)

| File | Purpose |
|------|---------|
| `~/.config/water_dashboard/.env` | Secrets: `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| `~/.config/water_dashboard/config.sh` | Copy of `database/config.sh`, placed here by `deploy.sh` so systemd can find it at a fixed path |

---

## Why two config files?

The split between `.env` and `config.sh` follows a standard security principle: **secrets and non-secrets live separately**.

- `.env` contains credentials. It lives outside the repo entirely and is never committed to GitHub. Each machine has its own copy with real values.
- `config.sh` contains configuration that isn't sensitive — the database name, port, container name. It lives in the repo, is version controlled, and is consistent across all machines.

This means anyone cloning the repo only needs to create a `.env` file with their own credentials — everything else is already defined.

---

## How the pieces connect at runtime

When `postgres.service` starts, systemd does the following in order:

1. Reads the generated unit file at `~/.config/containers/systemd/postgres.container` (a symlink into the repo, created by `deploy.sh`)
2. Loads `~/.config/water_dashboard/.env` — makes `POSTGRES_USER` and `POSTGRES_PASSWORD` available in the service environment
3. Loads `~/.config/water_dashboard/config.sh` — makes `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_CONTAINER` available in the service environment
4. Runs the generated `podman run` command, with all `${VAR}` references expanded from that environment

Step 4 is why `Environment=POSTGRES_DB=${POSTGRES_DB}` in `[Container]` works even though `POSTGRES_DB` is defined in `config.sh` inside `[Service]` — systemd has already loaded it before running anything.

---

## Why `EnvironmentFile=` is in `[Service]`, not `[Container]`

`[Container]` and `[Service]` are processed by completely different systems:

- `[Container]` is read by **Podman's Quadlet generator**, which translates it into a `podman run` command
- `[Service]` is read by **systemd**, which handles it natively

`EnvironmentFile=` is a systemd directive — Quadlet wouldn't know what to do with it in `[Container]`. It belongs in `[Service]`, where systemd can act on it.

The textual layout can feel backwards (variables defined below where they're used), but the execution order is what matters: systemd loads the environment files first, then runs the command. Moving both `EnvironmentFile=` lines to the top of `[Service]` makes the intent clearer to a human reader, which is why they appear there.

---

## How bash scripts use `config.sh`

Bash scripts source `config.sh` directly from the repo using `SCRIPT_DIR` to find it, rather than relying on the copy at `~/.config/water_dashboard/config.sh`. This keeps everything relative to the repo:

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/../database/config.sh"       # non-secret config
source "$HOME/.config/water_dashboard/.env"       # secrets

psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" \
     -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
     -f your_script.sql
```

The path to `config.sh` will vary depending on where the script calling it lives — adjust `../database/config.sh` to match the relative path from your script's location.

---

## How `deploy.sh` fits in

`deploy.sh` bridges the gap between "files in the repo" and "files systemd can find at a fixed path":

1. Validates `~/.config/water_dashboard/.env` exists and has the required variables
2. Symlinks `database/config.sh` to `~/.config/water_dashboard/config.sh` so systemd can reference it at a fixed path
3. Symlinks `database/quadlets/*.container` and `database/quadlets/*.volume` into `~/.config/containers/systemd/` where Podman Quadlets looks for unit files
4. Runs `systemctl --user daemon-reload` so systemd picks up the new unit files
5. Starts `postgres.service`

Running `deploy.sh` again after a `git pull` is safe — it is idempotent and handles both first-time setup and updates.

Because `config.sh` is symlinked rather than copied, edits to `database/config.sh` in the repo are immediately visible to systemd at the fixed path without re-running `deploy.sh`. However, the running container won't pick up the changes automatically — systemd reads `config.sh` once at startup and loads the values into the container's environment. To apply changes, run:

```bash
systemctl --user daemon-reload
systemctl --user restart postgres.service
```

---

## Data persistence

Postgres data is stored in a named Podman volume (`systemd-postgres-data`), not inside the container or the repo folder. This means:

- Data survives container restarts and even container deletion
- The volume lives at `~/.local/share/containers/storage/volumes/systemd-postgres-data/_data/` on the host
- Inspecting the volume: `podman volume inspect systemd-postgres-data`
- Deliberately deleting the volume (full reset): `podman volume rm systemd-postgres-data`
