import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from legacy_migrations import skip_legacy_update

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "harness"
INSTALLER = REPO_ROOT / "installer" / "harness.py"
WORKFLOW = SOURCE / "ci" / "harness-facts-approval.yml"
FACTS = "agent-docs/facts.md"
LABEL = "facts-approved"
ENTRY = "- The CI runner has 4 GB of memory. — source: user, 2026-11-17; re-check: ask the user"
OTHER = "- Peak load is 40 requests per second. — source: user, 2026-11-13; re-check: ask the user"
_TARGETS_DIR = tempfile.TemporaryDirectory()
os.environ["HARNESS_TARGETS_FILE"] = str(Path(_TARGETS_DIR.name) / "targets.json")


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=check)


class FactsCheckCase(unittest.TestCase):
    def make_repo(self, docs_root=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "test@test.com")
        git(repo, "config", "user.name", "test")
        git(repo, "config", "commit.gpgsign", "false")
        (repo / ".harness" / "git").mkdir(parents=True)
        (repo / ".harness" / "lib").mkdir()
        shutil.copy(SOURCE / "git" / "check_facts_change.py", repo / ".harness" / "git")
        shutil.copy(SOURCE / "lib" / "config.py", repo / ".harness" / "lib")
        shutil.copy(SOURCE / "config.default.json", repo / ".harness")
        if docs_root:
            (repo / ".harness" / "config.json").write_text(json.dumps({"docs_root": docs_root}))
        self.commit(repo, {"README.md": "x\n"})
        return repo

    def commit(self, repo, files, delete=()):
        for name, text in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            git(repo, "add", "-f", name)
        for name in delete:
            git(repo, "rm", "-q", name)
        git(repo, "commit", "-q", "--allow-empty", "-m", "c")
        return git(repo, "rev-parse", "HEAD").stdout.strip()

    def check(self, repo, base, head, approved):
        return subprocess.run(
            [sys.executable, str(repo / ".harness" / "git" / "check_facts_change.py"), base, head, "--approved", approved],
            cwd=repo, capture_output=True, text=True,
        )

    def errors(self, result):
        return [line for line in result.stdout.splitlines() if line.startswith("::error")]


