# ADR 006: Pass the API key to the server as a Docker secret from the host keychain

Status: Accepted. It replaces the first design, in which the server read the OS keychain directly.

Date: 2026-11-09

## Context

The user asked for the server to read the API key from a secret store, and they chose the OS keychain. They then asked for every part of the project to run in Docker. A container can't read the host keychain.

## Options

1. Pass the key as an environment variable of the container
2. Use a Compose secret from a file on the host
3. Use a Compose secret from a variable that a host script fills from the keychain for one command

## Decision

`scripts/compose-up.sh` reads the key from the host keychain and passes it to Docker Compose in a variable that only the `docker compose` process can see. Compose copies the value into the container as `/run/secrets/anthropic_api_key`, and the server reads only that file.

## Consequences

- The key isn't written to a file on the host, and it isn't set as a variable in the container or shown by `docker inspect`.
- Compose refuses a secret from a variable in a container with a read-only root filesystem, so the `app` container's root filesystem is writable. The container still drops every capability and runs as a user without root rights.
- The secret file is readable by every user in the container, because Compose sets its owner and mode only in Swarm mode.
- Storing the key needs a keychain tool on the host, e.g., `security` on macOS or `secret-tool` on Linux.
