"""Shell script section generators for setup.sh, session-start.sh, and diagnose.sh."""

from __future__ import annotations

# ── setup.sh sections ────────────────────────────────────────────────────────


def setup_header() -> str:
    return """\
#!/bin/bash
# Cloud environment setup script for Claude Code web environments.
# Automatically invoked by session-start.sh if the setup marker is missing.
# Can also be pasted into the "Setup script" field in Claude Code environment
# settings at claude.ai/code for faster cold starts (runs before session-start).
#
# Runs as root on Ubuntu 24.04. Idempotent — safe to run multiple times.
set -euo pipefail

SETUP_START=$(date +%s)
echo "=== Cloud environment setup ($(date -Iseconds)) ==="

_installed() { command -v "$1" &>/dev/null; }
_timer() {
  local label="$1" start="$2"
  echo "  done: ${label} ($(( $(date +%s) - start ))s)"
}
"""


def setup_system_packages() -> str:
    return """\
# ── System packages ──────────────────────────────────────────────────────────
t=$(date +%s)
echo "Installing system packages..."
apt-get update -qq

apt-get install -y -qq --no-install-recommends \\
  jq curl wget httpie sqlite3 build-essential \\
  tree htop ripgrep fd-find bat \\
  2>/dev/null || true

apt-get clean
_timer "System packages" "$t"
"""


def setup_browser_deps() -> str:
    return """\
# ── Browser dependencies ────────────────────────────────────────────────────
t=$(date +%s)
echo "Installing browser dependencies..."
apt-get update -qq
apt-get install -y -qq --no-install-recommends \\
  fonts-liberation libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 \\
  libxdamage1 libxrandr2 libgbm1 libasound2t64 libpango-1.0-0 libcairo2 \\
  libcups2 libxss1 libgtk-3-0 libxshmfence1 xvfb \\
  2>/dev/null || true
apt-get clean
_timer "Browser deps" "$t"
"""


def setup_chromium() -> str:
    return """\
# ── Chromium via Playwright ──────────────────────────────────────────────────
t=$(date +%s)
PLAYWRIGHT_CHROMIUM=$(find /root/.cache/ms-playwright -name "chrome" -path "*/chrome-linux/chrome" 2>/dev/null | head -1)
if [ -z "$PLAYWRIGHT_CHROMIUM" ]; then
  echo "Installing Playwright Chromium..."
  npx playwright install --with-deps chromium 2>/dev/null || true
  PLAYWRIGHT_CHROMIUM=$(find /root/.cache/ms-playwright -name "chrome" -path "*/chrome-linux/chrome" 2>/dev/null | head -1)
else
  echo "Playwright Chromium already installed"
fi
if [ -z "$PLAYWRIGHT_CHROMIUM" ]; then
  PLAYWRIGHT_CHROMIUM=$(find /root/.cache/ms-playwright -name "headless_shell" -path "*/chrome-linux/headless_shell" 2>/dev/null | head -1)
fi

# Move mismatched pre-installed chromedriver aside
for p in /opt/node22/bin/chromedriver /opt/node20/bin/chromedriver; do
  [ -f "$p" ] && [ ! -f "${p}.orig" ] && mv "$p" "${p}.orig"
done
_timer "Chromium" "$t"
"""


def setup_gh() -> str:
    return """\
# ── gh CLI ───────────────────────────────────────────────────────────────────
if ! _installed gh; then
  t=$(date +%s)
  echo "Installing gh CLI..."
  GH_VERSION="2.74.1"
  curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.deb" \\
    -o /tmp/gh.deb && dpkg -i /tmp/gh.deb && rm -f /tmp/gh.deb \\
    || apt-get install -y -qq gh 2>/dev/null \\
    || echo "  Warning: gh CLI installation failed (non-fatal)"
  _timer "gh CLI" "$t"
fi
"""


