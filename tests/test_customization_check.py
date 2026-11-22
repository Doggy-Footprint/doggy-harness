import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from customization_case import copy_source
from test_installer import REPO_ROOT, InstallerTestCase, run_git, run_installer

WARNING = re.compile(r"^customization: changes to (.+) will ask repositories with a customization at (.+) to review "
                     r"it after update$", re.M)
_TEMPLATE = {}


def template_repo():
    if "dir" not in _TEMPLATE:
        tmp = tempfile.TemporaryDirectory()
        _TEMPLATE["tmp"] = tmp
        root = Path(tmp.name) / "template"
        root.mkdir()
        copy_source(root)
        run_git(root, "init", "-q")
        run_git(root, "config", "user.email", "test@test.com")
        run_git(root, "config", "user.name", "test")
        run_git(root, "add", "-A")
        run_git(root, "commit", "-q", "--no-verify", "-m", "base")
        _TEMPLATE["dir"] = root
    return _TEMPLATE["dir"]


def remove_phase(root, name="verify", from_names=True):
    phases = root / "harness" / "skills" / "doggy-workflow" / "phases.json"
    data = json.loads(phases.read_text())
    data.pop(name)
    phases.write_text(json.dumps(data, indent=2) + "\n")
    edit_declaration(root, lambda d: [p["names"].remove(name) for p in d["points"]
                                      if p["id"] == "phase-rules" and from_names])


def edit_declaration(root, edit):
    path = root / "harness" / "customization.json"
    data = json.loads(path.read_text())
    edit(data)
    path.write_text(json.dumps(data, indent=2) + "\n")


def point(data, point_id):
    return next(p for p in data["points"] if p["id"] == point_id)


class CheckCase(InstallerTestCase):
    def repo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        shutil.copytree(template_repo(), repo, symlinks=True)
        return repo

    def check(self, repo, *args):
        return subprocess.run([sys.executable, str(repo / "installer" / "customization_check.py"), *args],
                              cwd=repo, capture_output=True, text=True)

    def output(self, result):
        return result.stdout + result.stderr

    def commit_all(self, repo, message="change"):
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-q", "--no-verify", "-m", message)

    def failure_lines(self, result):
        return [l for l in self.output(result).splitlines() if l.strip() and not WARNING.match(l)]

    def assert_fails_naming(self, result, *names):
        self.assertEqual(result.returncode, 1, self.output(result))
        lines = self.failure_lines(result)
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(any(name in line for line in lines), (name, lines))


class TestCheckBaseline(CheckCase):
    def test_the_unchanged_copy_passes_with_no_output_lines_of_failure(self):
        repo = self.repo()
        result = self.check(repo)
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(self.failure_lines(result), [])
        staged = self.check(repo, "--staged")
        self.assertEqual(staged.returncode, 0, self.output(staged))


