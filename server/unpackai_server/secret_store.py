"""Read the Claude API key from a secret store.

There are two secret stores, and UNPACKAI_SECRET_SOURCE picks one:

- "keychain" (the default) reads the OS keychain: macOS Keychain, Windows
  Credential Manager, or the Linux Secret Service. Use it when the server runs
  directly on your computer. Store the key with:

      python -m unpackai_server.set_key

- "docker-secret" reads the Docker secret at /run/secrets/anthropic_api_key.
  Use it when the server runs in a container. Docker mounts the secret into
  the container as a read-only file, and compose.yaml sets this source.

The server never reads the key from an environment variable, a file in the
repository, or a request header. UNPACKAI_SECRET_SOURCE and
UNPACKAI_SECRET_FILE only choose where to look, and they never hold the key.
"""
from __future__ import annotations

import os
from pathlib import Path

SERVICE = "unpackai"
USERNAME = "anthropic_api_key"
DEFAULT_SECRET_FILE = "/run/secrets/anthropic_api_key"
SOURCES = ("keychain", "docker-secret")


class SecretStoreError(RuntimeError):
    """The key is missing or the secret store can't be reached.

    The message never contains the key.
    """


def source() -> str:
    value = os.environ.get("UNPACKAI_SECRET_SOURCE", "keychain").strip().lower()
    if value not in SOURCES:
        raise SecretStoreError(f"UNPACKAI_SECRET_SOURCE must be one of {', '.join(SOURCES)}.")
    return value


def _secret_file() -> Path:
    return Path(os.environ.get("UNPACKAI_SECRET_FILE", DEFAULT_SECRET_FILE))


def _read_keychain() -> str | None:
    import keyring
    from keyring.errors import KeyringError

    try:
        return keyring.get_password(SERVICE, USERNAME)
    except KeyringError as exc:
        raise SecretStoreError(
            f"The OS keychain can't be reached ({type(exc).__name__}). "
            "On Linux, install and unlock a Secret Service provider, e.g., GNOME Keyring."
        ) from None


def _read_docker_secret() -> str | None:
    path = _secret_file()
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SecretStoreError(f"The Docker secret at {path} can't be read ({type(exc).__name__}).") from None


def read_api_key() -> str:
    src = source()
    key = (_read_keychain() if src == "keychain" else _read_docker_secret()) or ""
    key = key.strip()
    if key:
        return key
    if src == "keychain":
        raise SecretStoreError(
            f"No API key is stored in the OS keychain under service '{SERVICE}'. "
            "Run: python -m unpackai_server.set_key"
        )
    raise SecretStoreError(
        f"The Docker secret at {_secret_file()} is missing or empty. "
        "Start the containers with scripts/compose-up.sh, which passes the key from your keychain."
    )


def key_is_configured() -> bool:
    try:
        return bool(read_api_key())
    except SecretStoreError:
        return False


def store_api_key(key: str) -> None:
    import keyring

    keyring.set_password(SERVICE, USERNAME, key.strip())
