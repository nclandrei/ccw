# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

ccweb is a Python CLI (`uvx ccweb init`) that generates shell scripts to auto-provision Claude Code web environments (Ubuntu 24.04 VMs). It outputs `setup.sh`, `session-start.sh`, `diagnose.sh`, `post-tool-use.sh`, and wires `.claude/settings.json` (SessionStart + PostToolUse hooks).

## Build and run

```bash
# Run the CLI locally (no install needed)
PYTHONPATH=src python3 -m ccw.cli --help
PYTHONPATH=src python3 -m ccw.cli init --toolchains node,python --force

# Build the package
uvx --from build pyproject-build

# Publish to PyPI (also triggered by GitHub Release via .github/workflows/publish.yml)
uv publish --token "$PYPI_API_TOKEN" dist/ccweb-*
```

Unit tests live in `tests/` and run via `python3 -m unittest discover -s tests`. The e2e loop is: generate scripts and run them against a clean Ubuntu 24.04 container via `uvx ccweb test` (or in a real Claude Code web session) and check `bash scripts/diagnose.sh` output.

## Architecture

Source files in `src/ccw/`:

- **`cli.py`** — argparse CLI with `init`, `doctor`, and `test` subcommands. The `--help` text is a self-contained agent-readable instruction manual (Showboat/Proctor pattern). All help goes through `HELP_TEXT`, not argparse's built-in help.
- **`sections.py`** — Pure functions that return shell script fragments. Each function (`setup_go()`, `setup_rust()`, `setup_chromium()`, etc.) returns a bash string. `build_setup_sh()`, `build_session_start_sh()`, `build_diagnose_sh()`, and `build_post_tool_use_sh()` assemble the fragments based on selected toolchains/extras. This is the largest file and where most changes happen.
- **`detect.py`** — Auto-detects toolchains and extras from project marker files (lockfiles, `pyproject.toml`, `Cargo.toml`, Terraform dirs, etc.) when the user passes `--toolchains auto` or `--extras auto`.
- **`settings.py`** — Merges the SessionStart and PostToolUse hooks into `.claude/settings.json` without clobbering existing settings.

The `scripts/` directory at repo root contains the generated scripts for ccweb's own repo (dog-fooding), including `post-tool-use.sh` — the PostToolUse hook that formats edited files via ruff, gofmt, rustfmt, zig fmt, mix format, shfmt, clang-format, rubocop, google-java-format, php-cs-fixer, terraform fmt, and prettier (with deno fmt fallback).

## Key design decisions

- **All toolchains/extras default to "all"** — users opt out, not in.
- **`setup.sh` is idempotent** — it writes a marker to `/etc/environment` and skips on re-run.
- **`session-start.sh` auto-triggers `setup.sh`** — no need to paste setup.sh into the claude.ai Setup Script field.
- **Chromium is symlinked to PATH** (`/usr/local/bin/chromium`, `/usr/local/bin/google-chrome`) — env vars don't persist in Claude's Bash tool without `CLAUDE_ENV_FILE`.
- **pnpm/yarn use `npm install -g`** with symlinks into `/usr/local/bin` — corepack is unreliable on the VM.
- **Version lives in two places** — `src/ccw/__init__.py` and `pyproject.toml`. Both must be bumped together.

## The --help pattern

The help text in `cli.py` follows the Showboat/Proctor pattern: a flat, self-contained instruction manual that an agent can read once and use the tool without other docs. When changing commands or behavior, update `HELP_TEXT` — it is the primary documentation.

## Release process

1. Bump version in `src/ccw/__init__.py` and `pyproject.toml` (must match)
2. Commit and push
3. Build: `uvx --from build pyproject-build`
4. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
5. Create GitHub Release with artifacts:
   ```bash
   gh release create vX.Y.Z dist/ccweb-X.Y.Z* --title "vX.Y.Z" --notes "..."
   ```
6. The `.github/workflows/publish.yml` Action auto-publishes to PyPI via trusted publishing (OIDC, no token needed) when the release is created.

Manual PyPI fallback (if the Action fails or for pre-release):

```bash
uv publish --token "$PYPI_API_TOKEN" dist/ccweb-X.Y.Z*
```