class TestCompareWarnings(CheckCase):
    def test_c38_a_phase_fragment_change_warns_naming_phase_rules_and_exits_0(self):
        repo = self.repo()
        phases = json.loads((repo / "harness" / "skills" / "doggy-workflow" / "phases.json").read_text())
        entry = phases["verify"][0]
        fragment = entry if isinstance(entry, str) else entry["name"]
        path = repo / "harness" / "skills" / "doggy-workflow" / "phases" / f"{fragment}.md"
        path.write_text(path.read_text() + "\nA new harness sentence.\n")
        result = self.check(repo)
        self.assertEqual(result.returncode, 0, self.output(result))
        found = WARNING.search(self.output(result))
        self.assertIsNotNone(found, self.output(result))
        self.assertIn(f"{fragment}.md", found[1])
        self.assertIn("phase-rules", found[2])
        self.assertEqual(self.failure_lines(result), [])

    def test_changes_to_other_compare_paths_name_their_points(self):
        cases = {
            "harness/instructions/harness-block.md": "project-instructions",
            "harness/git/pre-push": "git-hook",
            "harness/agents/implementer.md": "agent-instructions",
            "harness/hooks/hooks.spec.json": "hook-script",
        }
        for rel, point_id in cases.items():
            with self.subTest(changed=rel):
                repo = self.repo()
                path = repo / rel
                path.write_bytes(path.read_bytes() + b"\n")
                result = self.check(repo)
                self.assertEqual(result.returncode, 0, self.output(result))
                found = WARNING.search(self.output(result))
                self.assertIsNotNone(found, self.output(result))
                self.assertIn(rel.rsplit("/", 1)[1], found[1])
                self.assertIn(point_id, found[2])

    def test_a_change_to_a_file_that_is_no_compare_path_does_not_warn(self):
        repo = self.repo()
        path = repo / "harness" / "hooks" / "spec_gate.py"
        path.write_bytes(path.read_bytes() + b"\n# x\n")
        result = self.check(repo)
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIsNone(WARNING.search(self.output(result)))

    def test_staged_looks_at_the_index_and_the_default_at_the_working_tree(self):
        repo = self.repo()
        path = repo / "harness" / "instructions" / "harness-block.md"
        path.write_bytes(path.read_bytes() + b"\nnew\n")
        self.assertIsNone(WARNING.search(self.output(self.check(repo, "--staged"))))
        self.assertIsNotNone(WARNING.search(self.output(self.check(repo))))
        run_git(repo, "add", "harness/instructions/harness-block.md")
        self.assertIsNotNone(WARNING.search(self.output(self.check(repo, "--staged"))))
        run_git(repo, "restore", "--worktree", "--source=HEAD", "--", "harness/instructions/harness-block.md")
        self.assertIsNotNone(WARNING.search(self.output(self.check(repo, "--staged"))))
        self.assertIsNone(WARNING.search(self.output(self.check(repo))))


