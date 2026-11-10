#!/bin/sh
# Run the page checks from the unpack skill inside the checks container.
#
# Usage: docker compose --profile checks run --rm checks [dossier-id]
#
# Screenshots go to /shots, which compose.yaml maps to ./shots on the host.
# With a dossier id, only that dossier's tabs get screenshots.
set -eu
cd /app
python3 .claude/skills/unpack/scripts/check_text.py \
  index.html README.md CLAUDE.md server/README.md .claude/skills/unpack/SKILL.md
if [ -d /shots ] && [ -w /shots ]; then
  node .claude/skills/unpack/scripts/check_dossiers.js /shots "$@"
else
  node .claude/skills/unpack/scripts/check_dossiers.js
fi
