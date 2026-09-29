#!/bin/bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: project_dir.sh
# author: William Hovdestad
#
# uses relative path and knowledge of how far deep into the project directory we are,
# to create a variable storing the project directory;
# other BASH scripts can import and use this variable



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

# Source - https://stackoverflow.com/a/246128
# Posted by dogbane, modified by community. See post 'Timeline' for change history
# Retrieved 2026-05-22, License - CC BY-SA 4.0
BASH_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR="$BASH_DIR"
#PROJECT_DIR=$(dirname "$BASH_DIR")
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into

# set current folder name
CURRENT_FOLDER_NAME="BASH_scripts"


LAYERS_DEEP=2 # this file is two-levels away from main project dir
LIMIT="$LAYERS_DEEP"
for ((i=1; i<=LIMIT; i++))
do
    PROJECT_DIR=$(dirname "$PROJECT_DIR")
done

cmd="echo 'PROJECT_DIR=$PROJECT_DIR' > 01__PROJECT_DIR__'$CURRENT_FOLDER_NAME'.env"
eval "$cmd"