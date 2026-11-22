import ast
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path

from hook_case import HookCase, out
from old_release import BASE_0491, base_file, release_source
from test_installer import REPO_ROOT, InstallerTestCase, load_installer_module, run_git, run_installer
import skill_text

ID_A = "aaaaaaaaaaaaaaaa"
BASE_X = "abc123def4567890abc123def4567890abc123de"
NOTICE_PREFIX = "spec lifecycle: "
PRINCIPLE_NOTE = "Principles 2 and 3 will be replaced by a new approach; until then, following them is not required."
PROGRESS_IGNORE_LINES = (".harness/sessions/progress-*.json", ".harness/sessions/progress-*.d/",
                         ".harness/sessions/installer-run.json")
RULES_IGNORE_LINE = ".harness/sessions/rules-*.d/"
CONTINUE_ON_TARGET = "../../.agents/skills/continue-on"
REMOVED_SOURCE = ("harness/lib/progress.py", "harness/hooks/progress_hook.py", "harness/bin/progress.py",
                  "harness/git/sync_progress.py", "harness/instructions/progress.md", "harness/skills/continue-on")
REMOVED_INSTALLED = (".harness/lib/progress.py", ".harness/hooks/progress_hook.py", ".harness/bin/progress.py",
                     ".harness/git/sync_progress.py", ".harness/instructions/progress.md",
                     ".agents/skills/continue-on", ".claude/skills/continue-on")
REMOVED_STATE = ("agent-docs/progress", "agent-docs/progress-logs", ".harness/sessions/progress-x.json",
                 ".harness/sessions/progress-x.d", ".harness/sessions/installer-run.json")
PLAN_NAMES = (r"agent-docs/progress(?!-)", r"agent-docs/progress-logs", re.escape(".harness/sessions/progress-*.json"),
              re.escape(".harness/sessions/progress-*.d"), re.escape(".harness/sessions/installer-run.json"),
              re.escape(".claude/skills/continue-on"), re.escape(".gitignore"))
PROGRESS_COMMAND = 'python3 "$CLAUDE_PROJECT_DIR"/.harness/hooks/progress_hook.py'
USER_STOP = {"hooks": [{"type": "command", "command": "echo user-stop-hook"}]}
SCRIPT_PATH = re.compile(r"\.harness/[\w./-]+?\.py")
LOCAL_MARK = "LOCAL-POST-MERGE-RAN"
LEFT_IN_PLACE = ".claude/skills/continue-on is not the harness symlink; left in place"
STEP1_RESUME = "Resume it only when the user asks;"
STEP9_LIMIT = "For verifier-budget exhaustion, set status `limit`, archive with `--status limit`, then emit end limit."
STEP9_HANDOFF = "For a nonterminal stop, keep the spec `active` and emit end handoff without archiving."


def ignore_lines(repo):
    path = repo / ".gitignore"
    return [line.strip().lstrip("/") for line in path.read_text().splitlines()] if path.is_file() else []


def tree_state(repo):
    state = {}
    for path in sorted(repo.rglob("*")):
        rel = path.relative_to(repo)
        if rel.parts[0] == ".git" or "__pycache__" in rel.parts:
            continue
        if path.is_symlink():
            state[rel.as_posix()] = "link:" + os.readlink(path)
        elif path.is_file():
            state[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            state[rel.as_posix()] = "dir"
    return state


def hook_groups(data):
    return [(event, group) for event, groups in data.get("hooks", {}).items() for group in groups]


def harness_scripts(data):
    commands = [hook["command"] for _, group in hook_groups(data) for hook in group.get("hooks", [])]
    harness = [command for command in commands if "/.harness/" in command]
    return harness, [script for command in harness for script in SCRIPT_PATH.findall(command)]


def migration_section(stdout, version="0.50.0"):
    marker = f"migration {version}:"
    if marker not in stdout:
        return None
    return re.split(r"\n(?=migration \d|Apply migration|== )", stdout.split(marker, 1)[1])[0]


class SpecNoticeCase(HookCase):
    def open_spec(self, repo):
        path = repo / "agent-docs" / "specs" / f"{ID_A}-alpha.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nstatus: active\nbase_commit: {BASE_X}\n---\n\n# Body\n")
        return path

    def notice_cli(self, repo):
        return subprocess.run([sys.executable, str(repo / ".harness" / "bin" / "spec_lifecycle.py"), "notice"],
                              cwd=repo, capture_output=True, text=True, env=self.env())

    def session_start(self, repo):
        return self.run_script(repo, "spec_notice.py", {"hook_event_name": "SessionStart", "session_id": "sessnote",
                                                        "source": "startup", "cwd": str(repo)})

    def assert_quiet(self, result):
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class TestSpecNotice(SpecNoticeCase):
    def test_vo4_n1_open_spec_prints_the_notice_lines(self):
        repo = self.new_repo()
        self.open_spec(repo)
        expected = self.notice_cli(repo)
        self.assertEqual(expected.returncode, 0, out(expected))
        result = self.session_start(repo)
        self.assertEqual(result.returncode, 0, out(result))
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, expected.stdout)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 1, result.stdout)
        self.assertTrue(lines[0].startswith(NOTICE_PREFIX), lines[0])
        self.assertIn(f"agent-docs/specs/{ID_A}-alpha.md", lines[0])
        self.assertIn(BASE_X, lines[0])

    def test_vo4_n2_nothing_to_report_prints_nothing(self):
        repo = self.new_repo()
        specs = repo / "agent-docs" / "specs"
        specs.mkdir(parents=True, exist_ok=True)
        self.assertEqual(sorted(specs.glob("*.md")), [])
        self.assertFalse((specs / ".running").exists())
        self.assert_quiet(self.session_start(repo))

    def test_vo4_n3_failing_spec_state_prints_nothing_and_exits_zero(self):
        variants = {
            "raises on import": "raise RuntimeError('spec state broken')\n",
            "raises on call": ("def _fail(*args, **kwargs):\n    raise RuntimeError('spec state broken')\n\n\n"
                               "print_notice = notice_lines = _fail\n"),
        }
        for label, body in variants.items():
            with self.subTest(variant=label):
                repo = self.new_repo()
                self.open_spec(repo)
                module = repo / ".harness" / "lib" / "spec_state.py"
                self.assertTrue(module.is_file(), "spec_state.py is expected in .harness/lib")
                module.write_text(body)
                shutil.rmtree(module.parent / "__pycache__", ignore_errors=True)
                self.assert_quiet(self.session_start(repo))


