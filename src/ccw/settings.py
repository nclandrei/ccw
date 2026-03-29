"""Merge SessionStart hook into .claude/settings.json without clobbering."""

from __future__ import annotations

import json
from pathlib import Path


def _default_settings(scripts_dir: str) -> dict:
    return {
        "permissions": {
            "allow": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
        },
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'"$CLAUDE_PROJECT_DIR"/{scripts_dir}/session-start.sh',
                        }
                    ],
                }
            ]
        },
    }


def _hook_entry(scripts_dir: str) -> dict:
    return {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": f'"$CLAUDE_PROJECT_DIR"/{scripts_dir}/session-start.sh',
            }
        ],
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

    # Check if SessionStart hook already exists
    hooks = data.get("hooks", {})
    session_hooks = hooks.get("SessionStart", [])

    if session_hooks:
        # Validate matcher — fix common "startup" bug
        changed = False
        for entry in session_hooks:
            if entry.get("matcher") == "startup":
                entry["matcher"] = ""
                changed = True
        if changed:
            data["hooks"]["SessionStart"] = session_hooks
            settings_path.write_text(json.dumps(data, indent=2) + "\n")
            return f'Fixed matcher in {settings_path} ("startup" -> "")'
        return f"SessionStart hook already configured in {settings_path}"

    # Add the hook
    if "hooks" not in data:
        data["hooks"] = {}
    data["hooks"]["SessionStart"] = [_hook_entry(scripts_dir)]
    settings_path.write_text(json.dumps(data, indent=2) + "\n")
    return f"Added SessionStart hook to {settings_path}"
