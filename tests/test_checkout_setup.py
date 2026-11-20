import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

import skill_text
from checkout_box import (
    BUN, JS_CREATE, JS_TOOLS, M_HOOKS, NPM, PDM, PNPM, POETRY, PY_CREATE, PY_TOOLS, S_NONE, UV,
    YARN, CheckoutCase, call, pyproject_text, m_failed, m_manual, m_nomanager, m_retry, m_running_pattern, m_start, s_failed,
    s_manual, s_nolock, s_nomanager, s_off, s_pending, s_runnable, s_running_pattern, s_settled, sha,
)
from test_installer import REPO_ROOT, InstallerTestCase, init_repo, run_git, run_installer

RID = "49bafb302bb6593c"
HOOK_LIMIT = 3.0


def make_py_tools(repo, names=PY_TOOLS):
    for name in names:
        (repo / ".venv" / "lib" / "python3.12" / "site-packages" / name).mkdir(parents=True)


def make_js_tools(repo, names=JS_TOOLS):
    for name in names:
        directory = repo / "node_modules" / name
        directory.mkdir(parents=True)
        (directory / "package.json").write_text("{}\n")


def make_unrelated_node_modules(repo):
    directory = repo / "node_modules" / "left-pad"
    directory.mkdir(parents=True)
    (directory / "package.json").write_text("{}\n")


def draft_rules(repo):
    root = repo / ".harness" / "skills" / "doggy-workflow"
    names = [skill_text.entry_name(e) for e in json.loads((root / "phases.json").read_text())["draft"]]
    return "\n".join((root / "phases" / f"{name}.md").read_text() for name in names)


def tree(path):
    return sorted(str(p.relative_to(path)) for p in Path(path).rglob("*") if "__pycache__" not in p.parts)


