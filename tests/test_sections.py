"""Tests for ccw.sections — focused on the always-on CLI tools baseline."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make src/ importable without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ccw.sections import (  # noqa: E402
    ALL_EXTRAS,
    ALL_TOOLCHAINS,
    build_diagnose_sh,
    build_setup_sh,
)


class AllExtrasTests(unittest.TestCase):
    """gh and sqlite are now always-on, so they should not be gated as extras."""

    def test_gh_is_not_an_extra(self):
        self.assertNotIn("gh", ALL_EXTRAS)

    def test_sqlite_is_not_an_extra(self):
        self.assertNotIn("sqlite", ALL_EXTRAS)

    def test_remaining_extras_are_stack_specific(self):
        # These still have a legitimate opt-out reason
        for extra in ("browser", "docker", "postgres", "redis", "uv", "pnpm", "yarn", "bun"):
            self.assertIn(extra, ALL_EXTRAS)


class AlwaysOnAptPackagesTests(unittest.TestCase):
    """The apt baseline should install these unconditionally — even with empty sets."""

    def setUp(self):
        self.setup_sh = build_setup_sh(set(), set())

    def test_existing_baseline_still_present(self):
        for pkg in ("jq", "curl", "wget", "ripgrep", "fd-find", "bat", "tree", "htop"):
            self.assertIn(pkg, self.setup_sh, f"{pkg} missing from apt baseline")

    def test_new_apt_baseline_installed(self):
        for pkg in (
            "shellcheck",
            "shfmt",
            "pandoc",
            "git-lfs",
            "unzip",
            "zip",
            "rsync",
            "sqlite3",
        ):
            self.assertIn(pkg, self.setup_sh, f"{pkg} should be in apt baseline")


class AlwaysOnGithubBinariesTests(unittest.TestCase):
    """duckdb, yq, and gh ship as GitHub-release binaries and should always install."""

    def setUp(self):
        self.setup_sh = build_setup_sh(set(), set())

    def test_gh_installed_unconditionally(self):
        # gh CLI is no longer gated behind an extra
        self.assertIn("gh CLI", self.setup_sh)
        self.assertIn("cli/cli/releases", self.setup_sh)

    def test_duckdb_installed_unconditionally(self):
        self.assertIn("duckdb", self.setup_sh.lower())
        self.assertIn("duckdb/duckdb/releases", self.setup_sh)

    def test_yq_installed_unconditionally(self):
        self.assertIn("yq", self.setup_sh)
        self.assertIn("mikefarah/yq/releases", self.setup_sh)


class DiagnoseAlwaysOnChecksTests(unittest.TestCase):
    """diagnose.sh should check for the always-on tools without needing any extras."""

    def setUp(self):
        self.diagnose_sh = build_diagnose_sh(set(), set())

    def test_always_on_tools_checked(self):
        for tool in ("jq", "curl", "gh", "duckdb", "yq", "shellcheck", "sqlite3", "pandoc"):
            self.assertIn(tool, self.diagnose_sh, f"diagnose.sh should check {tool}")


class FullBuildSmokeTest(unittest.TestCase):
    """Build with every toolchain and extra — should not raise or produce an empty script."""

    def test_full_build_setup(self):
        script = build_setup_sh(set(ALL_TOOLCHAINS), set(ALL_EXTRAS))
        self.assertIn("#!/bin/bash", script)
        self.assertIn("Setup complete", script)

    def test_full_build_diagnose(self):
        script = build_diagnose_sh(set(ALL_TOOLCHAINS), set(ALL_EXTRAS))
        self.assertIn("#!/bin/bash", script)
        self.assertIn("Done.", script)


if __name__ == "__main__":
    unittest.main()
