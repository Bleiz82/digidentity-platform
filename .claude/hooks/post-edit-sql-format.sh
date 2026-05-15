#!/usr/bin/env bash
# .claude/hooks/post-edit-sql-format.sh
#
# Post-edit hook: format SQL files modified by Claude Code via sqlfluff.
# Runs on save / after edit, keeps SQL style consistent across migrations and Pack schemas.

set -euo pipefail

# Argument: file path that was just edited
FILE="${1:-}"

if [[ -z "$FILE" ]]; then
    exit 0
fi

# Only act on .sql files
if [[ "$FILE" != *.sql ]]; then
    exit 0
fi

# Require sqlfluff in PATH
if ! command -v sqlfluff >/dev/null 2>&1; then
    echo "Warning: sqlfluff not installed, skipping SQL format hook for $FILE"
    echo "Install: pip install sqlfluff"
    exit 0
fi

# Format in-place with the project's dialect (Postgres)
sqlfluff format --dialect postgres "$FILE"

# Lint and report (non-blocking; surfaces issues without aborting the edit)
if ! sqlfluff lint --dialect postgres "$FILE"; then
    echo ""
    echo "sqlfluff reported lint issues in $FILE (non-blocking)."
    echo "Run: sqlfluff fix --dialect postgres $FILE"
fi

exit 0