def setup_go() -> str:
    return """\
# ── Go ───────────────────────────────────────────────────────────────────────
if ! _installed go; then
  t=$(date +%s)
  GO_VERSION="1.24.7"
  echo "Installing Go ${GO_VERSION}..."
  curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" \\
    | tar -C /usr/local -xzf -
  ln -sf /usr/local/go/bin/go   /usr/local/bin/go
  ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt
  _timer "Go ${GO_VERSION}" "$t"
fi
"""


def setup_rust() -> str:
    return """\
# ── Rust ─────────────────────────────────────────────────────────────────────
if ! _installed rustc; then
  t=$(date +%s)
  echo "Installing Rust..."
  curl -fsSL https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal 2>/dev/null || true
  [ -f /root/.cargo/env ] && source /root/.cargo/env
  _timer "Rust" "$t"
fi
"""


def setup_uv() -> str:
    return """\
# ── uv (fast Python package manager) ────────────────────────────────────────
if ! _installed uv; then
  t=$(date +%s)
  echo "Installing uv..."
  curl -fsSL https://astral.sh/uv/install.sh | sh 2>/dev/null || true
  _timer "uv" "$t"
fi
"""


def setup_node_managers(extras: set[str]) -> str:
    parts = [
        '# ── Node.js package managers ────────────────────────────────────────────────',
        't=$(date +%s)',
        'NPM_GLOBAL_BIN="$(npm config get prefix 2>/dev/null)/bin"',
    ]
    if "pnpm" in extras:
        parts.append('_installed pnpm || npm install -g pnpm 2>/dev/null || true')
    if "yarn" in extras:
        parts.append('_installed yarn || npm install -g yarn 2>/dev/null || true')

    bins = []
    if "pnpm" in extras:
        bins.extend(["pnpm", "pnpx"])
    if "yarn" in extras:
        bins.extend(["yarn", "yarnpkg"])

    if bins:
        bin_list = " ".join(bins)
        parts.append(f'for bin in {bin_list}; do')
        parts.append('  [ -f "${NPM_GLOBAL_BIN}/${bin}" ] && [ ! -e "/usr/local/bin/${bin}" ] \\')
        parts.append('    && ln -sf "${NPM_GLOBAL_BIN}/${bin}" "/usr/local/bin/${bin}"')
        parts.append("done")

    parts.append('_timer "JS package managers" "$t"')
    return "\n".join(parts) + "\n"


def setup_env_block(toolchains: set[str], extras: set[str]) -> str:
    lines = [
        '# ── Persist environment variables ────────────────────────────────────────────',
        'MARKER="# === claude-code-setup ==="',
        'if ! grep -q "$MARKER" /etc/environment 2>/dev/null; then',
        '  cat >> /etc/environment <<ENVEOF',
        '${MARKER}',
    ]
    if "browser" in extras:
        lines.extend([
            'PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=${PLAYWRIGHT_CHROMIUM:-}',
            'PUPPETEER_EXECUTABLE_PATH=${PLAYWRIGHT_CHROMIUM:-}',
            'PUPPETEER_SKIP_DOWNLOAD=true',
            'CHROME_BIN=${PLAYWRIGHT_CHROMIUM:-}',
        ])
    if "go" in toolchains:
        lines.append('GOPATH=/root/go')
    lines.append('ENVEOF')

    # PATH construction
    path_parts = []
    if "rust" in toolchains:
        path_parts.append("/root/.cargo/bin")
    if "uv" in extras:
        path_parts.append("/root/.local/bin")
    if "go" in toolchains:
        path_parts.extend(["/usr/local/go/bin", "/root/go/bin"])

    if path_parts:
        path_str = ":".join(path_parts)
        lines.append(f'  echo \'PATH="{path_str}:${{PATH}}"\' >> /etc/environment')

    lines.extend(['fi', ''])

    # Export for current script context
    if "go" in toolchains:
        lines.append('export GOPATH=/root/go')
    if path_parts:
        path_str = ":".join(path_parts)
        lines.append(f'export PATH="{path_str}:$PATH"')

    return "\n".join(lines) + "\n"