def harness_group(script, matcher=None):
    group = {"hooks": [{"type": "command", "command": f'python3 "$CLAUDE_PROJECT_DIR"/.harness/hooks/{script}'}]}
    if matcher:
        group = {"matcher": matcher, **group}
    return group


def user_group(name, matcher=None):
    group = {"hooks": [{"type": "command", "command": f"echo {name}"}]}
    if matcher:
        group = {"matcher": matcher, **group}
    return group


MERGE_RULES = [
    ("r1_harness_new_user", True, True, True),
    ("r2_harness_new_no_user", True, True, False),
    ("r3_harness_dropped_user", True, False, True),
    ("r4_harness_dropped_no_user", True, False, False),
    ("r5_no_harness_new_user", False, True, True),
    ("r6_no_harness_new_no_user", False, True, False),
    ("r7_no_harness_dropped_user", False, False, True),
    ("r8_no_harness_dropped_no_user", False, False, False),
]


class TestMergeHooksDict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_installer_module()

    def settings(self, hooks):
        return {"permissions": {"allow": ["Bash(ls)"]}, "hooks": hooks, "env": {"KEEP": "1"}}

    def test_vo5_decision_table_over_harness_group_event_kept_and_user_group(self):
        for rule, harness, kept, user in MERGE_RULES:
            with self.subTest(rule=rule):
                existing_stop = []
                if user:
                    existing_stop.append(user_group("user-one"))
                if harness:
                    existing_stop.append(harness_group("progress_hook.py"))
                if user:
                    existing_stop.append(user_group("user-two", matcher="x"))
                existing_hooks = {"Stop": existing_stop} if existing_stop else {}
                new_hooks = {"PreToolUse": [harness_group("rule_injection.py", "Write|Edit|MultiEdit")]}
                if kept:
                    new_hooks["Stop"] = [harness_group("session_lock.py")]

                result = self.module.merge_hooks_dict(self.settings(copy.deepcopy(existing_hooks)),
                                                      {"hooks": copy.deepcopy(new_hooks)})

                expected_stop = ([user_group("user-one"), user_group("user-two", matcher="x")] if user else [])
                if kept:
                    expected_stop.append(harness_group("session_lock.py"))
                expected_hooks = {"PreToolUse": [harness_group("rule_injection.py", "Write|Edit|MultiEdit")]}
                if expected_stop:
                    expected_hooks["Stop"] = expected_stop
                self.assertEqual(result, self.settings(expected_hooks))
                self.assertEqual(list(result), ["permissions", "hooks", "env"])
                if not expected_stop:
                    self.assertNotIn("Stop", result["hooks"])

    def test_vo5_c16_events_missing_from_the_new_set_lose_their_harness_groups(self):
        existing = self.settings({
            "UserPromptSubmit": [harness_group("progress_hook.py")],
            "PreCompact": [harness_group("progress_hook.py")],
            "Stop": [harness_group("progress_hook.py"), USER_STOP],
        })
        new_hooks = {"PreToolUse": [harness_group("rule_injection.py", "Write|Edit|MultiEdit")],
                     "SessionStart": [harness_group("spec_notice.py")]}

        result = self.module.merge_hooks_dict(existing, {"hooks": copy.deepcopy(new_hooks)})

        self.assertNotIn("UserPromptSubmit", result["hooks"])
        self.assertNotIn("PreCompact", result["hooks"])
        self.assertEqual(result["hooks"]["Stop"], [USER_STOP])
        self.assertEqual(result["hooks"]["PreToolUse"], new_hooks["PreToolUse"])
        self.assertEqual(result["hooks"]["SessionStart"], new_hooks["SessionStart"])

    def test_vo5_c17_kept_event_keeps_user_groups_first_in_order_and_replaces_harness_groups(self):
        existing = self.settings({"PreToolUse": [
            user_group("user-a", "Write"), harness_group("spec_gate.py", "Bash"),
            user_group("user-b", "Bash"), harness_group("progress_hook.py", "Bash|Write|Edit|MultiEdit"),
        ]})
        new_groups = [harness_group("spec_gate.py", "Bash"), harness_group("rule_injection.py", "Write|Edit|MultiEdit")]

        result = self.module.merge_hooks_dict(existing, {"hooks": {"PreToolUse": copy.deepcopy(new_groups)}})

        self.assertEqual(result["hooks"]["PreToolUse"],
                         [user_group("user-a", "Write"), user_group("user-b", "Bash"), *new_groups])


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
        self.assertEqual(json.loads((repo / ".harness" / "manifest.json").read_text())["version"], "0.49.1")
        return repo

    def write(self, repo, rel, text):
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def add_hook_fixtures(self, repo):
        claude_path = repo / ".claude" / "settings.json"
        claude = json.loads(claude_path.read_text())
        for event in ("UserPromptSubmit", "PreCompact", "Stop"):
            groups = claude.setdefault("hooks", {}).setdefault(event, [])
            if not any("progress_hook.py" in h["command"] for g in groups for h in g.get("hooks", [])):
                groups.append({"hooks": [{"type": "command", "command": PROGRESS_COMMAND}]})
        claude["hooks"]["Stop"].append(copy.deepcopy(USER_STOP))
        claude_path.write_text(json.dumps(claude, indent=2) + "\n")
        codex_path = repo / ".codex" / "hooks.json"
        codex = json.loads(codex_path.read_text())
        codex.setdefault("hooks", {}).setdefault("Stop", []).append(copy.deepcopy(USER_STOP))
        codex_path.write_text(json.dumps(codex, indent=2) + "\n")

    def populate(self, repo, dirty=False):
        self.write(repo, "agent-docs/progress/1111111111111111-a.md", "# A\n")
        self.write(repo, "agent-docs/progress-logs/2222222222222222-b.md", "# B\n")
        self.write(repo, "agent-docs/progress-logs/4444444444444444-d.md", "# D\n")
        self.write(repo, ".harness/sessions/progress-x.json", "{}\n")
        self.write(repo, ".harness/sessions/progress-x.d/rule-todos", "")
        self.write(repo, ".harness/sessions/installer-run.json", "{}\n")
        self.write(repo, ".harness/sessions/progress-notes.txt", "keep\n")
        link = repo / ".claude" / "skills" / "continue-on"
        if link.is_symlink() or link.is_file():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
        self.assertTrue((repo / ".agents" / "skills" / "continue-on").is_dir())
        os.symlink(CONTINUE_ON_TARGET, link)
        lines = ignore_lines(repo)
        missing = [line for line in PROGRESS_IGNORE_LINES if line not in lines]
        with (repo / ".gitignore").open("a") as handle:
            handle.write("".join(f"{line}\n" for line in missing) + "user-build/\n")
        self.add_hook_fixtures(repo)
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-q", "--no-verify", "-m", "0.49.1 state")
        for line in PROGRESS_IGNORE_LINES:
            self.assertIn(line, ignore_lines(repo))
        if dirty:
            self.write(repo, "agent-docs/progress/3333333333333333-c.md", "# C untracked\n")
            self.write(repo, "agent-docs/progress-logs/4444444444444444-d.md", "# D modified\n")
        return repo

    def update(self, repo, *flags):
        return run_installer("update", str(repo), *flags, input="y\n" * 80, exact=True)

    def assert_no_progress_state(self, repo):
        for rel in (*REMOVED_STATE, *REMOVED_INSTALLED):
            with self.subTest(path=rel):
                self.assertFalse(os.path.lexists(repo / rel), rel)
        lines = ignore_lines(repo)
        for line in PROGRESS_IGNORE_LINES:
            self.assertNotIn(line, lines)
        self.assertIn("user-build/", lines)

    def assert_hook_files_coexist(self, repo):
        for rel in (".claude/settings.json", ".codex/hooks.json"):
            with self.subTest(file=rel):
                data = json.loads((repo / rel).read_text())
                harness, scripts = harness_scripts(data)
                self.assertTrue(harness, rel)
                self.assertEqual([s for s in scripts if not (repo / s).is_file()], [])
                self.assertNotIn("progress_hook.py", json.dumps(data))
                stop = data.get("hooks", {}).get("Stop", [])
                self.assertEqual([g for g in stop if g == USER_STOP], [USER_STOP])

    def plan_text_names_every_item(self, text):
        for pattern in PLAN_NAMES:
            with self.subTest(name=pattern):
                self.assertRegex(text, pattern)


