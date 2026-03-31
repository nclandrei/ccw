#!/bin/bash
# Cloud environment setup script for Claude Code web environments.
# Automatically invoked by session-start.sh if the setup marker is missing.
# Can also be pasted into the "Setup script" field in Claude Code environment
# settings at claude.ai/code for faster cold starts (runs before session-start).
#
# Runs as root on Ubuntu 24.04. Idempotent — safe to run multiple times.
#
# Installs a comprehensive development environment:
#   System:  jq, curl, wget, httpie, build-essential, tree, htop, ripgrep, fd, bat
#   CLI:     gh
#   Python:  uv, pytest, black, ruff, mypy
#   Node.js: typescript, jest, eslint, prettier, playwright
#   Go:      latest stable
#   Rust:    stable toolchain via rustup
#   Ruby:    bundler
#   Java:    Maven
set -euo pipefail

SETUP_START=$(date +%s)
echo "=== Cloud environment setup ($(date -Iseconds)) ==="

_installed() { command -v "$1" &>/dev/null; }
_timer() {
  local label="$1" start="$2"
  echo "  done: ${label} ($(( $(date +%s) - start ))s)"
}

# ── Discover pre-installed runtime paths ─────────────────────────────────────
# The base image ships Node.js, Ruby (rbenv), etc. in non-standard paths.
# Discover them so _installed checks and the summary work correctly.
for d in /opt/node*/bin /opt/rbenv/versions/*/bin /opt/rbenv/shims; do
  [ -d "$d" ] && export PATH="$d:$PATH"
done

# ── System packages ──────────────────────────────────────────────────────────
t=$(date +%s)
echo "Installing system packages..."
apt-get update -qq

apt-get install -y -qq --no-install-recommends \
  jq curl wget httpie build-essential pkg-config libssl-dev \
  tree htop ripgrep fd-find bat \
  maven \
  2>/dev/null || true

apt-get clean
_timer "System packages" "$t"

# ── gh CLI ───────────────────────────────────────────────────────────────────
if ! _installed gh; then
  t=$(date +%s)
  echo "Installing gh CLI..."
  GH_VERSION="2.74.1"
  curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.deb" \
    -o /tmp/gh.deb && dpkg -i /tmp/gh.deb && rm -f /tmp/gh.deb \
    || apt-get install -y -qq gh 2>/dev/null \
    || echo "  Warning: gh CLI installation failed (non-fatal)"
  _timer "gh CLI" "$t"
fi

# ── uv (fast Python package manager) ────────────────────────────────────────
if ! _installed uv; then
  t=$(date +%s)
  echo "Installing uv..."
  curl -fsSL https://astral.sh/uv/install.sh | sh 2>/dev/null || true
  _timer "uv" "$t"
fi

export PATH="/root/.local/bin:$PATH"

# ── Python tools ─────────────────────────────────────────────────────────────
t=$(date +%s)
echo "Installing Python tools (pytest, black, ruff, mypy)..."
if _installed uv; then
  uv tool install pytest       2>/dev/null || true
  uv tool install black        2>/dev/null || true
  uv tool install ruff         2>/dev/null || true
  uv tool install mypy         2>/dev/null || true
else
  pip install --quiet pytest black ruff mypy 2>/dev/null || true
fi
_timer "Python tools" "$t"

# ── Node.js tools ────────────────────────────────────────────────────────────
t=$(date +%s)
echo "Installing Node.js tools (typescript, jest, eslint, prettier, playwright)..."
if _installed npm; then
  npm install -g --silent \
    typescript \
    jest \
    eslint \
    prettier \
    playwright \
    2>/dev/null || true
  # Install Playwright browser binaries (Chromium only to save time/space)
  if ! npx playwright install --check chromium &>/dev/null; then
    npx --yes playwright install --with-deps chromium 2>/dev/null || true
  fi
fi
_timer "Node.js tools" "$t"

# ── Go ───────────────────────────────────────────────────────────────────────
if ! _installed go; then
  t=$(date +%s)
  echo "Installing Go..."
  GO_VERSION="1.23.4"
  curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" \
    | tar -C /usr/local -xz 2>/dev/null \
    || echo "  Warning: Go installation failed (non-fatal)"
  _timer "Go" "$t"
fi
export PATH="/usr/local/go/bin:$PATH"

# ── Rust ─────────────────────────────────────────────────────────────────────
if ! _installed rustc; then
  t=$(date +%s)
  echo "Installing Rust (stable)..."
  curl -fsSL https://sh.rustup.rs | sh -s -- -y --default-toolchain stable 2>/dev/null || true
  _timer "Rust" "$t"
fi
export PATH="/root/.cargo/bin:$PATH"

# ── Ruby bundler ─────────────────────────────────────────────────────────────
if _installed gem && ! _installed bundler; then
  t=$(date +%s)
  echo "Installing Ruby Bundler..."
  gem install bundler --silent 2>/dev/null || true
  _timer "Ruby Bundler" "$t"
fi

# ── Persist environment variables ────────────────────────────────────────────
MARKER="# === claude-code-setup ==="
if ! grep -q "$MARKER" /etc/environment 2>/dev/null; then
  cat >> /etc/environment <<ENVEOF
${MARKER}
PATH="/usr/local/go/bin:/root/.cargo/bin:/root/.local/bin:\${PATH}"
ENVEOF
fi

# ── Summary ──────────────────────────────────────────────────────────────────
ELAPSED=$(( $(date +%s) - SETUP_START ))
echo ""
echo "=== Setup complete (${ELAPSED}s) ==="
echo ""
echo "Installed tools:"
printf "  %-12s %s\n" "Python:" "$(python3 --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "uv:" "$(uv --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "pytest:" "$(pytest --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "black:" "$(black --version 2>/dev/null | head -1 || echo 'not found')"
printf "  %-12s %s\n" "ruff:" "$(ruff --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "mypy:" "$(mypy --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Node.js:" "$(node --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "npm:" "$(npm --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "TypeScript:" "$(tsc --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Jest:" "$(jest --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "ESLint:" "$(eslint --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Prettier:" "$(prettier --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Playwright:" "$(npx playwright --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Go:" "$(go version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Rust:" "$(rustc --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Cargo:" "$(cargo --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Ruby:" "$(ruby --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Bundler:" "$(bundler --version 2>/dev/null || echo 'not found')"
printf "  %-12s %s\n" "Java:" "$(JAVA_TOOL_OPTIONS= java -version 2>&1 | grep -v 'Picked up' | head -1 || echo 'not found')"
printf "  %-12s %s\n" "Maven:" "$(JAVA_TOOL_OPTIONS= mvn --version 2>&1 | grep -v 'Picked up' | head -1 || echo 'not found')"
printf "  %-12s %s\n" "gh:" "$(gh --version 2>/dev/null | head -1 || echo 'not found')"