class TestRemovals(CheckCase):
    def test_c39_a_removed_phase_without_retirement_fails_naming_the_phase(self):
        repo = self.repo()
        remove_phase(repo)
        self.assert_fails_naming(self.check(repo), "verify")

    def test_c39_a_retired_entry_whose_version_has_no_migration_still_fails(self):
        repo = self.repo()
        remove_phase(repo)
        edit_declaration(repo, lambda d: d.setdefault("retired", []).append(
            {"path": ".harness/local/doggy-workflow/verify.md", "version": "0.46.0", "note": "Renamed."}))
        self.assert_fails_naming(self.check(repo), "verify")

    def test_c39_a_retired_entry_whose_version_has_a_migration_passes(self):
        repo = self.repo()
        remove_phase(repo)
        edit_declaration(repo, lambda d: d.setdefault("retired", []).append(
            {"path": ".harness/local/doggy-workflow/verify.md", "version": "0.56.0", "note": "Renamed."}))
        result = self.check(repo)
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(self.failure_lines(result), [])

    def test_a_retired_version_above_the_harness_version_fails(self):
        repo = self.repo()
        (repo / "harness" / "VERSION").write_text("0.55.1\n")
        remove_phase(repo)
        edit_declaration(repo, lambda d: d.setdefault("retired", []).append(
            {"path": ".harness/local/doggy-workflow/verify.md", "version": "0.56.0", "note": "Renamed."}))
        self.assert_fails_naming(self.check(repo), "verify")

    def test_a_removed_point_id_fails_naming_the_point(self):
        repo = self.repo()
        edit_declaration(repo, lambda d: d["points"].remove(point(d, "hook-script")))
        self.assert_fails_naming(self.check(repo), "hook-script")

    def test_a_removed_config_key_fails_naming_the_key(self):
        repo = self.repo()
        edit_declaration(repo, lambda d: d["config_keys"].remove("exclude_dirs"))
        self.assert_fails_naming(self.check(repo), "exclude_dirs")

    def test_a_retired_point_id_passes(self):
        repo = self.repo()
        path = point(json.loads((repo / "harness" / "customization.json").read_text()), "hook-script")["path"]

        def edit(d):
            d["points"].remove(point(d, "hook-script"))
            d.setdefault("retired", []).append({"path": path, "version": "0.56.0", "note": "Removed."})

        edit_declaration(repo, edit)
        result = self.check(repo)
        self.assertEqual(result.returncode, 0, self.output(result))

    def test_a_retired_config_key_passes_when_the_key_is_also_gone_from_the_defaults(self):
        repo = self.repo()
        defaults = repo / "harness" / "config.default.json"
        data = json.loads(defaults.read_text())
        data.pop("exclude_dirs")
        defaults.write_text(json.dumps(data, indent=2) + "\n")

        def edit(d):
            d["config_keys"].remove("exclude_dirs")
            d.setdefault("retired", []).append({"path": "exclude_dirs", "version": "0.56.0", "note": "Removed."})

        edit_declaration(repo, edit)
        result = self.check(repo)
        self.assertEqual(result.returncode, 0, self.output(result))

    def test_a_removed_config_key_without_retirement_fails_even_when_the_defaults_dropped_it(self):
        repo = self.repo()
        defaults = repo / "harness" / "config.default.json"
        data = json.loads(defaults.read_text())
        data.pop("exclude_dirs")
        defaults.write_text(json.dumps(data, indent=2) + "\n")
        edit_declaration(repo, lambda d: d["config_keys"].remove("exclude_dirs"))
        self.assert_fails_naming(self.check(repo), "exclude_dirs")

    def test_a_retired_entry_with_a_different_path_does_not_cover_a_removed_point_id(self):
        repo = self.repo()

        def edit(d):
            d["points"].remove(point(d, "hook-script"))
            d.setdefault("retired", []).append(
                {"path": ".harness/local/other/**", "version": "0.56.0", "note": "Removed."})

        edit_declaration(repo, edit)
        self.assert_fails_naming(self.check(repo), "hook-script")

    def test_a_retired_entry_for_another_name_does_not_cover_a_removed_name(self):
        repo = self.repo()
        remove_phase(repo)
        edit_declaration(repo, lambda d: d.setdefault("retired", []).append(
            {"path": ".harness/local/doggy-workflow/old.md", "version": "0.56.0", "note": "Renamed."}))
        self.assert_fails_naming(self.check(repo), "verify")

    def test_a_retired_entry_for_another_key_does_not_cover_a_removed_config_key(self):
        repo = self.repo()
        defaults = repo / "harness" / "config.default.json"
        data = json.loads(defaults.read_text())
        data.pop("exclude_dirs")
        defaults.write_text(json.dumps(data, indent=2) + "\n")

        def edit(d):
            d["config_keys"].remove("exclude_dirs")
            d.setdefault("retired", []).append({"path": "some_other_key", "version": "0.56.0", "note": "Removed."})

        edit_declaration(repo, edit)
        self.assert_fails_naming(self.check(repo), "exclude_dirs")

    def test_a_removed_git_hook_name_fails_naming_the_name(self):
        repo = self.repo()
        edit_declaration(repo, lambda d: point(d, "git-hook")["names"].remove("pre-auto-gc"))
        run_git(repo, "rm", "-q", "harness/git/pre-auto-gc")
        self.assert_fails_naming(self.check(repo), "pre-auto-gc")

    def test_a_removal_that_is_already_committed_is_judged_against_the_declaration_at_head(self):
        repo = self.repo()
        remove_phase(repo)
        self.assert_fails_naming(self.check(repo), "verify")
        self.commit_all(repo)
        result = self.check(repo)
        self.assertEqual(result.returncode, 0, self.output(result))

    def test_staged_judges_the_index_and_the_default_the_working_tree(self):
        repo = self.repo()
        remove_phase(repo)
        self.assertEqual(self.check(repo).returncode, 1)
        self.assertEqual(self.check(repo, "--staged").returncode, 0, "nothing is staged yet")
        run_git(repo, "add", "-A")
        self.assert_fails_naming(self.check(repo, "--staged"), "verify")
        run_git(repo, "restore", "--worktree", "--source=HEAD", "--", ".")
        self.assertEqual(self.check(repo).returncode, 0)
        self.assert_fails_naming(self.check(repo, "--staged"), "verify")


