"""Store the Claude API key in the OS keychain.

Usage: python -m unpackai_server.set_key

The key is read with getpass, so it isn't echoed to the terminal or saved in
the shell history.
"""
import getpass
import sys

from .secret_store import SERVICE, USERNAME, store_api_key


def main() -> int:
    key = getpass.getpass("Claude API key (input is hidden): ")
    if not key.strip():
        print("No key entered. Nothing was stored.", file=sys.stderr)
        return 1
    store_api_key(key)
    print(f"Stored the key in the OS keychain under service '{SERVICE}', account '{USERNAME}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
