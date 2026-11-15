import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from hook_case import HookCase
from test_installer import REPO_ROOT, run_git, run_installer
from test_lazy_rules import split_sections
from text_checks import text_test

INSTRUCTIONS = ".harness/instructions"
RULE_FILES = ("index-and-staleness.md", "try-n-fail.md", "todos.md", "synced-comments.md")
HOOK = "rule_injection.py"
HEX_RECORD = "0123456789abcdef-x.md"
SID = "sessinj"
TODOS_RULES = ["todos.md", "index-and-staleness.md"]
S10 = """## Rule Files

These rules live in separate files under `.harness/instructions/`. A hook adds a rule's text to the session at its first Write or Edit in the rule's directory; read the file yourself before other work it covers. Hook and pre-commit messages name the file of a rule they find violated.

| file | read before |
| --- | --- |
| `index-and-staleness.md` | adding, renaming, or marking stale a record in `agent-docs/` |
| `try-n-fail.md` | proposing a try-n-fail record |
| `todos.md` | writing a todo |
| `synced-comments.md` | keeping one comment identical in several places, or editing code tagged `synced id:` |
"""


def header(name, directory):
    return f"harness: rule text of {INSTRUCTIONS}/{name} for writing in {directory}/:"


class InjectionCase(HookCase):
    def ready(self, docs_root=None):
        repo = self.new_repo()
        if docs_root:
            config_path = repo / ".harness" / "config.json"
            config = json.loads(config_path.read_text()) if config_path.is_file() else {}
            config["docs_root"] = docs_root
            config_path.write_text(json.dumps(config))
        return repo

    def indexed_dir(self, repo, rel):
        directory = repo / rel
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "index.md").write_text("")
        return directory

    def rule_text(self, repo, name, directory):
        return header(name, directory) + "\n\n" + (repo / INSTRUCTIONS / name).read_text()

    def expected(self, repo, names, directory):
        return "\n\n".join(self.rule_text(repo, name, directory) for name in names)

    def payload(self, repo, rel, sid=SID, tool="Write", absolute=True):
        target = str(repo / rel) if absolute else rel
        payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"file_path": target},
                   "cwd": str(repo)}
        if sid is not None:
            payload["session_id"] = sid
        return payload

    def pre(self, repo, rel, sid=SID, tool="Write", absolute=True, env=None):
        return self.run_script(repo, HOOK, self.payload(repo, rel, sid, tool, absolute), env=env)

    def assert_injected(self, result, text):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(json.loads(result.stdout),
                         {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}})

    def assert_silent(self, result):
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def marker_dirs(self, repo):
        sessions = self.sessions_dir(repo)
        return sorted(sessions.glob("rules-*.d")) if sessions.is_dir() else []

    def assert_no_marker(self, repo):
        self.assertEqual([p for d in self.marker_dirs(repo) for p in d.iterdir()], [])