class GateTests(FactsCheckCase):
    def with_facts(self, before, after):
        repo = self.make_repo()
        base = self.commit(repo, {FACTS: before})
        head = self.commit(repo, {FACTS: after})
        return repo, base, head

    def test_unchanged_facts_pass_without_label(self):
        repo = self.make_repo()
        base = self.commit(repo, {FACTS: f"# Facts\n\n{OTHER}\n"})
        head = self.commit(repo, {"src.py": "x = 1\n"})
        result = self.check(repo, base, head, "no")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.errors(result), [])

    def test_added_entry_without_label_fails_and_prints_the_text(self):
        repo, base, head = self.with_facts(f"# Facts\n\n{OTHER}\n", f"# Facts\n\n{OTHER}\n{ENTRY}\n")
        result = self.check(repo, base, head, "no")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Added (1 line(s)):", result.stdout)
        self.assertIn(f"  4: {ENTRY}", result.stdout)
        self.assertIn(f"::error file={FACTS},line=4,title=Unapproved facts line::{ENTRY}", result.stdout)
        self.assertNotIn(f": {OTHER}", result.stdout)
        self.assertIn(f"Missing {LABEL} label", self.errors(result)[-1])

    def test_added_entry_with_label_passes_and_still_prints_the_text(self):
        repo, base, head = self.with_facts(f"# Facts\n\n{OTHER}\n", f"# Facts\n\n{OTHER}\n{ENTRY}\n")
        result = self.check(repo, base, head, "yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"  4: {ENTRY}", result.stdout)
        self.assertEqual(self.errors(result), [])

    def test_removed_entry_without_label_fails_and_prints_the_old_text(self):
        repo, base, head = self.with_facts(f"# Facts\n\n{OTHER}\n{ENTRY}\n", f"# Facts\n\n{OTHER}\n")
        result = self.check(repo, base, head, "no")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Removed (1 line(s)):", result.stdout)
        self.assertIn(f"  4: {ENTRY}", result.stdout)
        self.assertNotIn("Added (", result.stdout)
        self.assertTrue(any("Unapproved facts removal (old line 4)" in line and ENTRY in line for line in self.errors(result)))

    def test_changed_entry_prints_both_old_and_new_text(self):
        changed = ENTRY.replace("4 GB", "8 GB")
        repo, base, head = self.with_facts(f"# Facts\n\n{ENTRY}\n", f"# Facts\n\n{changed}\n")
        result = self.check(repo, base, head, "no")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        added, removed = result.stdout.split("Removed (", 1)
        self.assertIn(f"  3: {changed}", added)
        self.assertIn(f"  3: {ENTRY}", removed)

    def test_new_and_deleted_facts_files_list_every_line(self):
        repo = self.make_repo()
        base = self.commit(repo, {"src.py": "x = 1\n"})
        created = self.commit(repo, {FACTS: f"# Facts\n\n{ENTRY}\n"})
        deleted = self.commit(repo, {}, delete=[FACTS])
        for start, end, title in ((base, created, "Added (3 line(s)):"), (created, deleted, "Removed (3 line(s)):")):
            with self.subTest(title=title):
                result = self.check(repo, start, end, "no")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(title, result.stdout)
                self.assertIn(f"  3: {ENTRY}", result.stdout)

    def test_changes_on_the_base_branch_alone_are_not_counted(self):
        repo = self.make_repo()
        fork = self.commit(repo, {FACTS: f"# Facts\n\n{OTHER}\n"})
        git(repo, "checkout", "-q", "-b", "feature")
        head = self.commit(repo, {"src.py": "x = 1\n"})
        git(repo, "checkout", "-q", "main")
        base = self.commit(repo, {FACTS: f"# Facts\n\n{OTHER}\n{ENTRY}\n"})
        self.assertNotEqual(fork, base)
        result = self.check(repo, base, head, "no")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_configured_docs_root_is_the_checked_location(self):
        repo = self.make_repo(docs_root="docs/agent")
        base = self.commit(repo, {"src.py": "x = 1\n"})
        ignored = self.commit(repo, {FACTS: f"{ENTRY}\n"})
        result = self.check(repo, base, ignored, "no")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        checked = self.commit(repo, {"docs/agent/facts.md": f"{ENTRY}\n"})
        result = self.check(repo, ignored, checked, "no")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("docs/agent/facts.md", result.stdout)

    def test_annotation_text_is_escaped(self):
        entry = "- 100% of builds run on one runner. — source: user, 2026-11-17; re-check: ask"
        repo, base, head = self.with_facts("# Facts\n", f"# Facts\n{entry}\n")
        result = self.check(repo, base, head, "no")
        self.assertIn("::- 100%25 of builds", result.stdout)
        self.assertIn(f"  2: {entry}", result.stdout)

    def test_unreadable_revision_fails_closed(self):
        repo = self.make_repo()
        result = self.check(repo, "0" * 40, "HEAD", "no")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(self.errors(result))

    def test_bad_arguments_exit_two(self):
        repo = self.make_repo()
        script = str(repo / ".harness" / "git" / "check_facts_change.py")
        for args in (("HEAD", "HEAD"), ("HEAD", "HEAD", "--approved", "maybe"), ("HEAD", "--approved", "no"),
                     ("--approved", "HEAD", "--approved", "no"), ("HEAD", "HEAD", "--approve", "no")):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, script, *args], cwd=repo, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage", result.stderr)