class TestNeedStates(CheckoutCase):
    def uv_checkout(self, python="both", **create):
        repo = self.checkout(python=python, locks=["uv.lock"])
        self.standin("uv", **(create or PY_CREATE))
        return repo

    def test_python_both_declared_environment_missing_installs_once_and_reports_runnable(self):
        repo = self.uv_checkout()
        before = self.tracked_snapshot(repo)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")

        self.assertEqual(self.calls(), [call(UV, repo)])
        state = self.read_state(repo)
        self.assertEqual(list(state), ["languages"])
        entry = state["languages"]["python"]
        self.assertEqual(set(entry), {"result", "verified", "lock_sha", "command", "finished"})
        self.assertEqual((entry["result"], entry["verified"], entry["command"]), ("ok", True, UV))
        self.assertEqual(entry["lock_sha"], sha(repo / "uv.lock"))
        self.assertIsInstance(entry["finished"], (int, float))
        self.assertLess(abs(entry["finished"] - time.time()), 600)
        self.assertFalse((self.state_dir(repo) / "lock").exists())
        self.assertEqual(self.lines(self.status(repo)), [s_runnable("python", PY_TOOLS)])
        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()
        self.assertEqual(self.calls(), [call(UV, repo)])
        self.assertEqual(self.tracked_snapshot(repo), before)

    def test_git_status_is_empty_after_the_python_install(self):
        repo = self.uv_checkout()

        self.lines(self.session_start(repo))
        self.wait_done(repo, "python")

        status = run_git(repo, "status", "--porcelain").stdout
        self.assertEqual(status, "")

    def test_python_both_declared_one_present_installs(self):
        repo = self.uv_checkout()
        make_py_tools(repo, ("hypothesis",))

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])

    def test_python_one_declared_and_present_does_nothing(self):
        repo = self.uv_checkout(python="mutmut")
        make_py_tools(repo, ("mutmut",))

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()

        self.assertEqual(self.calls(), [])
        self.assertFalse(self.state_dir(repo).exists())
        self.assertEqual(self.lines(self.status(repo)), [s_runnable("python", ("mutmut",))])

    def test_python_one_declared_and_absent_installs(self):
        repo = self.uv_checkout(python="mutmut")

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])

    def test_python_no_tool_declared_does_nothing_and_status_says_none(self):
        repo = self.uv_checkout(python="none")

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()

        self.assertEqual(self.calls(), [])
        self.assertFalse(self.state_dir(repo).exists())
        self.assertEqual(self.lines(self.status(repo)), [S_NONE])

    def test_python_without_lockfile_does_nothing_and_status_says_no_lockfile(self):
        repo = self.checkout(python="both")
        self.standin("uv", **PY_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()

        self.assertEqual(self.calls(), [])
        self.assertFalse(self.state_dir(repo).exists())
        self.assertEqual(self.lines(self.status(repo)), [s_nolock("python")])

    def test_javascript_both_declared_node_modules_missing_installs_with_npm_ci(self):
        repo = self.checkout(js="both", locks=["package-lock.json"])
        self.standin("npm", **JS_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([NPM])])
        self.wait_done(repo, "javascript")

        self.assertEqual(self.calls(), [call(NPM, repo)])
        entry = self.entry(repo, "javascript")
        self.assertEqual((entry["result"], entry["verified"], entry["command"]), ("ok", True, NPM))
        self.assertEqual(self.lines(self.status(repo)), [s_runnable("javascript", JS_TOOLS)])

    def test_javascript_node_modules_without_tools_under_npm_lock_is_manual_and_untouched(self):
        repo = self.checkout(js="both", locks=["package-lock.json"])
        self.standin("npm", **JS_CREATE)
        make_unrelated_node_modules(repo)
        before = tree(repo / "node_modules")

        self.assertEqual(self.lines(self.session_start(repo)), [m_manual(NPM)])
        self.settle()

        self.assertEqual(self.calls(), [])
        self.assertEqual(tree(repo / "node_modules"), before)
        self.assertFalse(self.state_dir(repo).exists())
        self.assertEqual(self.lines(self.status(repo)), [s_manual("javascript", NPM)])

    def test_javascript_node_modules_without_tools_under_pnpm_lock_installs(self):
        repo = self.checkout(js="both", locks=["pnpm-lock.yaml"])
        self.standin("pnpm", **JS_CREATE)
        make_unrelated_node_modules(repo)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([PNPM])])
        self.wait_done(repo, "javascript")
        self.assertEqual(self.calls(), [call(PNPM, repo)])

    def test_javascript_no_tool_declared_does_nothing_and_status_says_none(self):
        repo = self.checkout(js="none", locks=["package-lock.json"])
        self.standin("npm", **JS_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()

        self.assertEqual(self.calls(), [])
        self.assertFalse(self.state_dir(repo).exists())
        self.assertEqual(self.lines(self.status(repo)), [S_NONE])

    def test_javascript_without_lockfile_does_nothing_and_status_says_no_lockfile(self):
        repo = self.checkout(js="both")
        self.standin("npm", **JS_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()

        self.assertEqual(self.calls(), [])
        self.assertFalse(self.state_dir(repo).exists())
        self.assertEqual(self.lines(self.status(repo)), [s_nolock("javascript")])

    def test_both_languages_pending_run_in_one_worker_in_language_order(self):
        repo = self.checkout(python="both", js="both", locks=["uv.lock", "package-lock.json"])
        self.standin("uv", **PY_CREATE)
        self.standin("npm", **JS_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV, NPM])])
        self.wait_done(repo, "python", "javascript")

        self.assertEqual(self.calls(), [call(UV, repo), call(NPM, repo)])
        entries = self.read_state(repo)["languages"]
        self.assertEqual(sorted(entries), ["javascript", "python"])
        self.assertEqual([(e["result"], e["verified"]) for e in (entries["python"], entries["javascript"])],
                         [("ok", True), ("ok", True)])
        self.assertEqual(self.lines(self.status(repo)),
                         [s_runnable("python", PY_TOOLS), s_runnable("javascript", JS_TOOLS)])

    def declared_install(self, python=None, js=None, locks=("uv.lock",), manager="uv", create=None):
        repo = self.checkout(python="none" if python else None, js="none" if js else None, locks=list(locks))
        if python:
            (repo / "pyproject.toml").write_text(python)
        if js:
            (repo / "package.json").write_text(js)
        self.standin(manager, **(create or {}))
        return repo

    def test_python_requirement_with_upper_case_extra_and_marker_declares_the_tool(self):
        text = "[project]\nname = \"d\"\nversion = \"0\"\ndependencies = ['Hypothesis[cli]>=6; python_version > \"3.8\"']\n"
        repo = self.declared_install(python=text)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])

    def test_python_table_key_declares_the_tool(self):
        text = "[project]\nname = \"d\"\nversion = \"0\"\n\n[tool.mutmut]\npaths_to_mutate = \"src/\"\n"
        repo = self.declared_install(python=text)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])

    def test_python_similarly_named_package_declares_nothing(self):
        text = "[project]\nname = \"d\"\nversion = \"0\"\ndependencies = [\"hypothesis-jsonschema>=0.1\"]\n"
        repo = self.declared_install(python=text)

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.lines(self.status(repo)), [S_NONE])

    def test_javascript_tool_under_each_declaring_key_is_declared(self):
        for key in ("dependencies", "optionalDependencies", "peerDependencies"):
            with self.subTest(key=key):
                self.setUp()
                text = json.dumps({"name": "d", key: {"fast-check": "^3"}})
                repo = self.declared_install(js=text, locks=("package-lock.json",), manager="npm", create=JS_CREATE)

                self.assertEqual(self.lines(self.session_start(repo)), [m_start([NPM])])
                self.wait_done(repo, "javascript")
                self.assertEqual(self.calls(), [call(NPM, repo)])

    def test_javascript_tool_named_only_under_another_key_is_not_declared(self):
        text = json.dumps({"name": "d", "overrides": {"fast-check": "^3"}})
        repo = self.declared_install(js=text, locks=("package-lock.json",), manager="npm", create=JS_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.lines(self.status(repo)), [S_NONE])

    def test_node_modules_directory_without_package_json_is_not_present(self):
        repo = self.checkout(js="both", locks=["package-lock.json"])
        self.standin("npm", **JS_CREATE)
        for name in JS_TOOLS:
            (repo / "node_modules" / name).mkdir(parents=True)

        self.assertEqual(self.lines(self.session_start(repo)), [m_manual(NPM)])
        self.settle()
        self.assertEqual(self.calls(), [])

    def test_windows_layout_site_packages_counts_as_present(self):
        repo = self.uv_checkout()
        for name in PY_TOOLS:
            (repo / ".venv" / "Lib" / "site-packages" / name).mkdir(parents=True)

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.lines(self.status(repo)), [s_runnable("python", PY_TOOLS)])

    def test_install_runs_when_no_python3_is_reachable_on_path(self):
        repo = self.uv_checkout()
        only_git = self.box / "onlygit"
        only_git.mkdir()
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        (only_git / "git").symlink_to(real_git)
        for tool in ("basename", "mkdir", "sleep", "dirname"):
            (self.stand / tool).symlink_to(shutil.which(tool))
        path = f"{self.stand}:{only_git}"
        self.assertIsNone(shutil.which("python3", path=path))
        self.assertIsNone(shutil.which("python", path=path))

        self.assertEqual(self.lines(self.session_start(repo, env=self.sandbox_env(PATH=path))), [m_start([UV])])
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])

    def test_install_command_reads_end_of_file_from_stdin(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        record = self.box / "stdin.rec"
        self.standin("uv", stdin_record=record, **PY_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")
        self.assertEqual(record.read_text().strip(), "eof")


class TestLockfileTable(CheckoutCase):
    def assert_row(self, language, locks, command):
        repo = self.checkout(python="both" if language == "python" else None,
                             js="both" if language == "javascript" else None, locks=locks)
        for manager in ("uv", "poetry", "pdm", "pnpm", "yarn", "bun", "npm"):
            self.standin(manager)
        self.assertEqual(self.lines(self.session_start(repo)), [m_start([command])])
        self.wait_done(repo, language)
        self.assertEqual(self.calls(), [call(command, repo)])

    def test_python_rows(self):
        rows = {
            "uv": (["uv.lock"], UV), "poetry": (["poetry.lock"], POETRY), "pdm": (["pdm.lock"], PDM),
            "uv+poetry": (["uv.lock", "poetry.lock"], UV), "poetry+pdm": (["poetry.lock", "pdm.lock"], POETRY),
        }
        for label, (locks, command) in rows.items():
            with self.subTest(row=label):
                self.setUp()
                self.assert_row("python", locks, command)

    def test_javascript_rows(self):
        rows = {
            "pnpm": (["pnpm-lock.yaml"], PNPM), "yarn": (["yarn.lock"], YARN), "bun.lock": (["bun.lock"], BUN),
            "bun.lockb": (["bun.lockb"], BUN), "npm": (["package-lock.json"], NPM),
            "pnpm+yarn": (["pnpm-lock.yaml", "yarn.lock"], PNPM), "yarn+bun": (["yarn.lock", "bun.lock"], YARN),
            "bun+npm": (["bun.lock", "package-lock.json"], BUN),
        }
        for label, (locks, command) in rows.items():
            with self.subTest(row=label):
                self.setUp()
                self.assert_row("javascript", locks, command)


class TestOffSwitches(CheckoutCase):
    def uv_checkout(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", **PY_CREATE)
        return repo

    def assert_installs(self, repo, **kwargs):
        self.assertEqual(self.lines(self.session_start(repo, **kwargs)), [m_start([UV])])
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])

    def assert_off(self, repo, **kwargs):
        self.assertEqual(self.lines(self.session_start(repo, **kwargs)), [])
        self.settle()
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.state_dir(repo).exists())

    def never(self, path):
        self.prefs.write_text(json.dumps(
            {"repositories": {str(Path(path).resolve()): {"verification_tools_prompt": "never"}}}))

    def test_never_for_the_checkout_path_is_off(self):
        repo = self.uv_checkout()
        self.never(repo)
        self.assert_off(repo)
        self.assertEqual(self.lines(self.status(repo)), [s_off("python")])

    def test_never_for_the_main_worktree_path_is_off_in_a_linked_worktree(self):
        repo = self.uv_checkout()
        worktree = self.add_worktree(repo)
        self.never(repo)
        self.assert_off(worktree, payload={"hook_event_name": "SessionStart", "cwd": str(worktree)},
                        script_repo=repo)
        self.assertEqual(self.lines(self.status(worktree)), [s_off("python")])

    def test_never_for_the_linked_worktrees_own_path_only_is_off_in_that_worktree(self):
        repo = self.uv_checkout()
        worktree = self.add_worktree(repo)
        self.never(worktree)
        self.assert_off(worktree, payload={"hook_event_name": "SessionStart", "cwd": str(worktree)},
                        script_repo=repo)
        self.assertEqual(self.lines(self.status(worktree)), [s_off("python")])

    def test_never_for_an_unrelated_path_installs(self):
        repo = self.uv_checkout()
        self.never(self.box / "elsewhere")
        self.assert_installs(repo)

    def test_config_auto_install_false_is_off(self):
        repo = self.uv_checkout()
        (repo / ".harness" / "config.json").write_text(json.dumps({"auto_install": False}))
        self.assert_off(repo)
        self.assertEqual(self.lines(self.status(repo)), [s_off("python")])

    def test_config_auto_install_true_installs(self):
        repo = self.uv_checkout()
        (repo / ".harness" / "config.json").write_text(json.dumps({"auto_install": True}))
        self.assert_installs(repo)

    def test_config_without_the_key_installs(self):
        repo = self.uv_checkout()
        (repo / ".harness" / "config.json").write_text(json.dumps({"other": 1}))
        self.assert_installs(repo)

    def test_config_file_absent_installs(self):
        repo = self.uv_checkout()
        self.assertFalse((repo / ".harness" / "config.json").exists())
        self.assert_installs(repo)

    def test_config_that_is_not_an_object_is_off(self):
        repo = self.uv_checkout()
        (repo / ".harness" / "config.json").write_text(json.dumps([{"auto_install": True}]))
        self.assert_off(repo)
        self.assertEqual(self.lines(self.status(repo)), [s_off("python")])


