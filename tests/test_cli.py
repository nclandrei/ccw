"""Tests for ccw.cli — dry-run and show subcommand."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

# Make src/ importable without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ccw import cli  # noqa: E402


class DryRunInitTests(unittest.TestCase):
    """`ccweb init --dry-run` should print scripts but write nothing."""

    def _run_init(self, tmp: Path, **overrides) -> str:
        defaults = dict(
            toolchains="node",
            extras="",
            scripts_dir="scripts",
            skills=".claude/skills",
            versions="",
            env_file="",
            force=False,
            dry_run=True,
        )
        defaults.update(overrides)
        ns = mock.Mock(**defaults)
        buf = io.StringIO()
        cwd_before = Path.cwd()
        try:
            import os
            os.chdir(tmp)
            with redirect_stdout(buf):
                cli.cmd_init(ns)
        finally:
            os.chdir(cwd_before)
        return buf.getvalue()

    def test_dry_run_does_not_create_scripts_dir(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._run_init(tmp)
            self.assertFalse((tmp / "scripts").exists(),
                             "dry-run must not create scripts/ directory")

    def test_dry_run_does_not_write_settings_json(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._run_init(tmp)
            self.assertFalse((tmp / ".claude" / "settings.json").exists(),
                             "dry-run must not write settings.json")

    def test_dry_run_prints_setup_sh_content(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out = self._run_init(tmp)
            # The setup script shebang and marker should appear in output
            self.assertIn("#!/bin/bash", out)
            self.assertIn("setup.sh", out)

    def test_dry_run_prints_session_start_sh_content(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out = self._run_init(tmp)
            self.assertIn("session-start.sh", out)

    def test_dry_run_prints_diagnose_sh_content(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out = self._run_init(tmp)
            self.assertIn("diagnose.sh", out)


class ShowSetupCommandTests(unittest.TestCase):
    """`ccweb show setup` prints setup.sh content without side effects."""

    def test_show_setup_prints_shebang_and_setup_marker(self):
        ns = mock.Mock(
            toolchains="all",
            extras="all",
            versions="",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.cmd_show_setup(ns)
        out = buf.getvalue()
        self.assertIn("#!/bin/bash", out)
        self.assertIn("Setup complete", out)

    def test_show_setup_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ns = mock.Mock(toolchains="node", extras="", versions="")
            import os
            cwd_before = Path.cwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    cli.cmd_show_setup(ns)
            finally:
                os.chdir(cwd_before)
            # Nothing in the tmp dir should have been created
            self.assertEqual(list(tmp.iterdir()), [])


class CliParsingTests(unittest.TestCase):
    """The `init --dry-run` flag and `show setup` command must parse."""

    def test_init_accepts_dry_run_flag(self):
        with mock.patch.object(sys, "argv", ["ccweb", "init", "--dry-run",
                                             "--toolchains", "node", "--extras", ""]):
            with mock.patch.object(cli, "cmd_init") as m:
                cli.main()
                m.assert_called_once()
                ns = m.call_args[0][0]
                self.assertTrue(ns.dry_run)

    def test_init_defaults_dry_run_false(self):
        with mock.patch.object(sys, "argv", ["ccweb", "init",
                                             "--toolchains", "node", "--extras", ""]):
            with mock.patch.object(cli, "cmd_init") as m:
                cli.main()
                ns = m.call_args[0][0]
                self.assertFalse(ns.dry_run)

    def test_show_setup_dispatches(self):
        with mock.patch.object(sys, "argv", ["ccweb", "show", "setup"]):
            with mock.patch.object(cli, "cmd_show_setup") as m:
                cli.main()
                m.assert_called_once()


if __name__ == "__main__":
    unittest.main()
