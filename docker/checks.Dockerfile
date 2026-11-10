# syntax=docker/dockerfile:1
#
# The checks from the unpack skill: the plain-writing text check of the page
# and the documentation, and the browser check of every dossier tab. The Playwright image has Chromium and
# its system libraries, and the playwright package version must match it.

ARG PLAYWRIGHT_VERSION=1.63.0
ARG PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-noble
FROM ${PLAYWRIGHT_IMAGE}
ARG PLAYWRIGHT_VERSION
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN npm init -y >/dev/null && npm install --no-audit --no-fund "playwright@${PLAYWRIGHT_VERSION}"
ENV NODE_PATH=/app/node_modules
COPY docker/run-checks.sh /usr/local/bin/run-checks
COPY README.md AGENTS.md CLAUDE.md ./
COPY docs ./docs
COPY .claude/skills ./.claude/skills
COPY src/web ./src/web
COPY src/server/unpackai_server/text_check.py ./src/server/unpackai_server/text_check.py
COPY tests/web ./tests/web
USER pwuser
# Arguments after the service name go to the browser check, e.g., a dossier id.
ENTRYPOINT ["run-checks"]
