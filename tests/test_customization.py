import json
import os
import re

from customization_case import (
    AGENT_NAMES, AGENTS, FIVE, GIT_NAMES, PHASES, SKILL_DIR, CustomizationCase, split_paths, today_candidates,
)

HEX = re.compile(r"[0-9a-f]{64}")
UNCONFIRMED = ("unconfirmed", AGENTS, FIVE)


class TestStateTransitions(CustomizationCase):
    def test_t1_no_review_file_makes_the_project_instructions_unconfirmed(self):
        repo = self.project()
        self.assertIsNone(self.review(repo))
        self.assertEqual(self.status_lines(repo), [self.item_line("unconfirmed", AGENTS, FIVE)])

    def test_t2_confirm_makes_it_confirmed_and_records_both_hashes_version_and_date(self):
        repo = self.project()
        result = self.customization(repo, "confirm", AGENTS)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "confirmed AGENTS.md\n", ""))
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])
        record = self.review(repo)["items"][AGENTS]
        self.assertEqual(set(record), {"content", "compare", "harness_version", "confirmed"})
        self.assertRegex(record["content"], HEX)
        self.assertRegex(record["compare"], HEX)
        self.assertNotEqual(record["content"], record["compare"])
        self.assertEqual(record["harness_version"], self.version(repo))
        self.assertIn(record["confirmed"], today_candidates())
        self.assertEqual(self.notice(repo).stdout, "")

    def test_t3_edit_outside_the_block_makes_a_confirmed_item_unconfirmed(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        self.set_definition(repo, DEFINITION_EDITED)
        self.assertEqual(self.status_lines(repo), [self.item_line("unconfirmed", AGENTS, FIVE)])

    def test_t3_each_kind_of_edit_outside_the_block_counts(self):
        edits = {
            "text appended after the block": lambda t: t + "\nLater rule.\n",
            "text changed before the block": lambda t: t.replace("tabs", "spaces"),
            "text prepended": lambda t: "Intro.\n\n" + t,
        }
        for name, edit in edits.items():
            with self.subTest(edit=name):
                repo = self.project()
                self.confirm(repo, AGENTS)
                path = repo / AGENTS
                path.write_text(edit(path.read_text()))
                self.assertEqual(self.status_lines(repo), [self.item_line("unconfirmed", AGENTS, FIVE)])

    def test_t4_edit_inside_the_block_only_keeps_it_confirmed(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        path = repo / AGENTS
        text = path.read_text()
        self.assertIn("<!-- harness:end -->", text)
        path.write_text(text.replace("<!-- harness:end -->", "an older harness line\n<!-- harness:end -->"))
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])
        self.assertEqual(self.notice(repo).stdout, "")

    def test_t5_a_change_of_any_compare_file_makes_it_harness_changed(self):
        for rel in FIVE:
            with self.subTest(changed=rel):
                repo = self.project()
                self.confirm(repo, AGENTS)
                path = repo / rel
                path.write_bytes(path.read_bytes() + b"\nnew harness sentence\n")
                self.assertEqual(self.status_lines(repo), [self.item_line("harness-changed", AGENTS, FIVE)])

    def test_t5_a_deleted_compare_file_counts_as_a_change(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        (repo / FIVE[3]).unlink()
        self.assertEqual(self.status_lines(repo), [self.item_line("harness-changed", AGENTS, FIVE)])

    def test_t6_a_change_of_a_file_that_is_no_compare_path_keeps_it_confirmed(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        for rel in (".harness/hooks/spec_gate.py", f"{SKILL_DIR}/SKILL.md", ".harness/config.default.json"):
            with self.subTest(changed=rel):
                path = repo / rel
                path.write_bytes(path.read_bytes() + b"\n# other harness change\n")
                self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])
        self.assertEqual(self.notice(repo).stdout, "")

    def test_t7_confirm_turns_harness_changed_into_confirmed_and_records_the_new_compare_hash(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        before = self.review(repo)["items"][AGENTS]
        path = repo / FIVE[0]
        path.write_bytes(path.read_bytes() + b"\nnew harness sentence\n")
        self.confirm(repo, AGENTS)
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])
        after = self.review(repo)["items"][AGENTS]
        self.assertEqual(after["content"], before["content"])
        self.assertNotEqual(after["compare"], before["compare"])

    def test_t8_an_edit_outside_the_block_turns_harness_changed_into_unconfirmed(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        path = repo / FIVE[0]
        path.write_bytes(path.read_bytes() + b"\nnew harness sentence\n")
        self.assertEqual(self.status_lines(repo), [self.item_line("harness-changed", AGENTS, FIVE)])
        self.set_definition(repo, DEFINITION_EDITED)
        self.assertEqual(self.status_lines(repo), [self.item_line("unconfirmed", AGENTS, FIVE)])

    def test_the_notice_for_the_first_state_names_the_item_the_compare_files_and_the_confirm_command(self):
        repo = self.project()
        lines = self.notice_lines(repo)
        self.assertEqual(len(lines), 2, lines)
        self.assertEqual(lines[0], INSTRUCTION_LINE)
        found = re.fullmatch(re.escape(PREFIX_) + r"unconfirmed AGENTS\.md; compare with (.+); confirm: "
                             + re.escape("python3 .harness/bin/customization.py confirm AGENTS.md"), lines[1])
        self.assertIsNotNone(found, lines[1])
        self.assertEqual(split_paths(found[1]), FIVE)

    def test_a_missing_agents_md_yields_no_item(self):
        repo = self.project()
        (repo / AGENTS).unlink()
        self.assertEqual(self.status_lines(repo), ["no customizations"])
        self.assertEqual(self.notice(repo).stdout, "")


DEFINITION_EDITED = "# Project Definition\n\nA widget CLI.\n\nAlways use spaces.\n\n"


class TestConfirmTable(CustomizationCase):
    def seed_other_record(self, repo):
        record = {"content": "a" * 64, "compare": "b" * 64, "harness_version": "0.1.0", "confirmed": "2020-01-01"}
        self.write(repo, ".harness/customization-review.json", json.dumps({"items": {"other.md": record}}))
        return record

    def test_one_valid_path(self):
        repo = self.project()
        result = self.customization(repo, "confirm", AGENTS)
        self.assertEqual((result.returncode, result.stdout), (0, "confirmed AGENTS.md\n"))

    def test_the_same_valid_path_twice_is_accepted_and_recorded_once(self):
        repo = self.project()
        result = self.customization(repo, "confirm", AGENTS, AGENTS)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(set(result.stdout.splitlines()), {"confirmed AGENTS.md"})
        self.assertEqual(list(self.review(repo)["items"]), [AGENTS])
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])

    def bad_rows(self, repo):
        self.write(repo, ".harness/local/x.md", "x\n")
        self.write(repo, "README.md", "readme\n")
        return [
            ("valid and not found", [AGENTS, "nope.md"], ["nope.md: not found"]),
            ("unrecognized", [".harness/local/x.md"], [".harness/local/x.md: not a recognized customization"]),
            ("not an item", ["README.md"], ["README.md: not a recognized customization"]),
            ("not found", ["nope.md"], ["nope.md: not found"]),
        ]

    def test_bad_paths_exit_1_with_one_message_each_and_change_no_review_file_bytes(self):
        repo = self.project()
        self.seed_other_record(repo)
        review = repo / ".harness" / "customization-review.json"
        original = review.read_bytes()
        for name, paths, messages in self.bad_rows(repo):
            with self.subTest(row=name):
                result = self.customization(repo, "confirm", *paths)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                for message in messages:
                    self.assertIn(message, (result.stdout + result.stderr).splitlines())
                self.assertEqual(review.read_bytes(), original)

    def test_bad_paths_leave_an_absent_review_file_absent(self):
        repo = self.project()
        for name, paths, messages in self.bad_rows(repo):
            with self.subTest(row=name):
                result = self.customization(repo, "confirm", *paths)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse((repo / ".harness" / "customization-review.json").exists())

    def test_two_bad_paths_get_one_message_each(self):
        repo = self.project()
        self.write(repo, "README.md", "readme\n")
        result = self.customization(repo, "confirm", "nope.md", "README.md")
        self.assertEqual(result.returncode, 1)
        lines = (result.stdout + result.stderr).splitlines()
        self.assertIn("nope.md: not found", lines)
        self.assertIn("README.md: not a recognized customization", lines)

    def test_a_review_file_of_each_form_before_a_valid_confirm(self):
        forms = {"invalid json": b"{not json", "array": b"[]", "items array": b'{"items": []}'}
        for name, raw in forms.items():
            with self.subTest(form=name):
                repo = self.project()
                self.write(repo, ".harness/customization-review.json", raw)
                before = self.status_lines(repo)
                self.assertIn("review-file-invalid .harness/customization-review.json", before)
                self.assertIn(self.item_line("unconfirmed", AGENTS, FIVE), before)
                result = self.customization(repo, "confirm", AGENTS)
                self.assertEqual((result.returncode, result.stdout), (0, "confirmed AGENTS.md\n"))
                data = self.review(repo)
                self.assertEqual(list(data["items"]), [AGENTS])
                self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])

    def test_a_valid_review_file_with_another_record_keeps_that_record(self):
        repo = self.project()
        other = self.seed_other_record(repo)
        self.assertEqual(self.customization(repo, "confirm", AGENTS).returncode, 0)
        items = self.review(repo)["items"]
        self.assertEqual(items["other.md"], other)
        self.assertIn(AGENTS, items)

    def test_an_absent_review_file_is_created(self):
        repo = self.project()
        self.assertIsNone(self.review(repo))
        self.assertEqual(self.customization(repo, "confirm", AGENTS).returncode, 0)
        self.assertEqual(list(self.review(repo)["items"]), [AGENTS])

    def test_confirm_leaves_no_temporary_file_behind(self):
        repo = self.project()
        before = set(os.listdir(repo / ".harness"))
        self.customization(repo, "confirm", AGENTS)
        self.assertEqual(set(os.listdir(repo / ".harness")) - before, {"customization-review.json"})

    def test_confirming_one_item_records_that_items_current_content_hash_only(self):
        repo = self.project()
        self.write(repo, ".harness/local/git/pre-push", "#!/bin/sh\n", 0o755)
        self.assertEqual(self.customization(repo, "confirm", ".harness/local/git/pre-push").returncode, 0)
        items = self.review(repo)["items"]
        self.assertEqual(list(items), [".harness/local/git/pre-push"])
        self.assertEqual(self.status_lines(repo)[0].split(" ")[0], "confirmed")


