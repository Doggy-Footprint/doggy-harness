import os
import stat
import subprocess

from customization_case import GIT_NAMES, CustomizationCase
from test_installer import run_git

NOT_EXECUTABLE = "{name}: .harness/local/git/{name} is not executable; run chmod +x .harness/local/git/{name}"


class HookDispatchCase(CustomizationCase):
    def setUp(self):
        self.marks = self.temp_dir()

    def ready(self):
        repo = self.new_repo()
        run_git(repo, "config", "core.hooksPath", ".harness/git")
        return repo

    def script(self, label, code, record_stdin=False):
        lines = ["#!/bin/sh", f'echo "{label}:$*" >> "{self.marks}/order"']
        if record_stdin:
            lines.append(f'cat > "{self.marks}/{label}.stdin"')
        lines.append(f"exit {code}")
        return "\n".join(lines) + "\n"

    def install_hooks(self, repo, name, local, private, record_stdin=False):
        """local: None, an exit code, or 'plain' for a file without the executable bit; private: None or exit code."""
        if local == "plain":
            self.write(repo, f".harness/local/git/{name}", self.script("local", 0, record_stdin), 0o644)
        elif local is not None:
            self.write(repo, f".harness/local/git/{name}", self.script("local", local, record_stdin), 0o755)
        if private is not None:
            self.write(repo, f".git/hooks/{name}", self.script("private", private, record_stdin), 0o755)

    def order(self):
        path = self.marks / "order"
        return [line.split(":", 1)[0] for line in path.read_text().splitlines()] if path.exists() else []

    def orders_with_args(self):
        path = self.marks / "order"
        return path.read_text().splitlines() if path.exists() else []

    def reset(self):
        for path in self.marks.iterdir():
            path.unlink()

    def direct(self, repo, name, *args, stdin=b""):
        return subprocess.run([str(repo / ".harness" / "git" / name), *args], input=stdin, capture_output=True,
                              cwd=repo, env=self.env())

    def expected_order(self, local, private):
        order = []
        if local is not None and local != "plain":
            order.append("local")
        if local is None or local == "plain" or local == 0:
            if private is not None:
                order.append("private")
        return order

    def expected_status(self, local, private):
        if local not in (None, "plain", 0):
            return local
        return private or 0


COMBOS = [(local, private) for local in (None, 0, 1, "plain") for private in (None, 0)]


class TestUncheckedHooks(HookDispatchCase):
    ARGS = {"post-merge": ("0",), "pre-push": ("origin", "file:///x"), "post-checkout": ("a" * 40, "b" * 40, "1")}

    def test_every_local_and_private_combination_for_each_unchecked_hook(self):
        for name, args in self.ARGS.items():
            for local, private in COMBOS:
                with self.subTest(hook=name, local=local, private=private):
                    repo = self.ready()
                    self.reset()
                    self.install_hooks(repo, name, local, private)
                    result = self.direct(repo, name, *args, stdin=b"")
                    self.assertEqual(result.returncode, self.expected_status(local, private), result.stderr)
                    self.assertEqual(self.order(), self.expected_order(local, private))
                    arg_text = " ".join(args)
                    for line in self.orders_with_args():
                        self.assertEqual(line.split(":", 1)[1], arg_text)
                    notice = NOT_EXECUTABLE.format(name=name)
                    self.assertEqual(notice in result.stderr.decode().splitlines(), local == "plain", result.stderr)
                    self.assertEqual(result.stdout, b"")

    def test_a_failing_local_hook_exits_with_its_own_status(self):
        repo = self.ready()
        self.install_hooks(repo, "post-merge", 7, 0)
        self.assertEqual(self.direct(repo, "post-merge", "0").returncode, 7)
        self.assertEqual(self.order(), ["local"])

    def test_a_failing_private_hook_exits_with_its_own_status(self):
        repo = self.ready()
        self.install_hooks(repo, "post-merge", 0, 5)
        self.assertEqual(self.direct(repo, "post-merge", "0").returncode, 5)
        self.assertEqual(self.order(), ["local", "private"])


