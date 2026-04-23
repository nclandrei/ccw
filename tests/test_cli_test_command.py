"""Tests for the `ccweb test` subcommand (local Docker validation)."""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ccw import cli  # noqa: E402


class BuildDockerTestArgsTests(unittest.TestCase):
    """Pure function that assembles the `docker run` argv."""

    def test_exists(self):
        self.assertTrue(hasattr(cli, "build_docker_test_args"))

    def test_default_runs_setup_then_diagnose(self):
        argv = cli.build_docker_test_args(
            image="ubuntu:24.04",
            project_root=Path("/repo"),
            scripts_dir="scripts",
        )
        self.assertEqual(argv[0], "docker")
        self.assertEqual(argv[1], "run")
        self.assertIn("--rm", argv)
        # Mount the project root read-only into /workspace
        self.assertIn("-v", argv)
        self.assertIn("/repo:/workspace:ro", argv)
        # Workdir
        self.assertIn("-w", argv)
        self.assertIn("/workspace", argv)
        # Propagate CLAUDE_CODE_REMOTE so session-start-style code paths behave
        self.assertIn("-e", argv)
        self.assertIn("CLAUDE_CODE_REMOTE=true", argv)
        # Image appears before the bash -c payload
        self.assertIn("ubuntu:24.04", argv)
        # Last three args: bash -c <payload>
        self.assertEqual(argv[-3], "bash")
        self.assertEqual(argv[-2], "-c")
        payload = argv[-1]
        self.assertIn("scripts/setup.sh", payload)
        self.assertIn("scripts/diagnose.sh", payload)
        # setup must happen before diagnose
        self.assertLess(payload.index("setup.sh"), payload.index("diagnose.sh"))

    def test_custom_scripts_dir(self):
        argv = cli.build_docker_test_args(
            image="ubuntu:24.04",
            project_root=Path("/repo"),
            scripts_dir="ci/scripts",
        )
        payload = argv[-1]
        self.assertIn("ci/scripts/setup.sh", payload)
        self.assertIn("ci/scripts/diagnose.sh", payload)

    def test_custom_image(self):
        argv = cli.build_docker_test_args(
            image="ubuntu:22.04",
            project_root=Path("/repo"),
            scripts_dir="scripts",
        )
        self.assertIn("ubuntu:22.04", argv)

    def test_network_flag_is_injected(self):
        argv = cli.build_docker_test_args(
            image="ubuntu:24.04",
            project_root=Path("/repo"),
            scripts_dir="scripts",
            network="host",
        )
        # --network host must appear as two consecutive tokens
        idx = argv.index("--network")
        self.assertEqual(argv[idx + 1], "host")

    def test_network_is_omitted_by_default(self):
        argv = cli.build_docker_test_args(
            image="ubuntu:24.04",
            project_root=Path("/repo"),
            scripts_dir="scripts",
        )
        self.assertNotIn("--network", argv)

    def test_shell_mode_skips_payload(self):
        argv = cli.build_docker_test_args(
            image="ubuntu:24.04",
            project_root=Path("/repo"),
            scripts_dir="scripts",
            shell=True,
        )
        # In shell mode we want an interactive bash, no -c payload
        self.assertIn("-it", argv)
        self.assertEqual(argv[-1], "bash")
        self.assertNotIn("-c", argv)


class CmdTestDispatchTests(unittest.TestCase):
    """`ccweb test` should validate prerequisites before invoking docker."""

    def test_errors_when_scripts_missing(self):
        with mock.patch.object(cli, "Path") as mock_path_cls:
            fake_root = mock.MagicMock()
            mock_path_cls.cwd.return_value = fake_root
            # scripts/setup.sh does not exist
            fake_root.__truediv__.return_value.__truediv__.return_value.exists.return_value = False

            args = mock.MagicMock(scripts_dir="scripts", image="ubuntu:24.04", shell=False, network=None)
            with self.assertRaises(SystemExit) as ctx:
                cli.cmd_test(args)
            self.assertNotEqual(ctx.exception.code, 0)

    def test_errors_when_docker_not_installed(self):
        # Build a temp repo with the scripts present
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "setup.sh").write_text("#!/bin/bash\n")
            (scripts_dir / "diagnose.sh").write_text("#!/bin/bash\n")

            args = mock.MagicMock(scripts_dir="scripts", image="ubuntu:24.04", shell=False, network=None)
            with mock.patch.object(cli.Path, "cwd", return_value=tmp_path), \
                 mock.patch.object(cli.shutil, "which", return_value=None):
                with self.assertRaises(SystemExit) as ctx:
                    cli.cmd_test(args)
                self.assertNotEqual(ctx.exception.code, 0)

    def test_execs_docker_when_ready(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "setup.sh").write_text("#!/bin/bash\n")
            (scripts_dir / "diagnose.sh").write_text("#!/bin/bash\n")

            args = mock.MagicMock(scripts_dir="scripts", image="ubuntu:24.04", shell=False, network=None)
            with mock.patch.object(cli.Path, "cwd", return_value=tmp_path), \
                 mock.patch.object(cli.shutil, "which", return_value="/usr/bin/docker"), \
                 mock.patch.object(cli.os, "execvp") as mock_exec, \
                 redirect_stdout(io.StringIO()):
                cli.cmd_test(args)
                mock_exec.assert_called_once()
                prog, argv = mock_exec.call_args.args
                self.assertEqual(prog, "docker")
                self.assertEqual(argv[0], "docker")
                self.assertIn("ubuntu:24.04", argv)


class HelpTextMentionsTestTests(unittest.TestCase):
    """The HELP_TEXT contract: `ccweb test` must be documented."""

    def test_help_mentions_test_subcommand(self):
        self.assertIn("ccweb test", cli.HELP_TEXT)

    def test_help_mentions_docker(self):
        self.assertIn("Docker", cli.HELP_TEXT)


class ArgparseAcceptsTestTests(unittest.TestCase):
    """The CLI's argparse plumbing should route `test` to cmd_test."""

    def test_test_subcommand_parses(self):
        # Simulate argv and check that cli.main dispatches to cmd_test
        with mock.patch.object(sys, "argv", ["ccweb", "test"]), \
             mock.patch.object(cli, "cmd_test") as mock_cmd_test:
            cli.main()
            mock_cmd_test.assert_called_once()

    def test_test_subcommand_accepts_image_flag(self):
        with mock.patch.object(sys, "argv", ["ccweb", "test", "--image", "ubuntu:22.04"]), \
             mock.patch.object(cli, "cmd_test") as mock_cmd_test:
            cli.main()
            args = mock_cmd_test.call_args.args[0]
            self.assertEqual(args.image, "ubuntu:22.04")

    def test_test_subcommand_accepts_network_flag(self):
        with mock.patch.object(sys, "argv", ["ccweb", "test", "--network", "host"]), \
             mock.patch.object(cli, "cmd_test") as mock_cmd_test:
            cli.main()
            args = mock_cmd_test.call_args.args[0]
            self.assertEqual(args.network, "host")

    def test_test_subcommand_accepts_shell_flag(self):
        with mock.patch.object(sys, "argv", ["ccweb", "test", "--shell"]), \
             mock.patch.object(cli, "cmd_test") as mock_cmd_test:
            cli.main()
            args = mock_cmd_test.call_args.args[0]
            self.assertTrue(args.shell)


if __name__ == "__main__":
    unittest.main()
