#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!

# usage:
# remember to execute this in its own dedicated terminal!



########################################################################################################################
# file name: start_FastAPI.sh
# author: William Hovdestad
#
# Script to run terminal command to start FastAPI so I don't have to remember it 



########################################################################################################################
### BOILERPLATE setup

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
### BOILERPLATE config

# Source - https://stackoverflow.com/a/246128
# Posted by dogbane, modified by community. See post 'Timeline' for change history
# Retrieved 2026-05-22, License - CC BY-SA 4.0
CURRENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into



########################################################################################################################
### actual start of script

cmd="uv run uvicorn backend.backend_main:app --reload --reload-dir backend --reload-dir data_pipeline"
# NOTE: bug we encountere and fixed with `--reload`:
# We want the uvicorn app to watch for changes, so that we can see real-time changes when working in our local test environment
# HOWEVER, the Docker folder we setup - there's stuff in there that Docker says only Docker is allowed to read,
# so by attemping to watch that file, stuff crashes. 
# So the `--reload --reload-dir backend --reload-dir data_pipeline` explicitly tells it to JUST watch those two folders
# remember that FastAPI is our backend side of things, which only `backend` and to a lesser extent `data_pipeline` interact with
eval "$cmd"