class TestStdinIdentity(HookDispatchCase):
    PAYLOAD = b"refs/heads/main 1111111111111111111111111111111111111111 refs/heads/main 0000\n\xff\x00\xfe tail"

    def test_local_and_private_pre_push_receive_the_same_bytes_in_order(self):
        repo = self.ready()
        self.install_hooks(repo, "pre-push", 0, 0, record_stdin=True)
        result = self.direct(repo, "pre-push", "origin", "url", stdin=self.PAYLOAD)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.order(), ["local", "private"])
        self.assertEqual((self.marks / "local.stdin").read_bytes(), self.PAYLOAD)
        self.assertEqual((self.marks / "private.stdin").read_bytes(), self.PAYLOAD)

    def test_a_real_push_gives_both_hooks_the_same_ref_lines(self):
        repo = self.ready()
        remote = self.temp_dir() / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        run_git(repo, "remote", "add", "origin", str(remote))
        self.install_hooks(repo, "pre-push", 0, 0, record_stdin=True)
        branch = self.branch(repo)
        pushed = subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", branch], capture_output=True,
                                text=True, env=self.env())
        self.assertEqual(pushed.returncode, 0, pushed.stdout + pushed.stderr)
        self.assertEqual(self.order(), ["local", "private"])
        local = (self.marks / "local.stdin").read_bytes()
        self.assertEqual(local, (self.marks / "private.stdin").read_bytes())
        self.assertIn(self.head(repo).encode(), local)
        self.assertIn(f"refs/heads/{branch}".encode(), local)

    def test_a_real_push_is_refused_by_a_failing_local_hook_and_the_private_hook_does_not_run(self):
        repo = self.ready()
        remote = self.temp_dir() / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        run_git(repo, "remote", "add", "origin", str(remote))
        self.install_hooks(repo, "pre-push", 1, 0)
        pushed = subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", self.branch(repo)],
                                capture_output=True, text=True, env=self.env())
        self.assertNotEqual(pushed.returncode, 0)
        self.assertEqual(self.order(), ["local"])
        refs = subprocess.run(["git", "-C", str(remote), "for-each-ref"], capture_output=True, text=True).stdout
        self.assertEqual(refs, "")

    def test_a_pre_push_without_input_gives_empty_stdin_to_both(self):
        repo = self.ready()
        self.install_hooks(repo, "pre-push", 0, 0, record_stdin=True)
        self.direct(repo, "pre-push", "origin", "url", stdin=b"")
        self.assertEqual((self.marks / "local.stdin").read_bytes(), b"")
        self.assertEqual((self.marks / "private.stdin").read_bytes(), b"")


class TestGitInvokesTheHooks(HookDispatchCase):
    def test_post_checkout_runs_local_then_private_in_a_real_checkout(self):
        repo = self.ready()
        self.install_hooks(repo, "post-checkout", 0, 0)
        run_git(repo, "checkout", "-q", "-b", "other")
        lines = self.orders_with_args()
        self.assertEqual([l.split(":", 1)[0] for l in lines], ["local", "private"])
        self.assertEqual(lines[0].split(":", 1)[1], lines[1].split(":", 1)[1])
        self.assertEqual(len(lines[0].split(":", 1)[1].split()), 3)

    def test_post_merge_runs_local_then_private_in_a_real_merge(self):
        repo = self.ready()
        base = self.branch(repo)
        run_git(repo, "checkout", "-q", "-b", "feature")
        self.write(repo, "src/feature.py", "f = 1\n")
        run_git(repo, "add", "-A")
        self.commit(repo, "feature")
        run_git(repo, "checkout", "-q", base)
        self.install_hooks(repo, "post-merge", 0, 0)
        run_git(repo, "merge", "-q", "--ff-only", "feature")
        self.assertEqual(self.order(), ["local", "private"])


class TestCheckedHooks(HookDispatchCase):
    def stage(self, repo, name="src/b.py"):
        self.write(repo, name, "b = 2\n")
        run_git(repo, "add", name)

    def test_every_combination_for_pre_commit_and_commit_msg(self):
        for name in ("pre-commit", "commit-msg"):
            for local, private in COMBOS:
                with self.subTest(hook=name, local=local, private=private):
                    repo = self.ready()
                    self.reset()
                    self.install_hooks(repo, name, local, private)
                    self.stage(repo)
                    before = self.head(repo)
                    result = self.commit_with_hooks(
                        repo, "work\n\nRequest: a request\nIntent: an intent")
                    expected_status = self.expected_status(local, private)
                    self.assertEqual(result.returncode == 0, expected_status == 0, result.stdout + result.stderr)
                    self.assertEqual(self.head(repo) != before, expected_status == 0)
                    self.assertEqual(self.order(), self.expected_order(local, private))
                    notice = NOT_EXECUTABLE.format(name=name)
                    self.assertEqual(notice in result.stderr.splitlines(), local == "plain", result.stderr)

    def test_a_failing_harness_check_ends_pre_commit_before_the_local_and_private_hooks(self):
        repo = self.ready()
        self.install_hooks(repo, "pre-commit", 0, 0)
        records = repo / "agent-docs" / "try-n-fail"
        records.mkdir(parents=True, exist_ok=True)
        (records / "index.md").unlink(missing_ok=True)
        (records / "0123456789abcdef-x.md").write_text("# X\n")
        run_git(repo, "add", "-f", "agent-docs/try-n-fail/0123456789abcdef-x.md")
        before = self.head(repo)
        result = self.commit_with_hooks(repo, "violating")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.head(repo), before)
        self.assertEqual(self.order(), [])
        self.assertIn("harness rule violations found", result.stderr)

    def test_a_failing_local_pre_commit_runs_after_the_harness_checks_and_blocks_the_commit(self):
        repo = self.ready()
        self.install_hooks(repo, "pre-commit", 1, 0)
        self.stage(repo)
        before = self.head(repo)
        result = self.commit_with_hooks(repo, "work")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.head(repo), before)
        self.assertEqual(self.order(), ["local"])

    def test_the_local_pre_commit_receives_the_arguments_git_gives_it(self):
        repo = self.ready()
        self.install_hooks(repo, "commit-msg", 0, 0)
        self.stage(repo)
        self.commit_with_hooks(repo, "work\n\nRequest: a request\nIntent: an intent")
        lines = self.orders_with_args()
        self.assertEqual(len(lines), 2, lines)
        self.assertEqual(lines[0].split(":", 1)[1], lines[1].split(":", 1)[1])
        self.assertTrue(lines[0].split(":", 1)[1].strip())