def setup_summary(toolchains: set[str], extras: set[str]) -> str:
    lines = [
        '',
        '# ── Summary ──────────────────────────────────────────────────────────────────',
        'ELAPSED=$(( $(date +%s) - SETUP_START ))',
        'echo ""',
        'echo "=== Setup complete (${ELAPSED}s) ==="',
    ]

    checks: list[tuple[str, str]] = []
    if "node" in toolchains:
        checks.extend([
            ("Node", "node --version"),
            ("npm", "npm --version"),
        ])
        if "pnpm" in extras:
            checks.append(("pnpm", "pnpm --version"))
        if "yarn" in extras:
            checks.append(("yarn", "yarn --version"))
        if "bun" in extras:
            checks.append(("bun", "bun --version"))
    if "python" in toolchains:
        checks.append(("Python", "python3 --version"))
        if "uv" in extras:
            checks.append(("uv", "uv --version"))
    if "go" in toolchains:
        checks.append(("Go", "go version"))
    if "rust" in toolchains:
        checks.append(("Rust", "rustc --version"))
    if "ruby" in toolchains:
        checks.append(("Ruby", "ruby --version"))
    if "java" in toolchains:
        checks.append(("Java", "java -version 2>&1 | head -1"))
    if "gh" in extras:
        checks.append(("gh", "gh --version | head -1"))
    checks.append(("sqlite3", "sqlite3 --version"))

    for label, cmd in checks:
        lines.append(
            f'printf "%-10s %s\\n" "{label}:" "$({cmd} 2>/dev/null || echo \'not found\')"'
        )

    if "browser" in extras:
        lines.append('echo "Chromium:  ${PLAYWRIGHT_CHROMIUM:-not found}"')

    return "\n".join(lines) + "\n"


def build_setup_sh(toolchains: set[str], extras: set[str]) -> str:
    """Assemble setup.sh from selected sections."""
    parts = [setup_header(), setup_system_packages()]

    if "browser" in extras:
        parts.append(setup_browser_deps())
        parts.append(setup_chromium())
    if "gh" in extras:
        parts.append(setup_gh())
    if "go" in toolchains:
        parts.append(setup_go())
    if "rust" in toolchains:
        parts.append(setup_rust())
    if "uv" in extras:
        parts.append(setup_uv())
    if "node" in toolchains and (extras & {"pnpm", "yarn"}):
        parts.append(setup_node_managers(extras))
    parts.append(setup_env_block(toolchains, extras))
    parts.append(setup_summary(toolchains, extras))

    return "\n".join(parts)


# ── session-start.sh sections ────────────────────────────────────────────────


def session_header(scripts_dir: str) -> str:
    return f"""\
#!/bin/bash
# SessionStart hook — runs every time a session starts (new or resumed).
# Configured in .claude/settings.json under hooks.SessionStart.

# Only run in remote (cloud) environments
if [ "${{CLAUDE_CODE_REMOTE:-}}" != "true" ]; then
  echo "Local environment detected — skipping remote setup."
  exit 0
fi

echo "=== Session start (remote) ==="

# ── Auto-run setup.sh if it hasn't run yet ───────────────────────────────────
SETUP_MARKER="# === claude-code-setup ==="
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if ! grep -q "$SETUP_MARKER" /etc/environment 2>/dev/null; then
  echo "Setup marker not found — running setup.sh automatically..."
  if [ -x "${{SCRIPT_DIR}}/setup.sh" ] || [ -f "${{SCRIPT_DIR}}/setup.sh" ]; then
    bash "${{SCRIPT_DIR}}/setup.sh" 2>&1 || echo "Warning: setup.sh exited with $? (non-fatal)"
  else
    echo "Warning: setup.sh not found at ${{SCRIPT_DIR}}/setup.sh"
  fi
fi

# Source persisted env vars from setup.sh
set -a; source /etc/environment 2>/dev/null || true; set +a
"""


