import copy
import json

from customization_case import CustomizationCase
from old_release import BASE_0470, BASE_0551
from test_installer import run_installer

LINE = ("{path} already exists; a repository's own git hook now lives at .harness/local/git/{name}: move it there "
        "(git mv) and run update again")
OWN_HOOK = "#!/bin/sh\necho my own hook\n"


class TestExistingGitHooks(CustomizationCase):
    def conflict_lines(self, result):
        self.assertIn("== conflict ==", result.stdout)
        section = result.stdout.split("== conflict ==", 1)[1].split("\n== ", 1)[0]
        return [line.strip().removeprefix("- ") for line in section.splitlines()]

    def old_with_hook(self, commit, name):
        repo = self.install_old(commit)
        self.set_definition(repo)
        path = self.write(repo, f".harness/git/{name}", OWN_HOOK, 0o755)
        return repo, path

    def assert_refused(self, commit, name):
        repo, path = self.old_with_hook(commit, name)
        snapshot = self.snapshot(repo)
        manifest = (repo / ".harness" / "manifest.json").read_bytes()
        porcelain = self.porcelain(repo)
        result = run_installer("update", str(repo), "--no-ci", "--no-commit", input="y\n" * 80, exact=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(LINE.format(path=f".harness/git/{name}", name=name), self.conflict_lines(result))
        self.assertEqual(self.snapshot(repo), snapshot)
        self.assertEqual((repo / ".harness" / "manifest.json").read_bytes(), manifest)
        self.assertEqual(self.porcelain(repo), porcelain)
        self.assertEqual(path.read_text(), OWN_HOOK)
        return repo

    def assert_moves_and_updates(self, repo, name):
        local = repo / ".harness" / "local" / "git"
        local.mkdir(parents=True)
        (repo / ".harness" / "git" / name).rename(local / name)
        result = run_installer("update", str(repo), "--no-ci", "--no-commit", input="y\n" * 80, exact=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((local / name).read_text(), OWN_HOOK)
        self.assertNotEqual((repo / ".harness" / "git" / name).read_text(), OWN_HOOK)
        lines = [l for l in self.status_lines(repo) if l.startswith(f"unconfirmed .harness/local/git/{name}")]
        self.assertEqual(lines, [f"unconfirmed .harness/local/git/{name} — compare with .harness/git/{name}"])

    def test_an_existing_pre_push_stops_update_from_0_55_1(self):
        repo = self.assert_refused(BASE_0551, "pre-push")
        self.assert_moves_and_updates(repo, "pre-push")

    def test_an_existing_post_checkout_stops_update_from_0_47_0(self):
        repo = self.assert_refused(BASE_0470, "post-checkout")
        self.assert_moves_and_updates(repo, "post-checkout")

    def test_install_stops_the_same_way_before_writing(self):
        repo = self.make_repo()
        self.write(repo, ".harness/git/pre-push", OWN_HOOK, 0o755)
        before = self.snapshot(repo)
        result = run_installer("install", str(repo), "--no-ci")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(LINE.format(path=".harness/git/pre-push", name="pre-push"), self.conflict_lines(result))
        self.assertEqual(self.snapshot(repo), before)

    def test_a_harness_hook_that_the_old_manifest_lists_is_no_conflict(self):
        repo = self.old_fixture_without_hooks()
        result = run_installer("update", str(repo), "--no-ci", "--no-commit", input="y\n" * 80, exact=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("already exists; a repository's own git hook", result.stdout)

    def old_fixture_without_hooks(self):
        repo = self.install_old(BASE_0551)
        self.set_definition(repo)
        return repo


def is_harness(group):
    commands = [h.get("command", "") for h in group.get("hooks", [])]
    return any("/.harness/" in c for c in commands) and not any("/.harness/local/" in c for c in commands)


def command_group(command, matcher=None):
    group = {"hooks": [{"type": "command", "command": command}]}
    if matcher:
        group["matcher"] = matcher
    return group


LOCAL_GROUP = command_group('python3 "$CLAUDE_PROJECT_DIR/.harness/local/hooks/lint.py"', "Write|Edit")
SCRIPTS_GROUP = command_group('python3 "$CLAUDE_PROJECT_DIR/scripts/x.py"', "Bash")
MIXED_GROUP = {"matcher": "Bash", "hooks": [
    {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.harness/hooks/spec_gate.py"'},
    {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.harness/local/hooks/lint.py"'}]}
STALE_HARNESS_GROUP = command_group('python3 "$CLAUDE_PROJECT_DIR/.harness/hooks/gone_in_new_version.py"', "Bash")


class TestHookGroupMerge(CustomizationCase):
    def prepare(self, repo, rel):
        path = repo / rel
        data = json.loads(path.read_text())
        before = copy.deepcopy(data)
        groups = data["hooks"].setdefault("PostToolUse", [])
        added = [LOCAL_GROUP, STALE_HARNESS_GROUP, SCRIPTS_GROUP, MIXED_GROUP]
        data["hooks"]["PostToolUse"] = added[:1] + groups + added[1:]
        self.write_owned_if_listed(repo, rel, json.dumps(data, indent=2) + "\n")
        return before

    def write_owned_if_listed(self, repo, rel, text):
        path = self.write(repo, rel, text)
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if rel in manifest.get("files", {}):
            from customization_case import sha256
            manifest["files"][rel] = sha256(path.read_bytes())
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    def assert_merge(self, rel):
        repo = self.project()
        self.write(repo, ".harness/local/hooks/lint.py", "print(1)\n")
        baseline = json.loads((repo / rel).read_text())["hooks"].get("PostToolUse", [])
        self.prepare(repo, rel)
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        merged = json.loads((repo / rel).read_text())["hooks"]["PostToolUse"]
        kept = [g for g in merged if not is_harness(g)]
        self.assertEqual(kept, [LOCAL_GROUP, SCRIPTS_GROUP, MIXED_GROUP])
        self.assertEqual([g for g in merged if is_harness(g)], [g for g in baseline if is_harness(g)])
        self.assertNotIn("gone_in_new_version", json.dumps(merged))
        positions = [merged.index(g) for g in (LOCAL_GROUP, SCRIPTS_GROUP, MIXED_GROUP)]
        self.assertEqual(positions, sorted(positions))
        return repo

    def test_claude_settings_keep_repository_and_mixed_groups_in_order_and_replace_harness_groups(self):
        self.assert_merge(".claude/settings.json")

    def test_codex_hooks_do_the_same(self):
        self.assert_merge(".codex/hooks.json")

    def test_a_second_update_changes_nothing(self):
        repo = self.assert_merge(".claude/settings.json")
        first = (repo / ".claude" / "settings.json").read_bytes()
        self.assertEqual(run_installer("update", str(repo)).returncode, 0)
        self.assertEqual((repo / ".claude" / "settings.json").read_bytes(), first)

    def test_groups_under_other_events_and_other_settings_keys_stay(self):
        repo = self.project()
        path = repo / ".claude" / "settings.json"
        data = json.loads(path.read_text())
        data["permissions"] = {"allow": ["Bash(ls)"]}
        data["hooks"].setdefault("Stop", []).append(command_group('python3 "$CLAUDE_PROJECT_DIR/.harness/local/hooks/stop.py"'))
        self.write_owned_if_listed(repo, ".claude/settings.json", json.dumps(data, indent=2) + "\n")
        self.assertEqual(run_installer("update", str(repo)).returncode, 0)
        merged = json.loads(path.read_text())
        self.assertEqual(merged["permissions"], {"allow": ["Bash(ls)"]})
        self.assertIn(command_group('python3 "$CLAUDE_PROJECT_DIR/.harness/local/hooks/stop.py"'), merged["hooks"]["Stop"])


class TestMissingReferencedScript(CustomizationCase):
    MISSING = "missing .harness/local/hooks/gone.py (referenced by .claude/settings.json)"

    def with_group(self, repo, rel, command):
        path = repo / rel
        data = json.loads(path.read_text())
        data["hooks"].setdefault("PostToolUse", []).append(command_group(command, "Write"))
        path.write_text(json.dumps(data, indent=2) + "\n")

    def test_a_group_that_references_a_missing_local_script_is_a_problem(self):
        repo = self.project()
        self.with_group(repo, ".claude/settings.json", 'python3 "$CLAUDE_PROJECT_DIR/.harness/local/hooks/gone.py"')
        self.assertIn(self.MISSING, self.status_lines(repo))

    def test_the_same_reference_with_the_script_present_is_no_problem(self):
        repo = self.project()
        self.with_group(repo, ".claude/settings.json", 'python3 "$CLAUDE_PROJECT_DIR/.harness/local/hooks/gone.py"')
        self.write(repo, ".harness/local/hooks/gone.py", "print(1)\n")
        self.assertFalse([l for l in self.status_lines(repo) if l.startswith("missing ")])

    def test_a_reference_from_the_codex_file_is_not_reported(self):
        repo = self.project()
        self.with_group(repo, ".codex/hooks.json", 'python3 "$CLAUDE_PROJECT_DIR/.harness/local/hooks/gone.py"')
        self.assertFalse([l for l in self.status_lines(repo) if l.startswith("missing ")])

    def test_a_reference_outside_the_local_directory_is_not_reported(self):
        repo = self.project()
        self.with_group(repo, ".claude/settings.json", 'python3 "$CLAUDE_PROJECT_DIR/scripts/not-there.py"')
        self.assertFalse([l for l in self.status_lines(repo) if l.startswith("missing ")])

    def test_the_problem_shows_in_doctor_manual_review_without_failing_it(self):
        repo = self.project()
        self.with_group(repo, ".claude/settings.json", 'python3 "$CLAUDE_PROJECT_DIR/.harness/local/hooks/gone.py"')
        result = run_installer("doctor", str(repo))
        self.assertIn(self.MISSING, result.stdout)