class TestStateTransitions(CheckoutCase):
    def uv_checkout(self):
        return self.checkout(python="both", locks=["uv.lock"])

    def run_failing(self, repo, **standin):
        self.standin("uv", **standin)
        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")
        return self.entry(repo, "python")

    def test_t2_failure_reason_comes_from_stderr(self):
        repo = self.uv_checkout()
        entry = self.run_failing(repo, code=2, stderr="error: lock mismatch", stdout="ignored stdout")
        self.assertEqual((entry["result"], entry["reason"]), ("failed", "exit 2: error: lock mismatch"))
        self.assertEqual((entry["command"], entry["lock_sha"]), (UV, sha(repo / "uv.lock")))
        self.assertIsInstance(entry["finished"], (int, float))
        log = (self.state_dir(repo) / "install.log").read_text()
        self.assertIn(UV, log)
        self.assertIn("error: lock mismatch", log)
        self.assertFalse((self.state_dir(repo) / "lock").exists())

    def test_t2_failure_reason_falls_back_to_the_first_non_empty_stdout_line(self):
        repo = self.uv_checkout()
        entry = self.run_failing(repo, code=3, stdout="\n   \n  resolver broke  \nsecond line")
        self.assertEqual(entry["reason"], "exit 3: resolver broke")

    def test_t2_failure_without_output_is_the_exit_code_alone(self):
        repo = self.uv_checkout()
        entry = self.run_failing(repo, code=4)
        self.assertEqual(entry["reason"], "exit 4")

    def test_t3_phase_reports_the_failure_without_running_anything(self):
        repo = self.uv_checkout()
        self.run_failing(repo, code=2, stderr="error: lock mismatch")
        before = (self.state_dir(repo) / "state.json").read_bytes()

        out = self.phase(repo, "--run-id", RID, "--phase", "draft").stdout
        self.settle()

        head = out.split("\n\n", 1)[0].split("\n")
        self.assertEqual(head[1:], [m_failed("python", "exit 2: error: lock mismatch", UV)])
        self.assertEqual(self.calls(), [call(UV, repo)])
        self.assertEqual((self.state_dir(repo) / "state.json").read_bytes(), before)
        self.assertEqual(self.lines(self.status(repo)),
                         [s_failed("python", "exit 2: error: lock mismatch", UV)])

    def test_t4_hook_retries_a_failed_install_and_it_becomes_ok(self):
        repo = self.uv_checkout()
        self.run_failing(repo, code=2, stderr="error: lock mismatch")
        self.standin("uv", **PY_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)),
                         [m_retry("exit 2: error: lock mismatch", [UV])])
        self.wait_done(repo, "python", check=lambda entries: entries["python"]["result"] == "ok")

        self.assertEqual(self.calls(), [call(UV, repo), call(UV, repo)])
        self.assertTrue(self.entry(repo, "python")["verified"])

    def test_t5_timeout_marks_failed_and_kills_the_command(self):
        repo = self.uv_checkout()
        pidfile = self.box / "uv.pid"
        self.standin("uv", sleep=5, exec_sleep=True, pidfile=pidfile)
        env = self.sandbox_env(HARNESS_CHECKOUT_SETUP_TIMEOUT="1")

        self.assertEqual(self.lines(self.session_start(repo, env=env)), [m_start([UV])])
        self.wait_done(repo, "python")

        self.assertEqual(self.entry(repo, "python")["reason"], "timeout after 1s")
        self.assertEqual(self.entry(repo, "python")["result"], "failed")
        pid = int(pidfile.read_text())

        def gone():
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            return False
        self.assertTrue(self.wait_until(gone, 4.0), "the timed-out command is still running")

    def test_t6_success_that_creates_nothing_is_ok_but_unverified(self):
        repo = self.checkout(python="both", locks=["poetry.lock"])
        self.standin("poetry")

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([POETRY])])
        self.wait_done(repo, "python")

        entry = self.entry(repo, "python")
        self.assertEqual((entry["result"], entry["verified"], entry["command"]), ("ok", False, POETRY))

    def test_t7_unverified_install_with_the_same_lockfile_is_not_repeated(self):
        repo = self.checkout(python="both", locks=["poetry.lock"])
        self.standin("poetry")
        self.lines(self.session_start(repo))
        self.wait_done(repo, "python")

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()

        self.assertEqual(self.calls(), [call(POETRY, repo)])
        self.assertEqual(self.lines(self.status(repo)), [s_settled("python", POETRY)])

    def test_t8_unverified_install_runs_again_when_the_lockfile_bytes_change(self):
        repo = self.checkout(python="both", locks=["poetry.lock"])
        self.standin("poetry")
        self.lines(self.session_start(repo))
        self.wait_done(repo, "python")
        (repo / "poetry.lock").write_text("poetry.lock v2\n")
        new_sha = sha(repo / "poetry.lock")

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([POETRY])])
        self.wait_done(repo, "python", check=lambda entries: entries["python"]["lock_sha"] == new_sha)

        self.assertEqual(self.calls(), [call(POETRY, repo), call(POETRY, repo)])

    def test_t8_failed_install_runs_again_when_the_lockfile_bytes_change(self):
        repo = self.uv_checkout()
        self.run_failing(repo, code=2, stderr="error: lock mismatch")
        self.standin("uv", **PY_CREATE)
        (repo / "uv.lock").write_text("uv.lock v2\n")
        new_sha = sha(repo / "uv.lock")

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python", check=lambda entries: entries["python"]["lock_sha"] == new_sha)

        self.assertEqual(self.calls(), [call(UV, repo), call(UV, repo)])
        self.assertEqual(self.entry(repo, "python")["result"], "ok")

    def test_t9_missing_manager_is_reported_without_a_worker_or_state(self):
        repo = self.uv_checkout()

        self.assertEqual(self.lines(self.session_start(repo)), [m_nomanager("uv", UV)])
        self.settle()

        self.assertEqual(self.calls(), [])
        self.assertFalse((self.state_dir(repo) / "state.json").exists())
        self.assertEqual(self.lines(self.status(repo)), [s_nomanager("python", "uv", UV)])

    def test_t10_failed_npm_install_over_existing_node_modules_is_retried_by_the_hook(self):
        repo = self.checkout(js="both", locks=["package-lock.json"])
        self.standin("npm", **JS_CREATE)
        make_unrelated_node_modules(repo)
        self.write_state(repo, {"javascript": self.failed_entry(repo, "package-lock.json", NPM, "exit 1")})

        self.assertEqual(self.lines(self.session_start(repo)), [m_retry("exit 1", [NPM])])
        self.wait_done(repo, "javascript", check=lambda entries: entries["javascript"]["result"] == "ok")

        self.assertEqual(self.calls(), [call(NPM, repo)])


