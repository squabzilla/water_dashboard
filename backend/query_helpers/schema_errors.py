"""
name: schema_errors.py
author: William Hovdestad

Purpose: holds custom-error-messages for database-querying and schema-related errors.
(Since I want my queries to check-in with schema to make sure its good)
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
# get path for environment so I can load it later



########################################################################################################################
### script-setup 2: library imports
# does this script even neeed any? lol



########################################################################################################################
### section 1: setup some classes and stuff

# let's declare an error type for schema registry
class SchemaError(Exception):
    """Raised when the database schema doesn't match what the query layer expects."""

# another one for filters
class FilterError(Exception):
    """Raised when a requested filter references an unknown table, column, or operator."""