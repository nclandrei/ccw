"""Merge SessionStart and PostToolUse hooks into .claude/settings.json without clobbering."""

from __future__ import annotations

import json
from pathlib import Path


def _session_start_entry(scripts_dir: str) -> dict:
    return {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": f'"$CLAUDE_PROJECT_DIR"/{scripts_dir}/session-start.sh',
            }
        ],
    }


def _post_tool_use_entry(scripts_dir: str) -> dict:
    return {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
            {
                "type": "command",
                "command": f'"$CLAUDE_PROJECT_DIR"/{scripts_dir}/post-tool-use.sh',
            }
        ],
    }


def _default_settings(scripts_dir: str) -> dict:
    return {
        "permissions": {
            "allow": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
        },
        "hooks": {
            "SessionStart": [_session_start_entry(scripts_dir)],
            "PostToolUse": [_post_tool_use_entry(scripts_dir)],
        },
    }


def merge_settings(project_root: Path, scripts_dir: str) -> str:
    """Read, merge, and write .claude/settings.json. Returns a status message."""
    settings_path = project_root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if not settings_path.exists():
        settings_path.write_text(
            json.dumps(_default_settings(scripts_dir), indent=2) + "\n"
        )
        return f"Created {settings_path}"

    data = json.loads(settings_path.read_text())
    hooks = data.setdefault("hooks", {})
    changes: list[str] = []

    # SessionStart — fix legacy "startup" matcher, or add if missing
    session_hooks = hooks.get("SessionStart", [])
    if session_hooks:
        for entry in session_hooks:
            if entry.get("matcher") == "startup":
                entry["matcher"] = ""
                changes.append('fixed SessionStart matcher ("startup" -> "")')
    else:
        hooks["SessionStart"] = [_session_start_entry(scripts_dir)]
        changes.append("added SessionStart hook")

    # PostToolUse — add only if not already configured
    if not hooks.get("PostToolUse"):
        hooks["PostToolUse"] = [_post_tool_use_entry(scripts_dir)]
        changes.append("added PostToolUse hook")

    if not changes:
        return f"Hooks already configured in {settings_path}"

    settings_path.write_text(json.dumps(data, indent=2) + "\n")
    return f"Updated {settings_path}: {', '.join(changes)}"
