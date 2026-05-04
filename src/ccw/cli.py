"""ccweb CLI — Bootstrap Claude Code web environments."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
import textwrap
from pathlib import Path

from . import __version__
from .detect import detect_extras, detect_toolchains, detect_versions
from .sections import (
    ALL_EXTRAS,
    ALL_TOOLCHAINS,
    DEFAULT_VERSIONS,
    build_diagnose_sh,
    build_post_tool_use_sh,
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


def _resolve_toolchains(value: str, project_root: Path) -> set[str]:
    """Resolve --toolchains. 'auto' sniffs project_root for marker files."""
    if value == "auto":
        return detect_toolchains(project_root)
    return _parse_set(value, ALL_TOOLCHAINS, "toolchains")


def _resolve_extras(value: str, project_root: Path) -> set[str]:
    """Resolve --extras. 'auto' sniffs project_root for marker files."""
    if value == "auto":
        return detect_extras(project_root)
    return _parse_set(value, ALL_EXTRAS, "extras")


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
            print(
                f"Error: --versions entry must be KEY=VALUE, got: {pair}",
                file=sys.stderr,
            )
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
    project_root = Path.cwd()
    toolchains = _resolve_toolchains(args.toolchains, project_root)
    extras = _resolve_extras(args.extras, project_root)
    explicit_versions = _parse_versions(args.versions)
    auto_versions = detect_versions(project_root)
    # Explicit --versions always wins over auto-detected pins (per key).
    versions = {**auto_versions, **explicit_versions}
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

        def _fmt_pin(k: str, v: str) -> str:
            if k in explicit_versions:
                return f"{k}={v}"
            return f"{k}={v} (auto)"

        pins = ", ".join(_fmt_pin(k, v) for k, v in sorted(versions.items()))
        print(f"Versions:     {pins}")
    if dry_run:
        print("Mode:         dry-run (no files written)")
    print()

    scripts = [
        (scripts_path / "setup.sh", build_setup_sh(toolchains, extras, versions)),
        (
            scripts_path / "session-start.sh",
            build_session_start_sh(
                toolchains, extras, scripts_dir, skills_dir, env_file
            ),
        ),
        (
            scripts_path / "diagnose.sh",
            build_diagnose_sh(toolchains, extras, skills_dir, env_file),
        ),
        (scripts_path / "post-tool-use.sh", build_post_tool_use_sh()),
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
    print(
        "No diagnose.sh found — running full diagnostics against all toolchains/extras."
    )
    print()
    os.execvp("bash", ["bash", tmp_path])


def build_docker_test_args(
    image: str,
    project_root: Path,
    scripts_dir: str,
    shell: bool = False,
    network: str | None = None,
) -> list[str]:
    """Assemble the `docker run` argv that validates setup.sh + diagnose.sh
    against a clean Ubuntu container."""
    argv = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{project_root}:/workspace:ro",
        "-w",
        "/workspace",
        "-e",
        "CLAUDE_CODE_REMOTE=true",
    ]
    if network:
        argv.extend(["--network", network])
    if shell:
        argv.extend(["-it", image, "bash"])
        return argv

    payload = (
        "set -e\n"
        f'echo "=== ccweb test: setup.sh (on $(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d \\")) ==="\n'
        f"bash {scripts_dir}/setup.sh\n"
        'echo ""\n'
        'echo "=== ccweb test: diagnose.sh ==="\n'
        f"bash {scripts_dir}/diagnose.sh\n"
    )
    argv.extend([image, "bash", "-c", payload])
    return argv


def cmd_test(args: argparse.Namespace) -> None:
    """Validate generated scripts against a clean Ubuntu Docker container."""
    project_root = Path.cwd()
    scripts_dir = args.scripts_dir
    scripts_path = project_root / scripts_dir

    setup_sh = scripts_path / "setup.sh"
    diagnose_sh = scripts_path / "diagnose.sh"
    if not setup_sh.exists() or not diagnose_sh.exists():
        missing = setup_sh if not setup_sh.exists() else diagnose_sh
        print(f"Error: {missing} not found. Run 'ccweb init' first.", file=sys.stderr)
        sys.exit(1)

    if not shutil.which("docker"):
        print(
            "Error: docker not found on PATH. Install Docker to run 'ccweb test'.",
            file=sys.stderr,
        )
        sys.exit(1)

    argv = build_docker_test_args(
        image=args.image,
        project_root=project_root,
        scripts_dir=scripts_dir,
        shell=args.shell,
        network=args.network,
    )
    print(f"Image:   {args.image}")
    print(f"Mount:   {project_root} -> /workspace (ro)")
    if args.shell:
        print("Mode:    interactive shell")
    else:
        print(f"Runs:    {scripts_dir}/setup.sh then {scripts_dir}/diagnose.sh")
    print()
    os.execvp(argv[0], argv)


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
                               java,deno,elixir,zig,dotnet,php (default: all).
                               Use 'auto' to detect from project marker files
                               (package.json, go.mod, Cargo.toml, etc.) and
                               install only what the repo actually uses.
  ccweb init --extras EX       Comma-separated: uv,pnpm,yarn,bun,browser,
                               postgres,redis,docker,cloud,liquibase
                               (default: all). Use 'auto' to detect from
                               lockfiles and other markers (pnpm-lock.yaml,
                               Dockerfile, uv.lock, playwright in
                               package.json, postgres/redis in
                               docker-compose, db.changelog-master.* for
                               liquibase, etc.).
  ccweb init --scripts-dir D   Output directory for scripts (default: scripts)
  ccweb init --skills DIR      Path (repo-relative) to a directory of Claude
                               Code skills. Each subdirectory containing
                               SKILL.md is symlinked into ~/.claude/skills/
                               at session start (default: .claude/skills).
                               Pass --skills "" to disable.
  ccweb init --versions PINS   Pin tool versions, e.g. go=1.23.0,zig=0.14.0.
                               Valid keys: go, zig, gh, duckdb, yq,
                               dotnet_channel, terraform, kubectl, liquibase.
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
  ccweb test                   Validate setup.sh + diagnose.sh in a clean
                               Docker ubuntu:24.04 container. Catches broken
                               installs before pushing. Requires a local
                               Docker daemon. Flags:
                                 --image IMG     base image (default ubuntu:24.04)
                                 --scripts-dir D scripts location (default scripts)
                                 --shell         drop into an interactive shell
                                                 instead of auto-running
                                 --network NET   docker network mode (e.g. host)
                                                 — useful behind corporate DNS

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
  scripts/post-tool-use.sh     PostToolUse hook — runs after every Edit/Write.
                               Reads the edited file path from the hook payload
                               and dispatches to the matching formatter:
                                 ruff               → .py
                                 gofmt              → .go
                                 rustfmt            → .rs
                                 zig fmt            → .zig
                                 mix format         → .ex, .exs
                                 shfmt              → .sh, .bash
                                 clang-format       → .c/.h/.cc/.cpp/.hpp/.m/...
                                 rubocop            → .rb
                                 google-java-format → .java
                                 php-cs-fixer       → .php
                                 terraform fmt      → .tf, .tfvars
                                 csharpier / dotnet format
                                                    → .cs/.csproj/.fs/.fsproj/
                                                      .vb/.vbproj
                                 prettier           → .js/.ts/.json/.md/.css/...
                                                      (falls back to `deno fmt`
                                                      when prettier is missing)
                               Each call is guarded by `command -v`, and the
                               hook always exits 0 so a missing or failing
                               formatter never blocks the agent.
  .claude/settings.json        Wires session-start.sh as a SessionStart hook
                               and post-tool-use.sh as a PostToolUse hook
                               (matcher: Edit|Write|MultiEdit). Also writes
                               a permissive default for network and tool use:
                                 sandbox.network.allowedDomains = ["*"]
                                 permissions.allow includes WebFetch,
                                 WebSearch, and mcp__github__* so the agent
                                 can hit the network and call GitHub MCP
                                 tools without prompts.
                               Merges with existing settings, never clobbers
                               a user-defined sandbox block or custom allow
                               entries.

Network & GitHub access (what ccweb can and cannot configure):
  Network:   ccweb sets sandbox.network.allowedDomains to ["*"] in
             .claude/settings.json, which gives the agent unrestricted
             outbound network access on the web VM. To tighten it, edit the
             generated sandbox block (or set your own before running init —
             ccweb will not overwrite an existing sandbox config).

  GitHub repository scope is NOT something a repo's settings.json can
  override — it is enforced by the claude.ai/code environment template and
  by the Claude GitHub App's installation scope. To get "all repositories"
  access for every Claude Code web session:
    1. Visit https://github.com/settings/installations, click Configure
       on the Claude GitHub App, and set Repository access to
       "All repositories".
    2. At claude.ai/code, when creating an environment/agent, do not pin
       it to a single repo unless you want to.
  ccweb pre-allows mcp__github__* in permissions.allow so the GitHub MCP
  tools never prompt — but the system prompt restriction set by the
  environment template still applies until you do steps 1 and 2 above.

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
  liquibase  Installs the Liquibase CLI for declarative database schema
             migrations. Reads YAML/XML/JSON/SQL changelogs and applies them
             against any JDBC-supported database. Requires Java at runtime —
             enable the `java` toolchain (or rely on the pre-installed JRE)
             when this extra is used.

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

  Valid keys: go, zig, gh, duckdb, yq, dotnet_channel, terraform, kubectl,
  liquibase.

  Auto-detection: if the project root contains any of these version files,
  pins are picked up automatically (no flag needed):
    .tool-versions       asdf/mise — lines like `golang 1.22.0`, `zig 0.14.0`,
                         `terraform 1.9.8`, `kubectl 1.31.2`. Lines for tools
                         that aren't pinnable (nodejs, python, ruby, ...) are
                         ignored because those ship pre-installed on the VM.
    .go-version          single-line Go version (wins over .tool-versions).
    .terraform-version   single-line Terraform version (wins over .tool-versions).
    .nvmrc, .python-version  read but ignored — no pinnable key.

  Explicit --versions entries always override auto-detected pins per key.

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

  # Auto-detect toolchains and extras from the repo's marker files
  uvx ccweb init --toolchains auto --extras auto

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

  # Validate generated scripts against a clean Ubuntu container before pushing
  ccweb test

  # Try a different base image, or drop into an interactive shell
  ccweb test --image ubuntu:22.04
  ccweb test --shell
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

    # test — local Docker validation
    test_p = sub.add_parser("test", add_help=False)
    test_p.add_argument("--image", default="ubuntu:24.04")
    test_p.add_argument("--scripts-dir", dest="scripts_dir", default="scripts")
    test_p.add_argument("--shell", action="store_true")
    test_p.add_argument("--network", default=None)
    test_p.add_argument("-h", "--help", action="store_true")

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
    elif args.command == "test":
        cmd_test(args)
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
