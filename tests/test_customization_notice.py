import json
import os
import re
import shutil
import subprocess
import sys

from customization_case import AGENT_NAMES, AGENTS, FIVE, INSTRUCTION, PREFIX, CustomizationCase, split_paths
from test_installer import run_git

ITEM_LINE = re.compile(re.escape(PREFIX) + r"(unconfirmed|harness-changed) (\S+); compare with (.+); confirm: "
                       r"python3 \.harness/bin/customization\.py confirm (\S+)")


class NoticeCase(CustomizationCase):
    def assert_item_lines(self, lines, expected):
        self.assertEqual(len(lines), len(expected), lines)
        for line, (state, path, compare) in zip(lines, expected):
            found = ITEM_LINE.fullmatch(line)
            self.assertIsNotNone(found, line)
            self.assertEqual((found[1], found[2], found[4]), (state, path, path))
            self.assertEqual(split_paths(found[3]), compare)


class TestNoticeTable(NoticeCase):
    def test_all_confirmed_and_no_problem_prints_nothing(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        result = self.notice(repo)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_one_unconfirmed_item(self):
        repo = self.project()
        result = self.notice(repo)
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], INSTRUCTION)
        self.assert_item_lines(lines[1:], [("unconfirmed", AGENTS, FIVE)])
        self.assertTrue(result.stdout.endswith("\n"))

    def test_one_harness_changed_item(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        path = repo / FIVE[1]
        path.write_bytes(path.read_bytes() + b"\nnew sentence\n")
        lines = self.notice_lines(repo)
        self.assertEqual(lines[0], INSTRUCTION)
        self.assert_item_lines(lines[1:], [("harness-changed", AGENTS, FIVE)])

    def test_one_unrecognized_item(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        self.write(repo, ".harness/local/notes.txt", "n\n")
        self.assertEqual(self.notice_lines(repo), [
            INSTRUCTION, PREFIX + "unrecognized .harness/local/notes.txt; the harness does not read this file"])

    def test_one_problem_only(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        self.write(repo, ".harness/config.json", "[]")
        self.assertEqual(self.notice_lines(repo), [
            INSTRUCTION,
            PREFIX + "config-invalid .harness/config.json; harness defaults are used until it is fixed"])

    def test_mixed_output_orders_the_instruction_then_items_by_path_then_problems(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        self.write(repo, ".harness/local/notes.txt", "n\n")
        self.write(repo, ".harness/local/git/pre-push", "#!/bin/sh\n", 0o755)
        path = repo / FIVE[0]
        path.write_bytes(path.read_bytes() + b"\nnew sentence\n")
        self.write(repo, ".harness/config.json", '{"auto_instal": 1}')
        lines = self.notice_lines(repo)
        self.assertEqual(lines[0], INSTRUCTION)
        self.assert_item_lines(lines[1:2], [("unconfirmed", ".harness/local/git/pre-push", [".harness/git/pre-push"])])
        self.assertEqual(lines[2], PREFIX + "unrecognized .harness/local/notes.txt; the harness does not read this file")
        self.assert_item_lines(lines[3:4], [("harness-changed", AGENTS, FIVE)])
        self.assertEqual(lines[4:], [PREFIX + "unknown-config-key auto_instal in .harness/config.json; "
                                              "the harness ignores it"])

    def test_the_not_executable_and_missing_problems_have_their_fixed_texts(self):
        repo = self.project()
        self.confirm(repo, AGENTS)
        self.write(repo, ".harness/local/git/pre-push", "#!/bin/sh\n", 0o644)
        settings = repo / ".claude" / "settings.json"
        data = json.loads(settings.read_text())
        data["hooks"].setdefault("PostToolUse", []).append({"matcher": "Write", "hooks": [
            {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.harness/local/hooks/gone.py"'}]})
        settings.write_text(json.dumps(data, indent=2) + "\n")
        lines = self.notice_lines(repo)
        self.assertIn(PREFIX + "not-executable .harness/local/git/pre-push; the git hook does not run until you run "
                      "chmod +x .harness/local/git/pre-push", lines)
        self.assertIn(PREFIX + "missing .harness/local/hooks/gone.py (referenced by .claude/settings.json); restore "
                      "the file or remove the hook from .claude/settings.json", lines)

    def test_every_line_carries_the_prefix(self):
        repo = self.project()
        self.write(repo, ".harness/config.json", "{")
        for line in self.notice_lines(repo):
            self.assertTrue(line.startswith(PREFIX), line)

    def test_the_notice_ignores_stdin(self):
        repo = self.project()
        plain = self.notice(repo, stdin="").stdout
        for text in ("{", json.dumps({"hook_event_name": "SessionStart"}), "garbage\n" * 100):
            self.assertEqual(self.notice(repo, stdin=text).stdout, plain)


class TestNoticeRobustness(NoticeCase):
    def assert_survives(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stdout)

    def test_a_declaration_that_is_unreadable(self):
        line = PREFIX + "customization declaration missing or invalid: .harness/customization.json"
        for name, prepare in {
            "a directory": lambda p: (p.unlink(), p.mkdir()),
            "not utf-8": lambda p: p.write_bytes(b"\xff\xfe\x00{"),
            "empty": lambda p: p.write_bytes(b""),
        }.items():
            with self.subTest(declaration=name):
                repo = self.project()
                prepare(repo / ".harness" / "customization.json")
                result = self.notice(repo)
                self.assert_survives(result)
                self.assertIn(line, result.stdout.splitlines())

    def test_a_local_path_that_is_a_file(self):
        repo = self.project()
        self.write(repo, ".harness/local", "i am a file\n")
        self.assert_survives(self.notice(repo))
        self.assert_survives(self.customization(repo, "status"))

    def test_a_review_file_that_is_a_directory(self):
        repo = self.project()
        (repo / ".harness" / "customization-review.json").mkdir()
        self.assert_survives(self.notice(repo))

    def test_the_library_raising_prints_nothing_and_exits_0(self):
        stand_in = self.temp_dir()
        self.write(stand_in, "json.py", (
            "import importlib.util, os, sys, sysconfig\n"
            "_dir = os.path.join(sysconfig.get_paths()['stdlib'], 'json')\n"
            "_spec = importlib.util.spec_from_file_location('json', os.path.join(_dir, '__init__.py'),\n"
            "                                               submodule_search_locations=[_dir])\n"
            "_mod = importlib.util.module_from_spec(_spec)\n"
            "sys.modules['json'] = _mod\n"
            "_spec.loader.exec_module(_mod)\n"
            "def _boom(*a, **k):\n"
            "    raise RuntimeError('stand-in failure')\n"
            "_mod.loads = _boom\n"
            "_mod.load = _boom\n"))
        repo = self.project()
        env = self.env(PYTHONPATH=str(stand_in))
        result = self.notice(repo, env=env)
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)

    def test_stdin_closed(self):
        repo = self.project()
        script = str(repo / ".harness" / "hooks" / "customization_notice.py")
        expected = self.notice(repo).stdout
        for name, kwargs in {"devnull": {"stdin": subprocess.DEVNULL}}.items():
            with self.subTest(stdin=name):
                result = subprocess.run([sys.executable, script], capture_output=True, text=True, cwd=repo,
                                        env=self.env(), **kwargs)
                self.assert_survives(result)
                self.assertEqual(result.stdout, expected)
        proc = subprocess.Popen([sys.executable, script], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, cwd=repo, env=self.env())
        proc.stdin.close()
        stdout = proc.stdout.read()
        proc.stdout.close()
        proc.stderr.close()
        self.assertEqual(proc.wait(), 0)
        self.assertEqual(stdout, expected)

    def test_the_notice_works_outside_a_git_work_tree_of_its_own(self):
        repo = self.project()
        shutil.rmtree(repo / ".git")
        result = self.notice(repo)
        self.assert_survives(result)


SID = "sess-1"


class ContextCase(CustomizationCase):
    def payload(self, repo, rel, sid=SID, tool="Write", absolute=True, event="PostToolUse"):
        target = str(repo / rel) if absolute else rel
        payload = {"hook_event_name": event, "tool_name": tool, "tool_input": {"file_path": target}, "cwd": str(repo)}
        if sid is not None:
            payload["session_id"] = sid
        return payload

    def post(self, repo, rel, **kwargs):
        env = kwargs.pop("env", None)
        return self.run_script(repo, "customization_context.py", self.payload(repo, rel, **kwargs), env=env)

    def assert_silent(self, result):
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def context_of(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(set(data), {"hookSpecificOutput"})
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        return data["hookSpecificOutput"]["additionalContext"]

    def recognized_pattern(self, path, point, compare):
        return re.compile(
            re.escape(f"harness customization: {path} is a customization ({point}). It is followed where it "
                      "disagrees with ") + r"(.+)" + re.escape(
                f". Read those files, tell the user each disagreement before you finish, and run python3 "
                f".harness/bin/customization.py confirm {path} only after the user confirms."))

    def assert_recognized(self, text, path, point, compare):
        found = self.recognized_pattern(path, point, compare).fullmatch(text)
        self.assertIsNotNone(found, text)
        self.assertEqual(split_paths(found[1]), compare)


class TestContextHookTable(ContextCase):
    def test_agents_md_first_call_emits_the_recognized_text(self):
        repo = self.project()
        text = self.context_of(self.post(repo, AGENTS))
        self.assert_recognized(text, AGENTS, "project-instructions", FIVE)

    def test_the_same_session_second_call_is_silent_and_a_new_session_emits_again(self):
        repo = self.project()
        self.context_of(self.post(repo, AGENTS))
        self.assert_silent(self.post(repo, AGENTS))
        self.assert_silent(self.post(repo, AGENTS))
        self.assert_recognized(self.context_of(self.post(repo, AGENTS, sid="sess-2")), AGENTS,
                               "project-instructions", FIVE)

    def test_two_items_in_one_session_each_speak_once(self):
        repo = self.project()
        self.context_of(self.post(repo, AGENTS))
        self.write(repo, ".harness/local/notes.txt", "n\n")
        self.assertIn("notes.txt", self.context_of(self.post(repo, ".harness/local/notes.txt")))
        self.assert_silent(self.post(repo, ".harness/local/notes.txt"))
        self.assert_silent(self.post(repo, AGENTS))

    def test_an_unrecognized_local_path_says_the_harness_does_not_read_it_and_lists_the_recognized_paths(self):
        repo = self.project()
        self.write(repo, ".harness/local/notes.txt", "n\n")
        text = self.context_of(self.post(repo, ".harness/local/notes.txt"))
        head = "harness customization: the harness does not read .harness/local/notes.txt. Recognized customization paths: "
        self.assertTrue(text.startswith(head), text)
        self.assertTrue(text.endswith("."), text)
        listed = text[len(head):]
        position = 0
        for point in self.declaration(repo)["points"]:
            found = listed.find(point["path"], position)
            self.assertNotEqual(found, -1, (point["path"], listed))
            position = found + len(point["path"])

    def test_a_retired_path_gets_the_unrecognized_text(self):
        repo = self.project()
        path = ".harness/local/doggy-workflow/old.md"
        decl = repo / ".harness" / "customization.json"
        data = json.loads(decl.read_text())
        data.setdefault("retired", []).append({"path": path, "version": "0.56.0", "note": "Renamed."})
        decl.write_text(json.dumps(data, indent=2) + "\n")
        self.write(repo, path, "old\n")
        text = self.context_of(self.post(repo, path))
        head = f"harness customization: the harness does not read {path}. Recognized customization paths: "
        self.assertTrue(text.startswith(head), text)
        listed = text[len(head):]
        for point in data["points"]:
            self.assertIn(point["path"], listed)

    def test_a_path_of_each_other_point_names_its_point_and_compare_paths(self):
        repo = self.project()
        cases = {
            ".harness/local/git/pre-push": ("git-hook", [".harness/git/pre-push"]),
            ".harness/local/agents/implementer.md": ("agent-instructions", [".claude/agents/implementer.md"]),
            ".harness/local/hooks/lint.py": ("hook-script", [".harness/hooks/hooks.spec.json"]),
        }
        for path, (point, compare) in cases.items():
            with self.subTest(path=path):
                self.write(repo, path, "x\n", 0o755)
                self.assert_recognized(self.context_of(self.post(repo, path)), path, point, compare)
        phase_path = ".harness/local/doggy-workflow/verify.md"
        self.write(repo, phase_path, "x\n")
        text = self.context_of(self.post(repo, phase_path))
        found = self.recognized_pattern(phase_path, "phase-rules", []).fullmatch(text)
        self.assertIsNotNone(found, text)
        listed = split_paths(found[1])
        self.assertEqual(listed[0], ".harness/skills/doggy-workflow/phases.json")
        self.assertEqual(sorted(listed[1:]), sorted(self.phase_compare(repo, "verify")[1:]))

    def test_relative_and_absolute_file_paths_both_resolve_to_the_root_agents_md(self):
        for name, rel, absolute in (("absolute", AGENTS, True), ("relative", AGENTS, False),
                                    ("dot relative", "./AGENTS.md", False)):
            with self.subTest(form=name):
                repo = self.project()
                text = self.context_of(self.post(repo, rel, absolute=absolute))
                self.assert_recognized(text, AGENTS, "project-instructions", FIVE)

    def test_a_relative_local_path_resolves_too(self):
        repo = self.project()
        self.write(repo, ".harness/local/notes.txt", "n\n")
        self.assertIn("notes.txt", self.context_of(self.post(repo, ".harness/local/notes.txt", absolute=False)))

    def test_agents_md_in_a_subdirectory_is_ignored(self):
        repo = self.project()
        self.write(repo, "docs/AGENTS.md", "x\n")
        self.assert_silent(self.post(repo, "docs/AGENTS.md"))
        self.assert_silent(self.post(repo, "docs/AGENTS.md", absolute=False))

    def test_a_path_outside_the_repository_is_ignored(self):
        repo = self.project()
        outside = self.temp_dir()
        self.write(outside, "AGENTS.md", "x\n")
        self.write(outside, ".harness/local/notes.txt", "x\n")
        for target in (str(outside / "AGENTS.md"), str(outside / ".harness" / "local" / "notes.txt"),
                       "../elsewhere/AGENTS.md"):
            with self.subTest(target=target):
                payload = self.payload(repo, target, absolute=False)
                self.assert_silent(self.run_script(repo, "customization_context.py", payload))

    def test_no_session_id_means_no_output_and_no_marker(self):
        repo = self.project()
        self.assert_silent(self.post(repo, AGENTS, sid=None))
        self.assert_silent(self.post(repo, AGENTS, sid=None))
        self.assertEqual(sorted(self.sessions_dir(repo).glob("rules-*")) if self.sessions_dir(repo).exists() else [], [])

    def test_outside_a_git_work_tree_prints_nothing(self):
        repo = self.project()
        shutil.rmtree(repo / ".git")
        self.assert_silent(self.post(repo, AGENTS))
        elsewhere = self.temp_dir()
        self.assert_silent(self.run_script(repo, "customization_context.py", self.payload(repo, AGENTS),
                                           cwd=elsewhere))

    def test_other_tools_are_handled_by_the_tool_name(self):
        repo = self.project()
        self.assert_silent(self.post(repo, AGENTS, tool="Read", sid="read-session"))
        for tool in ("Edit", "MultiEdit", "Write"):
            with self.subTest(tool=tool):
                self.assert_recognized(self.context_of(self.post(repo, AGENTS, tool=tool, sid=f"s-{tool}")), AGENTS,
                                       "project-instructions", FIVE)

    def test_malformed_stdin_prints_nothing_and_exits_0(self):
        repo = self.project()
        for name, raw in {"truncated": '{"tool_input": ', "array": "[1]", "string": '"x"', "number": "7",
                          "empty": "", "null": "null",
                          "tool_input not an object": json.dumps({"session_id": SID, "tool_input": "x"}),
                          "file_path not a string": json.dumps({"session_id": SID, "tool_input": {"file_path": 7}}),
                          }.items():
            with self.subTest(stdin=name):
                self.assert_silent(self.run_script(repo, "customization_context.py", raw=raw))

    def test_the_session_marker_is_ignored_by_git(self):
        repo = self.project()
        self.context_of(self.post(repo, AGENTS))
        self.write(repo, ".harness/local/notes.txt", "n\n")
        self.context_of(self.post(repo, ".harness/local/notes.txt"))
        markers = [p for p in self.sessions_dir(repo).rglob("*") if p.is_file()]
        self.assertTrue(markers)
        for marker in markers:
            with self.subTest(marker=str(marker.relative_to(repo))):
                checked = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", str(marker.relative_to(repo))])
                self.assertEqual(checked.returncode, 0)
        self.assertNotIn(".harness/sessions", run_git(repo, "status", "--porcelain", "-uall").stdout)


class TestSubagentAdditions(ContextCase):
    TEXT = "Always run the linter first."

    def start(self, repo, agent, agent_id="a1", **kwargs):
        payload = {"hook_event_name": "SubagentStart", "agent_type": agent, "agent_id": agent_id}
        return self.run_script(repo, "customization_context.py", payload, **kwargs)

    def expected(self, agent, text=TEXT):
        return {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": (
            "## Project instructions for this agent\n"
            f"From .harness/local/agents/{agent}.md. Where these disagree with your instructions above, follow these."
            f"\n\n{text}")}}

    def test_every_harness_agent_with_a_file_gets_exactly_its_text(self):
        repo = self.project()
        for agent in AGENT_NAMES:
            self.write(repo, f".harness/local/agents/{agent}.md", self.TEXT)
        for agent in AGENT_NAMES:
            with self.subTest(agent=agent):
                result = self.start(repo, agent)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), self.expected(agent))

    def test_a_harness_agent_without_a_file_gets_nothing(self):
        repo = self.project()
        self.write(repo, ".harness/local/agents/implementer.md", self.TEXT)
        for agent in AGENT_NAMES:
            if agent != "implementer":
                with self.subTest(agent=agent):
                    self.assert_silent(self.start(repo, agent))

    def test_a_non_harness_agent_gets_nothing_even_with_a_same_named_file(self):
        repo = self.project()
        for name in ("explore", "Explore", "general-purpose", "my-agent"):
            self.write(repo, f".harness/local/agents/{name}.md", self.TEXT)
        for agent in ("Explore", "explore", "general-purpose", "my-agent", ""):
            with self.subTest(agent=agent):
                self.assert_silent(self.start(repo, agent))

    def test_an_unreadable_file_gives_no_additional_context(self):
        repo = self.project()
        self.write(repo, ".harness/local/agents/implementer.md", b"\xff\xfe not utf-8 \x80")
        self.assert_silent(self.start(repo, "implementer"))
        if os.geteuid() != 0:
            path = self.write(repo, ".harness/local/agents/code-explorer.md", self.TEXT, 0o000)
            self.addCleanup(path.chmod, 0o644)
            self.assert_silent(self.start(repo, "code-explorer"))

    def test_a_directory_in_place_of_the_file_gives_nothing(self):
        repo = self.project()
        (repo / ".harness" / "local" / "agents" / "implementer.md").mkdir(parents=True)
        self.assert_silent(self.start(repo, "implementer"))

    def test_malformed_stdin_and_missing_fields_print_nothing(self):
        repo = self.project()
        self.write(repo, ".harness/local/agents/implementer.md", self.TEXT)
        for name, raw in {"truncated": "{", "array": "[]", "empty": "",
                          "no agent_type": json.dumps({"hook_event_name": "SubagentStart"}),
                          "agent_type not a string": json.dumps({"hook_event_name": "SubagentStart",
                                                                 "agent_type": ["implementer"]})}.items():
            with self.subTest(stdin=name):
                self.assert_silent(self.run_script(repo, "customization_context.py", raw=raw))

    def test_the_same_agent_started_twice_gets_the_text_each_time(self):
        repo = self.project()
        self.write(repo, ".harness/local/agents/implementer.md", self.TEXT)
        result = self.start(repo, "implementer", agent_id="a9")
        self.assertEqual(json.loads(result.stdout), self.expected("implementer"))
        again = self.start(repo, "implementer", agent_id="a9")
        self.assertEqual(json.loads(again.stdout), self.expected("implementer"))

    def write_spec(self, repo):
        path = repo / "agent-docs" / "specs" / "0123456789abcdef-x.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\nversion: 1\n---\n# Paths\nTest command: python3 -m unittest\n")

    def gate(self, repo, payload):
        return self.run_script(repo, "spec_gate.py", payload)

    def test_spec_gate_still_writes_its_running_marker_for_implementer_with_a_local_file(self):
        repo = self.project()
        self.write(repo, ".harness/local/agents/implementer.md", self.TEXT)
        self.write_spec(repo)
        started = {"hook_event_name": "SubagentStart", "agent_type": "implementer", "agent_id": "a1"}
        context = self.run_script(repo, "customization_context.py", started)
        self.assertEqual(json.loads(context.stdout), self.expected("implementer"))
        self.assertEqual(self.gate(repo, started).returncode, 0)
        blocked = self.gate(repo, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                   "tool_input": {"command": "python3 -m unittest"}})
        self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
        again = self.run_script(repo, "customization_context.py", started)
        self.assertEqual(json.loads(again.stdout), self.expected("implementer"))


class TestHookRegistration(CustomizationCase):
    def groups(self, event):
        repo = self.project()
        data = json.loads((repo / ".claude" / "settings.json").read_text())
        return data["hooks"].get(event, [])

    def running(self, groups, script):
        return [g for g in groups if any(f".harness/hooks/{script}" in h.get("command", "") for h in g["hooks"])]

    def test_post_tool_use_runs_the_context_hook_for_write_edit_and_multiedit(self):
        found = self.running(self.groups("PostToolUse"), "customization_context.py")
        self.assertEqual([g.get("matcher") for g in found], ["Write|Edit|MultiEdit"])

    def test_subagent_start_runs_the_context_hook(self):
        self.assertTrue(self.running(self.groups("SubagentStart"), "customization_context.py"))

    def test_session_start_runs_the_notice_hook(self):
        self.assertTrue(self.running(self.groups("SessionStart"), "customization_notice.py"))