class TestUpdateFrom0491(Update0491Case):
    def test_vo6_s1_c18_update_with_commit_removes_everything_and_leaves_a_clean_tree(self):
        repo = self.populate(self.installed_0491())
        head = run_git(repo, "rev-parse", "HEAD").stdout.strip()

        result = self.update(repo)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(LEFT_IN_PLACE, result.stdout)
        self.assert_no_progress_state(repo)
        self.assertTrue((repo / ".harness" / "sessions" / "progress-notes.txt").is_file())
        self.assert_hook_files_coexist(repo)
        manifest = json.loads((repo / ".harness" / "manifest.json").read_text())
        self.assertEqual(manifest["version"], "0.56.0")
        for name in ("progress_hook", "sync_progress", "continue-on", "lib/progress.py", "bin/progress.py",
                     "instructions/progress.md"):
            self.assertEqual([k for k in manifest.get("files", {}) if name in k], [], name)
        for rel in (".harness/hooks/rule_injection.py", ".harness/hooks/spec_notice.py"):
            self.assertTrue((repo / rel).is_file(), rel)
        self.assertNotEqual(run_git(repo, "rev-parse", "HEAD").stdout.strip(), head)
        changes = run_git(repo, "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD").stdout.splitlines()
        for rel in ("agent-docs/progress/1111111111111111-a.md", "agent-docs/progress-logs/2222222222222222-b.md",
                    "agent-docs/progress-logs/4444444444444444-d.md"):
            self.assertIn(f"D\t{rel}", changes)
        self.assertEqual(run_git(repo, "status", "--porcelain", "--untracked-files=all").stdout, "")

    def test_vo6_s1_fr6_untracked_and_modified_records_are_deleted_too(self):
        repo = self.populate(self.installed_0491(), dirty=True)

        result = self.update(repo)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertNotIn("Traceback", result.stderr)
        self.assert_no_progress_state(repo)
        self.assert_hook_files_coexist(repo)

    def test_vo6_s2_c19_dry_run_changes_nothing_and_prints_the_plan(self):
        repo = self.populate(self.installed_0491(), dirty=True)
        before = tree_state(repo)
        head = run_git(repo, "rev-parse", "HEAD").stdout.strip()
        status = run_git(repo, "status", "--porcelain", "--untracked-files=all").stdout

        result = run_installer("update", str(repo), "--dry-run", forbid_input=True)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertEqual(tree_state(repo), before)
        self.assertEqual(run_git(repo, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertEqual(run_git(repo, "status", "--porcelain", "--untracked-files=all").stdout, status)
        section = migration_section(result.stdout)
        self.assertIsNotNone(section, result.stdout)
        self.plan_text_names_every_item(section)

    def test_vo6_s2_fr6_direct_dry_run_returns_plan_lines_and_changes_nothing(self):
        module = load_installer_module()
        repo = self.populate(self.installed_0491(), dirty=True)
        before = tree_state(repo)

        lines = module.migrate_remove_progress(repo, True)

        self.assertIsInstance(lines, list)
        self.assertTrue(all(isinstance(line, str) for line in lines), lines)
        self.plan_text_names_every_item("\n".join(lines))
        self.assertEqual(tree_state(repo), before)

    def test_vo6_s2_migration_is_registered_for_0500(self):
        module = load_installer_module()
        entries = [entry for entry in module.MIGRATIONS if entry[0] == module.parse_version("0.50.0")]
        self.assertEqual(len(entries), 1, entries)
        self.assertIs(entries[0][2], module.migrate_remove_progress)
        later = module.MIGRATIONS[module.MIGRATIONS.index(entries[0]) + 1:]
        self.assertTrue(all(entry[0] > module.parse_version("0.50.0") for entry in later))

    def test_vo6_s3_c20_continue_on_that_is_not_the_harness_symlink_is_left_and_reported(self):
        def user_dir(link):
            link.mkdir()
            (link / "SKILL.md").write_text("user skill\n")

        def other_link(link):
            os.symlink("../../elsewhere/continue-on", link)

        for label, make in (("user directory", user_dir), ("symlink elsewhere", other_link)):
            with self.subTest(case=label):
                repo = self.populate(self.installed_0491())
                link = repo / ".claude" / "skills" / "continue-on"
                link.unlink()
                make(link)
                run_git(repo, "add", "-A")
                run_git(repo, "commit", "-q", "--no-verify", "-m", "user continue-on")
                before = tree_state(repo)[".claude/skills/continue-on"]
                planned = load_installer_module().migrate_remove_progress(repo, True)
                self.assertIn(LEFT_IN_PLACE, planned)

                result = self.update(repo)

                self.assertEqual(result.returncode, 0, out(result))
                self.assertTrue(os.path.lexists(link))
                self.assertEqual(tree_state(repo)[".claude/skills/continue-on"], before)
                if label == "user directory":
                    self.assertEqual((link / "SKILL.md").read_text(), "user skill\n")
                self.assertIn(LEFT_IN_PLACE, result.stdout)
                for rel in ("agent-docs/progress", "agent-docs/progress-logs"):
                    self.assertFalse((repo / rel).exists(), rel)


    def test_vo6_s3_harness_symlink_gets_no_left_in_place_line(self):
        repo = self.populate(self.installed_0491())
        planned = load_installer_module().migrate_remove_progress(repo, True)
        self.assertNotIn(LEFT_IN_PLACE, planned)
        self.assertTrue((repo / ".claude" / "skills" / "continue-on").is_symlink())

    def test_vo6_s6_c30_custom_docs_root_progress_directories_are_removed_too(self):
        repo = self.installed_0491()
        config_path = repo / ".harness" / "config.json"
        config = json.loads(config_path.read_text()) if config_path.is_file() else {}
        config["docs_root"] = "docs/agent"
        config_path.write_text(json.dumps(config))
        records = ("docs/agent/progress/1111111111111111-a.md", "docs/agent/progress-logs/2222222222222222-b.md",
                   "agent-docs/progress/3333333333333333-c.md", "agent-docs/progress-logs/4444444444444444-d.md")
        for rel in records:
            self.write(repo, rel, "# record\n")
        run_git(repo, "add", "-A")
        run_git(repo, "add", "-f", "--", *records)
        run_git(repo, "commit", "-q", "--no-verify", "-m", "custom docs root records")
        self.assertTrue(all((repo / rel).is_file() for rel in records))

        result = self.update(repo)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertNotIn("Traceback", result.stderr)
        for rel in ("docs/agent/progress", "docs/agent/progress-logs", "agent-docs/progress", "agent-docs/progress-logs"):
            with self.subTest(path=rel):
                self.assertFalse(os.path.lexists(repo / rel), rel)
        self.assertEqual(json.loads(config_path.read_text())["docs_root"], "docs/agent")

    def test_vo6_s7_update_from_0491_leaves_the_rules_marker_ignore_line(self):
        repo = self.installed_0491()

        result = self.update(repo, "--no-commit")

        self.assertEqual(result.returncode, 0, out(result))
        lines = ignore_lines(repo)
        self.assertIn(RULES_IGNORE_LINE, lines)
        for line in PROGRESS_IGNORE_LINES:
            self.assertNotIn(line, lines)


class TestLegacyChainAndClean(Update0491Case):
    def legacy(self, version):
        repo = self.install()
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = version
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        result = run_installer("update", str(repo), input="y\n" * 80, exact=True)
        self.assertEqual(result.returncode, 0, out(result))
        self.assertEqual(json.loads(manifest_path.read_text())["version"], "0.56.0")
        for rel in ("agent-docs/progress", "agent-docs/progress-logs", ".claude/skills/continue-on",
                    ".agents/skills/continue-on", ".harness/hooks/progress_hook.py"):
            self.assertFalse(os.path.lexists(repo / rel), rel)
        self.assertIn("migration 0.50.0:", result.stdout)

    def test_vo6_s4_c21_update_from_0400_through_the_chain_ends_without_progress(self):
        self.legacy("0.40.0")

    def test_vo6_s4_c21_update_from_0320_through_the_chain_ends_without_progress(self):
        self.legacy("0.32.0")

    def test_vo6_s5_migration_without_progress_artifacts_changes_nothing_and_still_plans(self):
        module = load_installer_module()
        repo = self.installed_copy("--no-ci")[0]
        before = tree_state(repo)

        lines = module.migrate_remove_progress(repo, False)

        self.assertEqual(tree_state(repo), before)
        self.plan_text_names_every_item("\n".join(lines))
        self.assertFalse(os.path.lexists(repo / ".claude" / "skills" / "continue-on"))
        self.assertNotIn(LEFT_IN_PLACE, lines)

    def test_vo6_s5_update_from_0491_state_without_artifacts_succeeds_and_announces_the_step(self):
        repo = self.installed_copy("--no-ci")[0]
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = "0.49.1"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        result = run_installer("update", str(repo), "--no-commit", input="y\n" * 80, exact=True)

        self.assertEqual(result.returncode, 0, out(result))
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(re.findall(r"^migration (\d+\.\d+\.\d+):", result.stdout, re.MULTILINE), ["0.50.0", "0.51.0", "0.52.0", "0.53.0", "0.54.0", "0.55.0", "0.55.1", "0.56.0"])
        self.plan_text_names_every_item(migration_section(result.stdout))
        self.assertNotIn(LEFT_IN_PLACE, result.stdout)
        self.assertEqual(json.loads(manifest_path.read_text())["version"], "0.56.0")


class TestFreshInstall(InstallerTestCase):
    def test_vo7_i1_fresh_install_creates_no_progress_directories_and_ignores_rule_markers(self):
        repo = self.fresh_install()
        for rel in ("agent-docs/progress", "agent-docs/progress-logs", ".claude/skills/continue-on",
                    ".agents/skills/continue-on"):
            self.assertFalse(os.path.lexists(repo / rel), rel)
        lines = ignore_lines(repo)
        self.assertIn(RULES_IGNORE_LINE, lines)
        for line in PROGRESS_IGNORE_LINES:
            self.assertNotIn(line, lines)
        module = load_installer_module()
        declared = [line.lstrip("/") for line in module.GITIGNORE_LINES]
        self.assertIn(RULES_IGNORE_LINE, declared)
        for line in PROGRESS_IGNORE_LINES:
            self.assertNotIn(line, declared)


def json_entries(data):
    if isinstance(data, list):
        return [(None, item) for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        found = []
        for key, value in data.items():
            if isinstance(value, list):
                found += [(key, item) for item in value if isinstance(item, dict)]
            elif isinstance(value, dict):
                found += [(f"{key}/{inner}", item) for inner, item in json_entries(value)]
        return found
    return []


def mentions(entry, *names):
    text = json.dumps(entry[1])
    return any(name in text for name in names)


class TestInstalledRepository(HookCase):
    def test_vo8_f1_removed_files_are_absent_from_source_and_install(self):
        repo = self.new_repo()
        for rel in REMOVED_SOURCE:
            with self.subTest(path=rel):
                self.assertFalse(os.path.lexists(REPO_ROOT / rel), rel)
        for rel in REMOVED_INSTALLED:
            with self.subTest(path=rel):
                self.assertFalse(os.path.lexists(repo / rel), rel)
        for rel in ("harness/hooks/rule_injection.py", "harness/hooks/spec_notice.py"):
            self.assertTrue((REPO_ROOT / rel).is_file(), rel)
            self.assertTrue((repo / rel.replace("harness/", ".harness/", 1)).is_file(), rel)

    def test_vo8_f2_hook_registrations_match_the_new_set(self):
        repo = self.new_repo()
        claude = json.loads((repo / ".claude" / "settings.json").read_text())["hooks"]
        codex_text = (repo / ".codex" / "hooks.json").read_text()

        def groups_running(event, script):
            return [g for g in claude.get(event, []) if any(script in h["command"] and "/.harness/" in h["command"]
                                                             for h in g["hooks"])]

        injection = groups_running("PreToolUse", "rule_injection.py")
        self.assertEqual(len(injection), 1, claude.get("PreToolUse"))
        self.assertEqual(injection[0]["matcher"], "Write|Edit|MultiEdit")
        self.assertEqual(len(groups_running("SessionStart", "spec_notice.py")), 1, claude.get("SessionStart"))
        self.assertNotIn("progress_hook.py", json.dumps(claude))
        for script in ("rule_injection.py", "spec_notice.py", "progress_hook.py"):
            self.assertNotIn(script, codex_text)

    def test_vo8_f2_hooks_spec_keeps_other_entries_and_targets_new_ones_at_claude(self):
        rel = "harness/hooks/hooks.spec.json"
        current = json_entries(json.loads((REPO_ROOT / rel).read_text()))
        base = json_entries(json.loads(base_file(BASE_0491, rel)))
        self.assertNotIn("progress_hook.py", (REPO_ROOT / rel).read_text())
        for script in ("rule_injection.py", "spec_notice.py"):
            with self.subTest(script=script):
                entries = [entry for entry in current if mentions(entry, script)]
                self.assertEqual(len(entries), 1, entries)
                self.assertEqual(entries[0][1].get("targets"), ["claude"])
        kept_base = [(k, json.dumps(e, sort_keys=True)) for k, e in base if not mentions((k, e), "progress_hook.py")]
        session_start_0540 = {"command": 'python3 "{root}/.harness/bin/checkout_setup.py" hook',
                              "event": "SessionStart", "targets": ["claude"]}
        added = [e for _, e in current if e == session_start_0540]
        self.assertEqual(len(added), 1, current)
        customization = [e for k, e in current if mentions((k, e), "customization_notice.py", "customization_context.py")]
        self.assertEqual(len(customization), 3, customization)
        self.assertEqual([e.get("targets") for e in customization], [["claude"]] * 3)
        self.assertEqual(sorted(e["event"] for e in customization), ["PostToolUse", "SessionStart", "SubagentStart"])
        kept_now = [(k, json.dumps(e, sort_keys=True)) for k, e in current
                    if not mentions((k, e), "rule_injection.py", "spec_notice.py", "customization_notice.py",
                                    "customization_context.py") and e != session_start_0540]
        self.assertEqual(kept_now, kept_base)

    def test_vo8_f3_commit_in_an_installed_repo_passes_pre_commit(self):
        repo = self.new_repo()
        (repo / "src" / "a.py").write_text("a = 2\n")
        run_git(repo, "add", "-A")
        result = self.commit_with_hooks(repo, "change a")
        self.assertEqual(result.returncode, 0, out(result))
        self.assertNotIn("progress", out(result).lower())
        self.assertNotIn("Traceback", out(result))

    def test_vo8_f4_new_todo_gets_a_commit_stamp_and_commits(self):
        repo = self.new_repo()
        head = self.head(repo)
        name = "0123456789abcdef-add-flag.md"
        todo = repo / "agent-docs" / "todos" / name
        todo.write_text("# Add flag\n\n## Next Step\ndo it\n")
        (repo / "agent-docs" / "todos" / "index.md").write_text(
            f"File: {name}\nSummary: s\nRelated Files: none\nRelated Symbols: none\n")
        stamp = self.run_script(repo, "doc_commit.py", {"hook_event_name": "PostToolUse", "tool_name": "Write",
                                                        "cwd": str(repo), "tool_input": {"file_path": str(todo)}})
        self.assertEqual(stamp.returncode, 0, out(stamp))
        self.assertEqual(todo.read_text(), f"---\ncommit: {head}\n---\n\n# Add flag\n\n## Next Step\ndo it\n")
        run_git(repo, "add", "-A")
        result = self.commit_with_hooks(repo, "add todo")
        self.assertEqual(result.returncode, 0, out(result))
        self.assertNotIn("progress", out(result).lower())

    def install_local_post_merge(self, repo):
        common = Path(run_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip())
        hooks_path = run_git(repo, "config", "--get", "core.hooksPath").stdout.strip()
        self.assertTrue(hooks_path)
        self.assertNotEqual((repo / hooks_path).resolve(), (common / "hooks").resolve())
        local = common / "hooks" / "post-merge"
        local.parent.mkdir(exist_ok=True)
        local.write_text(f"#!/bin/sh\necho {LOCAL_MARK}\n")
        local.chmod(local.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def test_vo8_f5_post_merge_moves_nothing_and_runs_the_local_hook(self):
        record = "agent-docs/progress/1111111111111111-merged.md"
        for label, rel, advance_main, flags in (
                ("fast-forward with a former progress record", record, False, ("--ff-only",)),
                ("true merge", "src/feature.py", True, ("--no-ff", "--no-edit"))):
            with self.subTest(case=label):
                repo = self.new_repo()
                self.install_local_post_merge(repo)
                main = self.branch(repo)
                run_git(repo, "checkout", "-q", "-b", "feature")
                (repo / rel).parent.mkdir(parents=True, exist_ok=True)
                (repo / rel).write_text("# merged\n")
                run_git(repo, "add", "--", rel)
                self.commit(repo, "feature work")
                run_git(repo, "checkout", "-q", main)
                if advance_main:
                    (repo / "src" / "main_only.py").write_text("m = 1\n")
                    run_git(repo, "add", "-A")
                    self.commit(repo, "main work")

                result = subprocess.run(["git", "-C", str(repo), "merge", *flags, "feature"], stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, env=self.env())

                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn(LOCAL_MARK, result.stdout)
                self.assertNotIn("Traceback", result.stdout)
                self.assertEqual((repo / rel).read_text(), "# merged\n")
                self.assertFalse((repo / "agent-docs" / "progress-logs").exists())

    def precommit_outcome(self, directory, files):
        repo = self.new_repo()
        for name, text in files.items():
            path = repo / "agent-docs" / directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        run_git(repo, "add", "-A")
        run_git(repo, "add", "-f", "--", f"agent-docs/{directory}")
        result = self.commit_with_hooks(repo, "record")

        def normalized(text):
            for root in {str(repo), str(repo.resolve())}:
                text = text.replace(root, "<repo>")
            return text.replace(f"agent-docs/{directory}", "agent-docs/DIR").replace(f"{directory}/", "DIR/")

        return result.returncode, normalized(result.stdout), normalized(result.stderr)

    def test_vo8_f8_c31_former_progress_directory_is_checked_like_any_other_directory(self):
        name = "0123456789abcdef-x.md"
        well_formed = "# Record\n\n## Next Step\ndo it\n"
        index = f"File: {name}\nSummary: s\nRelated Files: none\nRelated Symbols: none\n"
        cases = {
            "well-formed with index": {name: well_formed, "index.md": index},
            "well-formed without index": {name: well_formed},
            "malformed pair": {name: "no heading here\n", "0123456789abcdee-y.md": "no heading either\n"},
        }
        for label, files in cases.items():
            with self.subTest(case=label):
                self.assertEqual(self.precommit_outcome("progress", files), self.precommit_outcome("notes", files))

    def test_vo8_f9_installed_config_has_no_progress_paths_and_pre_commit_no_sync_progress(self):
        repo = self.new_repo()
        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, str(Path('.harness/lib').resolve()))\n"
            "import config\n"
            "try:\n"
            "    paths = config.load_paths()\n"
            "except TypeError:\n"
            "    paths = config.load_paths(Path.cwd())\n"
            "names = list(paths) if isinstance(paths, dict) else dir(paths)\n"
            "print(json.dumps({'progress': hasattr(paths, 'progress'), 'progress_logs': hasattr(paths, 'progress_logs'),"
            " 'names': [n for n in names if 'progress' in str(n)]}))\n"
        )
        result = subprocess.run([sys.executable, "-c", script], cwd=repo, capture_output=True, text=True, env=self.env())
        self.assertEqual(result.returncode, 0, out(result))
        self.assertEqual(json.loads(result.stdout), {"progress": False, "progress_logs": False, "names": []})
        self.assertNotIn("sync_progress", (repo / ".harness" / "git" / "pre-commit").read_text())

    def test_vo8_f7_no_harness_or_installer_module_imports_progress(self):
        importers = []
        files = sorted([*(REPO_ROOT / "harness").rglob("*.py"), *(REPO_ROOT / "installer").rglob("*.py")])
        self.assertTrue(files)
        for path in files:
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [alias.name for alias in node.names]
                elif (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
                      and isinstance(node.args[0].value, str)
                      and getattr(node.func, "attr", getattr(node.func, "id", "")) in ("import_module", "__import__")):
                    names = [node.args[0].value]
                if any("progress" in name.split(".") for name in names):
                    importers.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
        self.assertEqual(importers, [])


def numbered_step(text, number):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{number}. **"))
    end = next((i for i, line in enumerate(lines) if i > start and (re.match(r"\d+\. \*\*", line) or line.startswith("#"))),
               len(lines))
    return "\n".join(lines[start:end])


class TestShippedText(unittest.TestCase):
    def source(self, *parts):
        return (REPO_ROOT / "harness" / Path(*parts)).read_text()

    def test_vo9_x1_principle_2_is_replaced_and_the_note_is_gone(self):
        base = base_file(BASE_0491, "harness/instructions/harness-block.md").splitlines()
        p2 = next(line for line in base if line.startswith("2. **Preserve Failed Attempts**"))
        p3 = next(line for line in base if line.startswith("3. **Record Observations, Not Mandates**"))
        lines = self.source("instructions", "harness-block.md").splitlines()
        self.assertNotIn(p2, lines)
        self.assertNotIn(PRINCIPLE_NOTE, lines)
        self.assertEqual(lines.count(p3), 1)
        self.assertTrue(lines[lines.index(p3) - 1].startswith("2. **Memory Has a Scope**"))
        self.assertLess(lines.index(p3), lines.index("### Comment Enforcement"))
        self.assertNotIn("progress", "\n".join(lines).lower())

    def test_vo9_x2_rule_files_table_keeps_four_rows_and_drops_progress(self):
        def rows(text):
            section = text.split("## Rule Files", 1)[1].split("\n#", 1)[0]
            return [line for line in section.splitlines() if line.startswith("| `")]

        base = [row for row in rows(base_file(BASE_0491, "harness/instructions/harness-block.md"))
                if not row.startswith("| `progress.md`")]
        current = rows(self.source("instructions", "harness-block.md"))
        self.assertEqual(current, base)
        self.assertEqual([row.split("`")[1] for row in current],
                         ["index-and-staleness.md", "try-n-fail.md", "todos.md", "synced-comments.md"])

    def test_vo9_x7_workflow_steps_1_and_9_carry_the_exact_fr10_strings(self):
        copies = {"shipped": REPO_ROOT / "harness" / "skills" / "doggy-workflow" / "SKILL.md",
                  "installed here": REPO_ROOT / ".agents" / "skills" / "doggy-workflow" / "SKILL.md"}
        for label, path in copies.items():
            with self.subTest(copy=label):
                text = skill_text.whole(path)
                step1, step9 = numbered_step(text, 1), numbered_step(text, 9)
                self.assertIn(STEP1_RESUME, step1)
                self.assertNotIn("/continue-on", step1)
                self.assertIn(STEP9_LIMIT, step9)
                self.assertIn(STEP9_HANDOFF, step9)
                self.assertNotIn("progress path", step9)
                self.assertNotIn("continue-on", text)
                self.assertNotIn("agent-docs/progress", text)

    def test_vo9_x4_try_n_fail_rule_names_no_progress_source(self):
        self.assertNotIn("progress", self.source("instructions", "try-n-fail.md").lower())

    def test_vo9_x5_index_rule_names_no_progress_directories(self):
        text = self.source("instructions", "index-and-staleness.md")
        for needle in ("agent-docs/progress", "progress-logs", "`progress/`"):
            self.assertNotIn(needle, text)

    def test_vo9_x6_this_repository_is_updated_past_0500(self):
        self.assertEqual((REPO_ROOT / "harness" / "VERSION").read_text().strip(), "0.56.0")
        self.assertEqual(json.loads((REPO_ROOT / ".harness" / "manifest.json").read_text())["version"], "0.56.0")
        for rel in ("agent-docs/progress", "agent-docs/progress-logs"):
            self.assertFalse(os.path.lexists(REPO_ROOT / rel), rel)


if __name__ == "__main__":
    unittest.main()