def session_env_detect(toolchains: set[str], extras: set[str]) -> str:
    lines = []

    if "browser" in extras:
        lines.extend([
            '# ── Detect Chromium ──────────────────────────────────────────────────────────',
            'PLAYWRIGHT_CHROMIUM=$(find /root/.cache/ms-playwright -name "chrome" -path "*/chrome-linux/chrome" 2>/dev/null | head -1)',
            '[ -z "$PLAYWRIGHT_CHROMIUM" ] && \\',
            '  PLAYWRIGHT_CHROMIUM=$(find /root/.cache/ms-playwright -name "headless_shell" -path "*/chrome-linux/headless_shell" 2>/dev/null | head -1)',
            '',
        ])

    lines.extend([
        '# ── Detect toolchain paths ──────────────────────────────────────────────────',
    ])
    if "rust" in toolchains:
        lines.append('CARGO_BIN=""; [ -d /root/.cargo/bin ] && CARGO_BIN="/root/.cargo/bin"')
    if "uv" in extras:
        lines.append('UV_BIN=""; [ -d /root/.local/bin ] && UV_BIN="/root/.local/bin"')

    return "\n".join(lines) + "\n"


def session_persist_env(toolchains: set[str], extras: set[str]) -> str:
    lines = [
        '',
        '# ── Persist env vars for Claude\'s Bash tool ──────────────────────────────────',
        '_persist() {',
        '  local k="$1" v="$2"',
        '  [ -n "${CLAUDE_ENV_FILE:-}" ] && echo "${k}=${v}" >> "$CLAUDE_ENV_FILE"',
        '  export "${k}=${v}"',
        '}',
        '',
    ]

    if "browser" in extras:
        lines.extend([
            '_persist CHROME_BIN                         "${PLAYWRIGHT_CHROMIUM:-}"',
            '_persist PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH "${PLAYWRIGHT_CHROMIUM:-}"',
            '_persist PUPPETEER_EXECUTABLE_PATH          "${PLAYWRIGHT_CHROMIUM:-}"',
            '_persist PUPPETEER_SKIP_DOWNLOAD            "true"',
        ])
    if "go" in toolchains:
        lines.append('_persist GOPATH                             "/root/go"')

    # PATH
    path_parts = []
    if "go" in toolchains:
        path_parts.append("/usr/local/go/bin:/root/go/bin")
    lines.append('')
    lines.append(f'NEW_PATH="{":".join(path_parts)}"' if path_parts else 'NEW_PATH=""')
    if "rust" in toolchains:
        lines.append('[ -n "${CARGO_BIN:-}" ] && NEW_PATH="${CARGO_BIN}:${NEW_PATH}"')
    if "uv" in extras:
        lines.append('[ -n "${UV_BIN:-}" ] && NEW_PATH="${UV_BIN}:${NEW_PATH}"')
    lines.append('[ -n "$NEW_PATH" ] && _persist PATH "${NEW_PATH}:${PATH}"')

    # Fallback profile.d
    lines.extend([
        '',
        '# Fallback for when CLAUDE_ENV_FILE isn\'t available',
        'if [ -z "${CLAUDE_ENV_FILE:-}" ]; then',
        '  cat > /etc/profile.d/claude-code-env.sh <<\'PROFILE\'',
    ])
    if "go" in toolchains:
        lines.append('export GOPATH=/root/go')

    fallback_path_parts = []
    if "rust" in toolchains:
        fallback_path_parts.append("/root/.cargo/bin")
    if "uv" in extras:
        fallback_path_parts.append("/root/.local/bin")
    if "go" in toolchains:
        fallback_path_parts.extend(["/usr/local/go/bin", "/root/go/bin"])
    if fallback_path_parts:
        lines.append(f'export PATH="{":".join(fallback_path_parts)}:$PATH"')

    lines.append('PROFILE')

    if "browser" in extras:
        lines.extend([
            '  if [ -n "${PLAYWRIGHT_CHROMIUM:-}" ]; then',
            '    cat >> /etc/profile.d/claude-code-env.sh <<CHROMIUM',
            'export CHROME_BIN="${PLAYWRIGHT_CHROMIUM}"',
            'export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="${PLAYWRIGHT_CHROMIUM}"',
            'export PUPPETEER_EXECUTABLE_PATH="${PLAYWRIGHT_CHROMIUM}"',
            'export PUPPETEER_SKIP_DOWNLOAD=true',
            'CHROMIUM',
            '  fi',
        ])

    lines.append('fi')
    return "\n".join(lines) + "\n"


