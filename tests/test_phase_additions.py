import subprocess
import sys

from customization_case import PHASES, CustomizationCase

RID = "49bafb302bb6593c"
HEADING = "## Project rules for this phase"
MARKERS = "## Markers of this phase"
TEXT = "Check the audit log before you report.\n\nSecond paragraph.\n"
REPLACED = "{path} could not be read; read it yourself."


class PhaseAdditionCase(CustomizationCase):
    def setUp(self):
        self.repo = self.project()

    def printed(self, phase, *flags, run=True):
        args = ["phase"] + (["--run-id", RID] if run else []) + ["--phase", phase, *flags]
        result = subprocess.run([sys.executable, str(self.repo / ".harness" / "bin" / "workflow_marker.py"), *args],
                                cwd=self.repo, env=self.env(), capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
        return result.stdout

    def body(self, output):
        return output.split("\n\n", 1)[1]

    def block(self, phase, text=TEXT):
        return (f"{HEADING}\nFrom .harness/local/doggy-workflow/{phase}.md. Where these disagree with the harness "
                f"rules above, follow these.\n\n{text}")

    def assert_block_between(self, with_file, without_file, block):
        self.assertEqual(with_file.count(HEADING), 1)
        if MARKERS not in without_file:
            self.assertNotIn(MARKERS, with_file)
            self.assertTrue(with_file.startswith(without_file.rstrip("\n")), "rules before the block changed")
            added = with_file[len(without_file.rstrip("\n")):]
            self.assertEqual(added.strip("\n"), block.strip("\n"))
            return
        self.assertEqual(with_file.count(MARKERS), 1)
        rules_with, markers_with = with_file.split(MARKERS, 1)
        rules_without, markers_without = without_file.split(MARKERS, 1)
        self.assertEqual(markers_with, markers_without)
        self.assertTrue(rules_with.startswith(rules_without.rstrip("\n")), "rules before the block changed")
        added = rules_with[len(rules_without.rstrip("\n")):]
        self.assertEqual(added.lstrip("\n").rstrip("\n"), block.rstrip("\n"))
        self.assertLess(with_file.index(HEADING), with_file.index(MARKERS))


class TestPhaseAdditions(PhaseAdditionCase):
    def test_the_recorded_phase_prints_the_block_between_rules_and_markers(self):
        for flags in ((), ("--again",), ("--again", "--all")):
            with self.subTest(flags=flags):
                self.setUp()
                without = self.body(self.printed("verify", *flags))
                self.write(self.repo, ".harness/local/doggy-workflow/verify.md", TEXT)
                with_file = self.body(self.printed("verify", *flags))
                self.assert_block_between(with_file, without, self.block("verify"))

    def test_the_block_is_printed_without_a_run_id_as_well(self):
        without = self.body(self.printed("verify", "--again", run=False))
        self.write(self.repo, ".harness/local/doggy-workflow/verify.md", TEXT)
        self.assert_block_between(self.body(self.printed("verify", "--again", run=False)), without,
                                  self.block("verify"))

    def test_the_header_lines_are_the_same_with_and_without_the_file(self):
        without = self.printed("verify", "--again").split("\n\n", 1)[0]
        self.write(self.repo, ".harness/local/doggy-workflow/verify.md", TEXT)
        self.assertEqual(self.printed("verify", "--again").split("\n\n", 1)[0], without)

    def test_a_print_only_phase_gets_its_own_block_too(self):
        without = self.body(self.printed("close", "--again"))
        self.write(self.repo, ".harness/local/doggy-workflow/close.md", TEXT)
        self.assert_block_between(self.body(self.printed("close", "--again")), without, self.block("close", TEXT))

    def test_every_phase_with_a_file_names_its_own_file_in_the_precedence_line(self):
        for phase in PHASES:
            with self.subTest(phase=phase):
                self.setUp()
                without = self.body(self.printed(phase, "--again"))
                self.write(self.repo, f".harness/local/doggy-workflow/{phase}.md", f"rules of {phase}\n")
                with_file = self.body(self.printed(phase, "--again"))
                self.assert_block_between(with_file, without, self.block(phase, f"rules of {phase}\n"))

    def test_without_a_file_the_output_has_no_block(self):
        for flags in ((), ("--again",), ("--again", "--all")):
            with self.subTest(flags=flags):
                self.assertNotIn(HEADING, self.printed("verify", *flags))
                self.assertIn(MARKERS, self.printed("verify", *flags))

    def test_a_file_for_another_phase_changes_nothing_for_this_one(self):
        without = {phase: self.printed(phase, "--again") for phase in ("verify", "brief")}
        self.write(self.repo, ".harness/local/doggy-workflow/amend.md", TEXT)
        for phase, text in without.items():
            with self.subTest(phase=phase):
                self.assertEqual(self.printed(phase, "--again"), text)
        self.assertIn(HEADING, self.printed("amend", "--again"))

    def test_a_file_that_is_not_utf8_is_replaced_by_the_read_it_yourself_line(self):
        path = ".harness/local/doggy-workflow/verify.md"
        for flags in ((), ("--again",)):
            with self.subTest(flags=flags):
                self.setUp()
                without = self.body(self.printed("verify", *flags))
                self.write(self.repo, path, b"valid start \xff\xfe\x80 invalid")
                with_file = self.body(self.printed("verify", *flags))
                self.assert_block_between(with_file, without, self.block("verify", REPLACED.format(path=path)))
                self.assertNotIn("valid start", with_file)

    def test_an_empty_file_prints_the_heading_and_precedence_line_with_no_text(self):
        without = self.body(self.printed("verify", "--again"))
        self.write(self.repo, ".harness/local/doggy-workflow/verify.md", b"")
        with_file = self.body(self.printed("verify", "--again"))
        rules_with, markers_with = with_file.split(MARKERS, 1)
        rules_without, markers_without = without.split(MARKERS, 1)
        self.assertEqual(markers_with, markers_without)
        self.assertTrue(rules_with.startswith(rules_without.rstrip("\n")))
        added = rules_with[len(rules_without.rstrip("\n")):].strip("\n")
        self.assertEqual(added, self.block("verify", "").strip("\n"))

    def test_a_directory_in_place_of_the_file_does_not_break_the_rules(self):
        without = self.body(self.printed("verify", "--again"))
        (self.repo / ".harness" / "local" / "doggy-workflow" / "verify.md").mkdir(parents=True)
        output = self.body(self.printed("verify", "--again"))
        self.assertTrue(output.endswith(without.split(MARKERS, 1)[1]))
        self.assertTrue(output.startswith(without.split(MARKERS, 1)[0].rstrip("\n")))
