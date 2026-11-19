import json
import re
import subprocess
import sys
import unittest

import skill_text
from test_installer import REPO_ROOT
from test_telemetry import TelemetryTestCase
from text_checks import text_test

SKILL_DIR = REPO_ROOT / "harness" / "skills" / "doggy-workflow"
SKILL = SKILL_DIR / "SKILL.md"
RID = "49bafb302bb6593c"
PRINT_ONLY = ("brief", "draft", "approve", "step", "close", "resume")
RECORDED = ("implement_test", "verify", "amend")
MARKER_COMMANDS = {
    "brief": ["brief"], "approve": ["brief", "start"], "verify": ["verifier", "verification"],
    "step": ["brief"], "close": ["brief", "end"], "resume": ["start-marker"],
}
# Claude Code re-attaches the first 5,000 tokens of a skill after compaction and
# cuts Bash output at 30,000 characters; both limits leave room below them here.
CORE_WORD_LIMIT = 3000
PHASE_CHARACTER_LIMIT = 20000
CITATIONS = {
    "closing-report": [({"quiz-rules"}, False), ({"quiz-rules"}, False)],
    "quiz-closing": [({"quiz-rules"}, True)],
    "quiz-completion-questions": [({"quiz-rules"}, True)],
    "rounds-approval": [({"voice"}, False), ({"quiz-rules"}, False)],
    "rounds-decision": [({"stepped-cut", "stepped-held"}, False)],
    "rounds-understanding": [({"decision-sweep"}, False)],
    "spec-format": [({"stepped-cut"}, False), ({"quiz-rules"}, False)],
    "stepped-end": [({"workflow-9-close"}, False)],
    "stepped-resume": [({"stepped-run"}, False)],
    "stepped-run": [({"voice"}, False)],
    "workflow-1-recover": [({"stepped-resume"}, False)],
    "workflow-6-triage": [({"verification-mutation-tool"}, True)],
    "workflow-9-close": [({"quiz-rules"}, False)],
}
CITATION = re.compile(r"\(see (?:Quiz|Stepped specs|Context pass)\)|as (?:Quiz|Stepped specs|Running a step) describes"
                      r"|in the terms of Voice|the rules above|as above|Workflow item 9")
LOOKED_UP = {
    ("brief", "rounds-approval", "quiz-rules"): "the approval brief is written in approve, which prints Quiz",
    ("brief", "rounds-decision", "stepped-cut"): "the decision round only outlines a cut; draft prints its rules",
    ("brief", "workflow-1-recover", "stepped-resume"): "a stepped spec is resumed through the resume phase",
    ("approve", "rounds-decision", "stepped-cut"): "printed here for the picks file; draft printed the cut",
    ("implement_test", "stepped-run", "voice"): "the step brief is given in the step phase, which prints Voice",
}
PLAIN_SPEC = "---\nversion: 1\n---\n# Paths\nFuzzing: none — no parser\nMutation tool: none\n\n# Version Log\n"
STEPPED_SPEC = (
    "---\nversion: 1\n---\n# Paths\nFuzzing: atheris, fuzz_parse, parse(), crash, seed 7, 60 s\nMutation tool: none\n\n"
    "# Steps\n| id | outcome |\n| --- | --- |\n| S1 | parser exists |\n| S2 | exporter exists |\n\n# Session Memory\n")


