#!/usr/bin/with-contenv bashio
set -euo pipefail

export RUST_BACKTRACE=full
export RUST_LOG_STYLE=always
export XDG_CACHE_HOME=/data

# Prefer MQTT details from the Home Assistant MQTT integration when available
if bashio::services.available mqtt; then
  export RYOBI_MQTT_HOST="$(bashio::services mqtt 'host')"
  export RYOBI_MQTT_PORT="$(bashio::services mqtt 'port')"
  export RYOBI_MQTT_USER="$(bashio::services mqtt 'username')"
  export RYOBI_MQTT_PASSWORD="$(bashio::services mqtt 'password')"
fi

# Override with explicit add-on configuration if provided
if bashio::config.has_value mqtt_host; then
  export RYOBI_MQTT_HOST="$(bashio::config mqtt_host)"
fi

if bashio::config.has_value mqtt_port; then
  export RYOBI_MQTT_PORT="$(bashio::config mqtt_port)"
fi

if bashio::config.has_value mqtt_username; then
  export RYOBI_MQTT_USER="$(bashio::config mqtt_username)"
fi

if bashio::config.has_value mqtt_password; then
  export RYOBI_MQTT_PASSWORD="$(bashio::config mqtt_password)"
fi

if bashio::config.has_value log_level; then
  export RYOBI_LOG_LEVEL="$(bashio::config log_level)"
fi

if bashio::config.has_value ryobi_email; then
  export RYOBI_EMAIL="$(bashio::config ryobi_email)"
fi

if bashio::config.has_value ryobi_password; then
  export RYOBI_PASSWORD="$(bashio::config ryobi_password)"
fi

export RYOBI_LOG_LEVEL="${RYOBI_LOG_LEVEL:-INFO}"
export RYOBI_MQTT_PORT="${RYOBI_MQTT_PORT:-1883}"

if [[ -z "${RYOBI_EMAIL:-}" ]]; then
  bashio::exit.nok "ryobi_email is required"
fi

if [[ -z "${RYOBI_PASSWORD:-}" ]]; then
  bashio::exit.nok "ryobi_password is required"
fi

if [[ -z "${RYOBI_MQTT_HOST:-}" ]]; then
  bashio::exit.nok "mqtt_host is required (or configure the MQTT integration in Home Assistant)"
fi

bashio::log.info "Starting Ryobi GDO to MQTT bridge"
env | grep RYOBI_ | grep -v PASSWORD | sed 's/^/  /'

cd /app
exec uv run ryobi-gdo-2-mqtt
