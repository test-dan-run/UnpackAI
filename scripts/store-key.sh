#!/usr/bin/env bash
# Store the Claude API key in the host keychain, for scripts/compose-up.sh.
#
# Usage: scripts/store-key.sh
#
# The keychain tool asks for the key itself and hides what you type, so the
# key isn't shown on screen, saved in the shell history, or passed as a
# command argument. scripts/compose-up.sh reads the entry with the same service
# and account names.
set -euo pipefail

SERVICE="unpackai"
ACCOUNT="anthropic_api_key"

if [[ "$(uname -s)" == "Darwin" ]] && command -v security >/dev/null; then
  # With -w as the last option and no value, security asks for the key twice.
  security add-generic-password -U -s "$SERVICE" -a "$ACCOUNT" -w
elif command -v secret-tool >/dev/null; then
  secret-tool store --label="UnpackAI Claude API key" service "$SERVICE" username "$ACCOUNT"
elif command -v python3 >/dev/null && python3 -c "import keyring" 2>/dev/null; then
  read -r -s -p "Claude API key (input is hidden): " key
  echo
  [[ -n "$key" ]] || { echo "No key entered. Nothing was stored." >&2; exit 1; }
  printf '%s' "$key" | python3 -c "import sys, keyring; keyring.set_password('$SERVICE', '$ACCOUNT', sys.stdin.read().strip())"
else
  echo "No keychain tool found. Install secret-tool (Linux) or the Python keyring package." >&2
  exit 1
fi
echo "Stored the key in the keychain under service '$SERVICE', account '$ACCOUNT'."
