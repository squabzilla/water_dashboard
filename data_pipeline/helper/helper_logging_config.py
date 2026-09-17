"""
file name: helper_logging_config.py
author: William Hovdestad

This script is a helper-function for my data-pipeline where I setup all the logging-logic for my data pipeline
so that I don't need to copy+paste in every script

Also makes it easy to make blanket changes to my logging

and finally, having a single place where I make all my notes to myself about how the hell logging works
"""



########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets great grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
import logging



########################################################################################################################
### LOGGING EXPLANATION
"""
NOTE: LOGGING LEVELS
each logging level has a numeric value

NOTE: DEBUG(10)
Think: speedometer log of car-trip.
Verbose diagnostic details for active trouble shooting. Variable values, function input/output, raw data, etc. etc.
Basically all the shit you used to throw in print-statements when testing, that you remove when done

# NOTE: INFO(20)
Think: Green-Light
Confirmation that things are working as expected. "Server started." "Download started." "Download complete." 
That sort of thing

# NOTE: WARNING(30)
Think: Yellow-Light
There's a potential problem or hiccup, but the program is still running fine.
A config value falls back to default, disk space getting low, etc.
Potential problem, but nothing crashed right now.

# NOTE: ERROR(40)
Think: Red-Light
Something failed, but the server is still running.
Your game crashed, but you can restart the game and load your file.

# NOTE: CRITICAL(50)
Think: Car accident.
Data corruption, unable to connect to server, hard-drive failure.

Convention: Production systems run at INFO (or WARNING), while DEBUG is switched on when investigating issues.
"""


########################################################################################################################
### setup-logging function

"""
quick usage example:

import logging
from helper_logging_config import setup_logging

logfile = "/full/path/to/log_file.log"
setup_logging(logfile)
logger = logging.getLogger(__name__)


logger.info("shows up everywhere")
logger.info("file only", extra={"console_exclude": True})
"""

def setup_logging(logfile: Path, logging_level: int = logging.INFO, disable_API_spam=True):
    """
    Configures logging level. Call it once from entry-point script;
    will raise error if called twice in a "module"

    The default level is INFO, but it's a variable, so I can change that if I want
    LIKE IF I WANT TO DEBUG OR SOMETHING!!!
    """

    # raise error if not given a logfile to log to
    if not logfile:
        raise ValueError("Error: logfile path must be provided.")

    # create variable to hold ***root logger***
    root = logging.getLogger()

    # raise error if it's already been run again
    if root.hasHandlers():
        msg = (
            "ERROR: `setup_logging()` was called after logging was already configured. "
            "It should only be called once, from entry-point script."
        )
        raise RuntimeError(msg)
    # NOTE: Explanation:
    # calling `logging.basicConfig` configures the ***root logger***
    # however, if the ***root logger*** already has handlers, i.e. has already been setup,
    # calling `logging.basicConfig` actually does nothing - the technical term is "no-op" as in "no-operation"
    # however, this could easily lead to a confusing scenario where I'm calling this function 
    # after the ***root logger*** has already been setup, and then I'm getting confused why it's not doing anything
    # so, instead, I want it to fail loudly instead of silently doing nothing when I expect SOMETHING

    # let's just disable my API spam - I don't need to log every fucking API call lol
    if disable_API_spam == True:
        logging.getLogger("httpx").setLevel(logging.WARNING)


    # by making these their own objects, I can add filters to them
    file_handler = logging.FileHandler(logfile) # handles output file
    console_handler = logging.StreamHandler() # writes log to a "stream" which by default is terminal/console

    # setup the logging-level for those handlers
    file_handler.setLevel(logging.INFO)
    # I will be tracking CRON-jobs with my file-handlers, so I don't want debug statements here
    console_handler.setLevel(logging.DEBUG)
    # I can use logging.DEBUG for all my "testing print statements",
    # and then set the log level to logging.INFO to turn them off when I'm done testing!

    # setup basic logging config
    # NOTE: `logging.basicConfig` sets up the ROOT LOGGER
    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[file_handler, console_handler],
    )

    # NOTE: logging levels: affects labelling and filtering when looking through errors
    # like remember how I'd tell Python "idgaf about that warning just stop telling me"
    # but also not wanting to eliminate like SERIOUS errors?
    # that's what the logging levels let us do
    


    # NOTE: 

    # now I create a method to exclude stuff from console
    def exclude_from_console(record): # every time you call `logger.<level>(...), logging makes a LogRecord instance
        # we can add extra stuff to it by adding `extra={}` to the log call
        return not getattr(record, "console_exclude", False)
    # pass the function to `console_handler.addFilter` - note we don't want to CALL the method, but pass the entire method
    console_handler.addFilter(exclude_from_console)

    # NOTE: `addFilter` explanation:
    # the `addFilter` instance needs to be passed some method/function that returns True/False
    # if that method returns True, the log proceeds normally; if it returns False, the log is filtered
    # the `getattr` function takes an object, the name of an attribute of the object, and a default value
    # it returns the value of object.attribute, or returns the default if it doesn't exist
    # "console_exclude" present and True  => getattr returns True  => function returns Not-True, aka False => log-statement-filtered
    # "console_exclude" not-present/False => getattr returns False => function returns Not-False, aka True => log-statement-unfiltered
    # and because I only attached it to the console-handler, only the console-handler is filtered