# syntax=docker/dockerfile:1
#
# The page checks from the unpack skill: the plain-writing text check and the
# browser check of every dossier tab. The Playwright image has Chromium and
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
COPY index.html README.md CLAUDE.md ./
COPY .claude/skills ./.claude/skills
COPY server/README.md ./server/README.md
USER pwuser
CMD ["run-checks"]