class TestStateTransitionsMore(CheckoutCase):
    def test_t11_python_failure_does_not_stop_the_javascript_install(self):
        repo = self.checkout(python="both", js="both", locks=["uv.lock", "package-lock.json"])
        self.standin("uv", code=2, stderr="boom")
        self.standin("npm", **JS_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV, NPM])])
        self.wait_done(repo, "python", "javascript")

        self.assertEqual(self.calls(), [call(UV, repo), call(NPM, repo)])
        entries = self.read_state(repo)["languages"]
        self.assertEqual((entries["python"]["result"], entries["python"]["reason"]), ("failed", "exit 2: boom"))
        self.assertEqual((entries["javascript"]["result"], entries["javascript"]["verified"]), ("ok", True))

    def test_reason_is_the_first_non_empty_stderr_line_after_blank_lines(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", code=2, stderr="\n\n  first real line  \nsecond line\nthird line")

        self.lines(self.session_start(repo))
        self.wait_done(repo, "python")

        self.assertEqual(self.entry(repo, "python")["reason"], "exit 2: first real line")

    def test_a_300_character_first_line_is_cut_to_200(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        line = "abcdefghij" * 30
        self.standin("uv", code=2, stderr=line)

        self.lines(self.session_start(repo))
        self.wait_done(repo, "python")

        self.assertEqual(self.entry(repo, "python")["reason"], "exit 2: " + line[:200])

    def test_install_log_holds_the_command_lines_of_two_consecutive_runs_in_order(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", code=2, stderr="run one failed")
        self.lines(self.session_start(repo))
        self.wait_done(repo, "python")
        self.standin("uv", code=2, stderr="run two failed")

        self.lines(self.session_start(repo))
        self.wait_done(repo, "python", check=lambda e: e["python"].get("reason") == "exit 2: run two failed")

        log = (self.state_dir(repo) / "install.log").read_text()
        first = log.index(UV)
        one = log.index("run one failed", first)
        second = log.index(UV, one)
        two = log.index("run two failed", second)
        self.assertTrue(first < one < second < two, log)


class TestStateTransitionsLaunch(CheckoutCase):
    def test_t12_unlaunchable_manager_is_a_failed_entry_with_the_exception_reason(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        broken = self.stand / "uv"
        broken.write_text("#!/nonexistent/interpreter\n")
        broken.chmod(0o755)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")

        entry = self.entry(repo, "python")
        self.assertEqual(entry["result"], "failed")
        self.assertRegex(entry["reason"], r"\AFileNotFoundError: [^\n]+\Z")
        self.assertFalse((self.state_dir(repo) / "lock").exists())
        self.assertEqual(self.lines(self.status(repo)), [s_failed("python", entry["reason"], UV)])

    def test_t13_worker_run_directly_without_the_manager_runs_nothing(self):
        repo = self.checkout(python="both", locks=["uv.lock"])

        result = self.worker(repo)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.settle()
        self.assertEqual(self.calls(), [])
        state = self.read_state(repo)
        self.assertNotIn("python", (state or {}).get("languages", {}))
        self.assertFalse((self.state_dir(repo) / "lock").exists())

    def test_both_languages_failed_give_one_retry_line_with_the_python_reason(self):
        repo = self.checkout(python="both", js="both", locks=["uv.lock", "package-lock.json"])
        self.standin("uv", **PY_CREATE)
        self.standin("npm", **JS_CREATE)
        self.write_state(repo, {"python": self.failed_entry(repo, "uv.lock", UV, "exit 2: py boom"),
                                "javascript": self.failed_entry(repo, "package-lock.json", NPM, "exit 1: js boom")})

        self.assertEqual(self.lines(self.session_start(repo)), [m_retry("exit 2: py boom", [UV, NPM])])
        self.wait_done(repo, "python", "javascript",
                       check=lambda e: e["python"]["result"] == "ok" and e["javascript"]["result"] == "ok")

        self.assertEqual(self.calls(), [call(UV, repo), call(NPM, repo)])

    def test_pending_python_with_a_missing_javascript_manager_prints_start_then_no_manager(self):
        repo = self.checkout(python="both", js="both", locks=["uv.lock", "package-lock.json"])
        self.standin("uv", **PY_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV]), m_nomanager("npm", NPM)])
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])

    def test_phase_without_again_lists_failed_python_then_manual_javascript(self):
        repo = self.checkout(python="both", js="both", locks=["uv.lock", "package-lock.json"])
        self.standin("uv", **PY_CREATE)
        self.standin("npm", **JS_CREATE)
        make_unrelated_node_modules(repo)
        self.write_state(repo, {"python": self.failed_entry(repo, "uv.lock", UV, "exit 2: py boom")})

        result = self.phase(repo, "--run-id", RID, "--phase", "draft")
        self.settle()

        self.assertEqual((result.returncode, result.stderr), (0, ""))
        head = result.stdout.partition("\n\n")[0].split("\n")
        self.assertEqual(head[1:], [m_failed("python", "exit 2: py boom", UV), m_manual(NPM)])
        self.assertEqual(self.calls(), [])


