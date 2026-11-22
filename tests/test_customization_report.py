import json
import re
import subprocess
import sys

from customization_case import AGENTS, FIVE, CustomizationCase, copy_source, sha256
from old_release import BASE_0470, BASE_0551
from test_installer import run_installer

LOCAL = {
    ".harness/local/git/pre-commit": (b"#!/bin/sh\nexit 0\n", 0o755),
    ".harness/local/git/post-merge": (b"#!/bin/sh\nexit 0\n", 0o644),
    ".harness/local/doggy-workflow/verify.md": ("Check the audit log.\n".encode(), 0o644),
    ".harness/local/agents/implementer.md": ("Run the linter.\n".encode(), 0o640),
    ".harness/local/hooks/sub/lint.py": (b"print('lint')\n", 0o755),
    ".harness/local/notes.txt": (b"\x00\xff\xfe binary \n", 0o600),
}
EMPTY_DIRS = (".harness/local/empty", ".harness/local/git/nested-empty")


class ReportCase(CustomizationCase):
    def customization_section(self, stdout):
        return self.section(stdout, "customization")

    def section_lines(self, stdout, name):
        section = self.section(stdout, name)
        self.assertIsNotNone(section, stdout)
        return [line.strip() for line in section.splitlines() if line.strip()]

    def migration_text(self, stdout):
        self.assertIn("migration 0.56.0:", stdout)
        return stdout[stdout.index("migration 0.56.0:"):]

    def planned_lines(self, stdout):
        rest = stdout.split("migration 0.56.0:", 1)[1].splitlines()[1:]
        lines = []
        for line in rest:
            if line.startswith("migration ") or line.startswith("==") or line.startswith("Apply migration"):
                break
            if line.strip().startswith("- "):
                lines.append(line.strip().lower())
        return lines

    def assert_migration_lines(self, stdout):
        self.assertIn("migration 0.56.0:", stdout)
        lines = self.planned_lines(stdout)
        self.assertTrue(lines, stdout)
        items = {
            "precedence": ("agents.md", ".harness/local/git/", ".harness/local/doggy-workflow/",
                           ".harness/local/agents/", ".harness/local/hooks/", "follow"),
            "edited file": ("edited", "stop", "update"),
            "shadowing skill": ("skill", "shadow", "stop"),
            "invalid config": ("config", "invalid", "install", "update"),
            "existing git hook": (".harness/git/", ".harness/local/git/", "move", "stop"),
            "kept hook groups": (".harness/local/", "hook", "kept"),
            "no data": ("no data is migrated",),
        }
        for name, words in items.items():
            with self.subTest(item=name):
                self.assertTrue(any(all(w in line for w in words) for line in lines), (words, lines))
        self.assertTrue(any("notice" in line and "confirm" in line and "agents.md" in line for line in lines), lines)

    def old_fixture(self, commit):
        repo = self.install_old(commit)
        self.set_definition(repo)
        return repo

    def update_old(self, repo, *args):
        return run_installer("update", str(repo), "--no-ci", "--no-commit", *args, input="y\n" * 80, exact=True)