class TestDirectoryClasses(InjectionCase):
    def test_vo1_p1_try_n_fail_injects_try_n_fail_then_index_rule(self):
        repo = self.ready()
        result = self.pre(repo, f"agent-docs/try-n-fail/{HEX_RECORD}")
        self.assert_injected(result, self.expected(repo, ["try-n-fail.md", "index-and-staleness.md"],
                                                   "agent-docs/try-n-fail"))

    def test_vo1_p2_todos_injects_todos_then_index_rule(self):
        repo = self.ready()
        result = self.pre(repo, f"agent-docs/todos/{HEX_RECORD}")
        self.assert_injected(result, self.expected(repo, TODOS_RULES, "agent-docs/todos"))

    def test_vo1_p3_synced_comments_injects_only_its_rule(self):
        repo = self.ready()
        result = self.pre(repo, "agent-docs/synced-comments/aabbccddeeff.md")
        self.assert_injected(result, self.expected(repo, ["synced-comments.md"], "agent-docs/synced-comments"))

    def test_vo1_p4_specs_prints_nothing_even_with_an_index(self):
        repo = self.ready()
        self.indexed_dir(repo, "agent-docs/specs")
        self.assert_silent(self.pre(repo, f"agent-docs/specs/{HEX_RECORD}"))
        self.assert_no_marker(repo)

    def test_vo1_p5_spec_logs_prints_nothing_even_with_an_index(self):
        repo = self.ready()
        self.indexed_dir(repo, "agent-docs/spec-logs")
        self.assert_silent(self.pre(repo, f"agent-docs/spec-logs/{HEX_RECORD}"))
        self.assert_no_marker(repo)

    def test_vo1_p6_directory_without_index_prints_nothing(self):
        repo = self.ready()
        for directory in ("facts", "plain"):
            with self.subTest(directory=directory):
                self.assertFalse((repo / "agent-docs" / directory / "index.md").exists())
                self.assert_silent(self.pre(repo, f"agent-docs/{directory}/{HEX_RECORD}"))
        self.assert_no_marker(repo)

    def test_vo1_p7_other_directory_with_index_injects_index_rule(self):
        repo = self.ready()
        self.indexed_dir(repo, "agent-docs/notes")
        result = self.pre(repo, f"agent-docs/notes/{HEX_RECORD}")
        self.assert_injected(result, self.expected(repo, ["index-and-staleness.md"], "agent-docs/notes"))

    def test_vo1_p8_file_directly_in_docs_root_prints_nothing(self):
        repo = self.ready()
        self.assert_silent(self.pre(repo, "agent-docs/notes.md"))
        self.assert_no_marker(repo)

    def test_vo1_p9_paths_outside_docs_root_print_nothing(self):
        repo = self.ready()
        for rel in ("src/a.py", "README.md", "agent-docs-other/todos/x.md", f"docs/todos/{HEX_RECORD}"):
            with self.subTest(path=rel):
                self.assert_silent(self.pre(repo, rel))
        self.assert_no_marker(repo)

    def test_vo1_p10_custom_docs_root_maps_under_that_root_and_not_under_agent_docs(self):
        repo = self.ready(docs_root="docs/agent")
        self.indexed_dir(repo, "docs/agent/todos")
        self.indexed_dir(repo, "docs/agent/notes")
        self.indexed_dir(repo, "docs/agent/specs")
        with self.subTest(case="default layout is outside the configured root"):
            self.assert_silent(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}", sid="sessdefault"))
        with self.subTest(case="todos under the configured root"):
            result = self.pre(repo, f"docs/agent/todos/{HEX_RECORD}")
            self.assert_injected(result, self.expected(repo, TODOS_RULES, "docs/agent/todos"))
        with self.subTest(case="other indexed directory under the configured root"):
            result = self.pre(repo, f"docs/agent/notes/{HEX_RECORD}", sid="sessnotes")
            self.assert_injected(result, self.expected(repo, ["index-and-staleness.md"], "docs/agent/notes"))
        with self.subTest(case="specs under the configured root"):
            self.assert_silent(self.pre(repo, f"docs/agent/specs/{HEX_RECORD}", sid="sessspecs"))

    def test_vo1_p11_relative_path_gives_the_same_result_as_absolute(self):
        repo = self.ready()
        relative = self.pre(repo, f"agent-docs/todos/{HEX_RECORD}", sid="sessrel", absolute=False)
        absolute = self.pre(repo, f"agent-docs/todos/{HEX_RECORD}", sid="sessabs")
        expected = self.expected(repo, TODOS_RULES, "agent-docs/todos")
        self.assert_injected(relative, expected)
        self.assert_injected(absolute, expected)

    def test_vo1_p11_relative_path_from_a_subdirectory_cwd_resolves_against_the_repo_root(self):
        repo = self.ready()
        payload = self.payload(repo, f"agent-docs/todos/{HEX_RECORD}", absolute=False)
        payload["cwd"] = str(repo / "src")
        result = self.run_script(repo, HOOK, payload, cwd=repo / "src")
        self.assert_injected(result, self.expected(repo, TODOS_RULES, "agent-docs/todos"))

    def test_vo1_p12_named_directories_without_index_still_inject_their_rules(self):
        repo = self.ready()
        table = (
            ("todos", TODOS_RULES),
            ("try-n-fail", ["try-n-fail.md", "index-and-staleness.md"]),
            ("synced-comments", ["synced-comments.md"]),
        )
        for number, (directory, names) in enumerate(table):
            with self.subTest(directory=directory):
                index = repo / "agent-docs" / directory / "index.md"
                if index.exists():
                    index.unlink()
                self.assertFalse(index.exists())
                result = self.pre(repo, f"agent-docs/{directory}/{HEX_RECORD}", sid=f"sessnoindex{number}")
                self.assert_injected(result, self.expected(repo, names, f"agent-docs/{directory}"))

    def test_vo1_p13_nested_file_maps_as_its_first_level_directory(self):
        repo = self.ready()
        result = self.pre(repo, f"agent-docs/todos/stale/{HEX_RECORD}")
        self.assert_injected(result, self.expected(repo, TODOS_RULES, "agent-docs/todos"))

    def test_vo1_edit_and_multiedit_inject_like_write(self):
        repo = self.ready()
        for number, tool in enumerate(("Edit", "MultiEdit")):
            with self.subTest(tool=tool):
                result = self.pre(repo, "agent-docs/synced-comments/aabbccddeeff.md", sid=f"sesstool{number}", tool=tool)
                self.assert_injected(result, self.expected(repo, ["synced-comments.md"], "agent-docs/synced-comments"))

    def test_vo1_read_tool_does_not_inject(self):
        repo = self.ready()
        self.assert_silent(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}", tool="Read"))
        self.assert_no_marker(repo)