class TestDeclarationRules(CheckCase):
    def committed(self, repo, edit):
        edit_declaration(repo, edit)
        self.commit_all(repo)

    def test_c40_a_declared_git_hook_without_its_file_fails(self):
        repo = self.repo()
        self.committed(repo, lambda d: point(d, "git-hook")["names"].append("pre-receive"))
        self.assert_fails_naming(self.check(repo), "pre-receive")

    def test_c40_an_agent_name_that_is_not_in_the_agents_directory_fails(self):
        repo = self.repo()
        self.committed(repo, lambda d: point(d, "agent-instructions")["names"].append("ghost"))
        self.assert_fails_naming(self.check(repo), "ghost")

    def test_c40_an_agent_file_that_is_not_declared_fails(self):
        repo = self.repo()
        agents = repo / "harness" / "agents"
        shutil.copy(agents / "implementer.md", agents / "extra-agent.md")
        text = (agents / "extra-agent.md").read_text()
        (agents / "extra-agent.md").write_text(re.sub(r"(?m)^name: .*$", "name: extra-agent", text, count=1))
        self.commit_all(repo)
        self.assert_fails_naming(self.check(repo), "extra-agent")

    def test_c40_a_phase_declared_that_phases_json_lacks_fails(self):
        repo = self.repo()
        self.committed(repo, lambda d: point(d, "phase-rules")["names"].append("ghost-phase"))
        self.assert_fails_naming(self.check(repo), "ghost-phase")

    def test_c40_a_phase_in_phases_json_that_is_not_declared_fails(self):
        repo = self.repo()
        phases = repo / "harness" / "skills" / "doggy-workflow" / "phases.json"
        data = json.loads(phases.read_text())
        data["extra-phase"] = list(data["verify"])
        phases.write_text(json.dumps(data, indent=2) + "\n")
        self.commit_all(repo)
        self.assert_fails_naming(self.check(repo), "extra-phase")

    def test_c40_a_config_default_key_missing_from_config_keys_fails(self):
        repo = self.repo()
        self.committed(repo, lambda d: d["config_keys"].remove("auto_install"))
        self.assert_fails_naming(self.check(repo), "auto_install")

    def test_c40_a_compare_path_that_does_not_exist_fails(self):
        repo = self.repo()
        self.committed(repo, lambda d: point(d, "project-instructions")["compare"].append(
            ".harness/instructions/no-such-file.md"))
        self.assert_fails_naming(self.check(repo), "no-such-file.md")

    def test_c40_a_compare_path_with_a_name_placeholder_is_checked_for_every_name(self):
        repo = self.repo()
        self.committed(repo, lambda d: point(d, "git-hook").update(compare=[".harness/git/{name}-missing"]))
        self.assert_fails_naming(self.check(repo), "-missing")

    def test_c40_invalid_json_fails_naming_the_declaration(self):
        repo = self.repo()
        (repo / "harness" / "customization.json").write_text("{")
        self.assert_fails_naming(self.check(repo), "customization.json")

    def test_c40_a_missing_declaration_fails(self):
        repo = self.repo()
        (repo / "harness" / "customization.json").unlink()
        self.assert_fails_naming(self.check(repo), "customization.json")

    def test_two_failures_get_one_line_each(self):
        repo = self.repo()
        self.committed(repo, lambda d: (point(d, "git-hook")["names"].append("pre-receive"),
                                        point(d, "agent-instructions")["names"].append("ghost")))
        result = self.check(repo)
        self.assertEqual(result.returncode, 1)
        lines = self.failure_lines(result)
        self.assertEqual(len([l for l in lines if "pre-receive" in l]), 1, lines)
        self.assertEqual(len([l for l in lines if "ghost" in l]), 1, lines)

    def test_every_failure_line_names_a_repository_relative_item_and_something_to_do(self):
        repo = self.repo()
        self.committed(repo, lambda d: point(d, "project-instructions")["compare"].append(
            ".harness/instructions/no-such-file.md"))
        lines = [l for l in self.failure_lines(self.check(repo)) if "no-such-file.md" in l]
        self.assertTrue(lines)
        for line in lines:
            self.assertGreater(len(line.split()), 3, line)
            self.assertNotIn(str(repo), line)