def session_deps(toolchains: set[str]) -> str:
    lines = [
        '',
        '# ── Install project dependencies ────────────────────────────────────────────',
        'cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" 2>/dev/null || exit 0',
        '',
    ]

    if "node" in toolchains:
        lines.extend([
            '# Node',
            'if   [ -f package-lock.json ];  then npm install --prefer-offline 2>/dev/null || true',
            'elif [ -f pnpm-lock.yaml ];     then pnpm install --frozen-lockfile 2>/dev/null || true',
            'elif [ -f yarn.lock ];          then yarn install --frozen-lockfile 2>/dev/null || true',
            'elif [ -f bun.lock ] || [ -f bun.lockb ]; then bun install --frozen-lockfile 2>/dev/null || true',
            'fi',
            '',
        ])

    if "python" in toolchains:
        lines.extend([
            '# Python',
            'if [ -f pyproject.toml ]; then',
            '  if   command -v uv &>/dev/null;     then uv sync 2>/dev/null || uv pip install -e . 2>/dev/null || true',
            '  elif command -v poetry &>/dev/null;  then poetry install 2>/dev/null || true',
            '  else pip install -e . 2>/dev/null || true; fi',
            'elif [ -f requirements.txt ]; then',
            '  if command -v uv &>/dev/null; then uv pip install -q -r requirements.txt 2>/dev/null || true',
            '  else pip install -q -r requirements.txt 2>/dev/null || true; fi',
            'fi',
            '',
        ])

    if "go" in toolchains:
        lines.append('[ -f go.mod ] && go mod download 2>/dev/null || true')
    if "rust" in toolchains:
        lines.append('[ -f Cargo.toml ] && command -v cargo &>/dev/null && cargo fetch 2>/dev/null || true')
    if "ruby" in toolchains:
        lines.append('[ -f Gemfile ] && command -v bundle &>/dev/null && bundle install --quiet 2>/dev/null || true')

    lines.extend(['', 'echo "=== Session ready ==="', 'exit 0'])
    return "\n".join(lines) + "\n"


def build_session_start_sh(
    toolchains: set[str], extras: set[str], scripts_dir: str
) -> str:
    """Assemble session-start.sh from selected sections."""
    parts = [
        session_header(scripts_dir),
        session_env_detect(toolchains, extras),
        session_persist_env(toolchains, extras),
        session_deps(toolchains),
    ]
    return "\n".join(parts)


# ── diagnose.sh ──────────────────────────────────────────────────────────────


