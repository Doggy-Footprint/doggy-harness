import filecmp
import json
import re
import subprocess
import sys
import unittest

import skill_text
from test_installer import REPO_ROOT, load_installer_module, run_installer
from test_telemetry import TelemetryTestCase

RID = "f054cffaaf3f0824"
PLAIN_SPEC = "---\nversion: 1\n---\n# Paths\nFuzzing: none — no parser\nMutation tool: none\n\n# Version Log\n"

S1 = ("2. Inject the violating behavior and run the focused run with a finite timeout suited to its expected runtime: "
      "the Test command narrowed to the tests that hold the intended assertion, with the Test command's environment "
      "and options kept. When the focused run passes, run the full Test command before recording the mutation as "
      "undetected. When the Test command cannot be narrowed, run it whole.")
P1 = "run the focused run with a finite timeout suited to its expected runtime"
P2 = "When the focused run passes, run the full Test command before recording the mutation as undetected."
P3 = "When the Test command cannot be narrowed, run it whole."
P4 = ("the Test command narrowed to the tests that hold the intended assertion, with the Test command's environment "
      "and options kept")
K1 = "one mutation at a time"
K4 = "failure rejects a finding only when the intended assertion detects the violation"
X1 = "Inject the violating behavior and run the Test command with a finite timeout suited to its expected runtime."
Q1 = "When a Test command run takes longer than two minutes, record its wall-clock time and its slowest single tests in the execution ledger."
Q2 = ("The slowest single test bounds the run, and more workers can make it slower when tests contend for processes "
      "or the file system, so measure before adding workers.")
Q3 = ("Propose splitting the slowest tests, with the measurements, in the closing report; do not change the test "
      "runner or tests outside the spec's paths for it.")
N1 = ("mutation, fuzz, and mutation-tool outcomes, the longest Test command run's wall-clock time and, when it took "
      "longer than two minutes, its slowest single tests and the proposal to speed it up,")
SUMMARY = ("hand mutations run a focused run of the tests holding the intended assertion first; a Test command "
           "slower than two minutes is diagnosed and reported")
PHASE_FILES = ("workflow-6-triage.md", "workflow-4-reconcile.md", "closing-report.md")
SOURCE_PHASES = REPO_ROOT / "harness" / "skills" / "doggy-workflow" / "phases"
INSTALLED_PHASES = {
    "harness": REPO_ROOT / ".harness" / "skills" / "doggy-workflow" / "phases",
    "agents": REPO_ROOT / ".agents" / "skills" / "doggy-workflow" / "phases",
}


class FocusedMutationCase(TelemetryTestCase):
    def setUp(self):
        self.repo = self.install()
        self.telemetry_dir = self.temp_dir()
        self.env = self.telemetry_env(self.telemetry_dir)
        path = self.repo / "agent-docs" / "specs" / f"{RID}-orders.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(PLAIN_SPEC)

    def phase(self, name):
        result = subprocess.run(
            [sys.executable, str(self.repo / ".harness" / "bin" / "workflow_marker.py"), "phase", "--run-id", RID,
             "--phase", name],
            cwd=self.repo, env=self.env, capture_output=True, text=True,
        )
        self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
        return result.stdout

    def numbers_line(self, output):
        lines = [line for line in output.splitlines() if line.strip().startswith("- *Numbers*")]
        self.assertEqual(len(lines), 1, lines)
        return lines[0]


class TestVerifyPhaseText(FocusedMutationCase):
    def test_verify_prints_the_focused_run_step_verbatim(self):
        self.assertIn(S1, self.phase("verify"))

    def test_verify_prints_the_timeout_phrase(self):
        self.assertIn(P1, self.phase("verify"))

    def test_verify_prints_the_full_run_for_a_passing_focused_run(self):
        self.assertIn(P2, self.phase("verify"))

    def test_verify_prints_the_whole_run_fallback_for_a_command_that_cannot_be_narrowed(self):
        self.assertIn(P3, self.phase("verify"))

    def test_verify_prints_the_narrowing_definition_with_environment_and_options_kept(self):
        self.assertIn(P4, self.phase("verify"))

    def test_verify_keeps_one_mutation_at_a_time(self):
        self.assertIn(K1, self.phase("verify"))

    def test_verify_keeps_the_seed_backup_as_sub_step_one_before_the_focused_run(self):
        output = self.phase("verify")
        backup = re.search(r"^\s*1\. .*seed\.py backup", output, re.MULTILINE)
        self.assertIsNotNone(backup, output)
        self.assertLess(backup.start(), output.index(S1))

    def test_verify_keeps_the_seed_restore_as_sub_step_three_after_the_focused_run(self):
        output = self.phase("verify")
        restore = re.search(r"^\s*3\. .*seed\.py restore", output, re.MULTILINE)
        self.assertIsNotNone(restore, output)
        self.assertGreater(restore.start(), output.index(S1))

    def test_verify_does_not_print_the_old_whole_run_sub_step(self):
        self.assertNotIn(X1, self.phase("verify"))


