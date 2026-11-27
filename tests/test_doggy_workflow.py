import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from hook_case import out
from old_release import BASE_0491, release_source
from test_installer import REPO_ROOT, InstallerTestCase, load_installer_module, run_installer
from test_remove_progress import tree_state
import skill_text as rules

OLD_SKILL = "workflow-approach"
NEW_SKILL = "doggy-workflow"
OLD_LINK_TARGET = f"../../.agents/skills/{OLD_SKILL}"
FACT_FILE = "0123456789abcdef-load-peak-rps.md"
FACT_TEXT = "dimension: load\nfact: peak is 40 requests per second\nsource: user, 2026-11-13\n"
FACTS_MD = "# Facts\n\n- Peak is 40 requests per second. — source: user, 2026-11-13; re-check: ask the user\n"
MEMORY_HEADINGS = ("## Failed Attempts & Reasons", "## Decisions & Reasons & Alternatives",
                   "## Unresolved Questions & Uncertainties")


def skill_text(root=REPO_ROOT / "harness"):
    return rules.whole(root / "skills" / NEW_SKILL / "SKILL.md")


def section(text, heading):
    level = heading.split(" ", 1)[0]
    lines = text.splitlines()
    start = lines.index(heading)
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"#{1,%d} \S" % len(level), lines[i]) and not in_fence(lines, i)), len(lines))
    return "\n".join(lines[start:end])


def in_fence(lines, index):
    return sum(line.startswith("````") for line in lines[:index]) % 2 == 1


