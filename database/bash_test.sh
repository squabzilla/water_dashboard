#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


# Source - https://stackoverflow.com/a/246128
# Posted by dogbane, modified by community. See post 'Timeline' for change history
# Retrieved 2026-05-22, License - CC BY-SA 4.0
SCRIPT_DIR_2=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )


ENV_FILE="${HOME}/.config/calgarywater/.env"
REQUIRED_VARS=(POSTGRES_USER POSTGRES_PASSWORD)


echo "--> Checking \`.env\` file."
# check that file exists
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: No .env found at $ENV_FILE"
    exit 1
fi

# now we know it it exists, we can safely grab it with `source`
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