class TestConcurrency(CheckoutCase):
    def uv_checkout(self, seconds=2):
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", sleep=seconds, **PY_CREATE)
        return repo

    def test_s1_two_simultaneous_hooks_run_the_command_once(self):
        for round_number in range(2):
            with self.subTest(round=round_number):
                if round_number:
                    self.setUp()
                repo = self.uv_checkout()
                barrier = threading.Barrier(2)

                def start():
                    barrier.wait()
                    return self.session_start(repo)

                with concurrent.futures.ThreadPoolExecutor(2) as pool:
                    results = [f.result() for f in [pool.submit(start), pool.submit(start)]]
                outputs = [self.lines(r) for r in results]
                self.wait_done(repo, "python")

                for lines in outputs:
                    self.assertEqual(len(lines), 1, outputs)
                    if lines[0] != m_start([UV]):
                        self.expect_running(lines[0], [UV], 0, 20)
                self.assertIn(m_start([UV]), [lines[0] for lines in outputs])
                self.assertEqual(self.calls(), [call(UV, repo)])
                self.assertFalse((self.state_dir(repo) / "lock").exists())

    def test_s2_lock_with_a_dead_pid_counts_as_absent(self):
        repo = self.uv_checkout(seconds=0)
        finished = subprocess.Popen([sys.executable, "-c", "pass"])
        finished.wait()
        self.write_lock(repo, finished.pid, int(time.time()), [UV])

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")

        self.assertEqual(self.calls(), [call(UV, repo)])
        self.assertFalse((self.state_dir(repo) / "lock").exists())

    def test_s3_lock_older_than_twice_the_timeout_with_a_live_pid_counts_as_absent(self):
        repo = self.uv_checkout(seconds=0)
        self.write_lock(repo, os.getpid(), int(time.time()) - 25, [UV])
        env = self.sandbox_env(HARNESS_CHECKOUT_SETUP_TIMEOUT="10")

        self.assertEqual(self.lines(self.session_start(repo, env=env)), [m_start([UV])])
        self.manual_locks.discard(repo)
        self.wait_done(repo, "python")

        self.assertEqual(self.calls(), [call(UV, repo)])
        self.assertFalse((self.state_dir(repo) / "lock").exists())

    def test_s5_lock_between_one_and_two_timeouts_old_with_a_live_pid_is_live(self):
        repo = self.uv_checkout(seconds=0)
        self.write_lock(repo, os.getpid(), int(time.time()) - 15, [UV])
        env = self.sandbox_env(HARNESS_CHECKOUT_SETUP_TIMEOUT="10")

        lines = self.lines(self.session_start(repo, env=env))

        self.assertEqual(len(lines), 1, lines)
        self.expect_running(lines[0], [UV], 15, 45)
        self.settle()
        self.assertEqual(self.calls(), [])

    def test_s6_killed_worker_leaves_the_language_pending_and_the_next_hook_installs(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        pidfile = self.box / "uv.pid"
        self.standin("uv", sleep=60, exec_sleep=True, pidfile=pidfile)
        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_lock(repo)

        def number(path, key=None):
            try:
                text = path.read_text()
                return json.loads(text)[key] if key else int(text)
            except (OSError, ValueError, KeyError):
                return None
        self.assertTrue(self.wait_until(lambda: number(self.state_dir(repo) / "lock", "pid") is not None
                                        and number(pidfile) is not None, 15.0))
        worker, command = number(self.state_dir(repo) / "lock", "pid"), number(pidfile)
        os.kill(worker, signal.SIGKILL)
        os.kill(command, signal.SIGKILL)

        def gone(pid):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            return False
        self.assertTrue(self.wait_until(lambda: gone(worker) and gone(command), 10.0))
        self.assertNotIn("python", (self.read_state(repo) or {}).get("languages", {}))
        self.standin("uv", **PY_CREATE)
        self.assertEqual(self.lines(self.status(repo)), [s_pending("python")])

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")

        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(self.entry(repo, "python")["result"], "ok")

    def test_s4_worker_started_under_a_live_lock_runs_nothing(self):
        repo = self.uv_checkout(seconds=0)
        self.write_lock(repo, os.getpid(), int(time.time()), [UV])
        lock = self.state_dir(repo) / "lock"
        before = lock.read_bytes()

        result = self.worker(repo)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.settle()
        self.assertEqual(self.calls(), [])
        self.assertEqual(lock.read_bytes(), before)
        self.assertFalse((self.state_dir(repo) / "state.json").exists())


class TestCheckoutResolution(CheckoutCase):
    def uv_checkout(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", **PY_CREATE)
        return repo

    def test_cwd_in_a_linked_worktree_with_the_main_checkouts_script_installs_in_the_worktree(self):
        repo = self.uv_checkout()
        worktree = self.add_worktree(repo)
        main_before = self.tracked_snapshot(repo)

        payload = {"hook_event_name": "SessionStart", "cwd": str(worktree)}
        self.assertEqual(self.lines(self.session_start(repo, payload=payload)), [m_start([UV])])
        self.wait_done(worktree, "python")

        self.assertEqual(self.calls(), [call(UV, worktree)])
        self.assertTrue((self.state_dir(worktree) / "state.json").is_file())
        self.assertFalse(self.state_dir(repo).exists())
        self.assertFalse((repo / ".venv").exists())
        self.assertEqual(self.tracked_snapshot(repo), main_before)

    def test_cwd_in_a_subdirectory_resolves_to_the_checkout_root(self):
        repo = self.uv_checkout()

        payload = {"hook_event_name": "SessionStart", "cwd": str(repo / "src")}
        self.assertEqual(self.lines(self.session_start(repo, payload=payload)), [m_start([UV])])
        self.wait_done(repo, "python")

        self.assertEqual(self.calls(), [call(UV, repo)])
        self.assertFalse((repo / "src" / ".harness").exists())

    def test_payload_without_cwd_uses_the_process_working_directory(self):
        repo = self.uv_checkout()

        payload = {"hook_event_name": "SessionStart"}
        self.assertEqual(self.lines(self.session_start(repo, payload=payload)), [m_start([UV])])
        self.wait_done(repo, "python")

        self.assertEqual(self.calls(), [call(UV, repo)])

    def test_payload_without_cwd_in_a_worktree_process_directory_acts_on_the_worktree(self):
        repo = self.uv_checkout()
        worktree = self.add_worktree(repo)

        payload = {"hook_event_name": "SessionStart"}
        self.assertEqual(self.lines(self.session_start(repo, payload=payload, cwd=worktree)), [m_start([UV])])
        self.wait_done(worktree, "python")

        self.assertEqual(self.calls(), [call(UV, worktree)])
        self.assertFalse(self.state_dir(repo).exists())

    def test_empty_or_non_string_cwd_falls_back_to_the_process_working_directory(self):
        for label, value in (("empty", ""), ("number", 5)):
            with self.subTest(cwd=label):
                self.setUp()
                repo = self.uv_checkout()
                worktree = self.add_worktree(repo)

                payload = {"hook_event_name": "SessionStart", "cwd": value}
                self.assertEqual(self.lines(self.session_start(repo, payload=payload, cwd=worktree)),
                                 [m_start([UV])])
                self.wait_done(worktree, "python")

                self.assertEqual(self.calls(), [call(UV, worktree)])
                self.assertFalse(self.state_dir(repo).exists())

    def test_status_and_phase_do_nothing_when_the_manifest_is_missing(self):
        repo = self.uv_checkout()
        (repo / ".harness" / "manifest.json").unlink()

        self.assertEqual(self.lines(self.status(repo)), [])
        result = self.phase(repo, "--run-id", RID, "--phase", "draft")
        self.settle()

        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout, f"doggy-workflow phase: draft\n\n{draft_rules(repo)}")
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.state_dir(repo).exists())

    def test_cwd_in_a_git_repository_without_the_harness_changes_nothing(self):
        repo = self.uv_checkout()
        plain = self.box / "plain"
        plain.mkdir()
        init_repo(plain)
        (plain / "pyproject.toml").write_text((repo / "pyproject.toml").read_text())
        (plain / "uv.lock").write_text("uv.lock v1\n")
        before = self.snapshot(plain)
        config = (plain / ".git" / "config").read_bytes()

        payload = {"hook_event_name": "SessionStart", "cwd": str(plain)}
        self.assertEqual(self.lines(self.session_start(repo, payload=payload)), [])
        self.settle()

        self.assertEqual(self.calls(), [])
        self.assertEqual(self.snapshot(plain), before)
        self.assertEqual((plain / ".git" / "config").read_bytes(), config)
        self.assertEqual(self.hooks_path(plain), "")
        self.assertFalse(self.state_dir(repo).exists())

    def test_cwd_outside_git_prints_nothing_and_writes_nothing(self):
        repo = self.uv_checkout()
        loose = self.box / "loose"
        loose.mkdir()
        (loose / "pyproject.toml").write_text((repo / "pyproject.toml").read_text())
        (loose / "uv.lock").write_text("uv.lock v1\n")
        before = tree(loose)

        payload = {"hook_event_name": "SessionStart", "cwd": str(loose)}
        result = self.session_start(repo, payload=payload, cwd=loose)
        self.assertEqual(self.lines(result), [])
        self.settle()

        self.assertEqual(self.calls(), [])
        self.assertEqual(tree(loose), before)
        self.assertFalse(self.state_dir(repo).exists())


