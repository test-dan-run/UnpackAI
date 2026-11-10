# ADR 007: Keep the API key and request headers out of the logs

Status: Accepted

Date: 2026-11-09

## Context

The user asked for no logs of request headers that carry a key. The Anthropic SDK sends the key in the `Authorization` header. At DEBUG level, the SDK logs the full request options and the response headers.

## Options

1. Rely on the libraries' default log levels
2. Cap the library loggers, write a request log without headers, and redact secrets in every log handler

## Decision

The server caps the SDK and HTTP client loggers at WARNING, and it removes `ANTHROPIC_LOG` from its environment. Its own request log writes only the method, the path, the status code, and the time taken. A filter on every log handler replaces the key and any `Authorization` or `x-api-key` value with `[REDACTED]`.

## Consequences

- No log line has a header, a query string, or a body, so the logs can't show a key that a user puts in a URL.
- The uvicorn access log is off, because the server writes its own request log.
- A test runs a full unpack with debug logging and checks every log line and API response for the key, so a change that leaks the key fails the tests.
