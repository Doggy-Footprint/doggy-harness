import builtins
import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_ruleset_setup import RulesetCase, git

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "installer" / "harness.py"
NOT_ASKED = "(not asked: stdin is a socket; counted as no. Pipe the answer in to give one.)"


def load_installer_module():
    sys.path.insert(0, str(REPO_ROOT / "installer"))
    import harness as installer_module

    return installer_module


class AskTests(unittest.TestCase):
    def setUp(self):
        self.module = load_installer_module()

    def ask(self, stdin, prompt="Go? [y/N] "):
        output = io.StringIO()
        with mock.patch("sys.stdin", stdin), contextlib.redirect_stdout(output):
            answer = self.module.ask(prompt)
        return answer, output.getvalue()

    def test_a_socket_on_stdin_is_not_read_and_counts_as_no(self):
        reader, writer = socket.socketpair()
        self.addCleanup(reader.close)
        self.addCleanup(writer.close)
        stdin = reader.makefile("r")
        self.addCleanup(stdin.close)
        with mock.patch.object(builtins, "input", side_effect=AssertionError("read the socket")):
            answer, output = self.ask(stdin)
        self.assertEqual(answer, "")
        self.assertEqual(output, "Go? [y/N] " + NOT_ASKED + "\n")

    def test_a_pipe_on_stdin_is_read(self):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"y\n")
        os.close(write_fd)
        stdin = os.fdopen(read_fd, "r")
        self.addCleanup(stdin.close)
        answer, output = self.ask(stdin)
        self.assertEqual(answer, "y")
        self.assertNotIn("not asked", output)

    def test_a_regular_file_on_stdin_is_read(self):
        with tempfile.TemporaryFile("w+") as stdin:
            stdin.write("n\n")
            stdin.seek(0)
            answer, output = self.ask(stdin)
        self.assertEqual(answer, "n")
        self.assertNotIn("not asked", output)

    def test_an_in_memory_stdin_is_read(self):
        answer, output = self.ask(io.StringIO("y\n"))
        self.assertEqual(answer, "y")
        self.assertNotIn("not asked", output)


class SocketStdinRuns(RulesetCase):
    def run_on_socket(self, *args, path=None):
        held, child = socket.socketpair()
        self.addCleanup(held.close)
        env = dict(os.environ, FAKE_GH_LOG=str(self.log))
        env["HARNESS_PREFERENCES_FILE"] = str(self.root / "preferences.json")
        env["PATH"] = path if path is not None else f"{self.bindir}{os.pathsep}{os.environ['PATH']}"
        try:
            return subprocess.run([sys.executable, str(INSTALLER), *args], env=env, stdin=child.fileno(),
                                  capture_output=True, text=True, timeout=120)
        finally:
            child.close()

    def test_install_skips_the_ruleset_question_and_lists_the_command(self):
        result = self.run_on_socket("install", str(self.repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("until they include them. [y/N] " + NOT_ASKED, result.stdout)
        self.assertEqual(self.writes(), [])
        self.assertIn("ruleset not applied (not confirmed)", self.section(result.stdout, "manual review"))

    def test_install_skips_the_gitignore_question_and_stops(self):
        (self.repo / ".gitignore").write_text(".harness/\n")
        result = self.run_on_socket("install", str(self.repo), "--no-ci")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Add .gitignore exceptions for these harness paths and continue? [y/N] " + NOT_ASKED, result.stdout)
        self.assertIn("ignored harness paths: .gitignore exceptions were not confirmed",
                      self.section(result.stdout, "conflict"))
        self.assertEqual((self.repo / ".gitignore").read_text(), ".harness/\n")

    def test_update_skips_the_migration_question_and_stops(self):
        installed = self.run_on_socket("install", str(self.repo), "--no-ci")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "install")
        manifest = self.repo / ".harness" / "manifest.json"
        data = json.loads(manifest.read_text())
        data["version"] = "0.55.1"
        manifest.write_text(json.dumps(data, indent=2) + "\n")

        result = self.run_on_socket("update", str(self.repo), "--no-ci", "--no-commit")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Apply migration 0.56.0 (", result.stdout)
        self.assertIn(NOT_ASKED, result.stdout)
        self.assertIn("MigrationDeclined: migration was not confirmed", self.section(result.stdout, "conflict"))
        self.assertEqual(json.loads(manifest.read_text())["version"], "0.55.1")


if __name__ == "__main__":
    unittest.main()
