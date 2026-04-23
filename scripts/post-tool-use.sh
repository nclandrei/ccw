#!/bin/bash
# PostToolUse hook — auto-runs project formatters/linters after Edit/Write.
# Configured in .claude/settings.json under hooks.PostToolUse.
#
# Claude Code sends a JSON payload on stdin, e.g.:
#   {"tool_name":"Edit","tool_input":{"file_path":"/abs/path/foo.py"}, ...}
# We read file_path, dispatch on extension, and exit 0 regardless so a
# missing or failing formatter never blocks the agent.
set -u

PAYLOAD="$(cat)"
FILE=""
if command -v jq &>/dev/null; then
  FILE="$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
fi

# No file_path (e.g. Bash tool) — nothing to format.
if [ -z "${FILE:-}" ] || [ ! -f "$FILE" ]; then
  exit 0
fi

case "$FILE" in
  *.py)
    if command -v ruff &>/dev/null; then
      ruff format "$FILE" >/dev/null 2>&1 || true
      ruff check --fix "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.go)
    if command -v gofmt &>/dev/null; then
      gofmt -w "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs|*.json|*.jsonc|*.md|*.mdx|*.css|*.scss|*.html|*.yaml|*.yml)
    if command -v prettier &>/dev/null; then
      prettier --write --log-level=silent "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
esac

exit 0