class TestDogfoodWiring(InstallerTestCase):
    LOCAL_HOOK = REPO_ROOT / ".harness" / "local" / "git" / "pre-commit"

    def test_e2_the_check_passes_on_this_repositorys_working_tree(self):
        result = subprocess.run([sys.executable, str(REPO_ROOT / "installer" / "customization_check.py")],
                                cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_e1_the_local_pre_commit_exists_and_is_executable(self):
        self.assertTrue(self.LOCAL_HOOK.is_file(), "this repository's .harness/local/git/pre-commit is missing")
        self.assertTrue(os.access(self.LOCAL_HOOK, os.X_OK))

    def clone(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        repo.mkdir()
        run_git(repo, "init", "-q")
        run_git(repo, "config", "user.email", "test@test.com")
        run_git(repo, "config", "user.name", "test")
        installed = run_installer("install", str(repo), "--no-ci")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        copy_source(repo)
        target = repo / ".harness" / "local" / "git" / "pre-commit"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.LOCAL_HOOK, target)
        run_git(repo, "config", "core.hooksPath", ".harness/git")
        run_git(repo, "add", "-A", "-f")
        run_git(repo, "commit", "-q", "--no-verify", "-m", "base")
        return repo

    def commit(self, repo, message):
        return subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", message,], capture_output=True,
                              text=True)

    def test_e1_the_local_pre_commit_refuses_a_staged_removal_without_retirement(self):
        if not self.LOCAL_HOOK.is_file():
            self.fail("this repository's .harness/local/git/pre-commit is missing")
        repo = self.clone()
        remove_phase(repo)
        run_git(repo, "add", "-A")
        before = run_git(repo, "rev-parse", "HEAD").stdout
        result = self.commit(repo, "drop the verify phase\n\nRequest: test\nIntent: test")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(run_git(repo, "rev-parse", "HEAD").stdout, before)
        self.assertIn("verify", result.stdout + result.stderr)

    def test_e1_a_staged_violation_is_refused_although_the_working_tree_is_clean_again(self):
        if not self.LOCAL_HOOK.is_file():
            self.fail("this repository's .harness/local/git/pre-commit is missing")
        repo = self.clone()
        remove_phase(repo)
        run_git(repo, "add", "-A")
        run_git(repo, "restore", "--worktree", "--source=HEAD", "--", ".")
        before = run_git(repo, "rev-parse", "HEAD").stdout
        result = self.commit(repo, "drop the verify phase\n\nRequest: test\nIntent: test")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(run_git(repo, "rev-parse", "HEAD").stdout, before)

    def test_e1_a_clean_stage_is_committed_although_the_working_tree_holds_a_violation(self):
        if not self.LOCAL_HOOK.is_file():
            self.fail("this repository's .harness/local/git/pre-commit is missing")
        repo = self.clone()
        (repo / "notes.txt").write_text("a note\n")
        run_git(repo, "add", "notes.txt")
        remove_phase(repo)
        before = run_git(repo, "rev-parse", "HEAD").stdout
        result = self.commit(repo, "add a note\n\nRequest: test\nIntent: test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(run_git(repo, "rev-parse", "HEAD").stdout, before)

    def test_e1_the_local_pre_commit_lets_a_clean_staged_change_through(self):
        if not self.LOCAL_HOOK.is_file():
            self.fail("this repository's .harness/local/git/pre-commit is missing")
        repo = self.clone()
        (repo / "notes.txt").write_text("a note\n")
        run_git(repo, "add", "notes.txt")
        before = run_git(repo, "rev-parse", "HEAD").stdout
        result = self.commit(repo, "add a note\n\nRequest: test\nIntent: test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(run_git(repo, "rev-parse", "HEAD").stdout, before)