class PhaseCase(TelemetryTestCase):
    def setUp(self):
        self.repo = self.install()
        self.telemetry_dir = self.temp_dir()
        self.env = self.telemetry_env(self.telemetry_dir)

    @property
    def installed(self):
        return self.repo / ".harness" / "skills" / "doggy-workflow"

    def marker(self, *args):
        result = subprocess.run(
            [sys.executable, str(self.repo / ".harness" / "bin" / "workflow_marker.py"), *args],
            cwd=self.repo, env=self.env, capture_output=True, text=True,
        )
        self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
        return result.stdout

    def events(self):
        return self.read_events(self.telemetry_dir, self.repo)

    def spec(self, text, run_id=RID, name="orders"):
        path = self.repo / "agent-docs" / "specs" / f"{run_id}-{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def commit(self):
        done = subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q",
             "--allow-empty", "--no-verify", "-m", "first"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def printed(self, phase, run_id=RID, without=()):
        names = [skill_text.entry_name(entry) for entry in json.loads((self.installed / "phases.json").read_text())[phase]]
        self.assertLessEqual(set(without) - {"verification-marker"}, set(names))
        text = "\n".join((self.installed / "phases" / f"{name}.md").read_text()
                         for name in names if name not in without)
        commands = [key for key in MARKER_COMMANDS.get(phase, [])
                    if not (key == "verification" and "verification-marker" in without)]
        if phase not in MARKER_COMMANDS:
            return text
        markers = json.loads((self.installed / "markers.json").read_text())
        known = dict(markers["commands"])
        known["start-marker"] = known["start"].split(" && ", 1)[1]
        lines = [known[key].replace("--run-id ID", f"--run-id {run_id}") if run_id else known[key] for key in commands]
        sentences = dict(markers["rules"])
        rules = [skill_text.entry_name(entry) for entry in markers["phases"][phase]["rules"]]
        if "verification-marker" in without:
            rules.remove("verification")
        return (f"{text}\n## Markers of this phase\n\n```sh\n" + "\n".join(lines) + "\n```\n\n"
                + " ".join(sentences[name] for name in rules) + "\n")