class TestHooksPath(CheckoutCase):
    MANAGER_FILES = (".husky/pre-commit", "lefthook.yml", "lefthook.yaml", ".lefthook.yml", ".pre-commit-config.yaml")

    def bare(self):
        repo = self.checkout()
        subprocess.run(["git", "-C", str(repo), "config", "--unset", "core.hooksPath"], check=True)
        return repo

    def test_r1_unset_without_manager_files_is_set_once(self):
        repo = self.bare()

        self.assertEqual(self.lines(self.session_start(repo)), [M_HOOKS])
        self.assertEqual(self.hooks_path(repo), ".harness/git")
        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.assertEqual(self.hooks_path(repo), ".harness/git")

    def test_r2_already_set_to_the_harness_path_prints_nothing(self):
        repo = self.checkout()
        self.assertEqual(self.hooks_path(repo), ".harness/git")

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.assertEqual(self.hooks_path(repo), ".harness/git")

    def test_r3_another_value_is_left_alone(self):
        repo = self.checkout()
        run_git(repo, "config", "core.hooksPath", ".husky")

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.assertEqual(self.hooks_path(repo), ".husky")

    def test_r4_each_hook_manager_file_keeps_the_value_unset(self):
        for name in self.MANAGER_FILES:
            with self.subTest(file=name):
                self.setUp()
                repo = self.bare()
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_text("x\n")

                self.assertEqual(self.lines(self.session_start(repo)), [])
                self.assertEqual(self.hooks_path(repo), "")

    def test_r5_missing_harness_pre_commit_keeps_the_value_unset(self):
        repo = self.bare()
        (repo / ".harness" / "git" / "pre-commit").unlink()

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.assertEqual(self.hooks_path(repo), "")

    def test_r6_auto_install_false_does_not_stop_the_hooks_path(self):
        repo = self.bare()
        (repo / ".harness" / "config.json").write_text(json.dumps({"auto_install": False}))

        self.assertEqual(self.lines(self.session_start(repo)), [M_HOOKS])
        self.assertEqual(self.hooks_path(repo), ".harness/git")

    def test_r8_unwritable_git_directory_skips_the_hooks_line_but_not_the_install(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores directory permissions")
        repo = self.bare()
        (repo / "pyproject.toml").write_text(pyproject_text("both"))
        (repo / "uv.lock").write_text("uv.lock v1\n")
        self.standin("uv", **PY_CREATE)
        git_dir = repo / ".git"
        self.addCleanup(git_dir.chmod, 0o755)
        git_dir.chmod(0o555)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")
        self.assertEqual(self.hooks_path(repo), "")

    def test_r7_hooks_line_precedes_the_install_line(self):
        repo = self.bare()
        (repo / "pyproject.toml").write_text(pyproject_text("both"))
        (repo / "uv.lock").write_text("uv.lock v1\n")
        self.standin("uv", **PY_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [M_HOOKS, m_start([UV])])
        self.wait_done(repo, "python")


class TestMalformedInputs(CheckoutCase):
    def uv_checkout(self, **kwargs):
        kwargs.setdefault("python", "both")
        kwargs.setdefault("locks", ["uv.lock"])
        repo = self.checkout(**kwargs)
        self.standin("uv", **PY_CREATE)
        return repo

    def assert_installed(self, repo, result):
        self.assertEqual(self.lines(result), [m_start([UV])])
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])

    def test_malformed_hook_payloads_still_use_the_working_directory(self):
        for label, raw in (("empty", ""), ("not json", "{{{ nope"), ("array", "[1, 2]")):
            with self.subTest(stdin=label):
                self.setUp()
                repo = self.uv_checkout()
                self.assert_installed(repo, self.session_start(repo, raw=raw))

    def test_state_file_that_is_not_json_counts_as_absent(self):
        repo = self.uv_checkout()
        self.state_dir(repo).mkdir(parents=True)
        (self.state_dir(repo) / "state.json").write_text("not json at all")
        self.assert_installed(repo, self.session_start(repo))

    def test_state_entries_of_the_wrong_shape_count_as_absent(self):
        shapes = {
            "missing fields": lambda repo: {"languages": {"python": {
                "result": "ok", "verified": False, "lock_sha": sha(repo / "uv.lock")}}},
            "languages is a list": lambda repo: {"languages": []},
            "entry is a string": lambda repo: {"languages": {"python": "ok"}},
        }
        for label, build in shapes.items():
            with self.subTest(shape=label):
                self.setUp()
                repo = self.uv_checkout()
                self.state_dir(repo).mkdir(parents=True)
                (self.state_dir(repo) / "state.json").write_text(json.dumps(build(repo)))
                self.assert_installed(repo, self.session_start(repo))

    def test_lock_file_holding_undecodable_or_invalid_json_text_counts_as_absent(self):
        for label, content in (("invalid json", b"{ not json"), ("undecodable", b"\xff\xfe{\x00\x80")):
            with self.subTest(lock=label):
                self.setUp()
                repo = self.uv_checkout()
                self.state_dir(repo).mkdir(parents=True)
                (self.state_dir(repo) / "lock").write_bytes(content)
                self.assert_installed(repo, self.session_start(repo))

    def test_lock_file_holding_json_of_the_wrong_shape_counts_as_absent(self):
        shapes = {"number": "12345", "wrong types": json.dumps({"pid": "abc", "started": "now", "commands": 5}),
                  "missing keys": json.dumps({"pid": os.getpid()})}
        for label, content in shapes.items():
            with self.subTest(lock=label):
                self.setUp()
                repo = self.uv_checkout()
                self.state_dir(repo).mkdir(parents=True)
                (self.state_dir(repo) / "lock").write_text(content)
                self.assert_installed(repo, self.session_start(repo))

    def test_no_git_on_path_prints_nothing_and_does_not_fail(self):
        repo = self.uv_checkout()
        self.assertIsNone(shutil.which("git", path=str(self.stand)))

        result = self.session_start(repo, env=self.sandbox_env(PATH=str(self.stand)))

        self.assertEqual(self.lines(result), [])
        self.settle()
        self.assertEqual(self.calls(), [])

    def test_state_directory_path_occupied_by_a_file_does_not_fail_the_hook(self):
        repo = self.uv_checkout()
        (repo / ".harness" / "sessions").mkdir(parents=True, exist_ok=True)
        self.state_dir(repo).write_text("in the way")

        self.lines(self.session_start(repo))
        self.settle()

    def test_config_that_is_not_json_turns_the_install_off(self):
        repo = self.uv_checkout()
        (repo / ".harness" / "config.json").write_text("{ not json")

        self.assertEqual(self.lines(self.session_start(repo)), [])
        self.settle()
        self.assertEqual(self.calls(), [])

    def test_pyproject_that_is_not_toml_declares_nothing_while_javascript_still_installs(self):
        repo = self.checkout(python="both", js="both", locks=["uv.lock", "package-lock.json"])
        (repo / "pyproject.toml").write_text("this = [ is not toml")
        self.standin("uv", **PY_CREATE)
        self.standin("npm", **JS_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([NPM])])
        self.wait_done(repo, "javascript")

        self.assertEqual(self.calls(), [call(NPM, repo)])
        self.assertEqual(self.lines(self.status(repo)), [s_runnable("javascript", JS_TOOLS)])

    def test_package_json_that_is_an_array_declares_nothing_while_python_still_installs(self):
        repo = self.checkout(python="both", js="both", locks=["uv.lock", "package-lock.json"])
        (repo / "package.json").write_text("[1, 2, 3]")
        self.standin("uv", **PY_CREATE)
        self.standin("npm", **JS_CREATE)

        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_done(repo, "python")

        self.assertEqual(self.calls(), [call(UV, repo)])
        self.assertEqual(self.lines(self.status(repo)), [s_runnable("python", PY_TOOLS)])

    def test_preferences_that_are_not_json_leave_the_install_on(self):
        repo = self.uv_checkout()
        self.prefs.write_text("{{ broken")
        self.assert_installed(repo, self.session_start(repo))


