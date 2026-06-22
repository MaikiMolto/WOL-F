#!/bin/bash

echo "Launching GPTWOL..."

#Launch Cron
cron

# Launch application
cd /app
GUNICORN_CMD_ARGS="--bind=$IP:$PORT --workers=${GUNICORN_WORKERS:-3} --threads=${GUNICORN_THREADS:-2} --timeout=${GUNICORN_TIMEOUT:-60} --graceful-timeout=30" gunicorn --access-logfile - wol:app
