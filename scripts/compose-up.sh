#!/usr/bin/env bash
# Start the UnpackAI server container with the API key from the host keychain.
#
# Usage: scripts/compose-up.sh [extra docker compose up options]
#
# The script reads the key from the keychain and passes it to Docker Compose
# in a variable that only the docker compose process can see. Compose turns
# it into the Docker secret /run/secrets/anthropic_api_key. The key isn't
# written to a file, and it isn't set as a variable inside the container.
set -euo pipefail

SERVICE="unpackai"
ACCOUNT="anthropic_api_key"

read_key() {
  if [[ "$(uname -s)" == "Darwin" ]] && command -v security >/dev/null; then
    security find-generic-password -s "$SERVICE" -a "$ACCOUNT" -w 2>/dev/null && return
  fi
  if command -v secret-tool >/dev/null; then
    secret-tool lookup service "$SERVICE" username "$ACCOUNT" 2>/dev/null && return
  fi
  if command -v python3 >/dev/null && python3 -c "import keyring" 2>/dev/null; then
    python3 -m keyring get "$SERVICE" "$ACCOUNT" 2>/dev/null && return
  fi
  return 1
}

if ! key="$(read_key)" || [[ -z "$key" ]]; then
  echo "No API key found in the keychain under service '$SERVICE', account '$ACCOUNT'." >&2
  echo "Store it first with scripts/store-key.sh." >&2
  exit 1
fi

cd "$(dirname "$0")/.."
UNPACKAI_ANTHROPIC_API_KEY="$key" exec docker compose up -d --build "$@" app
