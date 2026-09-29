#!/bin/bash

# code to make this file executable:
# chmod +x nuke_and_rebuild.sh

########################################################################################################################
### script name: `nuke_and_rebuild.sh`
###
### SUMMARY: Stops my database service and deletes the data-volume, then calls `deploy.sh` to rebuild from scratch
###
### This script wipes my database and rebuilds it from scratch, in the case that the database gets severely screwed-up,
### and the easiest way to fix it is to just rebuild it from scratch.
### (Since all the data comes from external APIs, so we don't have the usual concern for data backup and integrity.)
### This makes wiping out the entire database and starting over actually a viable option.
### Note that the more data I have, the less optimal it becomes to "nuke and rebuild" since retrieving and re-processing
### the data will become more time-consuming as the project develops, so REAL database backups should eventually be made



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



########################################################################################################################
### WARNING MESSAGE AND CONFIRMATION - this does some irreversible changes, so I want warnings and manual confirmation

echo ""
echo "  WARNING: This will permanently delete all data in the calgary_watermains database."
echo "  This cannot be undone."
echo ""
echo "  Type 'yes' to continue, or anything else to cancel:"
read -r CONFIRMATION

if [[ "$CONFIRMATION" != "yes" ]]; then
    echo "Cancelled."
    exit 0
fi


### stop the service
echo ""
echo "--> Stopping Postgres service..."
systemctl --user stop postgres.service || true
# `|| true` prevents set -e from exiting if the service is already stopped


### delete the data volume
echo "--> Deleting data volume..."
podman volume rm systemd-postgres-data || true
# same reasoning - don't fail if the volume doesn't exist


### deploy script to rebuild
echo "--> Rebuilding..."
"$SCRIPT_DIR/deploy.sh"