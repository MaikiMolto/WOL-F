#!/bin/bash

echo "Launching GPTWOL..."

#Launch Cron
cron

# Optional built-in HTTPS (for setups without a reverse proxy). Self-signed cert
# is auto-generated in the persistent /app/db volume if none is provided.
SSL_ARGS=""
if [ "$(echo "${ENABLE_HTTPS:-false}" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
  CERT="${SSL_CERT:-/app/db/wol-f-cert.pem}"
  KEY="${SSL_KEY:-/app/db/wol-f-key.pem}"
  if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "ENABLE_HTTPS: generating self-signed certificate at $CERT"
    mkdir -p "$(dirname "$CERT")"
    openssl req -x509 -newkey rsa:2048 -nodes -keyout "$KEY" -out "$CERT" -days 3650 -subj "/CN=wol-f" >/dev/null 2>&1
  fi
  SSL_ARGS="--certfile=$CERT --keyfile=$KEY"
  echo "ENABLE_HTTPS: serving HTTPS on $IP:$PORT"
fi

# Launch application
cd /app
GUNICORN_CMD_ARGS="--bind=$IP:$PORT --workers=${GUNICORN_WORKERS:-3} --threads=${GUNICORN_THREADS:-2} --timeout=${GUNICORN_TIMEOUT:-60} --graceful-timeout=30 $SSL_ARGS" gunicorn --access-logfile - wol:app
