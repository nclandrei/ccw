"""ccweb CLI — Bootstrap Claude Code web environments."""

from __future__ import annotations

import argparse
import os
import stat
import sys
import textwrap
from pathlib import Path

from . import __version__
from .sections import (
    ALL_EXTRAS,
    ALL_TOOLCHAINS,
    DEFAULT_VERSIONS,
    build_diagnose_sh,
    build_session_start_sh,
    build_setup_sh,
)
from .settings import merge_settings


def _parse_set(value: str, valid: set[str], label: str) -> set[str]:
    if value == "all":
        return set(valid)
    if value.strip() == "":
        return set()
    items = {s.strip().lower() for s in value.split(",") if s.strip()}
    unknown = items - valid
    if unknown:
        print(f"Error: unknown {label}: {', '.join(sorted(unknown))}", file=sys.stderr)
        print(f"Valid {label}: {', '.join(sorted(valid))}", file=sys.stderr)
        sys.exit(1)
    return items


def _parse_versions(value: str) -> dict[str, str]:
    """Parse 'go=1.23.0,zig=0.14.0' into a dict. Empty string → {}."""
    if not value.strip():
        return {}
    out: dict[str, str] = {}
    for pair in value.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            print(f"Error: --versions entry must be KEY=VALUE, got: {pair}", file=sys.stderr)
            sys.exit(1)
        key, _, val = pair.partition("=")
        key = key.strip().lower()
        val = val.strip()
        if key not in DEFAULT_VERSIONS:
            print(f"Error: unknown version key: {key}", file=sys.stderr)
            print(f"Valid keys: {', '.join(sorted(DEFAULT_VERSIONS))}", file=sys.stderr)
            sys.exit(1)
        if not val:
            print(f"Error: empty version value for {key}", file=sys.stderr)
            sys.exit(1)
        out[key] = val
    return out


def _resolve_env_file(explicit: str | None, project_root: Path) -> str:
    """Resolve --env-file. Empty string disables. None auto-detects .env.example/.env.template."""
    if explicit == "":
        return ""
    if explicit is not None:
        return explicit
    for candidate in (".env.example", ".env.template"):
        if (project_root / candidate).exists():
            return candidate
    return ""


