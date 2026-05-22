#!/bin/bash

# code to make this file executable:
# chmod +x podman_setup.sh

########################################################################################################################
### script name: `deploy.sh`
###
### SUMMARY: Setup and start PSQL PostGIS Database, on (hopefully) any Linux machine
###
### This script is designed to setup/start the Podman containerization of the PSQL PostGIS database, 
### using Podman Quadlets, for the 'water_dashboard' project; or, to be more verbose:
### The Calgary Water Main Dashboard Project.
### The reasoning behind setting this up is it makes the project much more portable (to setup on new machines),
### and will (hopefully) make it easy for someone besides the author to setup and run the whole thing.
### ...pending completion of the rest of the project lol



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

# Source - https://stackoverflow.com/a/246128
# Posted by dogbane, modified by community. See post 'Timeline' for change history
# Retrieved 2026-05-22, License - CC BY-SA 4.0
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into

# set variable for Quadlet directory
QUADLET_DIR="${HOME}/.config/containers/systemd"
# NOTE: Quadlet is apparently hard coded to specifically check `~/.config/containers/systemd/` for its unit files

# set location of `.env` file
ENV_FILE="${HOME}/.config/water_dashboard/.env"
# make array storing required variables in `.env` file
REQUIRED_VARS=(POSTGRES_USER POSTGRES_PASSWORD)



########################################################################################################################
### check that `.env` file exists, and has proper variables we want

# start validating the `.env` file
echo "--> Checking \`.env\` file."

# first, check that it exists at proper location
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: No .env found at $ENV_FILE"
    exit 1 # we exit with error code if file not found
fi
# since we got here, now we know it it exists, we can safely grab it with `source`
source "$ENV_FILE"
# source reads that entire file into current shell - can load variables, functions, execute return statements...
# very dangerous if you don't know what your sourcing lol

# make (empty) arry to store any missing values we find...
MISSING=()
# loop thru required vars, add to MISSING if not found (hopefully they're here because of `source` tho)
for var in "${REQUIRED_VARS[@]}"; do
    # $var, ${var}, ${!var} explanation:
    # `$var` is equivalent to `${var}` - but if we're doing extra operations to `var`, we need squiggly brackets
    # `$var` or `${var}` gets the NAME of `var`, while `${!var} gets the VALUE of it
    # think of this as looping thry Python dict (key-value pair): `${var}` is the key, `${!var} gets the value
    # {!var:-} -> the `-` ending means "if unset, use follwing stuff to set it", and `:-` means "if unset-or-null"
    # so {!var:-CAKE} would mean "if value of `var` is unset-or-null, set value to CAKE
    # in this case, if $!{var} is unset-or-null, we set it to empty string (since there's no text between `-` and ending `}`)
    if [[ -z "${!var:-}" ]]; then
    # this statement checks if "${!var:-}" matches the `-z` flag, which is the empty-string
    # (dunno if `-z` is actually a flag or a keyword or whatnot, but whatever, doesn't matter here lol)
        MISSING+=("$var") # add value of var - the NAME of var - to MISSING array (list) if above condition met
    fi # end if
done # done loop

if [[ ${#MISSING[@]} -gt 0 ]]; then
# the `#` means COUNT-FOLLOWING; MISSING[@] means return all elements of MISSING; so ${#MISSING[@]} counts length of array
# `-gt` just means Greater-Then; sad we don't have `>`; so if LENGTH(ARRAY) > 0 - 
# which means the previous loop found missing elements
    echo "    ERROR: The following required variables are missing or empty in $ENV_FILE:"
    for var in "${MISSING[@]}"; do
        echo "      - $var"
    done
    exit 1
fi
echo "    .env looks good"



########################################################################################################################
### create symlinks to the Quadlet files
### Podman Quadlets is apparently hard coded to specifically check `~/.config/containers/systemd/` for its unit files,
### so we're going to symlink the Podman Quadlet files from our repo `<RepoFolder>/database/quadlets` with above path
### this basically creates a "pointer" between them, so when Podman Quadlets looks in `~/.config/containers/systemd/`,
### it gets directed to the ones in our repo


echo "--> Setting up and linking Quadlets..."
# make the Quadlet directory we defined earlier
# (ones outside main repo folder, in ~/.config/containers/systemd)
mkdir -p "$QUADLET_DIR"
# loop thru all of our files in SCRIPT_DIR/quadlets (that have valid Quadlet extensions)
# and link to "proper" Quadlet folder (one outside of main repo folder)
for f in "$SCRIPT_DIR"/quadlets/*.pod \
          "$SCRIPT_DIR"/quadlets/*.volume \
          "$SCRIPT_DIR"/quadlets/*.container; do
    # this line is the meat: we perform a link (or symlink) `ln` that's symbolic `-s` and forced `-f` 
    # "forced" in this context, means it removes existing destination files first
    # conceptually, a "link" like this is similar to a "shortcut"
    # - but "shortcuts" basically only work for PC-users, while symlinks work for programins (and shortcuts don't)
    ln -sf "$f" "$QUADLET_DIR/$(basename "$f")"
    # some long echo statements to explain PRECISELY what is happening
    echo "    LINKED:    \`$f\`"
    echo "      WITH:    \`$QUADLET_DIR/$(basename "$f")\`"
    #echo "    Linked: $(basename "$f")"
done



########################################################################################################################
### finally, start some of our stuff on linux-side so this shit all works lol

echo "--> Reloading systemd"
systemctl --user daemon-reload

echo "--> Booting-up PSQL service"
systemctl --user restart postgres.service
# we run this script on deployment or update - so if `postgres.service` is off, `reboot` will start it up
# and if `postgres.service` is currently active, the running we're running this script is we want to reboot things

echo "--> Enabling lingering (so app runs logged out, may prompt for sudo password)"
sudo loginctl enable-linger "$USER"

echo ""
echo "Done! Postgres is available at localhost:5433"
echo "Here are some quick console commands to test your deployment:"
echo ""

# NOTE: confirm it's working with:
# `podman exec -it postgres psql -U <your_postgres_user> -d calgary_watermains -c "\conninfo"`
# and
# `podman exec -it postgres psql -U <your_postgres_user> -d calgary_watermains -c "\dx"`