class TestProblemPartitions(CustomizationCase):
    def confirmed(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        return repo

    def config(self, repo, raw):
        self.write(repo, ".harness/config.json", raw)

    def test_config_absent_has_no_problem(self):
        repo = self.confirmed()
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])
        self.assertEqual(self.notice(repo).stdout, "")

    def test_config_with_every_known_key_has_no_problem(self):
        repo = self.confirmed()
        self.config(repo, json.dumps({"docs_root": "docs", "exclude_dirs": ["x"], "auto_install": True,
                                      "agent_model": "opus", "step_split_obligations": 12}))
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])
        self.assertEqual(self.notice(repo).stdout, "")

    def test_an_unknown_key_is_named_and_a_known_key_next_to_it_is_accepted(self):
        repo = self.confirmed()
        self.config(repo, json.dumps({"auto_instal": False, "agent_model": "opus"}))
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md", "unknown-config-key auto_instal"])
        self.assertEqual(self.notice_lines(repo), [
            INSTRUCTION_LINE,
            "harness customization: unknown-config-key auto_instal in .harness/config.json; the harness ignores it"])

    def test_every_config_that_is_not_a_json_object_is_config_invalid(self):
        for name, raw in {"truncated json": '{"auto_install": false,', "array": "[]", "string": '"x"'}.items():
            with self.subTest(config=name):
                repo = self.confirmed()
                self.config(repo, raw)
                lines = self.status_lines(repo)
                self.assertEqual(lines[0], "confirmed AGENTS.md")
                self.assertEqual(len(lines), 2, lines)
                self.assertTrue(lines[1].startswith("config-invalid .harness/config.json: "), lines)
                self.assertEqual(self.notice_lines(repo), [
                    INSTRUCTION_LINE,
                    "harness customization: config-invalid .harness/config.json; harness defaults are used until "
                    "it is fixed"])

    def test_no_local_directory_and_an_empty_one_yield_no_item(self):
        repo = self.confirmed()
        self.assertFalse((repo / ".harness" / "local").exists())
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])
        (repo / ".harness" / "local").mkdir()
        (repo / ".harness" / "local" / "empty").mkdir()
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])

    def test_one_unrecognized_file_and_one_in_a_nested_directory(self):
        repo = self.confirmed()
        self.write(repo, ".harness/local/notes.txt", "n\n")
        self.write(repo, ".harness/local/deep/er/more.txt", "n\n")
        self.assertEqual(self.status_lines(repo), [
            "unrecognized .harness/local/deep/er/more.txt", "unrecognized .harness/local/notes.txt",
            "confirmed AGENTS.md"])
        self.assertEqual(self.notice_lines(repo), [
            INSTRUCTION_LINE,
            "harness customization: unrecognized .harness/local/deep/er/more.txt; the harness does not read this file",
            "harness customization: unrecognized .harness/local/notes.txt; the harness does not read this file"])

    def test_pycache_files_are_skipped(self):
        repo = self.confirmed()
        self.write(repo, ".harness/local/__pycache__/x.cpython-312.pyc", b"\x00")
        self.write(repo, ".harness/local/hooks/__pycache__/lint.cpython-312.pyc", b"\x00")
        self.assertEqual(self.status_lines(repo), ["confirmed AGENTS.md"])

    def test_a_missing_or_invalid_declaration_is_reported_and_every_local_file_is_unrecognized(self):
        line = "customization declaration missing or invalid: .harness/customization.json"
        for name, prepare in {"missing": lambda p: p.unlink(), "invalid": lambda p: p.write_text("{")}.items():
            with self.subTest(declaration=name):
                repo = self.confirmed()
                self.write(repo, ".harness/local/git/pre-push", "#!/bin/sh\n", 0o755)
                prepare(repo / ".harness" / "customization.json")
                lines = self.status_lines(repo)
                self.assertIn(line, lines)
                self.assertIn("unrecognized .harness/local/git/pre-push", lines)
                result = self.notice(repo)
                self.assertEqual(result.returncode, 0)
                self.assertIn(PREFIX_ + line, result.stdout.splitlines())
                self.assertIn(PREFIX_ + "unrecognized .harness/local/git/pre-push; the harness does not read this file",
                              result.stdout.splitlines())

    def test_an_invalid_review_file_is_a_problem_and_every_item_counts_as_unconfirmed(self):
        repo = self.confirmed()
        self.write(repo, ".harness/customization-review.json", "[]")
        self.assertEqual(self.status_lines(repo), [
            self.item_line("unconfirmed", AGENTS, FIVE), "review-file-invalid .harness/customization-review.json"])
        lines = self.notice_lines(repo)
        self.assertEqual(lines[0], INSTRUCTION_LINE)
        self.assertEqual(lines[-1], "harness customization: review-file-invalid .harness/customization-review.json; "
                                    "every customization counts as unconfirmed")