class ScopeAndCompletenessTests(FactsCheckCase):
    def test_other_docs_and_other_facts_files_are_not_checked(self):
        repo = self.make_repo()
        base = self.commit(repo, {FACTS: f"# Facts\n\n{OTHER}\n", "agent-docs/index.md": "x\n"})
        head = self.commit(repo, {"agent-docs/index.md": "y\n", "agent-docs/other.md": f"{ENTRY}\n",
                                  "sub/facts.md": f"{ENTRY}\n", "agent-docs/sub/facts.md": f"{ENTRY}\n"})
        result = self.check(repo, base, head, "no")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.errors(result), [])

    def test_every_changed_line_is_listed_and_annotated_once(self):
        lines = [f"- fact {n}. — source: user, 2026-11-17; re-check: ask" for n in range(1, 6)]
        after = [lines[0], lines[1] + " (edited)", lines[2], lines[3] + " (edited)", lines[4], "- new a.", "- new b."]
        repo = self.make_repo()
        base = self.commit(repo, {FACTS: "\n".join(lines) + "\n"})
        head = self.commit(repo, {FACTS: "\n".join(after) + "\n"})
        result = self.check(repo, base, head, "no")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        added, removed = result.stdout.split("Removed (", 1)
        self.assertIn("Added (4 line(s)):", added)
        for number in (2, 4, 6, 7):
            self.assertIn(f"  {number}: {after[number - 1]}", added)
        self.assertTrue(removed.startswith("2 line(s)):"))
        for number in (2, 4):
            self.assertIn(f"  {number}: {lines[number - 1]}", removed)
        for unchanged in (lines[0], lines[2], lines[4]):
            self.assertNotIn(f": {unchanged}\n", result.stdout)
        errors = self.errors(result)
        self.assertEqual([e for e in errors if "title=Unapproved facts line::" in e],
                         [f"::error file={FACTS},line={n},title=Unapproved facts line::{after[n - 1]}" for n in (2, 4, 6, 7)])
        self.assertEqual(len([e for e in errors if "Unapproved facts removal" in e]), 2)
        self.assertEqual(len([e for e in errors if "Missing facts-approved label" in e]), 1)
        self.assertEqual(len(errors), 7)

    def test_carriage_returns_are_kept_and_escaped(self):
        repo = self.make_repo()
        base = self.commit(repo, {FACTS: "# Facts\n"})
        path = repo / FACTS
        path.write_bytes(b"# Facts\n- a\rb 50%\r\n")
        git(repo, "add", "-f", FACTS)
        git(repo, "commit", "-q", "-m", "crlf")
        head = git(repo, "rev-parse", "HEAD").stdout.strip()
        result = subprocess.run(
            [sys.executable, str(repo / ".harness" / "git" / "check_facts_change.py"), base, head, "--approved", "no"],
            cwd=repo, capture_output=True,
        )
        stdout = result.stdout.decode()
        self.assertEqual(result.returncode, 1, stdout)
        annotations = [l for l in stdout.split("\n") if "title=Unapproved facts line::" in l]
        self.assertEqual(annotations, [f"::error file={FACTS},line=2,title=Unapproved facts line::- a%0Db 50%25%0D"])
        self.assertIn("Added (1 line(s)):", stdout)

    def test_removals_with_label_pass_and_are_listed(self):
        repo = self.make_repo()
        base = self.commit(repo, {FACTS: f"# Facts\n{ENTRY}\n"})
        head = self.commit(repo, {FACTS: "# Facts\n"})
        result = self.check(repo, base, head, "yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"Removed (1 line(s)):\n  2: {ENTRY}", result.stdout)
        self.assertEqual(self.errors(result), [])

    def test_removal_only_failure_ends_with_the_label_error(self):
        repo = self.make_repo()
        base = self.commit(repo, {FACTS: f"# Facts\n{ENTRY}\n"})
        head = self.commit(repo, {FACTS: "# Facts\n"})
        result = self.check(repo, base, head, "no")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing facts-approved label", self.errors(result)[-1])

    def test_unreadable_revisions_fail_closed_even_with_the_label(self):
        repo = self.make_repo()
        for base, head in (("0" * 40, "HEAD"), ("HEAD", "f" * 40), ("HEAD", "nosuchref")):
            with self.subTest(base=base, head=head):
                result = self.check(repo, base, head, "yes")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertTrue(self.errors(result))

    def test_extra_or_malformed_arguments_exit_two(self):
        repo = self.make_repo()
        script = str(repo / ".harness" / "git" / "check_facts_change.py")
        for args in (("HEAD", "HEAD", "--approved", "no", "extra"), ("HEAD", "HEAD", "--approved", "YES"),
                     ("HEAD", "HEAD", "--approved", ""), ()):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, script, *args], cwd=repo, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage", result.stderr)


class WorkflowTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text()

    def test_triggers_include_label_events_and_no_pull_request_target(self):
        types = re.search(r"pull_request:\s*\n\s*types:\s*\[([^\]]*)\]", self.text).group(1)
        self.assertEqual(sorted(t.strip() for t in types.split(",")),
                         sorted(["opened", "synchronize", "reopened", "labeled", "unlabeled"]))
        self.assertNotIn("pull_request_target", self.text)

    def test_new_push_revokes_the_label(self):
        step = self.text.split("- name: Revoke facts approval on new push", 1)[1].split("- name:", 1)[0]
        self.assertRegex(step, r"if:\s*github\.event\.action == 'synchronize'")
        self.assertIn(f"labels/{LABEL}", step)
        self.assertRegex(step, r"continue-on-error:\s*true")

    def test_gate_passes_the_label_only_outside_synchronize(self):
        line = next(l for l in self.text.splitlines() if "check_facts_change.py" in l)
        self.assertIn('"${{ github.event.pull_request.base.sha }}" "${{ github.sha }}"', line)
        self.assertIn(f"github.event.action != 'synchronize' && contains(github.event.pull_request.labels.*.name, '{LABEL}')", line)
        self.assertIn("&& 'yes' || 'no'", line)


class InstallTests(FactsCheckCase):
    def install(self, *flags):
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, True)
        git(repo, "init", "-q")
        result = subprocess.run([sys.executable, str(INSTALLER), "install", str(repo), *flags], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return repo, result

    def test_install_adds_the_workflow_and_script_and_reports_the_label(self):
        repo, result = self.install()
        self.assertEqual((repo / ".github" / "workflows" / "harness-facts-approval.yml").read_bytes(), WORKFLOW.read_bytes())
        self.assertEqual((repo / ".harness" / "git" / "check_facts_change.py").read_bytes(),
                         (SOURCE / "git" / "check_facts_change.py").read_bytes())
        self.assertIn(f"`{LABEL}`", result.stdout)

    def test_no_ci_omits_the_workflow_and_the_label(self):
        repo, result = self.install("--no-ci")
        self.assertFalse((repo / ".github" / "workflows" / "harness-facts-approval.yml").exists())
        self.assertNotIn(LABEL, result.stdout)

    def test_dry_run_plans_the_label(self):
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, True)
        git(repo, "init", "-q")
        result = subprocess.run([sys.executable, str(INSTALLER), "install", str(repo), "--dry-run"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"GitHub label {LABEL} (if missing)", result.stdout)

    def test_update_from_0510_announces_the_facts_gate(self):
        repo, _ = self.install()
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = "0.51.0"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        skip_legacy_update(("update", str(repo)))
        result = subprocess.run([sys.executable, str(INSTALLER), "update", str(repo), "--no-commit"],
                                input="y\n" * 5, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        section = result.stdout.split("migration 0.52.0", 1)[1].split("Apply migration", 1)[0]
        self.assertIn(LABEL, section)
        self.assertIn("ruleset", section)
        self.assertIn("no bypass", section)


if __name__ == "__main__":
    unittest.main()
