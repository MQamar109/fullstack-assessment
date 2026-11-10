#!/usr/bin/env bash
# Render build step: install dependencies, collect static files, migrate.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
