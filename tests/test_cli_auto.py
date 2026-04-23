"""Tests for the 'auto' keyword in --toolchains / --extras."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ccw.cli import _resolve_extras, _resolve_toolchains  # noqa: E402


class _TmpRoot:
    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        return Path(self._tmp.name)

    def __exit__(self, *exc):
        self._tmp.cleanup()


def _touch(root: Path, *relpaths: str) -> None:
    for rel in relpaths:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")


class ResolveToolchainsTests(unittest.TestCase):
    def test_all_returns_full_set(self):
        with _TmpRoot() as root:
            from ccw.sections import ALL_TOOLCHAINS
            self.assertEqual(_resolve_toolchains("all", root), set(ALL_TOOLCHAINS))

    def test_empty_string_returns_empty_set(self):
        with _TmpRoot() as root:
            self.assertEqual(_resolve_toolchains("", root), set())

    def test_explicit_list_returns_listed(self):
        with _TmpRoot() as root:
            self.assertEqual(_resolve_toolchains("node,go", root), {"node", "go"})

    def test_auto_on_empty_dir_returns_empty(self):
        with _TmpRoot() as root:
            self.assertEqual(_resolve_toolchains("auto", root), set())

    def test_auto_on_node_repo_returns_node_only(self):
        with _TmpRoot() as root:
            _touch(root, "package.json")
            self.assertEqual(_resolve_toolchains("auto", root), {"node"})

    def test_auto_on_polyglot_repo(self):
        with _TmpRoot() as root:
            _touch(root, "package.json", "go.mod", "Cargo.toml")
            self.assertEqual(_resolve_toolchains("auto", root), {"node", "go", "rust"})


class ResolveExtrasTests(unittest.TestCase):
    def test_all_returns_full_set(self):
        with _TmpRoot() as root:
            from ccw.sections import ALL_EXTRAS
            self.assertEqual(_resolve_extras("all", root), set(ALL_EXTRAS))

    def test_empty_string_returns_empty_set(self):
        with _TmpRoot() as root:
            self.assertEqual(_resolve_extras("", root), set())

    def test_auto_on_empty_dir_returns_empty(self):
        with _TmpRoot() as root:
            self.assertEqual(_resolve_extras("auto", root), set())

    def test_auto_detects_pnpm_from_lockfile(self):
        with _TmpRoot() as root:
            _touch(root, "pnpm-lock.yaml")
            self.assertIn("pnpm", _resolve_extras("auto", root))

    def test_auto_detects_docker_from_dockerfile(self):
        with _TmpRoot() as root:
            _touch(root, "Dockerfile")
            self.assertIn("docker", _resolve_extras("auto", root))


class CmdInitWiringTests(unittest.TestCase):
    """End-to-end: invoke cmd_init with auto in a temp project root and inspect outputs."""

    def test_auto_toolchains_node_only_writes_minimal_setup(self):
        import argparse
        from ccw.cli import cmd_init

        with _TmpRoot() as root:
            _touch(root, "package.json")
            cwd = Path.cwd()
            try:
                import os
                os.chdir(root)
                args = argparse.Namespace(
                    toolchains="auto",
                    extras="auto",
                    scripts_dir="scripts",
                    skills="",
                    versions="",
                    env_file="",
                    force=True,
                )
                cmd_init(args)
                setup = (root / "scripts" / "setup.sh").read_text()
                # Node-related summary check should be present
                self.assertIn("Node", setup)
                # Go should NOT be in the build since go.mod isn't present
                self.assertNotIn("Installing Go", setup)
                self.assertNotIn("Installing Rust", setup)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