class TestPhaseCommand(CheckoutCase):
    HEADER = "doggy-workflow phase: draft"

    def rules(self, repo):
        return draft_rules(repo)

    def prepare(self, state, again):
        if state == "nothing":
            repo = self.checkout(python="none", locks=["uv.lock"])
            self.standin("uv", **PY_CREATE)
        elif state == "pending":
            repo = self.checkout(python="both", locks=["uv.lock"])
            self.standin("uv", sleep=0 if again else 6, **PY_CREATE)
        elif state == "running":
            repo = self.checkout(python="both", locks=["uv.lock"])
            self.standin("uv", **PY_CREATE)
            self.write_lock(repo, os.getpid(), int(time.time()) - 3, [UV])
        elif state == "failed":
            repo = self.checkout(python="both", locks=["uv.lock"])
            self.standin("uv", **PY_CREATE)
            self.write_state(repo, {"python": self.failed_entry(repo, "uv.lock", UV, "exit 2: boom")})
        elif state == "no-manager":
            repo = self.checkout(python="both", locks=["uv.lock"])
        else:
            repo = self.checkout(js="both", locks=["package-lock.json"])
            self.standin("npm", **JS_CREATE)
            make_unrelated_node_modules(repo)
        return repo

    def expected_notices(self, state, again):
        if state == "nothing":
            return []
        if state == "pending":
            return [] if again else [m_start([UV])]
        if state == "running":
            return [m_running_pattern([UV])]
        if state == "failed":
            return [m_failed("python", "exit 2: boom", UV)]
        if state == "no-manager":
            return [m_nomanager("uv", UV)]
        return [m_manual(NPM)]

    def test_the_twelve_rows_of_again_by_state(self):
        for again in (False, True):
            for state in ("nothing", "pending", "running", "failed", "no-manager", "manual"):
                with self.subTest(again=again, state=state):
                    self.setUp()
                    repo = self.prepare(state, again)
                    arguments = ["--run-id", RID, "--phase", "draft"] + (["--again"] if again else [])
                    state_before = (self.state_dir(repo) / "state.json")
                    state_bytes = state_before.read_bytes() if state_before.exists() else None

                    result, elapsed = self.timed(lambda: self.phase(repo, *arguments))

                    self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
                    head, separator, rest = result.stdout.partition("\n\n")
                    self.assertEqual(separator, "\n\n")
                    self.assertEqual(rest, self.rules(repo))
                    head_lines = head.split("\n")
                    header = [self.HEADER] + (["Printed again: nothing was recorded."] if again else [])
                    self.assertEqual(head_lines[:len(header)], header)
                    expected = self.expected_notices(state, again)
                    self.assertEqual(len(head_lines) - len(header), len(expected), head_lines)
                    for line, want in zip(head_lines[len(header):], expected):
                        if isinstance(want, str):
                            self.assertEqual(line, want)
                        else:
                            self.expect_running(line, [UV], 3, 45)
                    if state == "nothing":
                        self.assertEqual(result.stdout, "\n".join(header) + f"\n\n{self.rules(repo)}")
                    if state == "pending" and not again:
                        self.assertLess(elapsed, HOOK_LIMIT)
                        self.wait_done(repo, "python")
                        self.assertEqual(self.calls(), [call(UV, repo)])
                    else:
                        self.settle()
                        self.assertEqual(self.calls(), [])
                    if state_bytes is not None:
                        self.assertEqual(state_before.read_bytes(), state_bytes)
                    if state in ("no-manager", "manual", "nothing") or (state == "pending" and again):
                        self.assertFalse(self.state_dir(repo).exists())


class TestPhaseFailureInStep(CheckoutCase):
    def test_state_directory_path_occupied_by_a_file_leaves_the_rules_intact(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", **PY_CREATE)
        (repo / ".harness" / "sessions").mkdir(parents=True, exist_ok=True)
        self.state_dir(repo).write_text("in the way")

        result = self.phase(repo, "--run-id", RID, "--phase", "draft")
        self.settle()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        head, separator, rest = result.stdout.partition("\n\n")
        self.assertEqual(separator, "\n\n")
        self.assertEqual(rest, draft_rules(repo))


class TestPhaseBriefPlacement(CheckoutCase):
    def test_brief_notice_sits_after_the_header_lines_and_the_rest_is_unchanged(self):
        quiet = self.checkout(python="none", locks=["uv.lock"])
        baseline = self.phase(quiet, "--phase", "brief").stdout
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", sleep=6, **PY_CREATE)

        result, elapsed = self.timed(lambda: self.phase(repo, "--phase", "brief"))

        self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
        self.assertLess(elapsed, HOOK_LIMIT)
        head, _, rest = result.stdout.partition("\n\n")
        lines = head.split("\n")
        self.assertEqual(lines[0], "doggy-workflow phase: brief")
        issued = re.fullmatch(r"Run id of this run: ([0-9a-f]{16})", lines[1]).group(1)
        self.assertIn("literal value", lines[2])
        self.assertEqual(lines[3:], [m_start([UV])])
        base_head, _, base_rest = baseline.partition("\n\n")
        base_id = re.search(r"Run id of this run: ([0-9a-f]{16})", base_head).group(1)
        self.assertEqual(rest.replace(issued, "ID"), base_rest.replace(base_id, "ID"))
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])


class TestStatusCommand(CheckoutCase):
    def python_repo(self, **kwargs):
        repo = self.checkout(python="both", locks=kwargs.pop("locks", ["uv.lock"]))
        return repo

    def test_runnable_line_names_the_declared_tools(self):
        repo = self.python_repo()
        make_py_tools(repo)
        self.assertEqual(self.lines(self.status(repo)), [s_runnable("python", PY_TOOLS)])

    def test_off_line(self):
        repo = self.python_repo()
        (repo / ".harness" / "config.json").write_text(json.dumps({"auto_install": False}))
        self.assertEqual(self.lines(self.status(repo)), [s_off("python")])

    def test_no_lockfile_line(self):
        repo = self.checkout(python="both")
        self.assertEqual(self.lines(self.status(repo)), [s_nolock("python")])

    def test_settled_line(self):
        repo = self.python_repo(locks=["poetry.lock"])
        self.write_state(repo, {"python": self.ok_entry(repo, "poetry.lock", POETRY, False)})
        self.assertEqual(self.lines(self.status(repo)), [s_settled("python", POETRY)])

    def test_no_manager_line(self):
        repo = self.python_repo()
        self.assertEqual(self.lines(self.status(repo)), [s_nomanager("python", "uv", UV)])

    def test_manual_line(self):
        repo = self.checkout(js="both", locks=["package-lock.json"])
        self.standin("npm")
        make_unrelated_node_modules(repo)
        self.assertEqual(self.lines(self.status(repo)), [s_manual("javascript", NPM)])

    def test_failed_line(self):
        repo = self.python_repo()
        self.standin("uv")
        self.write_state(repo, {"python": self.failed_entry(repo, "uv.lock", UV, "exit 2: boom")})
        self.assertEqual(self.lines(self.status(repo)), [s_failed("python", "exit 2: boom", UV)])

    def test_pending_line(self):
        repo = self.python_repo()
        self.standin("uv")
        self.assertEqual(self.lines(self.status(repo)), [s_pending("python")])

    def test_running_line_for_a_pending_and_for_a_failed_language(self):
        for label in ("pending", "failed"):
            with self.subTest(state=label):
                self.setUp()
                repo = self.python_repo()
                self.standin("uv")
                if label == "failed":
                    self.write_state(repo, {"python": self.failed_entry(repo, "uv.lock", UV, "exit 2: boom")})
                self.write_lock(repo, os.getpid(), int(time.time()) - 4, [UV])

                lines = self.lines(self.status(repo))

                self.assertEqual(len(lines), 1, lines)
                match = s_running_pattern("python").fullmatch(lines[0])
                self.assertIsNotNone(match, lines)
                self.assertTrue(4 <= int(match.group(1)) <= 60, lines)

    def test_tools_present_win_over_auto_install_false(self):
        repo = self.python_repo()
        make_py_tools(repo)
        (repo / ".harness" / "config.json").write_text(json.dumps({"auto_install": False}))
        self.assertEqual(self.lines(self.status(repo)), [s_runnable("python", PY_TOOLS)])

    def test_off_wins_over_a_missing_lockfile(self):
        repo = self.checkout(python="both")
        (repo / ".harness" / "config.json").write_text(json.dumps({"auto_install": False}))
        self.assertEqual(self.lines(self.status(repo)), [s_off("python")])

    def test_settled_entry_wins_over_a_missing_manager(self):
        repo = self.python_repo()
        self.write_state(repo, {"python": self.ok_entry(repo, "uv.lock", UV, False)})
        self.assertEqual(self.lines(self.status(repo)), [s_settled("python", UV)])

    def test_missing_manager_wins_over_a_failed_entry(self):
        repo = self.python_repo()
        self.write_state(repo, {"python": self.failed_entry(repo, "uv.lock", UV, "exit 2: boom")})
        self.assertEqual(self.lines(self.status(repo)), [s_nomanager("python", "uv", UV)])

    def test_none_line(self):
        repo = self.checkout(python="none", locks=["uv.lock"])
        self.assertEqual(self.lines(self.status(repo)), [S_NONE])

    def test_two_languages_are_listed_python_first(self):
        repo = self.checkout(python="both", js="both", locks=["uv.lock", "package-lock.json"])
        self.standin("npm")
        make_py_tools(repo)
        make_unrelated_node_modules(repo)
        self.assertEqual(self.lines(self.status(repo)),
                         [s_runnable("python", PY_TOOLS), s_manual("javascript", NPM)])

        other = self.checkout(python="both", js="both", locks=["package-lock.json"])
        make_js_tools(other)
        self.assertEqual(self.lines(self.status(other)),
                         [s_nolock("python"), s_runnable("javascript", JS_TOOLS)])


