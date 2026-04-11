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
    scripts_dir = args.scripts_dir
    skills_dir = (args.skills).strip().strip("/")
    force = args.force

    # Auto-add uv when python is selected
    if "python" in toolchains:
        extras.add("uv")
    # Auto-add browser deps when browser extra is selected
    if "browser" in extras and "node" not in toolchains:
        # Chromium install needs npx
        toolchains.add("node")

    project_root = Path.cwd()
    scripts_path = project_root / scripts_dir

    print(f"Project root: {project_root}")
    tc_str = ", ".join(sorted(toolchains)) if toolchains != ALL_TOOLCHAINS else "all"
    ex_str = ", ".join(sorted(extras)) if extras != ALL_EXTRAS else "all"
    print(f"Toolchains:   {tc_str}")
    print(f"Extras:       {ex_str}")
    if skills_dir:
        print(f"Skills dir:   {skills_dir}")
    print()

    # Generate scripts
    _write_script(
        scripts_path / "setup.sh",
        build_setup_sh(toolchains, extras),
        force,
    )
    _write_script(
        scripts_path / "session-start.sh",
        build_session_start_sh(toolchains, extras, scripts_dir, skills_dir),
        force,
    )
    _write_script(
        scripts_path / "diagnose.sh",
        build_diagnose_sh(toolchains, extras, skills_dir),
        force,
    )

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

    # No diagnose.sh found — run inline diagnostics
    print("No diagnose.sh found. Running basic checks...")
    print()

    checks = [
        ("CLAUDE_CODE_REMOTE", os.environ.get("CLAUDE_CODE_REMOTE", "")),
        ("CLAUDE_ENV_FILE", os.environ.get("CLAUDE_ENV_FILE", "")),
    ]
    for name, val in checks:
        status = "set" if val else "not set"
        print(f"  {name}: {status}")

    import shutil

    tools = ["node", "python3", "go", "rustc", "ruby", "gh", "jq", "curl"]
    print()
    for tool in tools:
        path = shutil.which(tool)
        if path:
            print(f"  ok  {tool}: {path}")
        else:
            print(f"  --  {tool}: not found")


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
                               postgres,redis,docker (default: all)
  ccweb init --scripts-dir D   Output directory for scripts (default: scripts)
  ccweb init --skills DIR      Path (repo-relative) to a directory of Claude
                               Code skills. Each subdirectory containing
                               SKILL.md is symlinked into ~/.claude/skills/
                               at session start (default: .claude/skills).
                               Pass --skills "" to disable.
  ccweb init --force           Overwrite existing files without prompting
  ccweb doctor                 Run diagnostics on the current environment

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

  # Rust project, no opt-in extras (always-on CLI tools still included)
  uvx ccweb init --toolchains rust --extras ""

  # Wire user-level skills from a repo directory
  uvx ccweb init --skills .claude/skills

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
    init_p.add_argument("--force", action="store_true")
    init_p.add_argument("-h", "--help", action="store_true")

    # doctor
    doctor_p = sub.add_parser("doctor", add_help=False)
    doctor_p.add_argument("-h", "--help", action="store_true")

    args = parser.parse_args()

    # Subcommand --help falls through to the full help text
    if getattr(args, "help", False):
        print(HELP_TEXT)
        sys.exit(0)

    if args.command == "init":
        cmd_init(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    else:
        print(HELP_TEXT)
        sys.exit(0)


if __name__ == "__main__":
    main()