class Update0491Case(InstallerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = release_source(BASE_0491)

    def installed_0491(self):
        repo = self.make_repo()
        result = subprocess.run([sys.executable, str(self.source / "installer" / "harness.py"), "install", str(repo),
                                 "--no-ci"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, out(result))
        self.assertEqual(os.readlink(repo / ".claude" / "skills" / OLD_SKILL), OLD_LINK_TARGET)
        return repo

    def update(self, repo, *args):
        return run_installer("update", str(repo), "--no-ci", "--no-commit", *args, input="y\n" * 80, exact=True)

    def version(self, repo):
        return json.loads((repo / ".harness" / "manifest.json").read_text())["version"]

    def write(self, repo, rel, text):
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path


class TestRename(Update0491Case):
    def test_update_replaces_the_old_skill_with_the_new_one(self):
        repo = self.installed_0491()

        result = self.update(repo)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertEqual(self.version(repo), "0.59.0")
        for rel in (f".claude/skills/{OLD_SKILL}", f".agents/skills/{OLD_SKILL}", f".harness/skills/{OLD_SKILL}"):
            with self.subTest(removed=rel):
                self.assertFalse(os.path.lexists(repo / rel), rel)
        self.assertEqual(os.readlink(repo / ".claude" / "skills" / NEW_SKILL), f"../../.agents/skills/{NEW_SKILL}")
        for rel in (f".agents/skills/{NEW_SKILL}/SKILL.md", f".harness/skills/{NEW_SKILL}/SKILL.md"):
            with self.subTest(written=rel):
                self.assertIn(f"\nname: {NEW_SKILL}\n", (repo / rel).read_text())
        self.assertIn(f"remove the .claude/skills/{OLD_SKILL} symlink", result.stdout)

    def test_installed_agents_name_the_new_skill(self):
        repo = self.installed_0491()
        self.assertEqual(self.update(repo).returncode, 0)
        for path in sorted((repo / ".claude" / "agents").glob("*.md")):
            with self.subTest(agent=path.name):
                self.assertNotIn(OLD_SKILL, path.read_text())

    def test_old_link_that_is_not_the_harness_symlink_is_left_and_reported(self):
        repo = self.installed_0491()
        link = repo / ".claude" / "skills" / OLD_SKILL
        link.unlink()
        self.write(repo, f".claude/skills/{OLD_SKILL}/SKILL.md", "own skill\n")

        result = self.update(repo)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertEqual((link / "SKILL.md").read_text(), "own skill\n")
        self.assertIn(f".claude/skills/{OLD_SKILL} is not the harness symlink; left in place", result.stdout)

    def test_edited_old_skill_file_stops_the_update_and_is_kept(self):
        repo = self.installed_0491()
        old = repo / ".agents" / "skills" / OLD_SKILL / "SKILL.md"
        old.write_text(old.read_text() + "\nlocal note\n")

        result = self.update(repo)

        self.assertEqual(result.returncode, 1, out(result))
        self.assertTrue(old.read_text().endswith("\nlocal note\n"))
        self.assertIn(f".agents/skills/{OLD_SKILL}/SKILL.md: edited in place; harness files are not edited.", result.stdout)

    def test_retrospective_hook_is_removed(self):
        repo = self.installed_0491()
        self.assertTrue((repo / ".harness" / "git" / "warn_retrospective.py").is_file())

        self.assertEqual(self.update(repo).returncode, 0)

        self.assertFalse((repo / ".harness" / "git" / "warn_retrospective.py").exists())
        self.assertNotIn("warn_retrospective", (repo / ".harness" / "git" / "pre-commit").read_text())


class TestFactsMigration(Update0491Case):
    def assert_refused(self, repo, result, before, named):
        self.assertEqual(result.returncode, 1, out(result))
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("MigrationConflict", result.stdout)
        self.assertIn(named, result.stdout)
        self.assertIn("facts.md", result.stdout)
        self.assertEqual(tree_state(repo), before)
        self.assertEqual(self.version(repo), "0.49.1")

    def test_update_refuses_and_changes_nothing_while_the_facts_directory_holds_files(self):
        repo = self.installed_0491()
        self.write(repo, f"agent-docs/facts/{FACT_FILE}", FACT_TEXT)
        before = tree_state(repo)

        result = self.update(repo)

        self.assert_refused(repo, result, before, "agent-docs/facts/ holds 1 entry")
        self.assertIn(FACT_FILE, result.stdout)

    def test_dry_run_reports_the_same_refusal(self):
        repo = self.installed_0491()
        self.write(repo, f"agent-docs/facts/{FACT_FILE}", FACT_TEXT)
        before = tree_state(repo)

        result = self.update(repo, "--dry-run")

        self.assert_refused(repo, result, before, "agent-docs/facts/ holds 1 entry")

    def test_any_entry_counts_including_a_subdirectory(self):
        repo = self.installed_0491()
        (repo / "agent-docs" / "facts" / "stale").mkdir(parents=True)
        before = tree_state(repo)

        result = self.update(repo)

        self.assert_refused(repo, result, before, "agent-docs/facts/ holds 1 entry")

    def test_facts_directory_under_a_configured_docs_root_also_refuses(self):
        repo = self.installed_0491()
        config_path = repo / ".harness" / "config.json"
        config = json.loads(config_path.read_text()) if config_path.is_file() else {}
        config["docs_root"] = "docs/agent"
        config_path.write_text(json.dumps(config))
        self.write(repo, f"docs/agent/facts/{FACT_FILE}", FACT_TEXT)
        self.write(repo, "docs/agent/facts/second.md", "x\n")
        before = tree_state(repo)

        result = self.update(repo)

        self.assert_refused(repo, result, before, "docs/agent/facts/ holds 2 entries")

    def test_a_file_named_facts_refuses(self):
        repo = self.installed_0491()
        self.write(repo, "agent-docs/facts", "not a directory\n")
        before = tree_state(repo)

        result = self.update(repo)

        self.assert_refused(repo, result, before, "agent-docs/facts is not a directory")

    def test_empty_facts_directory_is_removed_and_the_update_proceeds(self):
        repo = self.installed_0491()
        (repo / "agent-docs" / "facts").mkdir(parents=True)

        result = self.update(repo)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertFalse(os.path.lexists(repo / "agent-docs" / "facts"))
        self.assertIn("remove the empty agent-docs/facts/", result.stdout)
        self.assertEqual(self.version(repo), "0.59.0")

    def test_absent_facts_directory_proceeds_without_a_removal_line(self):
        repo = self.installed_0491()

        result = self.update(repo)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertNotIn("remove the empty", result.stdout)

    def test_prepared_project_updates_and_keeps_facts_md_untouched(self):
        repo = self.installed_0491()
        self.write(repo, f"agent-docs/facts/{FACT_FILE}", FACT_TEXT)
        self.assertEqual(self.update(repo).returncode, 1)
        (repo / "agent-docs" / "facts" / FACT_FILE).unlink()
        (repo / "agent-docs" / "facts").rmdir()
        facts = self.write(repo, "agent-docs/facts.md", FACTS_MD)

        result = self.update(repo)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertEqual(facts.read_text(), FACTS_MD)
        self.assertEqual(self.version(repo), "0.59.0")
        verify = self.run_verify_rules(repo)
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_migration_is_registered_once_and_last(self):
        module = load_installer_module()
        entries = [entry for entry in module.MIGRATIONS if entry[0] == module.parse_version("0.51.0")]
        self.assertEqual(len(entries), 1, entries)
        self.assertIs(entries[0][2], module.migrate_doggy_workflow)
        self.assertEqual(module.MIGRATIONS[-1][0], module.parse_version("0.59.0"))


class TestInstalledRules(InstallerTestCase):
    def test_spec_start_requires_alternatives_and_open_questions(self):
        for heading in ("# Alternatives", "# Open Questions"):
            with self.subTest(missing=heading):
                repo = self.install()
                spec = self.write_valid_spec(repo)
                spec.write_text(spec.read_text().replace(f"{heading}\n\nnone\n\n", ""))
                result = self.run_lifecycle(repo, "validate", "--spec", str(spec))
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(f"missing heading {heading}", result.stderr)

    def test_spec_without_a_retrospective_section_is_valid(self):
        repo = self.install()
        spec = self.write_valid_spec(repo)
        self.assertNotIn("# Retrospective", spec.read_text())
        result = self.run_lifecycle(repo, "validate", "--spec", str(spec))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_facts_md_at_the_docs_root_passes_rule_verification(self):
        repo = self.install()
        (repo / "agent-docs" / "facts.md").write_text(FACTS_MD)
        result = self.run_verify_rules(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fresh_install_links_only_the_current_skills(self):
        repo = self.install()
        self.assertEqual(sorted(path.name for path in (repo / ".claude" / "skills").iterdir()), [NEW_SKILL, "project-map"])
        self.assertFalse((repo / ".harness" / "git" / "warn_retrospective.py").exists())
        self.assertFalse(os.path.lexists(repo / "agent-docs" / "facts"))


class TestShippedText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = skill_text()
        cls.lines = cls.text.splitlines()
        cls.flat = re.sub(r"\s+", " ", cls.text)

    def test_installed_copies_equal_the_shipped_skill(self):
        for rel in (f".agents/skills/{NEW_SKILL}/SKILL.md", f".harness/skills/{NEW_SKILL}/SKILL.md"):
            with self.subTest(copy=rel):
                self.assertEqual(rules.whole(REPO_ROOT / rel), self.text)
        self.assertFalse(os.path.lexists(REPO_ROOT / ".claude" / "skills" / OLD_SKILL))
        self.assertFalse((REPO_ROOT / "harness" / "skills" / OLD_SKILL).exists())

    def test_frontmatter_names_the_new_skill_and_the_old_name_is_gone(self):
        self.assertEqual(self.lines[1], f"name: {NEW_SKILL}")
        self.assertNotIn(OLD_SKILL, self.text)

    def test_spec_format_drops_retrospective_and_adds_alternatives_and_open_questions(self):
        self.assertNotIn("# Retrospective", self.lines)
        for heading in ("# Alternatives", "# Open Questions", "# Steps", "# Session Memory", *MEMORY_HEADINGS):
            with self.subTest(heading=heading):
                self.assertEqual(self.lines.count(heading), 1)
        order = [self.lines.index(h) for h in ("# Assumptions and Defaults", "# Alternatives", "# Open Questions",
                                               "# Traceability", "# Version Log", "# Steps", "# Session Memory",
                                               *MEMORY_HEADINGS)]
        self.assertEqual(order, sorted(order))
        self.assertRegex(self.flat, r"`# Steps` and `# Session Memory` exist only in a stepped spec")

    def test_facts_live_in_one_file_written_after_approval_and_read_whole(self):
        self.assertNotIn("agent-docs/facts/", self.text)
        memory = section(self.text, "# Memory")
        self.assertIn("`agent-docs/facts.md`", memory)
        self.assertRegex(memory, r"only after the user approves")
        self.assertRegex(memory, r"Read the whole file before the understanding round")
        self.assertRegex(memory, r"An answer is not approval of the wording")

    def test_try_n_fail_is_searched_at_two_moments_and_not_up_front(self):
        search = section(self.text, "## Try-n-fail search")
        self.assertRegex(search, r"Do not read `agent-docs/try-n-fail/` while understanding the task")
        self.assertRegex(search, r"\*\*Before carrying out the approach\*\*")
        self.assertRegex(search, r"\*\*At the first failure\*\*")
        self.assertRegex(search, r"open only the records that match")

    def test_voice_lowers_project_detail_and_judges_from_code_and_spec_alone(self):
        voice = section(self.text, "## Voice")
        for pattern in (r"Leave out file paths, function and variable names",
                        r"what it costs, what it rules out",
                        r"from the current code and the spec alone",
                        r"Do not keep a record of what the user knows"):
            with self.subTest(pattern=pattern):
                self.assertRegex(voice, pattern)

    def test_quiz_covers_tradeoff_engineer_calls_and_final_shape_and_is_never_recorded(self):
        quiz = section(self.text, "## Quiz")
        for pattern in (r"the core trade-off, the engineer calls, and the final shape",
                        r"predict or apply, not to recall",
                        r"Give no options, no hints, and no answers",
                        r"A quiz answer is never recorded and is never a decision or an instruction",
                        r"Only an amendment the user approves changes the spec",
                        r"The user may skip the quiz by saying so",
                        r"Main never skips or shortens it on its own"):
            with self.subTest(pattern=pattern):
                self.assertRegex(quiz, pattern)

    def test_closing_report_replaces_the_saved_retrospective(self):
        closing = section(self.text, "## Closing report")
        for pattern in (r"closing report in chat", r"replaces a saved retrospective",
                        r"\*What went wrong\*", r"\*Records to approve\*", r"Write only what the user approves"):
            with self.subTest(pattern=pattern):
                self.assertRegex(closing, pattern)
        step9 = next(line for line in self.lines if line.startswith("9. **"))
        self.assertRegex(step9, r"Then give the closing report with its quiz")
        self.assertNotRegex(self.text.lower(), r"retrospective entry")

    def test_stepped_specs_state_the_four_triggers_and_objective_session_memory(self):
        stepped = section(self.text, "# Stepped specs")
        for pattern in (r"15 rows or more", r"`step_split_obligations` in `\.harness/config\.json`",
                        r"\*order dependence\*", r"\*outside wait\*", r"\*too many decisions\*",
                        r"\*a stopped session\*", r"is a nonterminal stop",
                        r"Search try-n-fail for the step's approach",
                        r"every id belongs to exactly one step",
                        r"`max_verifier_invocations` bounds each step separately",
                        r"Every row is objective and reproducible",
                        r"No recommendations, preferences, or instructions",
                        r"These sections serve this task only"):
            with self.subTest(pattern=pattern):
                self.assertRegex(stepped, pattern)
        for heading in MEMORY_HEADINGS:
            with self.subTest(heading=heading):
                self.assertIn(f"*{heading[3:]}*", stepped)

    def test_decision_cap_offers_separate_tasks_or_steps_with_deferred_decisions(self):
        self.assertRegex(self.flat, r"When the count first exceeds 3.{0,200}separate tasks with a spec each"
                                    r".{0,200}held for their own step")

    def test_managed_block_states_the_memory_scope(self):
        block = (REPO_ROOT / "harness" / "instructions" / "harness-block.md").read_text()
        second = next(line for line in block.splitlines() if line.startswith("2. **"))
        for pattern in (r"^2\. \*\*Memory Has a Scope\*\*", r"`agent-docs/facts\.md`",
                        r"only after the user approves its exact text",
                        r"right before carrying out an approach and at the first failure",
                        r"A retrospective is reported to the user, not saved"):
            with self.subTest(pattern=pattern):
                self.assertRegex(second, pattern)
        self.assertNotIn("session progress", block)

    def test_try_n_fail_rule_file_states_when_to_search(self):
        rule = (REPO_ROOT / "harness" / "instructions" / "try-n-fail.md").read_text()
        self.assertRegex(rule, r"found by search, not read up front")
        self.assertRegex(rule, r"right before carrying out an approach and at the first failure")


if __name__ == "__main__":
    unittest.main()