class TestSessionStates(InjectionCase):
    def test_vo2_t1_first_write_injects_and_records_the_session(self):
        repo = self.ready()
        self.assertEqual(self.marker_dirs(repo), [])
        result = self.pre(repo, f"agent-docs/todos/{HEX_RECORD}")
        self.assert_injected(result, self.expected(repo, TODOS_RULES, "agent-docs/todos"))
        dirs = self.marker_dirs(repo)
        self.assertEqual(len(dirs), 1, dirs)
        self.assertIn(SID, dirs[0].name)
        self.assertTrue(any(dirs[0].iterdir()))

    def test_vo2_t2_repeat_write_in_the_same_directory_prints_nothing(self):
        repo = self.ready()
        self.assertTrue(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}").stdout)
        self.assert_silent(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}"))
        self.assert_silent(self.pre(repo, "agent-docs/todos/index.md", tool="Edit"))

    def test_vo2_t3_partial_state_injects_only_the_rule_not_yet_injected(self):
        repo = self.ready()
        self.indexed_dir(repo, "agent-docs/notes")
        self.assertTrue(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}").stdout)
        result = self.pre(repo, f"agent-docs/try-n-fail/{HEX_RECORD}")
        self.assert_injected(result, self.rule_text(repo, "try-n-fail.md", "agent-docs/try-n-fail"))
        self.assert_silent(self.pre(repo, f"agent-docs/notes/{HEX_RECORD}"))

    def test_vo2_t4_another_session_gets_the_sections_again(self):
        repo = self.ready()
        expected = self.expected(repo, TODOS_RULES, "agent-docs/todos")
        self.assert_injected(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}"), expected)
        self.assert_injected(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}", sid="sessother"), expected)
        self.assert_silent(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}"))


class TestMalformedInputs(InjectionCase):
    def raw(self, repo, text):
        return self.run_script(repo, HOOK, raw=text)

    def test_vo3_e1_empty_stdin_prints_nothing(self):
        repo = self.ready()
        self.assert_silent(self.raw(repo, ""))
        self.assert_no_marker(repo)

    def test_vo3_e2_invalid_json_prints_nothing(self):
        repo = self.ready()
        self.assert_silent(self.raw(repo, '{"session_id": "sessinj", "tool_input": '))
        self.assert_no_marker(repo)

    def test_vo3_e3_json_array_prints_nothing(self):
        repo = self.ready()
        self.assert_silent(self.raw(repo, json.dumps([self.payload(repo, f"agent-docs/todos/{HEX_RECORD}")])))
        self.assert_no_marker(repo)

    def test_vo3_e4_missing_session_id_prints_nothing(self):
        repo = self.ready()
        self.assert_silent(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}", sid=None))
        self.assert_no_marker(repo)

    def test_vo3_e5_missing_tool_input_or_file_path_prints_nothing(self):
        repo = self.ready()
        base = self.payload(repo, f"agent-docs/todos/{HEX_RECORD}")
        without_input = {k: v for k, v in base.items() if k != "tool_input"}
        without_path = dict(base, tool_input={"content": "x"})
        for label, payload in (("no tool_input", without_input), ("no file_path", without_path)):
            with self.subTest(case=label):
                self.assert_silent(self.run_script(repo, HOOK, payload))
        self.assert_no_marker(repo)

    def test_vo3_e6_directory_outside_a_git_work_tree_prints_nothing(self):
        repo = self.ready()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        plain = Path(tmp.name) / "plain"
        shutil.copytree(repo, plain, symlinks=True)
        shutil.rmtree(plain / ".git")
        result = self.pre(plain, f"agent-docs/todos/{HEX_RECORD}")
        self.assert_silent(result)
        self.assert_no_marker(plain)

    def test_vo3_e6_git_missing_from_path_prints_nothing(self):
        repo = self.ready()
        env = self.env(PATH=self.empty_path_dir())
        self.assert_silent(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}", env=env))

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "permission bits do not bind root")
    def test_vo3_e7_unwritable_marker_directory_still_prints_the_text_on_every_call(self):
        repo = self.ready()
        sessions = self.sessions_dir(repo)
        sessions.mkdir(parents=True, exist_ok=True)
        for leftover in sessions.glob("rules-*.d"):
            shutil.rmtree(leftover)
        self.addCleanup(os.chmod, sessions, 0o755)
        os.chmod(sessions, stat.S_IRUSR | stat.S_IXUSR)
        expected = self.expected(repo, TODOS_RULES, "agent-docs/todos")
        for call in ("first", "second"):
            with self.subTest(call=call):
                self.assert_injected(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}"), expected)

    def test_vo3_e8_missing_rule_file_is_skipped_and_the_others_print(self):
        repo = self.ready()
        rule = repo / INSTRUCTIONS / "todos.md"
        original = rule.read_text()
        rule.unlink()
        first = self.pre(repo, f"agent-docs/todos/{HEX_RECORD}")
        self.assert_injected(first, self.rule_text(repo, "index-and-staleness.md", "agent-docs/todos"))
        rule.write_text(original)
        second = self.pre(repo, f"agent-docs/todos/{HEX_RECORD}")
        self.assert_injected(second, self.rule_text(repo, "todos.md", "agent-docs/todos"))

    def test_vo3_e9_unreadable_rule_file_is_skipped_and_injected_after_restore(self):
        def directory_in_place(rule):
            rule.unlink()
            rule.mkdir()

            def restore(original):
                rule.rmdir()
                rule.write_text(original)
            return restore

        def mode_000(rule):
            rule.chmod(0)

            def restore(original):
                rule.chmod(0o644)
            return restore

        variants = [("directory in place", directory_in_place)]
        if not (hasattr(os, "geteuid") and os.geteuid() == 0):
            variants.append(("mode 000", mode_000))
        for label, make_unreadable in variants:
            with self.subTest(variant=label):
                repo = self.ready()
                rule = repo / INSTRUCTIONS / "todos.md"
                original = rule.read_text()
                restore = make_unreadable(rule)
                self.addCleanup(lambda r=rule: r.chmod(0o644) if r.is_file() else None)
                first = self.pre(repo, f"agent-docs/todos/{HEX_RECORD}")
                self.assert_injected(first, self.rule_text(repo, "index-and-staleness.md", "agent-docs/todos"))
                restore(original)
                second = self.pre(repo, f"agent-docs/todos/{HEX_RECORD}")
                self.assert_injected(second, self.rule_text(repo, "todos.md", "agent-docs/todos"))

    def test_vo3_e8_every_mapped_rule_file_missing_prints_nothing(self):
        repo = self.ready()
        (repo / INSTRUCTIONS / "todos.md").unlink()
        (repo / INSTRUCTIONS / "index-and-staleness.md").unlink()
        self.assert_silent(self.pre(repo, f"agent-docs/todos/{HEX_RECORD}"))


