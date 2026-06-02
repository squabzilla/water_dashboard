#!/usr/bin/env bash

# this was made by Claude, I should probs review it, but should follow same logic as `setup_cron.sh`?
# (I spent a lot of time going over and getting explanations for `setup_cron.sh`, but too tired to do that here as well)
# anyways, template might be useful if I want to automate removing cron jobs
# idk if it'll actually be useful, but it's not much effort to save it right now, so whatever

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/fetch_daily.py"

if crontab -l 2>/dev/null | grep -qF "$PYTHON_SCRIPT"; then
    crontab -l | grep -vF "$PYTHON_SCRIPT" | crontab -
    echo "Cron job removed."
else
    echo "No cron job found for $PYTHON_SCRIPT."
fi