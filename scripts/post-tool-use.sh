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
  *.rs)
    if command -v rustfmt &>/dev/null; then
      rustfmt --edition 2021 "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.zig)
    if command -v zig &>/dev/null; then
      zig fmt "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.ex|*.exs)
    if command -v mix &>/dev/null; then
      mix format "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.sh|*.bash)
    if command -v shfmt &>/dev/null; then
      shfmt -w "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.c|*.h|*.cc|*.cpp|*.cxx|*.hpp|*.hh|*.hxx|*.m|*.mm)
    if command -v clang-format &>/dev/null; then
      clang-format -i "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.rb)
    if command -v rubocop &>/dev/null; then
      rubocop -A "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.java)
    if command -v google-java-format &>/dev/null; then
      google-java-format -i "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.php)
    if command -v php-cs-fixer &>/dev/null; then
      php-cs-fixer fix --quiet "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.tf|*.tfvars)
    if command -v terraform &>/dev/null; then
      terraform fmt "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
  *.cs|*.csproj|*.fs|*.fsproj|*.vb|*.vbproj)
    if command -v csharpier &>/dev/null; then
      csharpier format "$FILE" >/dev/null 2>&1 \
        || csharpier "$FILE" >/dev/null 2>&1 || true
    elif command -v dotnet &>/dev/null; then
      dotnet format whitespace --include "$FILE" --no-restore >/dev/null 2>&1 || true
    fi
    ;;
  *.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs|*.json|*.jsonc|*.md|*.mdx|*.css|*.scss|*.html|*.yaml|*.yml)
    if command -v prettier &>/dev/null; then
      prettier --write --log-level=silent "$FILE" >/dev/null 2>&1 || true
    elif command -v deno &>/dev/null; then
      deno fmt --quiet "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
esac

exit 0