class TestPhaseOutput(PhaseCase):
    def test_without_a_spec_each_phase_prints_its_header_all_its_fragments_and_its_markers(self):
        self.marker("start", "--run-id", RID, "--spec", "orders", "--spec-version", "1")
        for phase in (*PRINT_ONLY, *RECORDED):
            with self.subTest(phase=phase):
                self.assertEqual(self.marker("phase", "--run-id", RID, "--phase", phase),
                                 f"doggy-workflow phase: {phase}\n\n{self.printed(phase)}")

    def test_marker_commands_carry_the_run_id_and_keep_the_placeholder_without_one(self):
        with_id = self.marker("phase", "--run-id", RID, "--phase", "close")
        self.assertIn(f"workflow_marker.py brief --run-id {RID} --stage ", with_id)
        self.assertIn(f"workflow_marker.py end --run-id {RID} --status complete|limit|handoff|aborted", with_id)
        self.assertNotIn("--run-id ID", with_id)
        self.assertIn("workflow_marker.py end --run-id ID --status", self.marker("phase", "--phase", "close", "--again"))
        resumed = self.marker("phase", "--run-id", RID, "--phase", "resume")
        self.assertIn(f"\npython3 .harness/bin/workflow_marker.py start --run-id {RID} --spec NAME --spec-version N\n",
                      resumed)
        self.assertNotIn("spec_lifecycle.py start", resumed.split("## Markers of this phase")[1])

    def test_brief_without_a_run_id_issues_a_fresh_16_hex_id_and_uses_it_in_the_marker_command(self):
        issued = []
        for _ in range(3):
            head, rest = self.marker("phase", "--phase", "brief").split("\n\n", 1)
            lines = head.split("\n")
            self.assertEqual(lines[0], "doggy-workflow phase: brief")
            run_id = re.fullmatch(r"Run id of this run: ([0-9a-f]{16})", lines[1]).group(1)
            self.assertIn("literal value", lines[2])
            self.assertEqual(rest, self.printed("brief", run_id=run_id))
            issued.append(run_id)
        self.assertEqual(len(set(issued)), 3, issued)

    def test_only_brief_without_a_run_id_issues_an_id(self):
        self.assertNotIn("Run id of this run", self.marker("phase", "--run-id", RID, "--phase", "brief"))
        for phase in ("draft", "approve", "step", "close", "resume"):
            with self.subTest(phase=phase):
                self.assertNotIn("Run id of this run", self.marker("phase", "--phase", phase))
        self.assertNotIn("Run id of this run", self.marker("phase", "--phase", "brief", "--again"))

    def test_print_only_phases_write_no_telemetry_line(self):
        self.marker("start", "--run-id", RID, "--spec", "orders", "--spec-version", "1")
        before = self.events()
        for phase in PRINT_ONLY:
            self.marker("phase", "--run-id", RID, "--phase", phase)
        self.marker("phase", "--phase", "brief")
        self.assertEqual(self.events(), before)

    def test_recorded_phases_record_one_line_each_and_say_nothing_about_recording(self):
        self.marker("start", "--run-id", RID, "--spec", "orders", "--spec-version", "1")
        for phase in RECORDED:
            self.assertNotIn("Not recorded", self.marker("phase", "--run-id", RID, "--phase", phase))
        self.assertEqual([event["phase"] for event in self.events() if event["event"] == "workflow_phase"],
                         list(RECORDED))

    def test_again_prints_the_rules_and_records_nothing(self):
        self.marker("start", "--run-id", RID, "--spec", "orders", "--spec-version", "1")
        for phase in RECORDED:
            self.marker("phase", "--run-id", RID, "--phase", phase)
        before = self.events()
        for phase in (*PRINT_ONLY, *RECORDED):
            for run in ((RID,), ()):
                with self.subTest(phase=phase, run=run):
                    arguments = ("--run-id", *run) if run else ()
                    self.assertEqual(self.marker("phase", *arguments, "--phase", phase, "--again"),
                                     f"doggy-workflow phase: {phase}\nPrinted again: nothing was recorded.\n\n"
                                     f"{self.printed(phase, run_id=run[0] if run else None)}")
        self.assertEqual(self.events(), before)

    def test_a_failed_telemetry_write_is_silent_and_the_rules_are_still_printed(self):
        self.marker("start", "--run-id", RID, "--spec", "orders", "--spec-version", "1")
        before = self.events()
        paths = list(self.telemetry_dir.rglob("*"))
        try:
            for path in paths:
                path.chmod(0o400)
            self.telemetry_dir.chmod(0o500)
            output = self.marker("phase", "--run-id", RID, "--phase", "verify")
        finally:
            self.telemetry_dir.chmod(0o700)
            for path in paths:
                path.chmod(0o600)
        self.assertEqual(output, f"doggy-workflow phase: verify\n\n{self.printed('verify')}")
        self.assertEqual(self.events(), before)

    def test_rules_are_printed_as_utf8_whatever_the_terminal_encoding(self):
        self.env["PYTHONIOENCODING"] = "ascii"
        for phase in ("brief", "draft"):
            with self.subTest(phase=phase):
                result = subprocess.run(
                    [sys.executable, str(self.repo / ".harness" / "bin" / "workflow_marker.py"),
                     "phase", "--run-id", RID, "--phase", phase],
                    cwd=self.repo, env=self.env, capture_output=True,
                )
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertEqual(result.stdout.decode("utf-8"), f"doggy-workflow phase: {phase}\n\n{self.printed(phase)}")
                self.assertFalse(result.stdout.isascii())

    def test_recorded_phase_without_an_active_run_prints_its_rules_and_says_it_was_not_recorded(self):
        cases = {"no run started": (RID,), "no run id": ()}
        for name, run in cases.items():
            for phase in RECORDED:
                with self.subTest(case=name, phase=phase):
                    arguments = ("--run-id", *run) if run else ()
                    head, rules = self.marker("phase", *arguments, "--phase", phase).split("\n\n", 1)
                    self.assertIn("Not recorded in telemetry: no run is active", head)
                    self.assertIn("emit `start` again", head)
                    self.assertNotIn("repeat", head)
                    self.assertEqual(rules, self.printed(phase, run_id=run[0] if run else None))
        self.assertEqual(self.events(), [])

    def test_a_run_ended_with_handoff_is_reported_as_not_active_until_start_is_emitted_again(self):
        self.marker("start", "--run-id", RID, "--spec", "orders", "--spec-version", "1")
        self.marker("end", "--run-id", RID, "--status", "handoff")
        self.assertIn("Not recorded in telemetry", self.marker("phase", "--run-id", RID, "--phase", "amend",
                                                               "--reason", "correction"))
        self.marker("start", "--run-id", RID, "--spec", "orders", "--spec-version", "2")
        self.assertNotIn("Not recorded", self.marker("phase", "--run-id", RID, "--phase", "amend",
                                                     "--reason", "correction"))

    def test_unreadable_rules_or_markers_point_to_the_files(self):
        damage = {
            "manifest missing": (lambda d: (d / "phases.json").unlink(), "phases.json"),
            "manifest not json": (lambda d: (d / "phases.json").write_text("{"), "phases.json"),
            "fragment missing": (lambda d: (d / "phases" / "voice.md").unlink(), "phases.json"),
            "markers missing": (lambda d: (d / "markers.json").unlink(), "markers.json"),
            "markers not json": (lambda d: (d / "markers.json").write_text("["), "markers.json"),
        }
        for name, (break_it, named) in damage.items():
            with self.subTest(damage=name):
                self.repo = self.install()
                break_it(self.installed)
                output = self.marker("phase", "--run-id", RID, "--phase", "approve")
                self.assertTrue(output.startswith("doggy-workflow phase: approve\n\n"), output[:80])
                self.assertIn(f".harness/skills/doggy-workflow/{named}", output)
                self.assertEqual("## Voice" in output, named == "markers.json")

    def test_unknown_phase_arguments_print_the_usage_line_and_record_nothing(self):
        self.marker("start", "--run-id", RID, "--spec", "orders", "--spec-version", "1")
        before = self.events()
        for args in (("--phase", "understand"), ("--run-id", RID), ("--run-id", RID, "--phase", "amend",
                                                                  "--reason", "because"), ()):
            with self.subTest(args=args):
                output = self.marker("phase", *args)
                self.assertTrue(output.startswith("doggy-workflow: unknown phase arguments."), output)
                for phase in (*PRINT_ONLY, *RECORDED):
                    self.assertIn(phase, output)
        self.assertEqual(self.events(), before)

    def test_phase_command_is_not_taken_for_a_brief_marker_by_the_hook(self):
        payload = self.post_tool_use_bash("python3 .harness/bin/workflow_marker.py phase --phase brief")
        result = self.run_hook_env(self.repo, "telemetry_hook.py", payload, self.env)
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertEqual([event for event in self.events() if event["event"] == "brief"], [])