class TestUpdateReport(ReportCase):
    def test_e1_update_from_0_47_0_lists_the_0_56_0_migration_and_the_customization_section(self):
        repo = self.old_fixture(BASE_0470)
        result = self.update_old(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_migration_lines(result.stdout)
        self.assertEqual(self.version(repo), "0.56.0")
        self.assertIn("- unconfirmed AGENTS.md", self.section_lines(result.stdout, "customization"))
        self.assertEqual(self.status_lines(repo), [self.item_line("unconfirmed", AGENTS, FIVE)])

    def test_e2_update_from_0_55_1_lists_the_0_56_0_migration_and_the_customization_section(self):
        repo = self.old_fixture(BASE_0551)
        result = self.update_old(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_migration_lines(result.stdout)
        self.assertEqual(re.findall(r"^migration (\d+\.\d+\.\d+):", result.stdout, re.MULTILINE), ["0.56.0"])
        self.assertIn("- unconfirmed AGENTS.md", self.section_lines(result.stdout, "customization"))

    def test_the_customization_section_follows_manual_review(self):
        repo = self.project()
        subprocess.run(["git", "-C", str(repo), "add", "-A", "-f"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "--no-verify", "-m", "base"], check=True)
        (repo / ".harness" / "hooks" / "spec_gate.py").unlink()
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== manual review ==", result.stdout)
        self.assertIn("== customization ==", result.stdout)
        self.assertLess(result.stdout.index("== manual review =="), result.stdout.index("== customization =="))

    def prepare_older_block(self, repo):
        self.write_owned(repo, FIVE[0], "an older harness block\n")
        self.confirm(repo, AGENTS)

    def test_e3_dry_run_shows_harness_changed_for_a_confirmed_item_and_writes_nothing(self):
        repo = self.project()
        self.prepare_older_block(repo)
        before = self.snapshot(repo)
        result = run_installer("update", str(repo), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("- harness-changed AGENTS.md", self.section_lines(result.stdout, "customization"))
        self.assertEqual(self.snapshot(repo), before)

    def test_update_that_rewrites_a_compare_file_lists_the_item_and_leaves_it_harness_changed(self):
        repo = self.project()
        self.prepare_older_block(repo)
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("- harness-changed AGENTS.md", self.section_lines(result.stdout, "customization"))
        self.assertEqual(self.status_lines(repo), [self.item_line("harness-changed", AGENTS, FIVE)])

    def test_e4_everything_confirmed_and_no_problem_has_no_section(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        for args in ((), ("--dry-run",)):
            with self.subTest(args=args):
                result = run_installer("update", str(repo), *args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("== customization ==", result.stdout)

    def test_problems_are_listed_with_a_dash(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        self.write(repo, ".harness/config.json", json.dumps({"auto_instal": True}))
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = self.section_lines(result.stdout, "customization")
        self.assertTrue(any(l.startswith("- unknown-config-key") and "auto_instal" in l for l in lines), lines)

    def test_a_local_unrecognized_file_is_listed_and_the_exit_status_is_unchanged(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        self.write(repo, ".harness/local/notes.txt", "n\n")
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.section_lines(result.stdout, "customization"), ["- unrecognized .harness/local/notes.txt"])


class TestDoctorAndImport(ReportCase):
    def test_doctor_reports_an_invalid_config_as_a_conflict_with_exit_1(self):
        for name, raw in {"truncated json": '{"auto_install": false,', "array": "[]"}.items():
            with self.subTest(config=name):
                repo = self.project()
                self.write(repo, ".harness/config.json", raw)
                result = run_installer("doctor", str(repo))
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                conflict = self.section(result.stdout, "conflict")
                self.assertIsNotNone(conflict, result.stdout)
                self.assertIn("config-invalid", conflict)
                self.assertIn(".harness/config.json", conflict)

    def test_doctor_lists_an_unknown_key_under_manual_review_without_changing_the_exit_status(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        self.write(repo, ".harness/config.json", json.dumps({"auto_instal": False, "agent_model": "opus"}))
        result = run_installer("doctor", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        review = self.section(result.stdout, "manual review")
        self.assertIn("unknown-config-key auto_instal", review)
        self.assertNotIn("agent_model", review)
        self.assertIsNone(self.section(result.stdout, "conflict"))

    def test_doctor_lists_an_unconfirmed_item_under_manual_review(self):
        repo = self.project()
        result = run_installer("doctor", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unconfirmed AGENTS.md", self.section(result.stdout, "manual review"))

    def test_doctor_lists_a_review_file_problem_under_manual_review(self):
        repo = self.project()
        self.write(repo, ".harness/customization-review.json", "[]")
        result = run_installer("doctor", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review-file-invalid", self.section(result.stdout, "manual review"))

    def test_doctor_with_everything_confirmed_and_no_problem_lists_no_customization_line(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        result = run_installer("doctor", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("unconfirmed", result.stdout)

    def prepare_import(self, repo):
        self.write(repo, ".harness/local/notes.txt", "n\n")
        self.write(repo, ".harness/config.json", json.dumps({"agent_model": "opus"}))
        self.confirm(repo, AGENTS)
        self.write(repo, ".harness/local/agents/implementer.md", "notes\n")

    def test_import_json_does_not_list_local_review_or_config_files_under_added(self):
        repo = self.project()
        self.prepare_import(repo)
        result = run_installer("import", str(repo), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        for path in data["added"]:
            self.assertFalse(path.startswith(".harness/local/"), path)
        for path in (".harness/customization-review.json", ".harness/config.json"):
            self.assertNotIn(path, data["added"])
        states = {entry["path"]: entry["state"] for entry in data["customization"]}
        self.assertEqual(states[AGENTS], "confirmed")
        self.assertEqual(states[".harness/local/notes.txt"], "unrecognized")
        self.assertEqual(states[".harness/local/agents/implementer.md"], "unconfirmed")

    def test_import_text_has_a_customization_section_and_lists_no_local_file_as_added(self):
        repo = self.project()
        self.prepare_import(repo)
        result = run_installer("import", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = self.section_lines(result.stdout, "customization")
        self.assertIn("confirmed AGENTS.md", [l.removeprefix("- ") for l in lines])
        self.assertIn("unrecognized .harness/local/notes.txt", [l.removeprefix("- ") for l in lines])
        outside = result.stdout.replace(self.section(result.stdout, "customization"), "")
        self.assertNotIn(".harness/local/", outside)
        self.assertNotIn("customization-review.json", outside)
        self.assertNotIn(".harness/config.json", outside)

    def test_import_without_any_item_says_none(self):
        repo = self.project()
        (repo / AGENTS).unlink()
        text = run_installer("import", str(repo))
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertEqual(self.section_lines(text.stdout, "customization"), ["none"])
        data = json.loads(run_installer("import", str(repo), "--json").stdout)
        self.assertEqual(data["customization"], [])


class TestRuntimeConfigFallback(CustomizationCase):
    WARNING = "pre-commit: .harness/config.json is not a JSON object; harness defaults are used"
    FORMS = {"truncated json": '{"auto_install": false,', "array": "[]", "string": '"x"'}

    def test_pre_commit_warns_and_still_commits(self):
        for name, raw in self.FORMS.items():
            with self.subTest(config=name):
                repo = self.new_repo()
                self.write(repo, ".harness/config.json", raw)
                self.write(repo, "src/b.py", "b = 2\n")
                subprocess.run(["git", "-C", str(repo), "add", "src/b.py"], check=True)
                before = self.head(repo)
                result = self.commit_with_hooks(repo, "add b")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotEqual(self.head(repo), before)
                self.assertIn(self.WARNING, result.stderr.splitlines())

    def test_pre_commit_with_a_valid_config_does_not_warn(self):
        repo = self.new_repo()
        self.write(repo, ".harness/config.json", json.dumps({"agent_model": "opus"}))
        self.write(repo, "src/b.py", "b = 2\n")
        subprocess.run(["git", "-C", str(repo), "add", "src/b.py"], check=True)
        result = self.commit_with_hooks(repo, "add b")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("not a JSON object", result.stderr)

    def start_implementer(self, repo):
        self.write(repo, "agent-docs/specs/0123456789abcdef-x.md",
                   "---\nversion: 1\n---\n# Paths\nTest command: python3 -m unittest\n")
        payload = {"hook_event_name": "SubagentStart", "agent_type": "implementer", "agent_id": "a1"}
        self.assertEqual(self.run_script(repo, "spec_gate.py", payload).returncode, 0)

    def gate_bash(self, repo, command="python3 -m unittest"):
        return self.run_script(repo, "spec_gate.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                                       "tool_input": {"command": command}})

    def test_the_test_command_gate_blocks_under_an_invalid_config(self):
        for name, raw in self.FORMS.items():
            with self.subTest(config=name):
                repo = self.new_repo()
                self.write(repo, ".harness/config.json", raw)
                self.start_implementer(repo)
                blocked = self.gate_bash(repo)
                self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
                self.assertNotIn("Traceback", blocked.stderr)

    def test_the_gate_lets_an_unrelated_command_pass_under_an_invalid_config(self):
        repo = self.new_repo()
        self.write(repo, ".harness/config.json", "[]")
        self.start_implementer(repo)
        self.assertEqual(self.gate_bash(repo, "ls").returncode, 0)

    def test_the_gate_blocks_with_a_valid_config_as_well(self):
        repo = self.new_repo()
        self.write(repo, ".harness/config.json", json.dumps({"agent_model": "opus"}))
        self.start_implementer(repo)
        self.assertEqual(self.gate_bash(repo).returncode, 2)


class TestLocalPreservation(ReportCase):
    def populate(self, repo):
        for rel, (data, mode) in LOCAL.items():
            self.write(repo, rel, data, mode)
        for rel in EMPTY_DIRS:
            (repo / rel).mkdir(parents=True, exist_ok=True)
        return self.local_state(repo)

    def local_state(self, repo):
        files, dirs = self.tree(repo)
        return files, dirs

    def tree(self, repo):
        from customization_case import tree
        return tree(repo, ".harness/local")

    def assert_preserved(self, repo, before):
        files, dirs = self.tree(repo)
        self.assertEqual(files, before[0])
        self.assertTrue(before[1] <= dirs, before[1] - dirs)

    def test_install_over_a_repository_that_already_has_local_files(self):
        repo = self.make_repo()
        before = self.populate(repo)
        result = run_installer("install", str(repo), "--no-ci")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_preserved(repo, before)

    def test_update_of_the_same_version(self):
        repo = self.project()
        before = self.populate(repo)
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_preserved(repo, before)

    def test_update_from_0_47_0_with_every_migration_confirmed(self):
        repo = self.old_fixture(BASE_0470)
        before = self.populate(repo)
        result = self.update_old(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.version(repo), "0.56.0")
        self.assert_preserved(repo, before)

    def test_update_dry_run(self):
        repo = self.project()
        before = self.populate(repo)
        result = run_installer("update", str(repo), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_preserved(repo, before)

    def test_update_with_no_ci(self):
        repo = self.project()
        before = self.populate(repo)
        result = run_installer("update", str(repo), "--no-ci")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_preserved(repo, before)

    def test_update_from_0_55_1_keeps_local_files_too(self):
        repo = self.old_fixture(BASE_0551)
        before = self.populate(repo)
        result = self.update_old(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_preserved(repo, before)

    def update_old(self, repo, *args):
        return run_installer("update", str(repo), "--no-ci", "--no-commit", *args, input="y\n" * 80, exact=True)

    def old_fixture(self, commit):
        repo = self.install_old(commit)
        self.set_definition(repo)
        return repo

    def test_an_edited_owned_file_refusal_leaves_local_files_unchanged_too(self):
        repo = self.project()
        before = self.populate(repo)
        gate = repo / ".harness" / "hooks" / "spec_gate.py"
        gate.write_bytes(gate.read_bytes() + b"\n#x\n")
        self.assertEqual(run_installer("update", str(repo)).returncode, 1)
        self.assert_preserved(repo, before)


class TestRetiredState(ReportCase):
    NOTE = "Renamed to verify; copy the text there."
    PATH = ".harness/local/doggy-workflow/old.md"
    LINE = f"retired {PATH}: {NOTE}"

    def retired_repo(self):
        root = self.temp_dir()

        def edit(data):
            data.setdefault("retired", []).append({"path": self.PATH, "version": "0.56.0", "note": self.NOTE})

        copy_source(root, edit)
        installer = root / "installer" / "harness.py"
        repo = self.make_repo()
        result = subprocess.run([sys.executable, str(installer), "install", str(repo), "--no-ci"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.set_definition(repo)
        self.confirm(repo, AGENTS)
        self.write(repo, self.PATH, "old rules\n")
        return repo, installer

    def run_with(self, installer, *args):
        return subprocess.run([sys.executable, str(installer), *args], input="y\n" * 80, capture_output=True,
                              text=True)

    def test_status_shows_the_retired_line_and_the_item_is_no_recognized_item(self):
        repo, _ = self.retired_repo()
        self.assertIn(self.LINE, self.status_lines(repo))

    def test_the_notice_shows_the_retired_line(self):
        repo, _ = self.retired_repo()
        lines = self.notice_lines(repo)
        self.assertIn("harness customization: " + self.LINE, lines)

    def test_the_update_section_shows_the_retired_line(self):
        repo, installer = self.retired_repo()
        self.set_manifest_version(repo, "0.55.1")
        result = self.run_with(installer, "update", str(repo), "--no-commit")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(any(self.LINE in l for l in self.section_lines(result.stdout, "customization")),
                        result.stdout)

    def test_doctor_shows_the_retired_line_under_manual_review(self):
        repo, installer = self.retired_repo()
        result = self.run_with(installer, "doctor", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(self.LINE, self.section(result.stdout, "manual review"))

    def test_import_text_shows_the_retired_line(self):
        repo, installer = self.retired_repo()
        result = self.run_with(installer, "import", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(self.LINE, self.section(result.stdout, "customization"))

    def test_import_json_gives_the_retired_state(self):
        repo, installer = self.retired_repo()
        result = self.run_with(installer, "import", str(repo), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        states = {e["path"]: e["state"] for e in json.loads(result.stdout)["customization"]}
        self.assertEqual(states[self.PATH], "retired")

    def test_confirm_refuses_a_retired_path(self):
        repo, _ = self.retired_repo()
        before = self.review(repo)
        result = self.customization(repo, "confirm", self.PATH)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"{self.PATH}: not a recognized customization", (result.stdout + result.stderr).splitlines())
        self.assertEqual(self.review(repo), before)

    def test_a_retired_file_that_matches_a_current_point_is_not_retired(self):
        repo, _ = self.retired_repo()
        self.write(repo, ".harness/local/doggy-workflow/verify.md", "x\n")
        items, _ = self.status(repo)
        self.assertEqual({p: s for s, p, _ in items}[".harness/local/doggy-workflow/verify.md"], "unconfirmed")

    def test_an_unlisted_unrecognized_file_stays_unrecognized(self):
        repo, _ = self.retired_repo()
        self.write(repo, ".harness/local/doggy-workflow/other-old.md", "x\n")
        items, _ = self.status(repo)
        self.assertEqual({p: s for s, p, _ in items}[".harness/local/doggy-workflow/other-old.md"], "unrecognized")