class TestInstalledSkillWholeText(FocusedMutationCase):
    def whole(self):
        return skill_text.whole(self.repo / ".harness" / "skills" / "doggy-workflow" / "SKILL.md")

    def test_the_old_whole_run_sub_step_is_absent(self):
        self.assertNotIn(X1, self.whole())

    def test_the_rejection_sentence_appears_exactly_once(self):
        self.assertEqual(self.whole().count(K4), 1)

    def test_the_rejection_sentence_appears_exactly_once_in_the_verify_output(self):
        self.assertEqual(self.phase("verify").count(K4), 1)

    def test_the_focused_run_step_is_in_the_installed_skill(self):
        self.assertIn(S1, self.whole())

    def test_one_mutation_at_a_time_is_in_the_installed_skill(self):
        self.assertIn(K1, self.whole())


class TestSlowRunAndClosingText(FocusedMutationCase):
    def test_implement_test_prints_the_slow_run_recording_sentence(self):
        self.assertIn(Q1, self.phase("implement_test"))

    def test_implement_test_prints_the_worker_contention_sentence(self):
        self.assertIn(Q2, self.phase("implement_test"))

    def test_implement_test_prints_the_split_proposal_sentence(self):
        self.assertIn(Q3, self.phase("implement_test"))

    def test_close_numbers_bullet_carries_the_slow_run_figures(self):
        self.assertIn(N1, self.numbers_line(self.phase("close")))


class TestMigrationTo0580(FocusedMutationCase):
    def test_update_from_0570_announces_0580_with_the_summary_and_no_data_migrated(self):
        manifest_path = self.repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = "0.57.0"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        result = run_installer("update", str(self.repo), "--no-ci", "--no-commit", input="y\n" * 10, exact=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(re.findall(r"^migration (\d+\.\d+\.\d+):", result.stdout, re.MULTILINE), ["0.58.0"])
        self.assertIn(SUMMARY, result.stdout)
        self.assertIn("no data is migrated", result.stdout)
        self.assertEqual(json.loads(manifest_path.read_text())["version"], "0.58.0")

    def test_fresh_install_writes_version_0580(self):
        repo = self.fresh_install()
        self.assertEqual(json.loads((repo / ".harness" / "manifest.json").read_text())["version"], "0.58.0")

    def test_source_version_file_is_0580(self):
        self.assertEqual((REPO_ROOT / "harness" / "VERSION").read_text().strip(), "0.58.0")

    def test_migrations_end_with_one_0580_entry_with_the_summary_and_the_no_data_note(self):
        module = load_installer_module()
        target = module.parse_version("0.58.0")
        entries = [entry for entry in module.MIGRATIONS if entry[0] == target]
        self.assertEqual(len(entries), 1)
        self.assertEqual(module.MIGRATIONS[-1][0], target)
        self.assertEqual(entries[0][1], SUMMARY)


class TestInstalledCopiesMatchSource(FocusedMutationCase):
    def assert_same(self, directory, name):
        self.assertTrue((directory / name).is_file(), directory / name)
        self.assertTrue(filecmp.cmp(SOURCE_PHASES / name, directory / name, shallow=False), directory / name)

    def test_this_repository_installed_copies_equal_the_source_phase_files(self):
        for label, directory in INSTALLED_PHASES.items():
            for name in PHASE_FILES:
                with self.subTest(copy=label, file=name):
                    self.assert_same(directory, name)

    def test_a_fresh_install_equals_the_source_phase_files(self):
        repo = self.fresh_install()
        for rel in (".harness", ".agents"):
            directory = repo / rel / "skills" / "doggy-workflow" / "phases"
            for name in PHASE_FILES:
                with self.subTest(copy=rel, file=name):
                    self.assert_same(directory, name)


if __name__ == "__main__":
    unittest.main()
