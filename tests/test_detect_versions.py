"""Tests for ccw.detect.detect_versions — auto-detecting tool pins from version files.

Supported files:
  .tool-versions      asdf/mise multi-tool (lines like `golang 1.22.0`)
  .go-version         single-line Go version
  .terraform-version  single-line Terraform version
  .nvmrc              read but silently ignored (node is pre-installed, not pinnable)
  .python-version     read but silently ignored (python is pre-installed, not pinnable)
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ccw.detect import detect_versions  # noqa: E402


class _TmpRoot:
    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        return Path(self._tmp.name)

    def __exit__(self, *exc):
        self._tmp.cleanup()


def _write(root: Path, relpath: str, content: str) -> None:
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


class DetectVersionsTests(unittest.TestCase):
    def test_empty_directory_detects_nothing(self):
        with _TmpRoot() as root:
            self.assertEqual(detect_versions(root), {})

    def test_tool_versions_golang_alias_maps_to_go(self):
        with _TmpRoot() as root:
            _write(root, ".tool-versions", "golang 1.22.0\n")
            self.assertEqual(detect_versions(root), {"go": "1.22.0"})

    def test_tool_versions_go_alias_maps_to_go(self):
        with _TmpRoot() as root:
            _write(root, ".tool-versions", "go 1.22.0\n")
            self.assertEqual(detect_versions(root), {"go": "1.22.0"})

    def test_tool_versions_multiple_known_tools(self):
        with _TmpRoot() as root:
            _write(
                root,
                ".tool-versions",
                "golang 1.22.0\nzig 0.14.0\nterraform 1.9.8\nkubectl 1.31.2\n",
            )
            self.assertEqual(
                detect_versions(root),
                {
                    "go": "1.22.0",
                    "zig": "0.14.0",
                    "terraform": "1.9.8",
                    "kubectl": "1.31.2",
                },
            )

    def test_tool_versions_unpinnable_tools_ignored(self):
        # nodejs/python are pre-installed on the VM and not in DEFAULT_VERSIONS.
        # They must be silently ignored rather than raising.
        with _TmpRoot() as root:
            _write(
                root,
                ".tool-versions",
                "nodejs 20.0.0\npython 3.12.0\nruby 3.3.0\n",
            )
            self.assertEqual(detect_versions(root), {})

    def test_tool_versions_comments_and_blanks_ignored(self):
        with _TmpRoot() as root:
            _write(
                root,
                ".tool-versions",
                "# pin go\ngolang 1.22.0\n\n# trailing\n",
            )
            self.assertEqual(detect_versions(root), {"go": "1.22.0"})

    def test_tool_versions_extra_whitespace_tolerated(self):
        with _TmpRoot() as root:
            _write(root, ".tool-versions", "  golang   1.22.0  \n")
            self.assertEqual(detect_versions(root), {"go": "1.22.0"})

    def test_tool_versions_garbage_line_ignored(self):
        with _TmpRoot() as root:
            _write(root, ".tool-versions", "golang\ngolang 1.22.0\n")
            self.assertEqual(detect_versions(root), {"go": "1.22.0"})

    def test_go_version_file(self):
        with _TmpRoot() as root:
            _write(root, ".go-version", "1.23.4\n")
            self.assertEqual(detect_versions(root), {"go": "1.23.4"})

    def test_terraform_version_file(self):
        with _TmpRoot() as root:
            _write(root, ".terraform-version", "1.9.8\n")
            self.assertEqual(detect_versions(root), {"terraform": "1.9.8"})

    def test_nvmrc_is_read_but_does_not_yield_a_pin(self):
        with _TmpRoot() as root:
            _write(root, ".nvmrc", "20.0.0\n")
            self.assertEqual(detect_versions(root), {})

    def test_python_version_is_read_but_does_not_yield_a_pin(self):
        with _TmpRoot() as root:
            _write(root, ".python-version", "3.12.0\n")
            self.assertEqual(detect_versions(root), {})

    def test_dedicated_version_file_wins_over_tool_versions(self):
        # If both .tool-versions and .go-version are present, prefer the
        # dedicated single-tool file (it's more specific and asdf applies it
        # at a higher precedence when both exist).
        with _TmpRoot() as root:
            _write(root, ".tool-versions", "golang 1.22.0\n")
            _write(root, ".go-version", "1.23.4\n")
            self.assertEqual(detect_versions(root), {"go": "1.23.4"})

    def test_only_first_tool_value_used_if_multiple_versions_listed(self):
        # asdf allows space-separated fallbacks (`golang 1.22.0 1.21.0`);
        # we pin to the first (most preferred) value.
        with _TmpRoot() as root:
            _write(root, ".tool-versions", "golang 1.22.0 1.21.0\n")
            self.assertEqual(detect_versions(root), {"go": "1.22.0"})


if __name__ == "__main__":
    unittest.main()
