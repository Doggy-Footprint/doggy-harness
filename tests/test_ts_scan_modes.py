import os
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.fake_uv import calls, tool_dir
from tests.test_comment_detection import WARNING_ENTRY
from tests.test_comment_gate import AGENT_SENTENCE, WARN, RepoTestCase, git

MODES = ("staged", "gate_yes", "gate_no", "legacy")
TITLE = "Comment check could not run"
PINS = ("tree-sitter==0.27.0", "tree-sitter-typescript==0.23.2")
TS_ONLY = {"a.ts": "const a = 1;\n// note\n"}
MIXED = {"a.py": "x = 1\n# c\n", "b.kt": "val a = 1\n// k\n"}


class ScanModeCase(RepoTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.log = Path(tmp.name) / "uv.log"

    def scenario(self, mode, files, base_files=None):
        repo = self.make_repo()
        self.commit_file(repo, "keep.md", "keep\n")
        for name, text in (base_files or {}).items():
            self.commit_file(repo, name, text)
        base = git(repo, "rev-parse", "HEAD").stdout.strip()
        for name, text in files.items():
            if text is None:
                (repo / name).unlink()
            else:
                (repo / name).write_text(text)
        git(repo, "add", "-A")
        if mode == "staged":
            return repo, ["--staged"]
        git(repo, "commit", "-q", "-m", "head")
        head = git(repo, "rev-parse", "HEAD").stdout.strip()
        extra = {"gate_yes": ["--approved", "yes"], "gate_no": ["--approved", "no"], "legacy": []}[mode]
        return repo, [base, head, *extra]

    def run_scan(self, repo, args, uv_mode=None):
        directory = tool_dir(self, with_uv=uv_mode is not None)
        env = dict(os.environ, PATH=str(directory), FAKE_UV_LOG=str(self.log), FAKE_UV_MODE=uv_mode or "ok")
        return subprocess.run([sys.executable, str(WARN), *args], cwd=repo, env=env, capture_output=True, text=True)

    def assert_findings(self, mode, r, path, line):
        expected_rc = 1 if mode == "gate_no" else 0
        self.assertEqual(r.returncode, expected_rc, r.stdout + r.stderr)
        self.assertNotIn(TITLE, r.stdout + r.stderr)
        if mode == "staged":
            self.assertRegex(r.stderr, rf"(?m)^{path}:{line}: ")
        else:
            self.assertIn((path, str(line)), WARNING_ENTRY.findall(r.stdout))

    def assert_could_not_run(self, mode, r, *fragments):
        out = r.stdout + r.stderr
        if mode == "staged":
            self.assertEqual(r.returncode, 0, out)
            self.assertIn("comment check could not run for a.ts: ", r.stderr)
            self.assertIn(AGENT_SENTENCE, r.stderr)
        elif mode.startswith("gate"):
            self.assertEqual(r.returncode, 1, out)
            self.assertTrue([l for l in r.stdout.splitlines() if l.startswith(f"::error title={TITLE}::")], out)
        else:
            self.assertEqual(r.returncode, 0, out)
            self.assertTrue([l for l in r.stdout.splitlines() if l.startswith(f"::warning title={TITLE}::")], out)
        self.assertIn("a.ts", out)
        for fragment in fragments:
            self.assertIn(fragment, out)

    def assert_command(self, argv, offline):
        self.assertEqual(argv[0], "run")
        self.assertIn("--no-project", argv)
        self.assertEqual("--offline" in argv, offline)
        for pin in PINS:
            self.assertEqual(argv[argv.index(pin) - 1], "--with")
        python = argv.index("python")
        self.assertEqual(argv[python + 1], "-I")
        self.assertEqual(Path(argv[python + 2]).name, "ts_comments.py")
        self.assertEqual(len(argv), python + 3)


class DecisionTableTests(ScanModeCase):
    def test_o4_t1_no_ts_file_never_starts_uv_and_keeps_findings(self):
        for mode in MODES:
            for uv_mode in (None, "ok", "both_fail", "list"):
                with self.subTest(rule="t1", mode=mode, uv=uv_mode):
                    self.log.unlink(missing_ok=True)
                    repo, args = self.scenario(mode, MIXED)
                    r = self.run_scan(repo, args, uv_mode)
                    self.assertEqual(calls(self.log), [])
                    self.assertEqual(r.returncode, 1 if mode == "gate_no" else 0, r.stdout + r.stderr)
                    self.assertNotIn(TITLE, r.stdout + r.stderr)
                    if mode == "staged":
                        self.assertIn("a.py:2: # c", r.stderr)
                        self.assertIn("b.kt:2: // k", r.stderr)
                    else:
                        self.assertIn(("a.py", "2"), WARNING_ENTRY.findall(r.stdout))
                        self.assertIn(("b.kt", "2"), WARNING_ENTRY.findall(r.stdout))

    def test_o4_t1_deletion_only_ts_changes_never_start_uv(self):
        base = {"a.ts": "const a = 1;\nconst b = 2;\nconst c = 3;\n"}
        variants = {
            "deleted_lines": {"a.ts": "const a = 1;\nconst c = 3;\n"},
            "deleted_file": {"a.ts": None},
        }
        for name, change in variants.items():
            for mode in MODES:
                for uv_mode in (None, "ok"):
                    with self.subTest(rule="t1", variant=name, mode=mode, uv=uv_mode):
                        self.log.unlink(missing_ok=True)
                        repo, args = self.scenario(mode, change, base)
                        r = self.run_scan(repo, args, uv_mode)
                        self.assertEqual(calls(self.log), [])
                        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                        self.assertNotIn(TITLE, r.stdout + r.stderr)
                        self.assertNotIn("::warning", r.stdout)
                        self.assertNotIn(AGENT_SENTENCE, r.stderr)

    def test_o4_t1_deletion_only_ts_change_with_python_comment_still_reports_it(self):
        base = {"a.ts": "const a = 1;\nconst b = 2;\nconst c = 3;\n"}
        change = {"a.ts": "const a = 1;\nconst c = 3;\n", "p.py": "x = 1\n# c\n"}
        for mode in MODES:
            for uv_mode in (None, "ok"):
                with self.subTest(rule="t1", mode=mode, uv=uv_mode):
                    self.log.unlink(missing_ok=True)
                    repo, args = self.scenario(mode, change, base)
                    r = self.run_scan(repo, args, uv_mode)
                    self.assertEqual(calls(self.log), [])
                    self.assert_findings(mode, r, "p.py", 2)

    def test_o4_t2_offline_success_is_one_call_with_pins_and_isolated_mode(self):
        for mode in MODES:
            with self.subTest(rule="t2", mode=mode):
                self.log.unlink(missing_ok=True)
                repo, args = self.scenario(mode, TS_ONLY)
                r = self.run_scan(repo, args, "ok")
                self.assert_findings(mode, r, "a.ts", 2)
                recorded = calls(self.log)
                self.assertEqual(len(recorded), 1)
                self.assert_command(recorded[0]["argv"], offline=True)

    def test_o4_t2_scanner_stdin_carries_path_grammar_and_source(self):
        import json
        repo, args = self.scenario("staged", TS_ONLY)
        self.run_scan(repo, args, "ok")
        stdin = json.loads(calls(self.log)[0]["stdin"])
        self.assertEqual(list(stdin), ["a.ts"])
        self.assertEqual(stdin["a.ts"]["grammar"], "typescript")
        self.assertIn("// note", stdin["a.ts"]["source"])

    def test_o4_t3_offline_failure_retries_online_once(self):
        for mode in MODES:
            with self.subTest(rule="t3", mode=mode):
                self.log.unlink(missing_ok=True)
                repo, args = self.scenario(mode, TS_ONLY)
                r = self.run_scan(repo, args, "offline_fail")
                self.assert_findings(mode, r, "a.ts", 2)
                recorded = calls(self.log)
                self.assertEqual(len(recorded), 2)
                self.assert_command(recorded[0]["argv"], offline=True)
                self.assert_command(recorded[1]["argv"], offline=False)
                self.assertEqual([a for a in recorded[0]["argv"] if a != "--offline"], recorded[1]["argv"])

    def test_o4_t4_uv_absent_fails_closed_in_every_mode(self):
        for mode in MODES:
            with self.subTest(rule="t4", mode=mode):
                repo, args = self.scenario(mode, TS_ONLY)
                r = self.run_scan(repo, args, None)
                self.assert_could_not_run(mode, r, "uv not found on PATH")

    def test_o4_t5_both_runs_failing_fail_closed_with_last_exit_code_and_stderr_line(self):
        for mode in MODES:
            with self.subTest(rule="t5", mode=mode):
                self.log.unlink(missing_ok=True)
                repo, args = self.scenario(mode, TS_ONLY)
                r = self.run_scan(repo, args, "both_fail")
                self.assert_could_not_run(mode, r, "7", "network down")
                self.assertEqual(len(calls(self.log)), 2)

    def test_o4_t6_malformed_scanner_output_fails_closed_in_every_mode(self):
        for mode in MODES:
            for uv_mode in ("list", "missing", "nonint", "notjson"):
                with self.subTest(rule="t6", mode=mode, output=uv_mode):
                    self.log.unlink(missing_ok=True)
                    repo, args = self.scenario(mode, TS_ONLY)
                    r = self.run_scan(repo, args, uv_mode)
                    self.assert_could_not_run(mode, r, "unexpected scanner output")
                    self.assertEqual(len(calls(self.log)), 1)


class GrammarSelectionTests(ScanModeCase):
    EXPECTED = {
        "e1.ts": "typescript", "e2.mts": "typescript", "e3.cts": "typescript",
        "e4.tsx": "tsx", "e5.js": "tsx", "e6.jsx": "tsx", "e7.mjs": "tsx", "e8.cjs": "tsx",
    }

    def test_o2_all_extensions_in_one_scan_with_grammar_per_extension(self):
        import json
        files = {name: "// k\n" for name in self.EXPECTED}
        files["p.py"] = "# c\n"
        repo, args = self.scenario("staged", files)
        r = self.run_scan(repo, args, "ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        recorded = calls(self.log)
        self.assertEqual(len(recorded), 1)
        stdin = json.loads(recorded[0]["stdin"])
        self.assertEqual({name: item["grammar"] for name, item in stdin.items()}, self.EXPECTED)
        for name in self.EXPECTED:
            self.assertRegex(r.stderr, rf"(?m)^{name}:1: // k")
        self.assertIn("p.py:1: # c", r.stderr)


class WorktreeTests(ScanModeCase):
    def linked(self):
        repo = self.make_repo()
        self.commit_file(repo, "keep.md", "keep\n")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        linked = Path(tmp.name) / "wt"
        git(repo, "worktree", "add", "-q", "-b", "wt", str(linked))
        (linked / "a.ts").write_text(TS_ONLY["a.ts"])
        git(linked, "add", "a.ts")
        return repo, linked

    def state(self, root):
        files = set()
        for current, dirs, names in os.walk(root):
            if ".git" in dirs:
                dirs.remove(".git")
            files.update(os.path.relpath(os.path.join(current, n), root) for n in names)
            files.update(os.path.relpath(os.path.join(current, d), root) + "/" for d in dirs)
        status = git(root, "status", "--porcelain", "--ignored").stdout
        return files, status

    def test_o4_t7_fake_uv_staged_scan_in_linked_worktree_adds_nothing(self):
        repo, linked = self.linked()
        before = (self.state(repo), self.state(linked))
        r = self.run_scan(linked, ["--staged"], "ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("a.ts:2: // note", r.stderr)
        recorded = calls(self.log)
        self.assertEqual(len(recorded), 1)
        self.assertIn("--offline", recorded[0]["argv"])
        self.assertEqual((self.state(repo), self.state(linked)), before)

    def test_o4_t7_real_uv_staged_scan_in_linked_and_main_worktree_adds_nothing(self):
        repo, linked = self.linked()
        (repo / "m.ts").write_text("const m = 1;\n// main\n")
        git(repo, "add", "m.ts")
        before = (self.state(repo), self.state(linked))
        for cwd, expected in ((linked, "a.ts:2: // note"), (repo, "m.ts:2: // main")):
            with self.subTest(worktree=cwd.name):
                r = subprocess.run([sys.executable, str(WARN), "--staged"], cwd=cwd, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(expected, r.stderr)
                self.assertNotIn(TITLE, r.stderr)
        self.assertEqual((self.state(repo), self.state(linked)), before)
