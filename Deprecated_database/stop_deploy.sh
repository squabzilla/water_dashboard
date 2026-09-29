#!/bin/bash

# code to make this file executable:
# chmod +x podman_setup.sh



########################################################################################################################
### script name: `stop_deploy.sh`
###
### summary: basically stop all services and system configuration settings made by `deploy.sh`
### note that the `.env` symlinks will still persist, and we're not touching the `volume` data because either



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

echo "--> Stopping Postgres service..."
systemctl --user stop postgres.service

echo "--> Reloading systemd..."
systemctl --user daemon-reload

echo "--> Disabling linger..."
sudo loginctl disable-linger $USER

echo ""
echo "Done! Volume data and Quadlet symlinks have been preserved."
echo "Run \`./deploy.sh\` to bring everything back up."
echo ""