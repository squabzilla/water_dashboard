########################################################################################################################
# file name: helper_PSQL.py
# author: William Hovdestad
#
# The purpose of this file is for standardized "constant" variables for my PSQL postgis table names.
# That way, I can ensure consistency in the use of table names across all the various Python files.

# TODO:
# need to modify .env file so `postgres_host`, `post_gres_port` and `database_name` aren't hardcoded
# - see line 196 at `class DBConfig(BaseSettings):`
# note from Claude about this:
"""
One thing worth reconsidering: postgres_host, postgres_port, and database_name are hardcoded as class defaults rather than pulled from .env.
That's fine for now since your DB is local, but you've mentioned a DigitalOcean droplet as your deployment target for this project - 
once you deploy, the host almost certainly won't be localhost and the port likely won't be 5433 (no native/containerized conflict to dodge on a droplet).
Hardcoding those means editing the Python file itself between dev and prod, which is exactly the problem pydantic-settings is meant to avoid.
Worth moving POSTGRES_HOST, POSTGRES_PORT, and DATABASE_NAME into .env too (keeping the current values only as fallback defaults) once you're closer to deploying.
"""

# TODO:
# Clean up this file lol

########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets great-grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
#from dotenv import load_dotenv # used for loading environment variables
#from dataclasses import dataclass # for making immutable classes, used for my CONFIG variables (user, login, API, etc.)

import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import create_engine # stuff needed to connect with postgis database
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, Engine

# setup environment directory which contains the `.env` file
env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")



########################################################################################################################
### section 1: variables related to sql-connection


class DBConfig(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, env_file=env_dir)
    postgres_user: str
    postgres_password: SecretStr
    api_key: SecretStr
    api_secret_key: SecretStr
    app_token: SecretStr
    postgres_host: str = "localhost"
    postgres_port: int = 5433 # using 5433 instead of 5432 so I don't get port conflict on local machine from native vs containerized PSQL install
    database_name: str = "calgary_watermains"

DATABASE_CONFIG = DBConfig()


def default_SQL_engine(config: DBConfig = DATABASE_CONFIG) -> Engine:
    url = URL.create(
        drivername="postgresql+psycopg",
        username=config.postgres_user,
        password=config.postgres_password.get_secret_value(),
        host=config.postgres_host,
        port=config.postgres_port,
        database=config.database_name,
    )
    engine = create_engine(url)
    return engine

"""
load_dotenv(env_dir) # get my environment variables

# setup config class
@dataclass(frozen=True) # set up unchanging, constants dataclass for these variables
class Config: # this is a custom class, I could name it whatever I want lol
    postgres_user: str
    postgres_password: str
    api_key: str
    api_secret_key: str
    app_token: str
    postgres_host: str
    postgres_port: int
    database_name: str

# initialize CONFIG variable of type `Config` class
CONFIG = Config(
    postgres_user = os.environ["POSTGRES_USER"], # NOTE: using `os.environ[]` means it'll crash if not found
    postgres_password = os.environ["POSTGRES_PASSWORD"], # `os.getenv()` would just return `None` if not found
    api_key = os.environ["API_KEY"],
    api_secret_key = os.environ["API_SECRET_KEY"],
    app_token = os.environ["APP_TOKEN"],
    postgres_host = "localhost",
    postgres_port = 5433, # using 5433 instead of 5432 so I don't get port conflict on local machine from native vs containerized PSQL install
    database_name = "calgary_watermains",
)

# set default text value for sqlalchemy engine initialization
ENGINE_TEXT = f"postgresql+psycopg://{CONFIG.postgres_user}:{CONFIG.postgres_password}@{CONFIG.postgres_host}:{CONFIG.postgres_port}/{CONFIG.database_name}"


# function to create engine
# doing as function instead of creating actual engine here as constant variable, 
# so errors with connection are found around query time, and so I don't initialize connection
# in scripts importing this module, that don't actually need the connection
# while none of this is relevant for my use-case, it's good to be aware of
def default_SQL_engine(text = ENGINE_TEXT):
    engine = create_engine(text)
    return engine
"""

var_n = 1 # 'useless' code so python doesn't do weird stuff with triple-quoted-text-block lol