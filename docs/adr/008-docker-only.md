# ADR 008: Run every part of the project in Docker

Status: Accepted

Date: 2026-11-10

## Context

The user asked for the project to run in containers so it's portable. At first the server could also run in a virtual environment on the host, so the repository had two setups. The user then asked for a cleaner repository with only the Docker setup.

## Options

1. Keep both the Docker setup and the setup on the host
2. Keep only the Docker setup

## Decision

The `app`, `test`, and `checks` containers in `compose.yaml` run the server, the server tests, and the page checks. The project has no setup outside a container.

## Consequences

- The host needs only Docker with Compose, a keychain tool, and a shell for the two scripts.
- The images copy the code at build time, so the `test` and `checks` commands use `--build` to check the latest changes.
- A network that inspects TLS traffic needs base images that trust its certificate, and the Dockerfiles take them as build arguments.
