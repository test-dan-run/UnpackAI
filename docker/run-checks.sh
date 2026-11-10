#!/bin/sh
# Run the page and documentation checks inside the checks container.
#
# Usage: docker compose --profile checks run --rm --build checks [dossier-id]
#
# First, the text check runs on the page and on every documentation file
# except the copied plain-writing skill, whose examples break the rules on
# purpose. Second, the browser check opens every tab of every dossier.
# Screenshots go to /shots, which compose.yaml maps to ./shots on the host.
# With a dossier id, only that dossier's tabs get screenshots.
set -eu
cd /app
find README.md AGENTS.md CLAUDE.md docs .claude/skills -name '*.md' \
  -not -path '.claude/skills/plain-writing/*' -print0 \
  | xargs -0 python3 src/server/unpackai_server/text_check.py src/web/index.html
if [ -d /shots ] && [ -w /shots ]; then
  node tests/web/check_dossiers.js /shots "$@"
else
  node tests/web/check_dossiers.js
fi
