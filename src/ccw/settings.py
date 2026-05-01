"""Merge SessionStart and PostToolUse hooks into .claude/settings.json without clobbering."""

from __future__ import annotations

import json
from pathlib import Path

# Tools we allow without prompting. Includes WebFetch/WebSearch (so the agent
# can use the network freely) and mcp__github__* (so GitHub MCP calls don't
# prompt). The actual GitHub repo scope is set on github.com via the Claude
# GitHub App installation — settings.json cannot override that.
_DEFAULT_ALLOWED_TOOLS = [
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "WebFetch",
    "WebSearch",
    "mcp__github__*",
]

# Default sandbox: full outbound network. Users who want a tighter policy can
# override by setting their own `sandbox` block before running `ccweb init`,
# or by editing settings.json afterwards.
_DEFAULT_SANDBOX = {
    "enabled": True,
    "network": {
        "allowedDomains": ["*"],
    },
}


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
            "allow": list(_DEFAULT_ALLOWED_TOOLS),
        },
        "sandbox": json.loads(json.dumps(_DEFAULT_SANDBOX)),
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
    changes: list[str] = []

    # permissions.allow — extend with any defaults the user is missing.
    permissions = data.get("permissions")
    if not isinstance(permissions, dict):
        data["permissions"] = {"allow": list(_DEFAULT_ALLOWED_TOOLS)}
        changes.append("added permissions.allow")
    else:
        allow = permissions.get("allow")
        if not isinstance(allow, list):
            permissions["allow"] = list(_DEFAULT_ALLOWED_TOOLS)
            changes.append("added permissions.allow")
        else:
            added = [t for t in _DEFAULT_ALLOWED_TOOLS if t not in allow]
            if added:
                allow.extend(added)
                changes.append(f"extended permissions.allow ({', '.join(added)})")

    # sandbox — only add when missing. If the user has any sandbox block,
    # respect it (they've made an explicit choice).
    if "sandbox" not in data:
        data["sandbox"] = json.loads(json.dumps(_DEFAULT_SANDBOX))
        changes.append("added sandbox (network: *)")

    hooks = data.setdefault("hooks", {})

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
