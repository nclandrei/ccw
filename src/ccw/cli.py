"""ccw CLI — Bootstrap Claude Code web environments."""

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
    items = {s.strip().lower() for s in value.split(",")}
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
    print()

    # Generate scripts
    _write_script(
        scripts_path / "setup.sh",
        build_setup_sh(toolchains, extras),
        force,
    )
    _write_script(
        scripts_path / "session-start.sh",
        build_session_start_sh(toolchains, extras, scripts_dir),
        force,
    )
    _write_script(
        scripts_path / "diagnose.sh",
        build_diagnose_sh(toolchains, extras),
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
    print("  5. Run `ccw doctor` to verify everything is working")


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


DESCRIPTION = "ccw — Bootstrap Claude Code web environments."

EPILOG = textwrap.dedent("""\
    examples:
      uvx ccw init                                    Install everything
      uvx ccw init --toolchains node,python           Just Node + Python
      uvx ccw init --toolchains go --extras gh        Go project with gh CLI
      uvx ccw init --force                            Overwrite existing scripts

    generated files:
      scripts/setup.sh           Paste into claude.ai/code "Setup script" field,
                                 or let session-start.sh auto-run it on first session.
      scripts/session-start.sh   SessionStart hook — detects lockfiles, installs deps.
      scripts/diagnose.sh        Runtime diagnostics — run anytime to check status.
      .claude/settings.json      Hooks + permissions (merges with existing, never clobbers).

    after running `ccw init`:
      1. Commit the generated files
      2. Push to your repo
      3. Start a Claude Code web session — session-start.sh auto-provisions the VM
      4. Run `ccw doctor` to verify everything is working

    more info: https://nclandrei.github.io/ccw
""")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ccw",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"ccw {__version__}"
    )

    sub = parser.add_subparsers(dest="command")

    # init
    init_p = sub.add_parser(
        "init",
        help="Generate setup scripts for the current project",
        description="Generate setup.sh, session-start.sh, diagnose.sh, and wire settings.json.",
    )
    init_p.add_argument(
        "--toolchains",
        default="all",
        metavar="TC",
        help="Comma-separated: node,python,go,rust,ruby,java (default: all)",
    )
    init_p.add_argument(
        "--extras",
        default="all",
        metavar="EX",
        help="Comma-separated: gh,uv,pnpm,yarn,bun,browser (default: all)",
    )
    init_p.add_argument(
        "--scripts-dir",
        default="scripts",
        metavar="DIR",
        help="Output directory for scripts (default: scripts)",
    )
    init_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting",
    )

    # doctor
    sub.add_parser(
        "doctor",
        help="Check if the environment is correctly configured",
        description="Run diagnostics on the current environment.",
    )

    args = parser.parse_args()
    if args.command == "init":
        cmd_init(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