PREFIX_ = "harness customization: "
INSTRUCTION_LINE = (
    PREFIX_ + "before other work, tell the user about each line below. Where a customization disagrees with "
    "harness text, the customization is followed: read both and name each disagreement. Run the confirm "
    "command for an item only after the user confirms it.")


class TestNewPoints(CustomizationCase):
    def test_every_recognized_name_of_every_point_is_a_recognized_item_with_its_compare_paths(self):
        repo = self.project()
        expected = {}
        for name in GIT_NAMES:
            self.write(repo, f".harness/local/git/{name}", "#!/bin/sh\n", 0o755)
            expected[f".harness/local/git/{name}"] = [f".harness/git/{name}"]
        for phase in PHASES:
            self.write(repo, f".harness/local/doggy-workflow/{phase}.md", f"{phase} rules\n")
            expected[f".harness/local/doggy-workflow/{phase}.md"] = self.phase_compare(repo, phase)
        for agent in AGENT_NAMES:
            self.write(repo, f".harness/local/agents/{agent}.md", f"{agent} notes\n")
            expected[f".harness/local/agents/{agent}.md"] = [f".claude/agents/{agent}.md"]
        for rel in ("lint.py", "sub/dir/check.sh"):
            self.write(repo, f".harness/local/hooks/{rel}", "x\n")
            expected[f".harness/local/hooks/{rel}"] = [".harness/hooks/hooks.spec.json"]
        items, rest = self.status(repo)
        self.assertEqual(rest, [])
        found = {path: (state, compare) for state, path, compare in items}
        for path, compare in expected.items():
            with self.subTest(path=path):
                state, got = found[path]
                self.assertEqual(state, "unconfirmed")
                if "doggy-workflow" in path:
                    self.assertEqual(got[0], compare[0])
                    self.assertEqual(sorted(got[1:]), sorted(compare[1:]))
                else:
                    self.assertEqual(got, compare)
        self.assertEqual(found[AGENTS][0], "unconfirmed")
        self.assertEqual([p for _, p, _ in items], sorted(p for _, p, _ in items))

    def test_unrecognized_names_under_each_point_directory(self):
        repo = self.project()
        paths = [".harness/local/doggy-workflow/nope.md", ".harness/local/agents/explore.md",
                 ".harness/local/git/pre-receive", ".harness/local/doggy-workflow/verify.txt",
                 ".harness/local/agents/implementer.txt"]
        for path in paths:
            self.write(repo, path, "x\n", 0o755)
        items, _ = self.status(repo)
        states = {path: state for state, path, _ in items}
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(states[path], "unrecognized")
        self.assertEqual(self.notice_lines(repo).count(
            PREFIX_ + "unrecognized .harness/local/git/pre-receive; the harness does not read this file"), 1)

    def test_a_phase_rules_item_follows_the_fragments_listed_for_its_own_phase_only(self):
        repo = self.project()
        own = self.phase_fragments(repo, "verify")
        others = {n for phase in PHASES if phase != "verify" for n in self.phase_fragments(repo, phase)} - set(own)
        self.assertTrue(own and others)
        path = ".harness/local/doggy-workflow/verify.md"
        self.write(repo, path, "verify rules\n")
        self.confirm(repo, path)
        for fragment in sorted(others):
            target = repo / SKILL_DIR / "phases" / f"{fragment}.md"
            target.write_bytes(target.read_bytes() + b"\nchanged\n")
        self.assertIn(f"confirmed {path}", self.status_lines(repo))
        for fragment in own:
            with self.subTest(fragment=fragment):
                target = repo / SKILL_DIR / "phases" / f"{fragment}.md"
                original = target.read_bytes()
                target.write_bytes(original + b"\nchanged\n")
                items, _ = self.status(repo)
                self.assertEqual({p: s for s, p, _ in items}[path], "harness-changed")
                target.write_bytes(original)
                self.assertIn(f"confirmed {path}", self.status_lines(repo))

    def test_a_change_of_phases_json_changes_every_phase_rules_item(self):
        repo = self.project()
        path = ".harness/local/doggy-workflow/brief.md"
        self.write(repo, path, "rules\n")
        self.confirm(repo, path)
        manifest = repo / SKILL_DIR / "phases.json"
        manifest.write_text(json.dumps(json.loads(manifest.read_text()), indent=4) + "\n\n")
        self.assertEqual({p: s for s, p, _ in self.status(repo)[0]}[path], "harness-changed")

    def test_an_agent_item_follows_its_own_agent_file_only(self):
        repo = self.project()
        path = ".harness/local/agents/implementer.md"
        self.write(repo, path, "notes\n")
        self.confirm(repo, path)
        other = repo / ".claude" / "agents" / "code-explorer.md"
        other.write_bytes(other.read_bytes() + b"\nchanged\n")
        self.assertIn(f"confirmed {path}", self.status_lines(repo))
        own = repo / ".claude" / "agents" / "implementer.md"
        own.write_bytes(own.read_bytes() + b"\nchanged\n")
        self.assertEqual({p: s for s, p, _ in self.status(repo)[0]}[path], "harness-changed")

    def test_a_hook_script_item_follows_hooks_spec_json(self):
        repo = self.project()
        path = ".harness/local/hooks/lint.py"
        self.write(repo, path, "print(1)\n")
        self.confirm(repo, path)
        other = repo / ".harness" / "hooks" / "spec_gate.py"
        other.write_bytes(other.read_bytes() + b"\n# x\n")
        self.assertIn(f"confirmed {path}", self.status_lines(repo))
        spec = repo / ".harness" / "hooks" / "hooks.spec.json"
        spec.write_bytes(spec.read_bytes() + b"\n")
        self.assertEqual({p: s for s, p, _ in self.status(repo)[0]}[path], "harness-changed")

    def test_a_git_hook_item_follows_the_dispatcher_of_the_same_name_only(self):
        repo = self.project()
        path = ".harness/local/git/pre-push"
        self.write(repo, path, "#!/bin/sh\n", 0o755)
        self.confirm(repo, path)
        other = repo / ".harness" / "git" / "post-merge"
        other.write_bytes(other.read_bytes() + b"\n# x\n")
        self.assertIn(f"confirmed {path}", self.status_lines(repo))
        own = repo / ".harness" / "git" / "pre-push"
        own.write_bytes(own.read_bytes() + b"\n# x\n")
        self.assertEqual({p: s for s, p, _ in self.status(repo)[0]}[path], "harness-changed")

    def test_a_git_hook_without_the_executable_bit_is_a_not_executable_problem(self):
        repo = self.project()
        self.write(repo, ".harness/local/git/pre-push", "#!/bin/sh\n", 0o644)
        self.write(repo, ".harness/local/git/post-merge", "#!/bin/sh\n", 0o755)
        lines = self.status_lines(repo)
        self.assertIn("not-executable .harness/local/git/pre-push", lines)
        self.assertNotIn("not-executable .harness/local/git/post-merge", lines)
        items, _ = self.status(repo)
        self.assertIn(("unconfirmed", ".harness/local/git/pre-push", [".harness/git/pre-push"]), items)

    def test_a_local_item_whose_content_changes_is_unconfirmed_again(self):
        repo = self.project()
        path = ".harness/local/agents/implementer.md"
        self.write(repo, path, "notes\n")
        self.confirm(repo, path)
        self.write(repo, path, "other notes\n")
        self.assertEqual({p: s for s, p, _ in self.status(repo)[0]}[path], "unconfirmed")