def _write_script(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        answer = input(f"  {path} already exists. Overwrite? [y/N] ").strip()
        if not answer.lower().startswith("y"):
            print(f"  Skipped {path}")
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  + {path}")
    return True


def cmd_init(args: argparse.Namespace) -> None:
    toolchains = _parse_set(args.toolchains, ALL_TOOLCHAINS, "toolchains")
    extras = _parse_set(args.extras, ALL_EXTRAS, "extras")
    versions = _parse_versions(args.versions)
    scripts_dir = args.scripts_dir
    skills_dir = (args.skills).strip().strip("/")
    force = args.force
    dry_run = getattr(args, "dry_run", False)

    # Auto-add uv when python is selected
    if "python" in toolchains:
        extras.add("uv")
    # Auto-add browser deps when browser extra is selected
    if "browser" in extras and "node" not in toolchains:
        # Chromium install needs npx
        toolchains.add("node")

    project_root = Path.cwd()
    scripts_path = project_root / scripts_dir
    env_file = _resolve_env_file(args.env_file, project_root)

    print(f"Project root: {project_root}")
    tc_str = ", ".join(sorted(toolchains)) if toolchains != ALL_TOOLCHAINS else "all"
    ex_str = ", ".join(sorted(extras)) if extras != ALL_EXTRAS else "all"
    print(f"Toolchains:   {tc_str}")
    print(f"Extras:       {ex_str}")
    if skills_dir:
        print(f"Skills dir:   {skills_dir}")
    if env_file:
        print(f"Env file:     {env_file}")
    if versions:
        pins = ", ".join(f"{k}={v}" for k, v in sorted(versions.items()))
        print(f"Versions:     {pins}")
    if dry_run:
        print("Mode:         dry-run (no files written)")
    print()

    scripts = [
        (scripts_path / "setup.sh", build_setup_sh(toolchains, extras, versions)),
        (
            scripts_path / "session-start.sh",
            build_session_start_sh(toolchains, extras, scripts_dir, skills_dir, env_file),
        ),
        (
            scripts_path / "diagnose.sh",
            build_diagnose_sh(toolchains, extras, skills_dir, env_file),
        ),
    ]

    if dry_run:
        for path, content in scripts:
            _print_script(path, content)
        print()
        print("Dry-run complete. Re-run without --dry-run to write these files.")
        return

    for path, content in scripts:
        _write_script(path, content, force)

    # Merge settings.json
    print()
    result = merge_settings(project_root, scripts_dir)
    print(f"  {result}")

    print()
    print("Done! Next steps:")
    print(f"  1. git add {scripts_dir}/ .claude/settings.json")
    print("  2. git commit -m 'Add Claude Code web environment setup'")
    print("  3. git push")
    print("  4. Start a Claude Code web session — session-start.sh auto-provisions")
    print("  5. Run `ccweb doctor` to verify everything is working")


def _print_script(path: Path, content: str) -> None:
    banner = f"===== {path} ====="
    print(banner)
    print(content, end="" if content.endswith("\n") else "\n")
    print("=" * len(banner))
    print()


def cmd_show_setup(args: argparse.Namespace) -> None:
    """Print setup.sh to stdout without writing anything."""
    toolchains = _parse_set(args.toolchains, ALL_TOOLCHAINS, "toolchains")
    extras = _parse_set(args.extras, ALL_EXTRAS, "extras")
    versions = _parse_versions(args.versions)
    if "python" in toolchains:
        extras.add("uv")
    if "browser" in extras and "node" not in toolchains:
        toolchains.add("node")
    sys.stdout.write(build_setup_sh(toolchains, extras, versions))


def cmd_doctor(args: argparse.Namespace) -> None:
    """Run diagnose.sh or equivalent checks."""
    # Look for diagnose.sh in common locations
    candidates = [
        Path.cwd() / "scripts" / "diagnose.sh",
        Path.cwd() / "diagnose.sh",
    ]
    for candidate in candidates:
        if candidate.exists():
            os.execvp("bash", ["bash", str(candidate)])

    # No diagnose.sh on disk — build the full diagnostic in-memory against
    # the superset of toolchains/extras and run it. Same output quality
    # whether `init` has been run or not.
    import tempfile

    project_root = Path.cwd()
    env_file = _resolve_env_file(None, project_root)
    script = build_diagnose_sh(ALL_TOOLCHAINS, ALL_EXTRAS, "", env_file)
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as tmp:
        tmp.write(script)
        tmp_path = tmp.name
    print("No diagnose.sh found — running full diagnostics against all toolchains/extras.")
    print()
    os.execvp("bash", ["bash", tmp_path])


HELP_TEXT = textwrap.dedent("""\
ccweb - bootstrap Claude Code web environments so they just work

ccweb generates shell scripts that auto-provision a fresh Ubuntu 24.04 VM
every time a Claude Code web session starts. The agent (or human) runs
ccweb once locally, commits the output, and every future cloud session
gets the right toolchains, package managers, CLI tools, and browser
automation without manual setup.

Reading this help text is not the task.
The task is to run ccweb init in the project root, commit the generated
files, push, and start a Claude Code web session. The VM provisions itself.

Commands:
  ccweb init                   Generate scripts and wire settings.json
  ccweb init --toolchains TC   Comma-separated: node,python,go,rust,ruby,
                               java,deno,elixir,zig,dotnet,php (default: all)
  ccweb init --extras EX       Comma-separated: uv,pnpm,yarn,bun,browser,
                               postgres,redis,docker,cloud (default: all)
  ccweb init --scripts-dir D   Output directory for scripts (default: scripts)
  ccweb init --skills DIR      Path (repo-relative) to a directory of Claude
                               Code skills. Each subdirectory containing
                               SKILL.md is symlinked into ~/.claude/skills/
                               at session start (default: .claude/skills).
                               Pass --skills "" to disable.
  ccweb init --versions PINS   Pin tool versions, e.g. go=1.23.0,zig=0.14.0.
                               Valid keys: go, zig, gh, duckdb, yq,
                               dotnet_channel, terraform, kubectl.
                               Unspecified tools use defaults.
  ccweb init --env-file PATH   Repo-relative path to an env schema file
                               (default: auto-detect .env.example or
                               .env.template). session-start.sh warns when
                               any declared var is unset; diagnose.sh shows
                               set/missing per var. Only variable NAMES are
                               read — ccweb never stores or transmits values.
                               Pass --env-file "" to disable auto-detection.
  ccweb init --force           Overwrite existing files without prompting
  ccweb init --dry-run         Print the scripts that would be generated to
                               stdout without writing anything to disk or
                               modifying .claude/settings.json.
  ccweb show setup             Print setup.sh to stdout without writing.
                               Accepts --toolchains, --extras, --versions to
                               preview a specific configuration. Useful for
                               piping into a reviewer, diffing, or pasting
                               into the claude.ai/code Setup Script field.
  ccweb doctor                 Run diagnostics on the current environment.
                               Uses scripts/diagnose.sh if present, otherwise
                               builds a full diagnostic in-memory against all
                               toolchains and extras.

What ccweb init generates:
  scripts/setup.sh             Runs as root on first session. Installs system
                               packages, toolchains, package managers, and CLI
                               tools. Idempotent — safe to run multiple times.
                               Can also be pasted into the "Setup script" field
                               at claude.ai/code for faster cold starts.
  scripts/session-start.sh     SessionStart hook — runs every session (new or
                               resumed). Auto-triggers setup.sh if the setup
                               marker is missing. Detects lockfiles and installs
                               project dependencies (npm, pip, cargo, go mod, etc).
  scripts/diagnose.sh          Prints green/red status for every installed tool.
                               Run anytime to verify the environment.
  .claude/settings.json        Wires session-start.sh as a SessionStart hook.
                               Merges with existing settings, never clobbers.

Toolchains (what each installs):
  node       Pre-installed on the VM. ccweb wires dependency install from
             lockfiles (package-lock.json, pnpm-lock.yaml, yarn.lock, bun.lock).
  python     Pre-installed. Adds uv automatically. Installs from pyproject.toml
             or requirements.txt via uv/pip.
  go         Installs Go 1.24. Downloads modules from go.mod.
  rust       Installs via rustup (stable, minimal profile). Cargo fetch from
             Cargo.toml. Adds ~/.cargo/bin to PATH.
  ruby       Pre-installed. Runs bundle install from Gemfile.
  java       Pre-installed (Java 21).
  deno       Installs from deno.land. Runs deno install from deno.json.
  elixir     Installs Erlang + Elixir via apt. Runs mix deps.get from mix.exs.
  zig        Installs Zig 0.15.2 from ziglang.org.
  dotnet     Installs .NET SDK via official install script. Runs dotnet restore.
  php        Installs PHP CLI + Composer via apt. Runs composer install.

Always-on CLI tools (installed unconditionally, no flag needed):
  Core:      jq, yq, curl, wget, httpie, ripgrep, fd-find, bat, tree, htop
  Shell:     shellcheck, shfmt, make, build-essential
  Git:       git, gh (GitHub CLI), git-lfs
  Data:      sqlite3, duckdb (analytical SQL over CSV/JSON/Parquet)
  Docs:      pandoc
  Files:     unzip, zip, rsync
  These are small, universally useful, and have no reason to be gated.

Extras (what each installs):
  uv         Fast Python package manager. Auto-added when python is selected.
  pnpm       Installed via npm install -g, symlinked to /usr/local/bin.
  yarn       Installed via npm install -g, symlinked to /usr/local/bin.
  bun        Pre-installed on the VM.
  browser    Installs Playwright Chromium + system dependencies. Symlinks to
             /usr/local/bin/chromium and /usr/local/bin/google-chrome so any
             tool can find it via PATH. Needed for Puppeteer, Playwright, or
             any headless browser automation.
  postgres   Installs PostgreSQL client (psql).
  redis      Installs redis-cli (redis-tools).
  docker     Installs Docker CLI. Note: the Docker daemon is not available on
             the VM, but the CLI is useful for docker compose files and remote
             Docker hosts.
  cloud      Installs the common cloud/infra CLIs: aws (AWS CLI v2), gcloud
             (Google Cloud SDK), terraform, kubectl, and helm. Authentication
             still relies on env vars / credentials set via the claude.ai
             Environment Variables UI; ccweb does not manage credentials.

Skills (--skills DIR, default: .claude/skills):
  Claude Code auto-discovers skills from ~/.claude/skills/<name>/SKILL.md.
  By default, session-start.sh looks for skills in .claude/skills/ in the
  repo and, for every subdirectory that contains a SKILL.md file, creates
  a symlink at ~/.claude/skills/<name> pointing back to the in-repo skill.
  This makes the repo's skills available at the user level for every
  session on the VM, without copying files. Typical layout:

    .claude/skills/my-skill/SKILL.md
    .claude/skills/my-skill/reference.md
    .claude/skills/another-skill/SKILL.md

  Pass --skills "" to disable skill wiring entirely.
  Example: --skills ai/skills         (custom path)

Environment variables (--env-file PATH):
  If the repo contains a .env.example or .env.template file (or --env-file
  points somewhere else), session-start.sh reads the variable NAMES from it
  and warns when any are unset in the running session. The file is a schema,
  not a secret store — ccweb never reads, copies, or transmits values.
  Secrets should live in the claude.ai/code Environment Variables UI at the
  project level. diagnose.sh gets a matching section that shows each declared
  variable as set or missing.

Version pinning (--versions KEY=VALUE,...):
  By default ccweb uses known-good versions for Go, Zig, gh, duckdb, yq, the
  .NET channel, terraform, and kubectl. Override any subset with --versions:

    --versions go=1.23.0
    --versions go=1.23.0,zig=0.14.0,gh=2.74.1
    --versions dotnet_channel=LTS
    --versions terraform=1.9.8,kubectl=1.31.2

  Valid keys: go, zig, gh, duckdb, yq, dotnet_channel, terraform, kubectl.

How it works at runtime:
  1. User opens a Claude Code web session on a repo that has ccweb scripts.
  2. Claude Code runs session-start.sh via the SessionStart hook.
  3. session-start.sh checks for the setup marker in /etc/environment.
     If missing (first session on this VM), it runs setup.sh automatically.
  4. setup.sh installs everything as root. Takes 1-3 minutes depending on
     selected toolchains. Writes a marker to /etc/environment so it only
     runs once per VM.
  5. session-start.sh detects lockfiles and installs project dependencies.
  6. The session is ready. All tools are on PATH.

  On resumed sessions (same VM), setup.sh is skipped (marker exists) and
  only dependency install runs. This takes seconds.

Workflow — what an agent should do:
  1. cd into the project root
  2. run: uvx ccweb init
     or for a specific stack: uvx ccweb init --toolchains node,python --extras gh,browser
  3. commit: git add scripts/ .claude/settings.json
  4. commit: git commit -m 'Add Claude Code web environment setup'
  5. push: git push
  6. start a Claude Code web session — it provisions automatically
  7. verify: ask the session to run bash scripts/diagnose.sh

  To verify an existing setup without generating new scripts:
  ccweb doctor

Environment:
  The target VM is Ubuntu 24.04 LTS with 4 cores, 15 GiB RAM, 30 GB disk.
  Node.js 20, Python 3.11, Ruby 3.3, Java 21, and bun are pre-installed.
  Scripts run as root. Network access is available during setup.

  CLAUDE_CODE_REMOTE is set to "true" in web sessions. session-start.sh
  checks this variable and exits immediately in local environments, so
  the hook is safe to leave wired on all machines.

Examples:
  # Full setup — every toolchain and extra
  uvx ccweb init

  # Node + Python project (most common)
  uvx ccweb init --toolchains node,python --extras uv,browser

  # Go backend with database tools
  uvx ccweb init --toolchains go --extras postgres,redis

  # Infra/DevOps workflow — cloud CLIs only (aws, gcloud, terraform, kubectl, helm)
  uvx ccweb init --toolchains "" --extras cloud

  # Rust project, no opt-in extras (always-on CLI tools still included)
  uvx ccweb init --toolchains rust --extras ""

  # Wire user-level skills from a repo directory
  uvx ccweb init --skills .claude/skills

  # Pin Go and Zig versions
  uvx ccweb init --versions go=1.23.0,zig=0.14.0

  # Declare required env vars via a schema file (auto-detected by default)
  uvx ccweb init --env-file .env.example

  # Overwrite existing scripts after upgrading ccweb
  uvx ccweb init --force

  # Check what's installed on the current VM
  ccweb doctor
""")


def main() -> None:
    # Show the full help text for --help and bare invocation,
    # but use argparse for flag parsing.
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h", "help"):
        if "--version" in sys.argv:
            print(f"ccweb {__version__}")
        else:
            print(HELP_TEXT)
        sys.exit(0)

    if sys.argv[1] == "--version":
        print(f"ccweb {__version__}")
        sys.exit(0)

    parser = argparse.ArgumentParser(prog="ccweb", add_help=False)
    sub = parser.add_subparsers(dest="command")

    # init
    init_p = sub.add_parser("init", add_help=False)
    init_p.add_argument("--toolchains", default="all")
    init_p.add_argument("--extras", default="all")
    init_p.add_argument("--scripts-dir", default="scripts")
    init_p.add_argument("--skills", default=".claude/skills")
    init_p.add_argument("--versions", default="")
    init_p.add_argument("--env-file", dest="env_file", default=None)
    init_p.add_argument("--force", action="store_true")
    init_p.add_argument("--dry-run", dest="dry_run", action="store_true")
    init_p.add_argument("-h", "--help", action="store_true")

    # doctor
    doctor_p = sub.add_parser("doctor", add_help=False)
    doctor_p.add_argument("-h", "--help", action="store_true")

    # show
    show_p = sub.add_parser("show", add_help=False)
    show_p.add_argument("target", nargs="?", default=None)
    show_p.add_argument("--toolchains", default="all")
    show_p.add_argument("--extras", default="all")
    show_p.add_argument("--versions", default="")
    show_p.add_argument("-h", "--help", action="store_true")

    args = parser.parse_args()

    # Subcommand --help falls through to the full help text
    if getattr(args, "help", False):
        print(HELP_TEXT)
        sys.exit(0)

    if args.command == "init":
        cmd_init(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "show":
        if args.target == "setup":
            cmd_show_setup(args)
        else:
            print("Usage: ccweb show setup", file=sys.stderr)
            sys.exit(2)
    else:
        print(HELP_TEXT)
        sys.exit(0)


if __name__ == "__main__":
    main()
