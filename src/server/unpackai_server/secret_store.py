"""Read the Claude API key from the Docker secret.

Docker mounts the secret into the container as the read-only file
/run/secrets/anthropic_api_key, and scripts/compose-up.sh passes the key from
the host keychain to Compose. The server never reads the key from an
environment variable, a file in the repository, or a request header.
UNPACKAI_SECRET_FILE only changes where to look, e.g., in the tests, and it
never holds the key.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_SECRET_FILE = "/run/secrets/anthropic_api_key"


class SecretStoreError(RuntimeError):
    """The key is missing or the secret can't be read.

    The message never contains the key.
    """


def secret_file() -> Path:
    return Path(os.environ.get("UNPACKAI_SECRET_FILE", DEFAULT_SECRET_FILE))


def read_api_key() -> str:
    path = secret_file()
    try:
        key = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        key = ""
    except OSError as exc:
        raise SecretStoreError(f"The Docker secret at {path} can't be read ({type(exc).__name__}).") from None
    if not key:
        raise SecretStoreError(
            f"The Docker secret at {path} is missing or empty. "
            "Start the containers with scripts/compose-up.sh, which passes the key from your keychain."
        )
    return key


def key_is_configured() -> bool:
    try:
        return bool(read_api_key())
    except SecretStoreError:
        return False