class TestStatusWait(CheckoutCase):
    def running_install(self, seconds):
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", sleep=seconds, **PY_CREATE)
        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])
        self.wait_lock(repo)
        return repo

    def test_wait_returns_when_the_install_ends_before_the_deadline(self):
        repo = self.running_install(2)

        result, elapsed = self.timed(lambda: self.status(repo, "--wait", "30"))

        self.assertEqual(self.lines(result), [s_runnable("python", PY_TOOLS)])
        self.assertLess(elapsed, 12.0)

    def test_wait_returns_at_the_deadline_while_the_install_still_runs(self):
        repo = self.running_install(5)

        result, elapsed = self.timed(lambda: self.status(repo, "--wait", "1"))

        lines = self.lines(result)
        self.assertEqual(len(lines), 1, lines)
        self.assertIsNotNone(s_running_pattern("python").fullmatch(lines[0]), lines)
        self.assertLessEqual(elapsed, 3.0)
        self.assertGreaterEqual(elapsed, 0.9)
        self.wait_done(repo, "python")


class TestHookTime(CheckoutCase):
    def test_hook_returns_within_the_limit_while_the_install_takes_six_seconds(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", sleep=6, **PY_CREATE)

        result, elapsed = self.timed(lambda: self.session_start(repo))

        self.assertEqual(self.lines(result), [m_start([UV])])
        self.assertLessEqual(elapsed, HOOK_LIMIT)
        self.wait_done(repo, "python")
        self.assertEqual(self.calls(), [call(UV, repo)])

    def test_worker_is_the_leader_of_its_own_session(self):
        repo = self.checkout(python="both", locks=["uv.lock"])
        self.standin("uv", sleep=4, **PY_CREATE)
        self.assertEqual(self.lines(self.session_start(repo)), [m_start([UV])])

        def lock_pid():
            try:
                return json.loads((self.state_dir(repo) / "lock").read_text())["pid"]
            except (OSError, ValueError, KeyError):
                return None
        self.assertTrue(self.wait_until(lambda: lock_pid() is not None, 15.0), "no readable lock")
        pid = lock_pid()

        self.assertEqual(os.getsid(pid), pid)
        self.wait_done(repo, "python")

    def test_hook_with_nothing_to_do_returns_within_the_limit(self):
        repo = self.checkout(python="none", js="none", locks=["uv.lock", "package-lock.json"])

        result, elapsed = self.timed(lambda: self.session_start(repo))

        self.assertEqual(self.lines(result), [])
        self.assertLessEqual(elapsed, HOOK_LIMIT)


class TestInstallerChanges(InstallerTestCase):
    LABEL = "install declared verification tools and restore git hooks at session start"
    LINES = (
        "a Claude SessionStart hook installs the lockfile's dependencies in the background when a verification "
        "tool declared in the project manifest is not present in the checkout, and sets core.hooksPath to "
        ".harness/git in a clone that has no hook manager",
        'set "auto_install": false in .harness/config.json to turn the automatic install off',
        "no data is migrated",
    )

    def session_start_commands(self, hooks):
        return [h["command"] for group in hooks.get("SessionStart", []) for h in group["hooks"]
                if "checkout_setup.py" in h["command"]]

    def assert_artefacts(self, repo):
        claude = json.loads((repo / ".claude" / "settings.json").read_text())["hooks"]
        commands = self.session_start_commands(claude)
        self.assertEqual(commands, ['python3 "$CLAUDE_PROJECT_DIR/.harness/bin/checkout_setup.py" hook'])
        self.assertNotIn("checkout_setup", (repo / ".codex" / "hooks.json").read_text())
        self.assertIn(".harness/sessions/checkout-setup/", (repo / ".gitignore").read_text().splitlines())
        default = json.loads((repo / ".harness" / "config.default.json").read_text())
        self.assertIs(default["auto_install"], True)

    def test_fresh_install_writes_the_hook_entry_the_ignore_line_and_the_config_default(self):
        repo = self.install()

        self.assert_artefacts(repo)
        self.assertEqual(json.loads((repo / ".harness" / "manifest.json").read_text())["version"], "0.55.0")
        self.assertEqual(run_installer("doctor", str(repo)).returncode, 0)

    def test_update_from_0530_announces_the_migration_and_keeps_doctor_green(self):
        repo = self.install()
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = "0.53.0"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        result = run_installer("update", str(repo), "--no-ci", "--no-commit", input="y\n" * 5)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(re.findall(r"^migration (\d+\.\d+\.\d+):", result.stdout, re.MULTILINE), ["0.54.0", "0.55.0"])
        self.assertIn(f"migration 0.54.0: {self.LABEL}", result.stdout)
        start = result.stdout.index("migration 0.54.0:")
        positions = [result.stdout.index(line, start) for line in self.LINES]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(json.loads(manifest_path.read_text())["version"], "0.55.0")
        self.assert_artefacts(repo)
        self.assertEqual(run_installer("doctor", str(repo)).returncode, 0)

    def test_update_from_an_install_without_the_new_artefacts_adds_them(self):
        repo = self.install()
        settings_path = repo / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        groups = settings["hooks"]["SessionStart"]
        settings["hooks"]["SessionStart"] = [
            g for g in groups if not any("checkout_setup.py" in h["command"] for h in g["hooks"])]
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        ignore = repo / ".gitignore"
        ignore.write_text("".join(line + "\n" for line in ignore.read_text().splitlines()
                                  if line != ".harness/sessions/checkout-setup/"))
        default_path = repo / ".harness" / "config.default.json"
        default = json.loads(default_path.read_text())
        del default["auto_install"]
        default_path.write_text(json.dumps(default, indent=2) + "\n")
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = "0.53.0"
        files = manifest.setdefault("files", {})
        files[".harness/config.default.json"] = hashlib.sha256(default_path.read_bytes()).hexdigest()
        for edited in (".claude/settings.json", ".gitignore"):
            if edited in files:
                files[edited] = hashlib.sha256((repo / edited).read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        result = run_installer("update", str(repo), "--no-ci", "--no-commit", input="y\n" * 5)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_artefacts(repo)


class TestSourceText(unittest.TestCase):
    def source_files(self):
        for root in ("harness", "installer"):
            for path in (REPO_ROOT / root).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    yield path

    def test_exactly_one_source_file_names_the_stryker_package(self):
        holders = [str(p.relative_to(REPO_ROOT)) for p in self.source_files()
                   if b"@stryker-mutator/core" in p.read_bytes()]
        self.assertEqual(len(holders), 1, holders)

    def test_readme_describes_the_switch_and_the_status_command(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("auto_install", readme)
        self.assertIn("checkout_setup.py status", readme)


if __name__ == "__main__":
    unittest.main()
