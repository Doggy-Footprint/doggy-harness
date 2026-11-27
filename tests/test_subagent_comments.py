import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import telemetry_sandbox  # noqa: F401
from hook_case import HookCase
from test_installer import run_git
from tests.fake_uv import tool_dir

SCRIPT = "subagent_comments.py"
HEADER = "harness: comment check before you hand back."
CATEGORIES = (
    "Keep a comment only when it records a non-obvious design constraint, external-system behavior, "
    "safety/security invariant, or reason a seemingly odd implementation is necessary. "
    "Delete every other comment above. List each comment you keep under Comments in your report, "
    "with its category, then hand back."
)
COULD_NOT_RUN_HEAD = "harness: the comment check could not run: "
COULD_NOT_RUN_TAIL = ". Write this under Comments in your report, then hand back."
IMPLEMENTER = "implementer"
TEST_IMPLEMENTER = "test-implementer"


class SubagentCase(HookCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.telemetry = Path(tmp.name)
        self.repo = self.new_repo()
        self.write_spec(self.repo)

    def write_spec(self, repo, name="fixture", status="active", impl="src/", tests="tests/"):
        path = repo / "agent-docs" / "specs" / f"aaaaaaaaaaaaaaaa-{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\nversion: 1\nrun_id: aaaaaaaaaaaaaaaa\nstatus: {status}\n---\n\n# Paths\n"
            f"Implementation: {impl}\nTests: {tests}\n"
        )
        return path

    def put(self, rel, text, repo=None):
        path = (repo or self.repo) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def hook_env(self, **extra):
        return self.env(HARNESS_TELEMETRY_DIR=str(self.telemetry), **extra)

    def no_uv_env(self):
        return self.hook_env(PATH=str(tool_dir(self, with_uv=False)))

    def payload(self, event, agent_id, agent_type, repo=None, **extra):
        data = {
            "hook_event_name": event,
            "agent_id": agent_id,
            "agent_type": agent_type,
            "session_id": "session-1",
            "cwd": str(repo or self.repo),
        }
        if event == "PreToolUse":
            data.update(tool_name="SubagentHandback", tool_input={})
        data.update(extra)
        return data

    def fire(self, event, agent_id, agent_type=IMPLEMENTER, repo=None, env=None, **extra):
        repo = repo or self.repo
        result = self.run_script(
            repo, SCRIPT, self.payload(event, agent_id, agent_type, repo, **extra),
            env=env or self.hook_env(), cwd=repo,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def start(self, agent_id, agent_type=IMPLEMENTER, **kw):
        return self.fire("SubagentStart", agent_id, agent_type, **kw)

    def handback(self, agent_id, agent_type=IMPLEMENTER, **kw):
        return self.fire("PreToolUse", agent_id, agent_type, **kw)

    def stop(self, agent_id, agent_type=IMPLEMENTER, **kw):
        return self.fire("SubagentStop", agent_id, agent_type, **kw)

    def assert_silent(self, result):
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def deny_reason(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "deny")
        return output["permissionDecisionReason"]

    def block_reason(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(set(output), {"decision", "reason"})
        self.assertEqual(output["decision"], "block")
        return output["reason"]

    def record_dir(self, repo=None):
        return (repo or self.repo) / ".harness" / "sessions" / "subagent-comments"

    def record_files(self, repo=None):
        directory = self.record_dir(repo)
        return sorted(directory.glob("*")) if directory.is_dir() else []

    def traces_of(self, agent_id, repo=None):
        sessions = self.sessions_dir(repo or self.repo)
        if not sessions.is_dir():
            return []
        found = []
        for path in sessions.rglob("*"):
            if path.is_file() and (agent_id in path.name or agent_id in path.read_text(errors="replace")):
                found.append(path)
        return found

    def events(self, agent_id):
        found = []
        for path in sorted(self.telemetry.glob("*.jsonl")):
            for line in path.read_text().splitlines():
                if line.strip():
                    event = json.loads(line)
                    if event.get("event") == "subagent_comments" and event.get("agent_id") == agent_id:
                        found.append(event)
        return found

    def fields(self, event):
        return {k: event[k] for k in ("stage", "trigger", "new_comments", "scan_ok", "blocked")}

    def entries(self, reason):
        return [l for l in reason.splitlines() if re.fullmatch(r"\S+:\d+: .*", l)]


class StateTransitionTests(SubagentCase):
    def test_o8_t1_start_records_baseline_silently(self):
        r = self.start("agent-t1")
        self.assert_silent(r)
        self.assertTrue((self.record_dir() / "agent-t1.json").is_file())

    def test_o8_t2_handback_without_new_comments_allows(self):
        self.start("agent-t2")
        r = self.handback("agent-t2")
        self.assert_silent(r)

    def test_o8_t3_handback_with_new_comment_denies_once_then_t4_allows(self):
        self.start("agent-t3")
        self.put("src/x.py", "x = 1\n# returns a+b\n")
        reason = self.deny_reason(self.handback("agent-t3"))
        self.assertIn("src/x.py:2: # returns a+b", reason)
        self.assert_silent(self.handback("agent-t3"))
        self.assert_silent(self.handback("agent-t3"))

    def test_o8_t5_stop_after_denied_handback_allows_and_cleans_up(self):
        self.start("agent-t5")
        self.put("src/x.py", "x = 1\n# returns a+b\n")
        self.deny_reason(self.handback("agent-t5"))
        self.assert_silent(self.stop("agent-t5", stop_hook_active=False))
        self.assertFalse((self.record_dir() / "agent-t5.json").exists())
        self.assertEqual(self.traces_of("agent-t5"), [])

    def test_o8_t6_stop_with_new_comment_blocks_once_then_allows(self):
        self.start("agent-t6")
        self.put("src/x.py", "x = 1\n# returns a+b\n")
        reason = self.block_reason(self.stop("agent-t6"))
        self.assertIn("src/x.py:2: # returns a+b", reason)
        self.assert_silent(self.stop("agent-t6", stop_hook_active=True))

    def test_o8_t7_scan_failure_at_finish_denies_once(self):
        self.start("agent-t7")
        self.put("src/x.ts", "const a = 1;\n// c\n")
        env = self.no_uv_env()
        reason = self.deny_reason(self.handback("agent-t7", env=env))
        self.assertTrue(reason.startswith(COULD_NOT_RUN_HEAD), reason)
        self.assert_silent(self.handback("agent-t7", env=env))

    def test_o8_t7_git_failure_at_finish_denies_once(self):
        self.start("agent-t7g")
        self.put("src/x.py", "# c\n")
        shutil.move(str(self.repo / ".git"), str(self.repo / ".git-away"))
        self.addCleanup(lambda: shutil.move(str(self.repo / ".git-away"), str(self.repo / ".git")))
        reason = self.deny_reason(self.handback("agent-t7g"))
        self.assertTrue(reason.startswith(COULD_NOT_RUN_HEAD), reason)
        self.assert_silent(self.handback("agent-t7g"))

    def test_o8_t2_t8_clean_handback_then_stop_is_silent_and_cleans_up(self):
        self.start("agent-f1")
        self.assert_silent(self.handback("agent-f1"))
        self.assert_silent(self.stop("agent-f1"))
        self.assertFalse((self.record_dir() / "agent-f1.json").exists())
        self.assertEqual(self.traces_of("agent-f1"), [])

    def test_o8_t2_t8_clean_handback_keeps_baseline_for_the_later_stop(self):
        self.put("src/m.py", "# old\n")
        self.start("agent-f1b")
        self.assert_silent(self.handback("agent-f1b"))
        self.assert_silent(self.stop("agent-f1b"))

    def test_o8_t2_t6_clean_handback_does_not_count_as_stopped(self):
        self.start("agent-f1c")
        self.assert_silent(self.handback("agent-f1c"))
        self.put("src/x.py", "x = 1\n# late\n")
        reason = self.block_reason(self.stop("agent-f1c"))
        self.assertEqual(self.entries(reason), ["src/x.py:2: # late"])

    def test_o8_t7_scan_failure_at_stop_blocks_once(self):
        self.start("agent-f5")
        self.put("src/x.ts", "const a = 1;\n// c\n")
        env = self.no_uv_env()
        reason = self.block_reason(self.stop("agent-f5", env=env))
        self.assertTrue(reason.startswith(COULD_NOT_RUN_HEAD), reason)
        self.assertTrue(reason.endswith(COULD_NOT_RUN_TAIL), reason)
        self.assertIn("uv not found on PATH", reason)
        self.assert_silent(self.stop("agent-f5", env=env, stop_hook_active=True))

    def test_o8_t8_stop_without_new_comments_allows_and_cleans_up(self):
        self.start("agent-t8")
        self.assert_silent(self.stop("agent-t8"))
        self.assertFalse((self.record_dir() / "agent-t8.json").exists())
        self.assertEqual(self.traces_of("agent-t8"), [])

    def test_o8_t9_malformed_or_unknown_payload_is_silent(self):
        cases = {
            "not_json": "not json",
            "json_list": "[]",
            "empty_object": "{}",
            "empty": "",
            "unknown_event": json.dumps({"hook_event_name": "Elsewhere", "agent_id": "x", "agent_type": IMPLEMENTER}),
            "missing_agent": json.dumps({"hook_event_name": "SubagentStart"}),
        }
        for label, raw in cases.items():
            with self.subTest(case=label):
                r = self.run_script(self.repo, SCRIPT, raw=raw, env=self.hook_env())
                self.assert_silent(r)
        self.assertEqual(self.record_files(), [])

    def test_o8_t10_unwritable_sessions_directory_is_silent(self):
        sessions = self.sessions_dir(self.repo)
        shutil.rmtree(sessions, ignore_errors=True)
        sessions.write_text("not a directory")
        self.assert_silent(self.start("agent-t10"))
        self.put("src/x.py", "# c\n")
        self.assert_silent(self.handback("agent-t10"))
        self.assert_silent(self.stop("agent-t10"))

    def test_o8_t10_missing_sessions_directory_is_silent_at_start(self):
        shutil.rmtree(self.sessions_dir(self.repo), ignore_errors=True)
        self.assert_silent(self.start("agent-t10m"))

    @unittest.skipIf(os.geteuid() == 0, "directory permissions do not bind root")
    def test_o8_t10_read_only_sessions_directory_is_silent(self):
        sessions = self.sessions_dir(self.repo)
        sessions.mkdir(parents=True, exist_ok=True)
        sessions.chmod(0o500)
        self.addCleanup(sessions.chmod, 0o700)
        self.assert_silent(self.start("agent-t10r"))
        self.assert_silent(self.stop("agent-t10r"))


class BaselineTests(SubagentCase):
    def test_o7_b1_empty_baseline_reports_new_comment(self):
        self.start("agent-b1")
        self.put("src/x.py", "x = 1\n# new\n")
        reason = self.deny_reason(self.handback("agent-b1"))
        self.assertEqual(self.entries(reason), ["src/x.py:2: # new"])

    def test_o7_b2_moved_comment_with_same_path_and_text_is_not_new(self):
        self.put("src/m.py", "# old\nx = 1\n")
        self.start("agent-b2")
        self.put("src/m.py", "x = 1\ny = 2\n# old\n")
        self.assert_silent(self.handback("agent-b2"))

    def test_o7_b2_unchanged_baseline_comment_is_not_new(self):
        self.put("src/m.py", "# old\nx = 1\n")
        self.start("agent-b2u")
        self.assert_silent(self.handback("agent-b2u"))

    def test_o7_b3_baseline_with_one_of_two_identical_comments_leaves_one(self):
        self.put("src/m.py", "# dup\n")
        self.start("agent-b3")
        self.put("src/m.py", "# dup\nx = 1\n# dup\n")
        reason = self.deny_reason(self.handback("agent-b3"))
        entries = self.entries(reason)
        self.assertEqual(len(entries), 1, reason)
        self.assertRegex(entries[0], r"^src/m\.py:\d+: # dup$")

    def test_o7_b3_different_comment_in_a_path_that_has_a_baseline_entry_is_new(self):
        self.put("src/a2.py", "# old\n")
        self.start("agent-f2")
        self.put("src/a2.py", "# old\n# new\n")
        reason = self.deny_reason(self.handback("agent-f2"))
        self.assertEqual(self.entries(reason), ["src/a2.py:2: # new"])

    def test_o7_b3_same_text_in_another_path_is_still_new(self):
        self.put("src/m.py", "# dup\n")
        self.start("agent-b3p")
        self.put("src/n.py", "# dup\n")
        reason = self.deny_reason(self.handback("agent-b3p"))
        self.assertEqual(self.entries(reason), ["src/n.py:1: # dup"])

    def test_o7_b4_missing_baseline_file_counts_as_empty(self):
        self.put("src/m.py", "# pre\n")
        self.start("agent-b4")
        (self.record_dir() / "agent-b4.json").unlink()
        reason = self.deny_reason(self.handback("agent-b4"))
        self.assertEqual(self.entries(reason), ["src/m.py:1: # pre"])

    def test_o7_b4_unreadable_baseline_file_counts_as_empty(self):
        self.put("src/m.py", "# pre\n")
        self.start("agent-b4u")
        (self.record_dir() / "agent-b4u.json").write_bytes(b"\xff\x00 not a baseline")
        reason = self.deny_reason(self.handback("agent-b4u"))
        self.assertEqual(self.entries(reason), ["src/m.py:1: # pre"])

    def test_o7_b5_failed_baseline_counts_as_empty(self):
        self.put("src/p.ts", "const a = 1;\n// pre\n")
        self.put("src/q.py", "# pq\n")
        self.start("agent-b5", env=self.no_uv_env())
        self.assertTrue((self.record_dir() / "agent-b5.json").is_file())
        reason = self.deny_reason(self.handback("agent-b5"))
        self.assertEqual(sorted(self.entries(reason)), ["src/p.ts:2: // pre", "src/q.py:1: # pq"])


class ReasonTextTests(SubagentCase):
    def comments_file(self, count):
        self.put("src/x.py", "".join(f"# c{i}\n" for i in range(1, count + 1)))

    def test_o9_m1_m2_m4_header_entries_and_categories(self):
        self.start("agent-m1")
        self.put("src/x.py", "x = 1\n# returns a+b\n")
        reason = self.deny_reason(self.handback("agent-m1"))
        lines = reason.splitlines()
        self.assertEqual(lines[0], HEADER)
        self.assertIn("src/x.py:2: # returns a+b", lines)
        self.assertTrue(reason.rstrip().endswith(CATEGORIES), reason)
        self.assertLess(reason.index("src/x.py:2: # returns a+b"), reason.index(CATEGORIES))

    def test_o9_m3_fifty_one_comments_list_fifty_and_one_more(self):
        self.start("agent-m3")
        self.comments_file(51)
        reason = self.deny_reason(self.handback("agent-m3"))
        self.assertEqual(len(self.entries(reason)), 50)
        self.assertEqual([l for l in reason.splitlines() if l.startswith("...")], ["... and 1 more"])

    def test_o9_m3_fifty_comments_list_fifty_without_more_line(self):
        self.start("agent-m3b")
        self.comments_file(50)
        reason = self.deny_reason(self.handback("agent-m3b"))
        self.assertEqual(len(self.entries(reason)), 50)
        self.assertEqual([l for l in reason.splitlines() if l.startswith("...")], [])

    def test_o9_m3_sixty_comments_list_fifty_and_ten_more(self):
        self.start("agent-m3f")
        self.comments_file(60)
        reason = self.deny_reason(self.handback("agent-m3f"))
        self.assertEqual(len(self.entries(reason)), 50)
        self.assertEqual([l for l in reason.splitlines() if l.startswith("...")], ["... and 10 more"])

    def test_o9_m3_stop_block_uses_the_same_reason(self):
        self.start("agent-m3s")
        self.comments_file(51)
        reason = self.block_reason(self.stop("agent-m3s"))
        self.assertEqual(reason.splitlines()[0], HEADER)
        self.assertEqual(len(self.entries(reason)), 50)
        self.assertIn("... and 1 more", reason.splitlines())

    def test_o9_m5_could_not_run_text(self):
        self.start("agent-m5")
        self.put("src/x.ts", "const a = 1;\n// c\n")
        reason = self.deny_reason(self.handback("agent-m5", env=self.no_uv_env()))
        self.assertTrue(reason.startswith(COULD_NOT_RUN_HEAD), reason)
        self.assertTrue(reason.endswith(COULD_NOT_RUN_TAIL), reason)
        message = reason[len(COULD_NOT_RUN_HEAD):-len(COULD_NOT_RUN_TAIL)]
        self.assertIn("uv not found on PATH", message)
        self.assertIn("src/x.ts", message)
        self.assertNotIn(HEADER, reason)


class TelemetryTests(SubagentCase):
    def test_o10_y1_start_record(self):
        self.start("agent-y1")
        events = self.events("agent-y1")
        self.assertEqual([self.fields(e) for e in events], [
            {"stage": "start", "trigger": "start", "new_comments": 0, "scan_ok": True, "blocked": False},
        ])

    def test_o10_y1_failed_baseline_start_record(self):
        self.put("src/p.ts", "// pre\n")
        self.start("agent-y1f", env=self.no_uv_env())
        self.assertEqual([self.fields(e) for e in self.events("agent-y1f")], [
            {"stage": "start", "trigger": "start", "new_comments": 0, "scan_ok": False, "blocked": False},
        ])

    def test_o10_y2_finish_allow(self):
        self.start("agent-y2")
        self.handback("agent-y2")
        self.assertEqual(self.fields(self.events("agent-y2")[-1]), {
            "stage": "finish", "trigger": "handback", "new_comments": 0, "scan_ok": True, "blocked": False,
        })

    def test_o10_y2_stop_allow(self):
        self.start("agent-y2s")
        self.stop("agent-y2s")
        self.assertEqual(self.fields(self.events("agent-y2s")[-1]), {
            "stage": "finish", "trigger": "stop", "new_comments": 0, "scan_ok": True, "blocked": False,
        })

    def test_o10_y3_finish_deny_on_handback_then_allowed_second(self):
        self.start("agent-y3")
        self.put("src/x.py", "# a\n# b\n")
        self.handback("agent-y3")
        self.handback("agent-y3")
        events = self.events("agent-y3")
        self.assertEqual(len(events), 3)
        self.assertEqual(self.fields(events[1]), {
            "stage": "finish", "trigger": "handback", "new_comments": 2, "scan_ok": True, "blocked": True,
        })
        self.assertIs(events[2]["blocked"], False)

    def test_o10_y4_finish_block_on_stop(self):
        self.start("agent-y4")
        self.put("src/x.py", "# a\n")
        self.stop("agent-y4")
        self.assertEqual(self.fields(self.events("agent-y4")[-1]), {
            "stage": "finish", "trigger": "stop", "new_comments": 1, "scan_ok": True, "blocked": True,
        })

    def test_o10_y5_finish_scan_failure(self):
        self.start("agent-y5")
        self.put("src/x.ts", "// c\n")
        self.handback("agent-y5", env=self.no_uv_env())
        last = self.events("agent-y5")[-1]
        self.assertEqual(
            {k: last[k] for k in ("stage", "trigger", "scan_ok", "blocked")},
            {"stage": "finish", "trigger": "handback", "scan_ok": False, "blocked": True},
        )


class ScenarioTests(SubagentCase):
    def test_o11_sc1_parallel_roles_each_see_only_their_own_comments(self):
        self.start("agent-impl", IMPLEMENTER)
        self.start("agent-test", TEST_IMPLEMENTER)
        self.put("src/impl.py", "x = 1\n# impl note\n")
        self.put("tests/test_impl.py", "y = 1\n# test note\n")
        test_reason = self.deny_reason(self.handback("agent-test", TEST_IMPLEMENTER))
        impl_reason = self.deny_reason(self.handback("agent-impl", IMPLEMENTER))
        self.assertEqual(self.entries(impl_reason), ["src/impl.py:2: # impl note"])
        self.assertEqual(self.entries(test_reason), ["tests/test_impl.py:2: # test note"])
        self.assertNotIn("test note", impl_reason)
        self.assertNotIn("impl note", test_reason)

    def test_o11_sc1_role_paths_are_the_union_of_active_specs_only(self):
        self.write_spec(self.repo, name="second", impl="lib/")
        self.write_spec(self.repo, name="finished", status="done", impl="docs/")
        self.start("agent-union")
        self.put("src/a.py", "# one\n")
        self.put("lib/b.py", "# two\n")
        self.put("docs/c.py", "# three\n")
        reason = self.deny_reason(self.handback("agent-union"))
        self.assertEqual(sorted(self.entries(reason)), ["lib/b.py:1: # two", "src/a.py:1: # one"])

    def test_o11_sc1_baseline_is_kept_per_agent_id(self):
        self.put("src/old.py", "# old\n")
        self.start("agent-first", IMPLEMENTER)
        self.start("agent-second", TEST_IMPLEMENTER)
        self.assert_silent(self.handback("agent-first", IMPLEMENTER))
        self.assert_silent(self.handback("agent-second", TEST_IMPLEMENTER))

    def test_o7_o11_a7_comma_separated_implementation_entries_directories_and_files(self):
        self.write_spec(self.repo, impl="src/, lib/, tools/run.py")
        self.start("agent-f4")
        for rel in ("src/a.py", "lib/b.py", "tools/run.py", "tools/other.py", "docs/z.py"):
            self.put(rel, "# c\n")
        reason = self.deny_reason(self.handback("agent-f4"))
        self.assertEqual(
            sorted(self.entries(reason)), ["lib/b.py:1: # c", "src/a.py:1: # c", "tools/run.py:1: # c"]
        )

    def test_o7_o11_a7_comma_separated_tests_entries_directories_and_files(self):
        self.write_spec(self.repo, tests="tests/, qa/, checks/run.py")
        self.start("agent-f4t", TEST_IMPLEMENTER)
        for rel in ("tests/a.py", "qa/b.py", "checks/run.py", "checks/other.py", "src/z.py"):
            self.put(rel, "# c\n")
        reason = self.deny_reason(self.handback("agent-f4t", TEST_IMPLEMENTER))
        self.assertEqual(
            sorted(self.entries(reason)), ["checks/run.py:1: # c", "qa/b.py:1: # c", "tests/a.py:1: # c"]
        )

    def assert_no_record_no_output(self, agent_type, rel):
        self.assert_silent(self.start("agent-quiet", agent_type))
        self.assertEqual(self.record_files(), [])
        self.put(rel, "# c\n")
        self.assert_silent(self.handback("agent-quiet", agent_type))
        self.assert_silent(self.stop("agent-quiet", agent_type))
        self.assertEqual(self.record_files(), [])

    def test_o11_sc2_other_agent_types_are_ignored(self):
        for agent_type in ("test-verifier", "code-explorer", "mutant-triager", ""):
            with self.subTest(agent_type=agent_type):
                self.assert_no_record_no_output(agent_type, "src/x.py")

    def test_o11_sc3_no_specs_directory(self):
        shutil.rmtree(self.repo / "agent-docs" / "specs")
        self.assert_no_record_no_output(IMPLEMENTER, "src/x.py")

    def test_o11_sc4_no_active_spec(self):
        self.write_spec(self.repo, status="done")
        self.assert_no_record_no_output(IMPLEMENTER, "src/x.py")

    def test_o11_sc4_specs_directory_without_any_spec(self):
        (self.repo / "agent-docs" / "specs" / "aaaaaaaaaaaaaaaa-fixture.md").unlink()
        self.assert_no_record_no_output(IMPLEMENTER, "src/x.py")

    def test_o11_sc5_empty_tests_paths_for_test_implementer(self):
        self.write_spec(self.repo, tests="")
        self.assert_no_record_no_output(TEST_IMPLEMENTER, "tests/t.py")

    def test_o11_sc6_linked_worktree_keeps_records_in_that_worktree(self):
        run_git(self.repo, "add", "-A")
        self.commit(self.repo, "spec")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        linked = Path(tmp.name) / "wt"
        run_git(self.repo, "worktree", "add", "-q", "-b", "wt", str(linked))
        shutil.copytree(self.repo / ".harness", linked / ".harness", dirs_exist_ok=True)
        shutil.rmtree(linked / ".harness" / "sessions", ignore_errors=True)
        self.put("src/main_only.py", "# main only\n")
        self.assert_silent(self.start("agent-wt", repo=linked))
        self.assertTrue((self.record_dir(linked) / "agent-wt.json").is_file())
        self.assertEqual(self.traces_of("agent-wt", self.repo), [])
        self.put("src/x.py", "x = 1\n# linked\n", repo=linked)
        reason = self.deny_reason(self.handback("agent-wt", repo=linked))
        self.assertEqual(self.entries(reason), ["src/x.py:2: # linked"])
        self.assert_silent(self.stop("agent-wt", repo=linked))
        self.assertEqual(self.traces_of("agent-wt", self.repo), [])
        self.assertEqual(self.traces_of("agent-wt", linked), [])