class TestRuleText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.repo = Path(cls.tmp.name)
        run_git(cls.repo, "init", "-q")
        result = run_installer("install", str(cls.repo), "--no-ci")
        if result.returncode != 0:
            raise RuntimeError(result.stdout + result.stderr)

    def payload(self, *parts):
        return (REPO_ROOT / "harness" / Path(*parts)).read_text()

    @text_test
    def test_rule_files_section_of_the_block_equals_the_expected_text_in_source_and_install(self):
        for label, text in (("payload", self.payload("instructions", "harness-block.md")),
                            ("installed", (self.repo / INSTRUCTIONS / "harness-block.md").read_text())):
            with self.subTest(copy=label):
                sections = split_sections(text)
                self.assertEqual([h for h, _ in sections].count("## Rule Files"), 1)
                self.assertEqual(dict(sections)["## Rule Files"].rstrip("\n"), S10.rstrip("\n"))

    @text_test
    def test_synced_comments_rule_names_end_markers_block_hash_and_refresh_command(self):
        text = self.payload("instructions", "synced-comments.md")
        for needle in ("synced end:", "synced-refresh"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    @text_test
    def test_index_rule_names_the_stale_command(self):
        self.assertIn("records.py stale", self.payload("instructions", "index-and-staleness.md"))

    @text_test
    def test_readme_mentions_the_records_command(self):
        self.assertIn("records.py", (REPO_ROOT / "README.md").read_text())

    def test_installed_copies_equal_the_payload_files(self):
        pairs = [(Path(INSTRUCTIONS) / name, Path("harness") / "instructions" / name) for name in (*RULE_FILES, "harness-block.md")]
        pairs.append((Path(".harness") / "bin" / "records.py", Path("harness") / "bin" / "records.py"))
        pairs.append((Path(".harness") / "hooks" / HOOK, Path("harness") / "hooks" / HOOK))
        for installed, source in pairs:
            with self.subTest(file=installed.name):
                self.assertEqual((self.repo / installed).read_bytes(), (REPO_ROOT / source).read_bytes())


if __name__ == "__main__":
    unittest.main()
