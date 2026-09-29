#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: SETUP.sh
# author: William Hovdestad
#
# setups shit we need to initialize the project... very dangerous script lol
# usage:
#   sudo ./SETUP.sh



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
### config

# Source - https://stackoverflow.com/a/246128
# Posted by dogbane, modified by community. See post 'Timeline' for change history
# Retrieved 2026-05-22, License - CC BY-SA 4.0
BASH_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into
PROJECT_DIR=$BASH_DIR # setup what the project directory is

### confirm we're in the right directory
WATER_DASHBOARD="water_dashboard"
# get basename of folder, then check if it's correct
BASH_DIR_BASENAME=$(basename $BASH_DIR)
SCRIPT_NAME=$(basename "$0")
if [[ "$BASH_DIR_BASENAME" != "$WATER_DASHBOARD" ]]; then
    echo "ERROR: \`$SCRIPT_NAME\` located in \`$BASH_DIR_BASENAME\` folder, not \`$WATER_DASHBOARD\` folder"
    exit 1
fi
# NOTE: at this point, we know this file is located in our main project-folder (or at least one with same name lol)



########################################################################################################################
### get some variables
PROJECT_CONFIG="$PROJECT_DIR/config.env"
# confirm it exists
if [[ ! -f "$PROJECT_CONFIG" ]]; then
    echo "ERROR: $PROJECT_DIR/config.env not found" >&2
    exit 1
fi

# `set -a` explanation: Each variable or function that is created or modified is given the export
#                       attribute and marked for export to the environment of subsequent commands.
set -a
# `shellcheck` is a useful thing to check shell-scripts, but also, 
# gets mad at using `source` on stuff it doesn't know is a filepath
# so we put in the following thing, so it doesn't get mad at a specific error on the next line:
# shellcheck disable=SC1090
source "$PROJECT_CONFIG" # this gets variables from objects in that file - so now we know ENV file location...
# `set +a` explanation: Using ‘+’ rather than ‘-’ causes these options to be turned off.
set +a

# confirm env file exists now lol
if [[ ! -f "$SECRET_ENV_FILE" ]]; then
    echo "ERROR: .env file not found at: $SECRET_ENV_FILE" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$SECRET_ENV_FILE" # now we source our .env file ahahahahaha
set +a



########################################################################################################################
### check that `.env` file exists, and has proper variables we want
REQUIRED_VARS=(POSTGRES_USER POSTGRES_PASSWORD)

# start validating the `.env` file
echo "--> Checking \`SECRET_CONFIG.env\` file."

# first, check that it exists at proper location
if [[ ! -f "$SECRET_ENV_FILE" ]]; then
    echo "ERROR: No .env found at $SECRET_ENV_FILE"
    exit 1 # we exit with error code if file not found
fi
# since we got here, now we know it it exists, we can safely grab it with `source`
source "$SECRET_ENV_FILE"
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
    echo "    ERROR: The following required variables are missing or empty in $SECRET_ENV_FILE:"
    for var in "${MISSING[@]}"; do
        echo "      - $var"
    done
    exit 1
fi
echo "    .env looks good"



########################################################################################################################
### update system, get UV, shllecheck
#exit 0 # because I don't wanna do this shit right now lol

#confirm we're on linux, or crash now lol
OS_TYPE="$(uname -s)"
if ! [ "$OS_TYPE" = "Linux" ]; then
    echo "Error. OS-type should be Linux. This script is not configured to work on non-Linux machines. Aborting."
    exit 1
fi



# update system
echo "updating system..."
update_everything="sudo apt update && sudo apt upgrade -y"
# eval "$update_everything" # be careful about whether you really want to execute this lol
echo "system updated"

# check for UV
echo "Checking if UV is installed..."
if ! command -v uv &> /dev/null; then # check for UV
    echo "UV not installed. Installing..."
    install_UV="curl -LsSf https://astral.sh/uv/install.sh | sh"
    eval "$install_UV"
    export PATH="$HOME/.local/bin:$PATH" # update path for installed stuff
    echo "UV has been successfully installed!"
else
    echo "UV is already installed. UV version:"
fi
check_uv_version="uv --version"
eval "$check_uv_version"

# check for shellcheck
echo "checking for shellcheck..."
if ! command -v shellcheck &> /dev/null; then # check for shellcheck
    install_shellcheck="sudo apt install shellcheck"
    eval "$install_shellcheck"
    export PATH="$HOME/.local/bin:$PATH" # update path for installed stuff
    echo "shellcheck has been successfully installed"
else
    echo "shellcheck is already installed"
fi
check_shellcheck_version="shellcheck --version"
eval "$check_shellcheck_version"



########################################################################################################################
### start database containerization, run our data-pipeline, setup cron jobs

# exit 0 # because I really don't want to do these right now lol

#setup_db="database/./deploy.sh" #whoops, for old shit
setup_db="cd $PROJECT_DIR/Docker && make up"
eval "$setup_db"

run_data_pipeline="$PROJECT_DIR/data_pipeline/./bash_backfill.sh"
eval "$run_data_pipeline"

run_cron_setup="$PROJECT_DIR/data_pipeline/./cron_setup.sh"
eval "$run_cron_setup"

echo "holy shit we're done setup everything worked AHHHHHHHHHHHHHH"
echo "okay I need to rename my \`.env\` file to \`secrets.env\` lol"