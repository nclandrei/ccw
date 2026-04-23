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


class ChromiumSectionIsPipefailSafeTest(unittest.TestCase):
    """setup.sh runs under `set -euo pipefail`. A `X=$(find ... | head -1)`
    assignment on a missing directory exits non-zero via pipefail and kills
    the script. Every such pipe in setup_chromium must be guarded with `|| true`
    (or similar) to keep the script running on a fresh container."""

    def test_find_head_pipes_are_guarded(self):
        from ccw.sections import setup_chromium
        script = setup_chromium()
        for line in script.splitlines():
            if "find /root/.cache/ms-playwright" in line and "| head -1" in line:
                self.assertIn("|| true", line, f"Unguarded pipe will trip set -e: {line!r}")


class SetupShResilienceTest(unittest.TestCase):
    """setup.sh runs 10+ best-effort installers over the network. A single
    transient failure (DNS, 503, SSL) must not abort the whole script and
    prevent the env marker from being written — otherwise session-start
    re-runs setup.sh every session forever."""

    def setUp(self):
        self.setup_sh = build_setup_sh(set(ALL_TOOLCHAINS), set(ALL_EXTRAS))

    def test_header_does_not_use_errexit(self):
        # `set -e` kills the script on any non-zero exit. For a best-effort
        # installer, use -uo pipefail only.
        first_set = next(
            (line for line in self.setup_sh.splitlines() if line.startswith("set -")),
            None,
        )
        self.assertIsNotNone(first_set, "setup.sh must declare set options")
        self.assertNotIn("-e", first_set, f"setup.sh must not use errexit: {first_set!r}")

    def test_go_curl_pipe_is_guarded(self):
        # Look at every line that pipes into tar downloading Go
        for line in self.setup_sh.splitlines():
            if "go.dev/dl/go" in line and "tar" in line:
                self.assertTrue(
                    "|| " in line or self.setup_sh.count("Go download failed") > 0,
                    f"Go download pipeline should be guarded: {line!r}",
                )

    def test_zig_curl_pipe_is_guarded(self):
        for line in self.setup_sh.splitlines():
            if "ziglang.org" in line and "tar" in line:
                self.assertTrue(
                    "|| " in line or "Zig download failed" in self.setup_sh,
                    f"Zig download pipeline should be guarded: {line!r}",
                )

    def test_env_marker_written_even_when_installers_would_fail(self):
        # Even if a downloader exits non-zero, setup.sh must still reach the
        # marker block. The simplest way to express this: the marker block
        # must appear AFTER all downloaders and must NOT sit behind a guard
        # that skips on failure.
        self.assertIn("# === claude-code-setup ===", self.setup_sh)
        # And the marker block should not be conditioned on earlier success
        marker_idx = self.setup_sh.index("# === claude-code-setup ===")
        tail = self.setup_sh[marker_idx:]
        # The marker-writing code must run unconditionally (outside `|| true` scopes)
        self.assertIn("/etc/environment", tail)


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
