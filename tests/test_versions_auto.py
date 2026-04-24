"""CLI + end-to-end tests for auto-detected tool versions flowing into setup.sh."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ccw.cli import cmd_init  # noqa: E402


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


def _init_args(**overrides) -> argparse.Namespace:
    base = dict(
        toolchains="all",
        extras="",
        scripts_dir="scripts",
        skills="",
        versions="",
        env_file="",
        force=True,
        dry_run=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class CmdInitAutoDetectsVersionsTests(unittest.TestCase):
    def test_tool_versions_pins_go_in_generated_setup(self):
        with _TmpRoot() as root:
            _write(root, ".tool-versions", "golang 1.23.4\n")
            cwd = Path.cwd()
            try:
                os.chdir(root)
                cmd_init(_init_args(toolchains="go"))
                setup = (root / "scripts" / "setup.sh").read_text()
                self.assertIn("1.23.4", setup)
                # Should not fall back to the default Go version when a pin
                # was detected.
                from ccw.sections import DEFAULT_VERSIONS

                default_go = DEFAULT_VERSIONS["go"]
                if default_go != "1.23.4":
                    self.assertNotIn(f"go{default_go}.linux", setup)
            finally:
                os.chdir(cwd)

    def test_explicit_versions_override_detected(self):
        with _TmpRoot() as root:
            _write(root, ".tool-versions", "golang 1.23.4\n")
            cwd = Path.cwd()
            try:
                os.chdir(root)
                cmd_init(_init_args(toolchains="go", versions="go=1.22.0"))
                setup = (root / "scripts" / "setup.sh").read_text()
                self.assertIn("1.22.0", setup)
                self.assertNotIn("1.23.4", setup)
            finally:
                os.chdir(cwd)

    def test_detected_pin_for_unselected_toolchain_is_harmless(self):
        # Zig is pinned in .tool-versions but zig isn't in --toolchains. We
        # should not crash and the resulting setup.sh should not install Zig.
        with _TmpRoot() as root:
            _write(root, ".tool-versions", "zig 0.14.0\n")
            cwd = Path.cwd()
            try:
                os.chdir(root)
                cmd_init(_init_args(toolchains="go"))
                setup = (root / "scripts" / "setup.sh").read_text()
                self.assertNotIn("Installing Zig", setup)
            finally:
                os.chdir(cwd)


class CmdInitE2ETest(unittest.TestCase):
    """End-to-end: a polyglot repo with .tool-versions + --toolchains auto."""

    def test_e2e_polyglot_with_tool_versions(self):
        with _TmpRoot() as root:
            # A realistic polyglot repo: Go + Terraform, both version-pinned
            # via asdf, detected automatically via marker files.
            _write(root, "go.mod", "module example.com/app\n\ngo 1.22\n")
            _write(root, "main.tf", 'provider "aws" {}\n')
            _write(
                root,
                ".tool-versions",
                "golang 1.23.4\nterraform 1.9.8\nnodejs 20.0.0\n",
            )
            cwd = Path.cwd()
            try:
                os.chdir(root)
                cmd_init(
                    _init_args(
                        toolchains="auto",
                        extras="auto",
                    )
                )
                setup = (root / "scripts" / "setup.sh").read_text()
                # Go pinned from .tool-versions
                self.assertIn("1.23.4", setup)
                # Terraform pinned from .tool-versions (cloud extra auto-detected
                # from main.tf)
                self.assertIn("1.9.8", setup)
                # nodejs pin ignored (not pinnable), but no crash
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
