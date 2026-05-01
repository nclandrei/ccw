"""Tests for the unrestricted network + GitHub MCP defaults in settings.json."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ccw.settings import merge_settings  # noqa: E402


def _read(root: Path) -> dict:
    return json.loads((root / ".claude" / "settings.json").read_text())


class FreshSettingsDefaultsTests(unittest.TestCase):
    """When no settings.json exists, defaults grant unrestricted network access."""

    def test_sandbox_network_wildcard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            merge_settings(root, "scripts")
            data = _read(root)
            self.assertEqual(
                data["sandbox"]["network"]["allowedDomains"],
                ["*"],
            )
            self.assertTrue(data["sandbox"]["enabled"])

    def test_permissions_allow_includes_web_and_github_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            merge_settings(root, "scripts")
            allow = _read(root)["permissions"]["allow"]
            for tool in ("WebFetch", "WebSearch", "mcp__github__*"):
                self.assertIn(tool, allow)

    def test_baseline_tools_still_present(self):
        # Adding new defaults must not remove the original allow list.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            merge_settings(root, "scripts")
            allow = _read(root)["permissions"]["allow"]
            for tool in ("Bash", "Read", "Write", "Edit", "Glob", "Grep"):
                self.assertIn(tool, allow)


class MergeSandboxTests(unittest.TestCase):
    def test_existing_sandbox_block_is_preserved(self):
        # If the user has explicitly chosen a tighter sandbox, keep it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            existing = {
                "sandbox": {
                    "enabled": True,
                    "network": {"allowedDomains": ["github.com"]},
                }
            }
            settings_path.write_text(json.dumps(existing))
            merge_settings(root, "scripts")
            data = _read(root)
            self.assertEqual(
                data["sandbox"]["network"]["allowedDomains"],
                ["github.com"],
            )

    def test_sandbox_added_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(json.dumps({"hooks": {}}))
            merge_settings(root, "scripts")
            data = _read(root)
            self.assertEqual(
                data["sandbox"]["network"]["allowedDomains"],
                ["*"],
            )


class MergePermissionsTests(unittest.TestCase):
    def test_existing_allow_list_is_extended_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            existing = {
                "permissions": {"allow": ["Bash", "CustomTool"]},
            }
            settings_path.write_text(json.dumps(existing))
            merge_settings(root, "scripts")
            allow = _read(root)["permissions"]["allow"]
            self.assertIn("CustomTool", allow)
            self.assertIn("Bash", allow)
            for tool in ("WebFetch", "WebSearch", "mcp__github__*"):
                self.assertIn(tool, allow)

    def test_allow_list_does_not_duplicate_existing_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            existing = {
                "permissions": {"allow": ["WebFetch", "Bash"]},
            }
            settings_path.write_text(json.dumps(existing))
            merge_settings(root, "scripts")
            allow = _read(root)["permissions"]["allow"]
            self.assertEqual(allow.count("WebFetch"), 1)
            self.assertEqual(allow.count("Bash"), 1)

    def test_missing_permissions_block_gets_full_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(json.dumps({"hooks": {}}))
            merge_settings(root, "scripts")
            allow = _read(root)["permissions"]["allow"]
            for tool in ("Bash", "WebFetch", "WebSearch", "mcp__github__*"):
                self.assertIn(tool, allow)


class IdempotencyTests(unittest.TestCase):
    def test_running_merge_twice_is_a_no_op_on_second_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            merge_settings(root, "scripts")
            first = _read(root)
            msg = merge_settings(root, "scripts")
            second = _read(root)
            self.assertEqual(first, second)
            self.assertIn("already configured", msg)


if __name__ == "__main__":
    unittest.main()