class TestPartsThatDoNotApply(PhaseCase):
    def left_out(self, output):
        found = re.search(r"^Left out: (.*)\. `--all` prints everything\.$", output.split("\n\n", 1)[0], re.MULTILINE)
        return found.group(1) if found else None

    def test_a_spec_without_steps_fuzzing_or_mutation_tool_leaves_those_rules_out(self):
        self.spec(PLAIN_SPEC)
        cases = {
            "implement_test": (["stepped-run"], "stepped-run (the spec has no steps)"),
            "close": (["stepped-end"], "stepped-end (the spec has no steps)"),
            "resume": (["stepped-resume", "stepped-run"],
                       "stepped-resume (the spec has no steps), stepped-run (the spec has no steps)"),
            "verify": (["verification-fuzz", "verification-mutation-tool", "verification-marker"],
                       "verification-fuzz (the spec declares no fuzzing), "
                       "verification-mutation-tool (the spec declares no mutation tool), "
                       "verification (the spec declares neither fuzzing nor a mutation tool)"),
        }
        for phase, (without, note) in cases.items():
            with self.subTest(phase=phase):
                output = self.marker("phase", "--run-id", RID, "--phase", phase, "--again")
                self.assertEqual(self.left_out(output), note)
                self.assertEqual(output.split("\n\n", 1)[1], self.printed(phase, without=without))

    def test_phases_without_conditional_parts_print_the_same_with_any_spec(self):
        self.spec(PLAIN_SPEC)
        for phase in ("brief", "draft", "approve", "amend", "step"):
            with self.subTest(phase=phase):
                output = self.marker("phase", "--run-id", RID, "--phase", phase, "--again")
                self.assertIsNone(self.left_out(output))
                self.assertEqual(output.split("\n\n", 1)[1], self.printed(phase))

    def test_a_stepped_spec_that_declares_fuzzing_gets_those_rules(self):
        self.spec(STEPPED_SPEC)
        cases = {
            "implement_test": ([], None),
            "close": ([], None),
            "resume": (["stepped-cut"], "stepped-cut (the spec already has steps)"),
            "verify": (["verification-mutation-tool"],
                       "verification-mutation-tool (the spec declares no mutation tool)"),
        }
        for phase, (without, note) in cases.items():
            with self.subTest(phase=phase):
                output = self.marker("phase", "--run-id", RID, "--phase", phase, "--again")
                self.assertEqual(self.left_out(output), note)
                self.assertEqual(output.split("\n\n", 1)[1], self.printed(phase, without=without))

    def test_all_prints_every_part_whatever_the_spec_says(self):
        self.spec(PLAIN_SPEC)
        for phase in ("implement_test", "verify", "close", "resume"):
            with self.subTest(phase=phase):
                output = self.marker("phase", "--run-id", RID, "--phase", phase, "--again", "--all")
                self.assertIsNone(self.left_out(output))
                self.assertEqual(output.split("\n\n", 1)[1], self.printed(phase))

    def test_everything_is_printed_when_the_spec_cannot_be_told(self):
        unknown = {
            "no spec for the run id": lambda: None,
            "two specs for the run id": lambda: (self.spec(PLAIN_SPEC), self.spec(PLAIN_SPEC, name="other")),
            "no run id given": lambda: self.spec(PLAIN_SPEC),
            "spec of another run": lambda: self.spec(PLAIN_SPEC, run_id="0000000000000000"),
        }
        for name, prepare in unknown.items():
            with self.subTest(case=name):
                self.repo = self.install()
                prepare()
                run = () if name == "no run id given" else ("--run-id", RID)
                output = self.marker("phase", *run, "--phase", "verify", "--again")
                self.assertIsNone(self.left_out(output))
                self.assertEqual(output.split("\n\n", 1)[1], self.printed("verify", run_id=run[1] if run else None))

    def test_the_template_as_created_counts_as_no_steps_and_as_declaring_both_tools(self):
        self.commit()
        created = subprocess.run(
            [sys.executable, str(self.repo / ".harness" / "bin" / "spec_lifecycle.py"), "new", "--run-id", RID,
             "--name", "orders"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertIsNone(self.left_out(self.marker("phase", "--run-id", RID, "--phase", "verify", "--again")))
        self.assertEqual(self.left_out(self.marker("phase", "--run-id", RID, "--phase", "close", "--again")),
                         "stepped-end (the spec has no steps)")


class TestNewSpec(PhaseCase):
    def setUp(self):
        super().setUp()
        self.commit()

    def test_new_refuses_in_a_repository_without_a_commit(self):
        self.repo = self.install()
        result = self.new("--run-id", RID, "--name", "export-orders")
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("the repository needs at least one commit", result.stderr)
        self.assertFalse((self.repo / "agent-docs" / "specs").exists()
                         and any((self.repo / "agent-docs" / "specs").iterdir()))

    def new(self, *args):
        return subprocess.run([sys.executable, str(self.repo / ".harness" / "bin" / "spec_lifecycle.py"), "new", *args],
                              cwd=self.repo, capture_output=True, text=True)

    def head(self):
        return subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip()

    def test_new_copies_the_template_with_the_frontmatter_filled_in_and_prints_the_path(self):
        result = self.new("--run-id", RID, "--name", "export-orders")
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, f"agent-docs/specs/{RID}-export-orders.md\n", ""))
        text = (self.repo / "agent-docs" / "specs" / f"{RID}-export-orders.md").read_text()
        template = (self.installed / "spec-template.md").read_text()
        expected = template
        for placeholder, value in (
                ("version: <positive integer>", "version: 1"),
                ("run_id: <16 lowercase hexadecimal characters>", f"run_id: {RID}"),
                ("status: draft|active|complete|limit|aborted", "status: draft"),
                ("base_commit: <full commit id at workflow start>", f"base_commit: {self.head()}")):
            self.assertEqual(template.count(placeholder), 1, placeholder)
            expected = expected.replace(placeholder, value)
        self.assertEqual(text, expected)
        self.assertTrue(text.startswith(f"---\nversion: 1\nrun_id: {RID}\nstatus: draft\nbase_commit: "))
        self.assertIn("\nmax_verifier_invocations: 2\n---\n", text)

    def test_new_refuses_and_writes_nothing(self):
        specs = self.repo / "agent-docs" / "specs"
        logs = self.repo / "agent-docs" / "spec-logs"
        refusals = {
            "run id too short": (("--run-id", "49bafb30", "--name", "x"), "16 lowercase hexadecimal"),
            "run id upper case": (("--run-id", RID.upper(), "--name", "x"), "16 lowercase hexadecimal"),
            "name with underscore": (("--run-id", RID, "--name", "export_orders"), "single hyphens"),
            "name with a slash": (("--run-id", RID, "--name", "a/b"), "single hyphens"),
            "name ending in a hyphen": (("--run-id", RID, "--name", "export-"), "single hyphens"),
        }
        for name, (args, message) in refusals.items():
            with self.subTest(refusal=name):
                result = self.new(*args)
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertIn(message, result.stderr)
                self.assertFalse(specs.exists() and any(specs.iterdir()))
        self.assertEqual(self.new("--run-id", RID, "--name", "first").returncode, 0)
        again = self.new("--run-id", RID, "--name", "second")
        self.assertEqual((again.returncode, again.stdout), (1, ""))
        self.assertIn(f"run id {RID} already has a spec: agent-docs/specs/{RID}-first.md", again.stderr)
        self.assertEqual([path.name for path in specs.iterdir()], [f"{RID}-first.md"])
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "0000000000000001-done.md").write_text("archived\n")
        archived = self.new("--run-id", "0000000000000001", "--name", "again")
        self.assertEqual(archived.returncode, 1)
        self.assertIn("already has a spec: agent-docs/spec-logs/0000000000000001-done.md", archived.stderr)

    def test_new_refuses_when_the_template_is_missing_or_lacks_a_frontmatter_line(self):
        template = self.installed / "spec-template.md"
        original = template.read_text()
        template.write_text(original.replace("version: <positive integer>", "version: 3"))
        changed = self.new("--run-id", RID, "--name", "x")
        self.assertEqual(changed.returncode, 1)
        self.assertIn("spec template has no line `version: <positive integer>`", changed.stderr)
        template.unlink()
        missing = self.new("--run-id", RID, "--name", "x")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("spec template not readable", missing.stderr)
        self.assertFalse((self.repo / "agent-docs" / "specs").exists()
                         and any((self.repo / "agent-docs" / "specs").iterdir()))