def build_diagnose_sh(toolchains: set[str], extras: set[str]) -> str:
    """Generate diagnose.sh for the selected toolchains/extras."""
    lines = [
        '#!/bin/bash',
        '# Diagnostic script for Claude Code web environments.',
        '# Usage: bash scripts/diagnose.sh',
        'set -uo pipefail',
        '',
        "G='\\033[0;32m'; Y='\\033[0;33m'; R='\\033[0;31m'; N='\\033[0m'",
        'ok()   { echo -e "  ${G}ok${N}  $1"; }',
        'warn() { echo -e "  ${Y}!!${N}  $1"; }',
        'fail() { echo -e "  ${R}no${N}  $1"; }',
        '',
        '_check() {',
        '  local name="$1" cmd="${2:-$1}"',
        '  if command -v "$cmd" &>/dev/null; then',
        '    ok "$name: $($cmd --version 2>&1 | head -1)"',
        '  else',
        '    fail "$name: not installed"',
        '  fi',
        '}',
        '',
        'echo "Claude Code Web Environment Diagnostics"',
        'echo "========================================"',
        'echo ""',
        '',
        'echo "System"',
        'ok "OS: $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d \'\\"\' || echo unknown)"',
        'ok "CPU: $(nproc 2>/dev/null || echo ?) cores | RAM: $(free -h 2>/dev/null | awk \'/Mem:/{print $2}\' || echo ?) | Disk: $(df -h / 2>/dev/null | awk \'NR==2{print $4}\' || echo ?)"',
        '',
        'echo ""',
        'echo "Cloud Environment"',
        '[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && ok "CLAUDE_CODE_REMOTE=true" || warn "CLAUDE_CODE_REMOTE not set"',
        '[ -n "${CLAUDE_ENV_FILE:-}" ] && ok "CLAUDE_ENV_FILE is set" || warn "CLAUDE_ENV_FILE not set"',
        '',
        'echo ""',
        'echo "Toolchains"',
    ]

    if "node" in toolchains:
        lines.extend([
            '_check "Node.js" node',
            '_check npm',
        ])
        if "pnpm" in extras:
            lines.append('_check pnpm')
        if "yarn" in extras:
            lines.append('_check yarn')
        if "bun" in extras:
            lines.append('_check bun')
    if "python" in toolchains:
        lines.append('_check "Python" python3')
        lines.append('_check pip')
        if "uv" in extras:
            lines.append('_check uv')
    if "go" in toolchains:
        lines.append('command -v go &>/dev/null && ok "Go: $(go version 2>&1)" || fail "Go: not installed"')
    if "rust" in toolchains:
        lines.extend(['_check "Rust" rustc', '_check Cargo cargo'])
    if "ruby" in toolchains:
        lines.append('_check Ruby ruby')
    if "java" in toolchains:
        lines.append('command -v java &>/dev/null && ok "Java: $(java -version 2>&1 | grep version | head -1)" || fail "Java: not installed"')

    lines.extend(['', 'echo ""', 'echo "CLI Tools"', '_check git'])
    if "gh" in extras:
        lines.append('_check gh')
    lines.extend(['_check jq', '_check curl', '_check sqlite3'])

    if "browser" in extras:
        lines.extend([
            '',
            'echo ""',
            'echo "Browser Automation"',
            'CHROMIUM=$(find /root/.cache/ms-playwright -name "chrome" -path "*/chrome-linux/chrome" 2>/dev/null | head -1)',
            '[ -n "$CHROMIUM" ] && ok "Playwright Chromium: $CHROMIUM" || fail "Playwright Chromium: not found"',
            '[ -n "${PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH:-}" ] && ok "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH set" || warn "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH not set"',
        ])

    lines.extend([
        '',
        'echo ""',
        'echo "Setup Status"',
        'grep -q "claude-code-setup" /etc/environment 2>/dev/null && ok "setup.sh has run" || warn "setup.sh marker not found"',
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        '[ -f "${SCRIPT_DIR}/setup.sh" ] && ok "setup.sh exists" || fail "setup.sh missing"',
        '[ -f "${SCRIPT_DIR}/session-start.sh" ] && ok "session-start.sh exists" || fail "session-start.sh missing"',
        'SETTINGS="${SCRIPT_DIR}/../.claude/settings.json"',
        '[ -f "$SETTINGS" ] && grep -q "SessionStart" "$SETTINGS" 2>/dev/null \\',
        '  && ok "SessionStart hook wired in settings.json" \\',
        '  || warn "SessionStart hook not configured"',
        '',
        'echo ""',
        'echo "Done."',
    ])

    return "\n".join(lines) + "\n"


# ── Public constants ─────────────────────────────────────────────────────────

ALL_TOOLCHAINS = {"node", "python", "go", "rust", "ruby", "java"}
ALL_EXTRAS = {"gh", "uv", "pnpm", "yarn", "bun", "browser"}
