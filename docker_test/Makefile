# 1. Pull from the public .env file located one folder higher up
# note: the "secret" environment file is just called ".env",
# while the public one is called "config.env"
include ../config.env

# 2. Start the containers - note: last piece is just in case lol, I had some orphaned containers at one point
up:
	docker compose --env-file ../config.env --env-file $(SECRET_ENV_FILE) up -d --remove-orphans

# 3. Stop the containers
down:
	docker compose --env-file ../config.env --env-file $(SECRET_ENV_FILE) down --remove-orphans