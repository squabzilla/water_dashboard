#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: run_SQL.sh
# author: William Hovdestad
#
# Runs a given SQL script in our repo, given an input SQL script
# I'll make handlers for running the actual scripts, but they can use this one
#
# Usage:
#   ./run_SQL.sh <SQL_SCRIPT.sql>



########################################################################################################################
### setup - create some variables, set configuration options

# some error handling stuff
set -euo pipefail
# Explanation:
# `set -e` - exit immediately if any command returns an error code, instead of plowing ahead
# `set -u` - treat unset variables as errors
# `set -o pipefail` - in pipelines specifically, such as `cmd1 | cmd2 | cmd3`, 
# only the exit (error) code of the LAST command is reported. This makes pipeline fail
# if ANY command in it fails, not just the last one.
# This isn't relevant to my script at the moment, but it's good general practice & future-proofing



########################################################################################################################
### config - get project directory

# get current dir
CURRENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# setup local env variable
LOCAL_ENV_NAME="01__PROJECT_DIR__BASH_scripts.env"
LOCAL_ENV_FILEPATH="$CURRENT_DIR/$LOCAL_ENV_NAME"

# import project directory variable
set -a
# shellcheck disable=SC1090
source "$LOCAL_ENV_FILEPATH" # ignore that shellcheck can't confirm if <variable> is proper path or not
set +a
# check that the variable we want exists and is not empty
if [[ -z "${PROJECT_DIR:-}" ]]; then
    echo "Error: PROJECT_DIR not set in $PROJECT_DIR" >&2
    exit 1
fi



########################################################################################################################
### import our SQL file and `config.env` exist; import variables from `config.env`

#SQL_FILE="$PROJECT_DIR/data_pipeline/SQL_scripts/annual_watermain_weather_summary.sql"
SQL_FILE="$1"
CONFIG_ENV_FILE="$PROJECT_DIR/config.env"

# confirm SQL_FILE exists
if [[ ! -f "$SQL_FILE" ]]; then
    echo "ERROR: SQL-file not found at: $SQL_FILE" >&2
    exit 1
fi

# confirm `config.env` exists
if [[ ! -f "$CONFIG_ENV_FILE" ]]; then
    echo "ERROR: config.env file not found at: $CONFIG_ENV_FILE" >&2
    exit 1
fi

set -a

# `shellcheck` is a useful thing to check shell-scripts, but also, 
# gets mad at using `source` on stuff it doesn't know is a filepath
# so we put in the following thing, so it doesn't get mad at a specific error on the next line:
# shellcheck disable=SC1090
source "$CONFIG_ENV_FILE" # this gets variables from objects in that file - so now we know ENV file location...

# `set +a` explanation: Using ‘+’ rather than ‘-’ causes these options to be turned off.
set +a



########################################################################################################################
### now we should have the SECRET_ENV_FILE variable, which is the filepath for the secret env file outside proj. dir.

# first, confirm that the variable SECRET_ENV_FILE exists
if [[ -z "${SECRET_ENV_FILE:-}" ]]; then
    echo "Error: SECRET_ENV_FILE not set in $SECRET_ENV_FILE" >&2
    exit 1
fi

# now, confirm it's a valid file
#if [[ ! -f "$SECRET_ENV_FILE:-}" ]]; then
#    echo "Error: SECRET_CONFIG.env not found at: $SECRET_ENV_FILE" >&2
#    exit 1
#fi
# actually, because of weirdness with how WSL2 runs as a virtual machine,
# the "path" for this starts with `home/`, which is not the full start-path on the windows machine, just the virtual linux part
# however, the `source` command seems to operate *inside* the WSL2 virtual machine,
# while the code that 

# so, we'll get tricky with importing the variable...
set -a
# shellcheck disable=SC1090
source "$SECRET_ENV_FILE" || { echo "Error: SECRET_CONFIG.env not found at: $SECRET_ENV_FILE" >&2; exit 1; }
set +a



########################################################################################################################
### check that specific variables exist

if [[ -z "${POSTGRES_DB:-}" ]]; then
    echo "ERROR: POSTGRES_DB is not set in $CONFIG_ENV_FILE" >&2
    exit 1
fi
 
if [[ -z "${POSTGRES_CONTAINER:-}" ]]; then
    echo "ERROR: POSTGRES_CONTAINER is not set in $CONFIG_ENV_FILE" >&2
    exit 1
fi
 
if [[ -z "${POSTGRES_USER:-}" ]]; then
    echo "ERROR: POSTGRES_USER is not set in $SECRET_ENV_FILE" >&2
    exit 1
fi
 
if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
    echo "ERROR: POSTGRES_PASSWORD is not set in $SECRET_ENV_FILE" >&2
    exit 1
fi

# some code to check our docker-shit I guess
if ! docker ps --format '{{.Names}}' | grep -qx "$POSTGRES_CONTAINER"; then
    echo "ERROR: no running container named '$POSTGRES_CONTAINER'." >&2
    echo "       Running containers:" >&2
    docker ps --format '  {{.Names}}\t{{.Image}}' >&2
    exit 1
fi



# --- Run -------------------------------------------------------------
# -i keeps stdin open so the SQL file can be piped into the container's
# psql process; there's no shared filesystem to point --file at instead.
# -e PGPASSWORD=... sets the password only inside the container, for
# this one command -- it's never exported on the host.
# ON_ERROR_STOP=1 is not psql's default -- without it, a failed statement
# is printed as an error and execution continues through the rest of the
# file, which is the opposite of fail-fast.
docker exec -i \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    "$POSTGRES_CONTAINER" \
    psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --set ON_ERROR_STOP=1 \
    < "$SQL_FILE"

echo "executed $SQL_FILE"