class TestEveryHookName(HookDispatchCase):
    def args_for(self, name):
        message = self.marks / "message"
        message.write_text("work\n\nRequest: a request\nIntent: an intent\n")
        return {
            "applypatch-msg": (str(message),), "commit-msg": (str(message),),
            "prepare-commit-msg": (str(message),), "pre-rebase": ("main",),
            "post-checkout": ("a" * 40, "a" * 40, "1"), "post-merge": ("0",), "pre-push": ("origin", "url"),
            "post-rewrite": ("amend",), "pre-auto-gc": (), "pre-applypatch": (), "post-applypatch": (),
            "pre-commit": (), "pre-merge-commit": (), "post-commit": (),
        }[name]

    def test_all_14_hooks_exist_are_executable_and_exit_0_silently_with_nothing_installed(self):
        repo = self.ready()
        self.assertEqual(len(GIT_NAMES), 14)
        for name in GIT_NAMES:
            with self.subTest(hook=name):
                path = repo / ".harness" / "git" / name
                self.assertTrue(path.is_file())
                self.assertTrue(os.access(path, os.X_OK))
                self.assertTrue(path.stat().st_mode & stat.S_IXUSR)
                result = self.direct(repo, name, *self.args_for(name), stdin=b"")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((result.stdout, result.stderr), (b"", b""))

    def test_the_hook_directory_ships_no_other_dispatched_name_than_the_14(self):
        repo = self.ready()
        shipped = {p.name for p in (repo / ".harness" / "git").iterdir() if p.suffix == ""}
        self.assertTrue(set(GIT_NAMES) <= shipped)
        for excluded in ("reference-transaction", "push-to-checkout", "fsmonitor-watchman", "post-index-change",
                         "sendemail-validate"):
            self.assertNotIn(excluded, shipped)


class TestWorktreeAdd(HookDispatchCase):
    def recording_hook(self, repo):
        self.write(repo, ".harness/local/git/post-checkout",
                   f'#!/bin/sh\npwd -P >> "{self.marks}/cwd"\necho ran >> "{self.marks}/order"\n', 0o755)

    def predating_branch(self, repo):
        empty_tree = run_git(repo, "hash-object", "-t", "tree", "/dev/null").stdout.strip()
        commit = run_git(repo, "commit-tree", empty_tree, "-m", "before the install").stdout.strip()
        run_git(repo, "branch", "predates", commit)
        self.assertEqual(run_git(repo, "ls-tree", "-r", "--name-only", "predates").stdout, "")
        return "predates"

    def assert_worktree_runs_the_local_hook_once(self, repo, branch):
        self.recording_hook(repo)
        target = self.temp_dir() / "wt"
        result = subprocess.run(["git", "-C", str(repo), "worktree", "add", str(target), branch],
                                capture_output=True, text=True, env=self.env())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.order(), ["ran"])
        recorded = (self.marks / "cwd").read_text().splitlines()
        self.assertEqual(len(recorded), 1, recorded)
        self.assertEqual(os.path.realpath(recorded[0]), os.path.realpath(target))

    def test_a_worktree_on_a_branch_that_predates_the_install_runs_the_main_checkouts_local_hook_once(self):
        repo = self.ready()
        self.assert_worktree_runs_the_local_hook_once(repo, self.predating_branch(repo))

    def test_a_worktree_on_a_branch_at_the_installed_commit_runs_the_local_hook_once_in_the_worktree(self):
        repo = self.ready()
        run_git(repo, "branch", "installed")
        self.assert_worktree_runs_the_local_hook_once(repo, "installed")
