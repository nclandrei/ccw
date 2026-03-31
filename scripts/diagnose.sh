#!/bin/bash
# Diagnostic script for Claude Code web environments.
# Verifies that all tools and frameworks installed by setup.sh are present
# and functional. Exit code 0 = all checks passed, 1 = some failed.
#
# Usage: bash scripts/diagnose.sh
set -uo pipefail

G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; B='\033[1m'; N='\033[0m'
PASS=0; WARN=0; FAIL=0

ok()   { echo -e "  ${G}ok${N}  $1"; ((PASS++)); }
warn() { echo -e "  ${Y}!!${N}  $1"; ((WARN++)); }
fail() { echo -e "  ${R}FAIL${N}  $1"; ((FAIL++)); }

_check() {
  local name="$1" cmd="${2:-$1}"
  if command -v "$cmd" &>/dev/null; then
    ok "$name: $($cmd --version 2>&1 | head -1)"
  else
    fail "$name: not installed"
  fi
}

_check_version() {
  local name="$1" cmd="$2" flag="${3:---version}"
  if command -v "$cmd" &>/dev/null; then
    ok "$name: $($cmd $flag 2>&1 | head -1)"
  else
    fail "$name: not installed"
  fi
}

echo -e "${B}Claude Code Web Environment Diagnostics${N}"
echo "========================================"
echo ""

# ── System ───────────────────────────────────────────────────────────────────
echo -e "${B}System${N}"
ok "OS: $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' || echo unknown)"
ok "CPU: $(nproc 2>/dev/null || echo ?) cores | RAM: $(free -h 2>/dev/null | awk '/Mem:/{print $2}' || echo ?) | Disk: $(df -h / 2>/dev/null | awk 'NR==2{print $4}' || echo ?) free"

echo ""
echo -e "${B}Cloud Environment${N}"
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && ok "CLAUDE_CODE_REMOTE=true" || warn "CLAUDE_CODE_REMOTE not set (expected in cloud)"
[ -n "${CLAUDE_ENV_FILE:-}" ] && ok "CLAUDE_ENV_FILE is set" || warn "CLAUDE_ENV_FILE not set"

# ── CLI Tools ────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}CLI Tools${N}"
_check git
_check gh
_check jq
_check curl
_check wget
_check tree
_check htop
_check ripgrep rg
_check "fd" fdfind

# ── Python ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}Python Ecosystem${N}"
_check_version "Python" python3
_check pip
_check uv
_check pytest
_check black
_check ruff
_check mypy

# ── Node.js ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}Node.js Ecosystem${N}"
_check_version "Node.js" node
_check npm
_check_version "TypeScript" tsc
_check jest
_check eslint
_check prettier

# Playwright needs special handling (npx)
if command -v npx &>/dev/null && npx playwright --version &>/dev/null 2>&1; then
  ok "Playwright: $(npx playwright --version 2>&1)"
else
  fail "Playwright: not installed"
fi

# ── Go ───────────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}Go${N}"
if command -v go &>/dev/null; then
  ok "Go: $(go version 2>&1)"
else
  fail "Go: not installed"
fi

# ── Rust ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}Rust Ecosystem${N}"
_check rustc
_check cargo
_check rustup

# ── Ruby ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}Ruby Ecosystem${N}"
_check ruby
_check gem
_check bundler

# ── Java ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}Java Ecosystem${N}"
if command -v java &>/dev/null; then
  ok "Java: $(JAVA_TOOL_OPTIONS= java -version 2>&1 | grep -v "Picked up" | head -1)"
else
  fail "Java: not installed"
fi
if command -v mvn &>/dev/null; then
  ok "Maven: $(JAVA_TOOL_OPTIONS= mvn --version 2>&1 | grep -v "Picked up" | head -1)"
else
  fail "Maven: not installed"
fi

# ── Setup Status ─────────────────────────────────────────────────────────────
echo ""
echo -e "${B}Setup Status${N}"
grep -q "claude-code-setup" /etc/environment 2>/dev/null && ok "setup.sh has run (marker present)" || warn "setup.sh marker not found in /etc/environment"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "${SCRIPT_DIR}/setup.sh" ] && ok "setup.sh exists" || fail "setup.sh missing"
[ -f "${SCRIPT_DIR}/session-start.sh" ] && ok "session-start.sh exists" || fail "session-start.sh missing"
SETTINGS="${SCRIPT_DIR}/../.claude/settings.json"
[ -f "$SETTINGS" ] && grep -q "SessionStart" "$SETTINGS" 2>/dev/null \
  && ok "SessionStart hook wired in settings.json" \
  || warn "SessionStart hook not configured"

# ── Verification Summary ─────────────────────────────────────────────────────
echo ""
echo "========================================"
echo -e "Results: ${G}${PASS} passed${N}, ${Y}${WARN} warnings${N}, ${R}${FAIL} failed${N}"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${G}All tools and frameworks are installed as expected.${N}"
  exit 0
else
  echo -e "${R}${FAIL} check(s) failed — see above for details.${N}"
  exit 1
fi
