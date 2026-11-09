"""Read the Claude API key from the operating system keychain.

The key lives in the OS keychain (macOS Keychain, Windows Credential Manager,
or the Linux Secret Service) under the service name "unpackai". The server
never reads the key from an environment variable, a file in the repository,
or a request header.

Store the key once with:

    python -m unpackai_server.set_key
"""
from __future__ import annotations

import keyring
from keyring.errors import KeyringError

SERVICE = "unpackai"
USERNAME = "anthropic_api_key"


class SecretStoreError(RuntimeError):
    """The key is missing or the keychain can't be reached.

    The message never contains the key.
    """


def read_api_key() -> str:
    try:
        key = keyring.get_password(SERVICE, USERNAME)
    except KeyringError as exc:
        raise SecretStoreError(
            f"The OS keychain can't be reached ({type(exc).__name__}). "
            "On Linux, install and unlock a Secret Service provider, e.g., GNOME Keyring."
        ) from None
    if not key:
        raise SecretStoreError(
            f"No API key is stored in the OS keychain under service '{SERVICE}'. "
            "Run: python -m unpackai_server.set_key"
        )
    return key.strip()


def key_is_configured() -> bool:
    try:
        return bool(keyring.get_password(SERVICE, USERNAME))
    except KeyringError:
        return False


def store_api_key(key: str) -> None:
    keyring.set_password(SERVICE, USERNAME, key.strip())
