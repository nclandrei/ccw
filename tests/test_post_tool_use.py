"""Tests for the PostToolUse formatter/linter hook."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ccw.sections import build_post_tool_use_sh  # noqa: E402
from ccw.settings import merge_settings  # noqa: E402


class BuildPostToolUseTests(unittest.TestCase):
    """post-tool-use.sh should dispatch to the right formatter per file extension."""

    def setUp(self):
        self.script = build_post_tool_use_sh()

    def test_has_bash_shebang(self):
        self.assertTrue(self.script.startswith("#!/bin/bash"))

    def test_reads_file_path_from_stdin_json(self):
        # Claude Code sends the hook payload as JSON on stdin.
        self.assertIn("file_path", self.script)
        self.assertIn("jq", self.script)

    def test_runs_ruff_for_python_files(self):
        self.assertIn("ruff", self.script)
        self.assertIn(".py", self.script)

    def test_runs_prettier_for_web_files(self):
        self.assertIn("prettier", self.script)
        for ext in (".js", ".ts", ".json", ".md", ".css"):
            self.assertIn(ext, self.script, f"prettier should handle {ext}")

    def test_runs_gofmt_for_go_files(self):
        self.assertIn("gofmt", self.script)
        self.assertIn(".go", self.script)

    def test_runs_rustfmt_for_rust_files(self):
        self.assertIn("rustfmt", self.script)
        self.assertIn(".rs", self.script)

    def test_runs_zig_fmt_for_zig_files(self):
        self.assertIn("zig fmt", self.script)
        self.assertIn(".zig", self.script)

    def test_runs_mix_format_for_elixir_files(self):
        self.assertIn("mix format", self.script)
        self.assertIn(".ex", self.script)
        self.assertIn(".exs", self.script)

    def test_runs_shfmt_for_shell_files(self):
        self.assertIn("shfmt", self.script)
        self.assertIn(".sh", self.script)
        self.assertIn(".bash", self.script)

    def test_deno_fmt_fallback_for_web_files(self):
        # If prettier is not available, deno fmt handles JS/TS/JSON/MD too.
        self.assertIn("deno fmt", self.script)

    def test_tool_presence_guarded(self):
        # Formatters may not be installed in every project — must be guarded.
        self.assertIn("command -v", self.script)

    def test_hook_always_exits_zero(self):
        # A non-zero exit would block the agent — never do that.
        self.assertIn("exit 0", self.script)

    def test_hook_skips_when_no_file_path(self):
        # Tools like Bash have no file_path — hook must no-op gracefully.
        self.assertRegex(self.script, r'(-z\s+"?\$?\{?FILE|\[\s+-z)')


class MergeSettingsPostToolUseTests(unittest.TestCase):
    """merge_settings should wire a PostToolUse hook alongside SessionStart."""

    def test_new_settings_get_post_tool_use_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            merge_settings(root, "scripts")
            data = json.loads((root / ".claude" / "settings.json").read_text())
            self.assertIn("PostToolUse", data["hooks"])
            entries = data["hooks"]["PostToolUse"]
            self.assertEqual(len(entries), 1)
            matcher = entries[0]["matcher"]
            self.assertIn("Edit", matcher)
            self.assertIn("Write", matcher)
            command = entries[0]["hooks"][0]["command"]
            self.assertIn("post-tool-use.sh", command)
            self.assertIn("scripts", command)

    def test_existing_post_tool_use_hook_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            existing = {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "scripts/session-start.sh",
                                }
                            ],
                        }
                    ],
                    "PostToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "echo hi"}],
                        }
                    ],
                }
            }
            settings_path.write_text(json.dumps(existing))
            merge_settings(root, "scripts")
            data = json.loads(settings_path.read_text())
            self.assertEqual(len(data["hooks"]["PostToolUse"]), 1)
            self.assertEqual(data["hooks"]["PostToolUse"][0]["matcher"], "Bash")

    def test_post_tool_use_added_when_session_start_exists(self):
        # If the user has SessionStart wired but no PostToolUse, add ours.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            existing = {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "scripts/session-start.sh",
                                }
                            ],
                        }
                    ],
                }
            }
            settings_path.write_text(json.dumps(existing))
            merge_settings(root, "scripts")
            data = json.loads(settings_path.read_text())
            self.assertIn("PostToolUse", data["hooks"])
            self.assertIn(
                "post-tool-use.sh",
                data["hooks"]["PostToolUse"][0]["hooks"][0]["command"],
            )


if __name__ == "__main__":
    unittest.main()