class TestShippedPhases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = {phase: [skill_text.entry_name(entry) for entry in entries]
                        for phase, entries in skill_text.phases(SKILL).items()}
        cls.markers = json.loads((SKILL_DIR / "markers.json").read_text(encoding="utf-8"))
        cls.fragments = {path.stem: path.read_text(encoding="utf-8") for path in (SKILL_DIR / "phases").glob("*.md")}
        cls.core = SKILL.read_text(encoding="utf-8").split("\n---\n", 1)[1]

    def test_manifest_names_exactly_the_phases_the_marker_accepts(self):
        self.assertEqual(sorted(self.manifest), sorted((*PRINT_ONLY, *RECORDED)))

    def test_every_fragment_is_used_and_every_name_has_a_file(self):
        used = {name for names in self.manifest.values() for name in names}
        self.assertEqual(used, set(self.fragments))

    def test_every_marker_command_and_rule_is_printed_by_some_phase(self):
        printed_commands = {skill_text.entry_name(entry) for phase in self.markers["phases"].values()
                            for entry in phase["commands"]}
        printed_rules = {skill_text.entry_name(entry) for phase in self.markers["phases"].values()
                         for entry in phase["rules"]}
        self.assertEqual(printed_commands - {"start-marker"}, set(self.markers["commands"]))
        self.assertEqual(printed_rules, {key for key, _sentence in self.markers["rules"]})
        self.assertEqual({phase: [skill_text.entry_name(entry) for entry in value["commands"]]
                          for phase, value in self.markers["phases"].items()}, MARKER_COMMANDS)
        self.assertLessEqual(set(self.markers["phases"]), set(self.manifest))

    def test_conditional_parts_are_the_stepped_fuzzing_and_mutation_tool_rules_only(self):
        conditional = {(phase, entry["name"], entry["when"]) for phase, entries in skill_text.phases(SKILL).items()
                       for entry in entries if not isinstance(entry, str)}
        self.assertEqual(conditional, {
            ("implement_test", "stepped-run", "stepped"), ("close", "stepped-end", "stepped"),
            ("resume", "stepped-resume", "stepped"), ("resume", "stepped-run", "stepped"),
            ("resume", "stepped-cut", "not-stepped"), ("verify", "verification-fuzz", "fuzzing"),
            ("verify", "verification-mutation-tool", "mutation-tool"),
        })

    def test_what_a_fragment_cites_is_printed_with_it_or_listed_as_looked_up(self):
        for name, text in self.fragments.items():
            with self.subTest(fragment=name):
                self.assertEqual(len(CITATION.findall(text)), len(CITATIONS.get(name, [])))
        unresolved = set()
        for phase, names in self.manifest.items():
            for position, name in enumerate(names):
                for cited, earlier in CITATIONS.get(name, []):
                    reach = names[:position] if earlier else names
                    if not cited & set(reach):
                        unresolved.add((phase, name, sorted(cited)[0]))
        self.assertEqual(unresolved, set(LOOKED_UP))

    def test_the_reading_order_helper_covers_every_fragment_once(self):
        names = skill_text.fragment_names()
        self.assertEqual(sorted(names), sorted(self.fragments))
        self.assertEqual(len(names), len(set(names)))

    def test_core_fits_what_survives_compaction_and_each_phase_fits_one_command_output(self):
        self.assertLessEqual(len(self.core.split()), CORE_WORD_LIMIT)
        sentences = dict(self.markers["rules"])
        for phase, names in self.manifest.items():
            with self.subTest(phase=phase):
                printed = "\n".join(self.fragments[name] for name in names)
                marked = self.markers["phases"].get(phase, {"commands": [], "rules": []})
                printed += "\n".join(self.markers["commands"].get(skill_text.entry_name(entry), "")
                                     for entry in marked["commands"])
                printed += " ".join(sentences[skill_text.entry_name(entry)] for entry in marked["rules"])
                self.assertLessEqual(len(printed), PHASE_CHARACTER_LIMIT)

    def test_installed_copies_carry_the_same_files(self):
        for copy in (".agents/skills/doggy-workflow", ".harness/skills/doggy-workflow"):
            with self.subTest(copy=copy):
                installed = REPO_ROOT / copy
                for name in ("phases.json", "markers.json", "spec-template.md"):
                    self.assertEqual((installed / name).read_text(encoding="utf-8"),
                                     (SKILL_DIR / name).read_text(encoding="utf-8"), name)
                self.assertEqual({path.stem: path.read_text(encoding="utf-8")
                                  for path in (installed / "phases").glob("*.md")}, self.fragments)

    def test_the_template_has_the_headings_the_lifecycle_check_requires(self):
        source = (REPO_ROOT / "harness" / "bin" / "spec_lifecycle.py").read_text(encoding="utf-8")
        required = re.findall(r'^    "(# [^"]+)",$', source.split("REQUIRED_HEADINGS = (", 1)[1].split(")", 1)[0],
                              re.MULTILINE)
        self.assertEqual(len(required), 16)
        headings = [line for line in (SKILL_DIR / "spec-template.md").read_text(encoding="utf-8").splitlines()
                    if line.startswith("# ")]
        self.assertEqual([heading for heading in headings if heading in required], required)
        self.assertEqual(headings[-2:], ["# Steps", "# Session Memory"])

    @text_test
    def test_core_tells_how_to_run_a_phase_and_what_to_do_with_its_output(self):
        flat = re.sub(r"\s+", " ", self.core)
        for phase in self.manifest:
            self.assertIn(f"| `{phase}` |", self.core)
        self.assertIn("python3 .harness/bin/workflow_marker.py phase --phase brief\n", self.core)
        self.assertIn("python3 .harness/bin/workflow_marker.py phase --run-id ID --phase NAME --again\n", self.core)
        self.assertRegex(flat, r"Never redirect, pipe, or discard it")
        self.assertRegex(flat, r"no longer in view[^.]*print them again with `--again`: that form records nothing")
        self.assertRegex(flat, r"refers to a section that is not in view, find the phase that prints it in the table")
        self.assertRegex(flat, r"leaves out what does not apply to the spec of the run[^.]*says what it left out; "
                               r"`--all` prints everything")
        self.assertRegex(flat, r"If the command cannot print the rules, it names the files to read instead")
        self.assertRegex(flat, r"The `phase` command is the exception: its output is the phase's rules")
        self.assertRegex(flat, r"under \*Markers of this phase\*, the marker commands that belong to it, with the run "
                               r"id filled in")

    @text_test
    def test_spec_format_points_to_the_command_that_creates_the_spec_from_the_template(self):
        flat = re.sub(r"\s+", " ", self.fragments["spec-format"])
        self.assertIn("python3 .harness/bin/spec_lifecycle.py new --run-id ID --name <kebab-name>\n",
                      self.fragments["spec-format"])
        self.assertRegex(flat, r"copies `\.harness/skills/doggy-workflow/spec-template\.md` to "
                               r"`agent-docs/specs/<run-id>-<kebab-name>\.md`")
        self.assertRegex(flat, r"delete both sections from the file of a spec without steps")
        self.assertNotIn("````", self.fragments["spec-format"])

    @text_test
    def test_verifier_marker_counts_are_defined_where_the_marker_is_printed(self):
        sentences = dict(self.markers["rules"])
        self.assertRegex(sentences["verifier-counts"], r"`--findings` counts the findings of that result")
        self.assertRegex(sentences["verifier-counts"], r"`--seeds-run` counts the confirming mutations")
        self.assertRegex(sentences["verifier-counts"], r"`--seeds-detected` those the intended assertion detected")
        self.assertIn("verifier-counts", self.markers["phases"]["verify"]["rules"])

    @text_test
    def test_every_section_of_the_single_file_skill_appears_once_and_the_workflow_items_stay_in_order(self):
        whole = skill_text.whole(SKILL)
        self.assertEqual(whole.count("\n# Phases\n"), 1)
        for heading in ("# Spec", "## Required format", "# Memory", "# Brief", "## Voice", "## Decision sweep",
                        "## Rounds", "## Quiz", "## Closing report", "# Stepped specs", "# Verification model",
                        "# Subagent model", "# Telemetry", "# Workflow"):
            with self.subTest(heading=heading):
                self.assertEqual(whole.count(f"\n{heading}\n"), 1)
        order = [whole.index(f"\n{number}. **") for number in range(1, 10)]
        self.assertEqual(order, sorted(order))
        for legacy in ("pre-0.10", "before harness 0.52.0"):
            self.assertNotIn(legacy, whole)


if __name__ == "__main__":
    unittest.main()
