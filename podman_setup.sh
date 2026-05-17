#!/bin/bash

# code to make executable:
# chmod +x podman_setup.sh

# Load environment variables
source .env

# Set up directories
mkdir -p poddata/postgres
mkdir -p poddata/pgadmin
podman unshare chown -R 5050:5050 ./poddata/pgadmin

# Create pod
podman pod create --name postgis \
  -p 127.0.0.1:5433:5432 \
  -p 127.0.0.1:8088:80

# Start postgres
podman run -d --pod postgis --name postgres \
  -e POSTGRES_USER=$POSTGRES_USER \
  -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
  -v ./poddata/postgres:/var/lib/postgresql/data:Z \
  docker.io/postgis/postgis

# Start pgadmin
podman run -d --pod postgis --name pgadmin \
  --user 5050:5050 \
  -e PGADMIN_DEFAULT_EMAIL=$PGADMIN_EMAIL \
  -e PGADMIN_DEFAULT_PASSWORD=$PGADMIN_PASSWORD \
  -v ./poddata/pgadmin:/var/lib/pgadmin:Z \
  docker.io/dpage/pgadmin4

printf "hello world \n"