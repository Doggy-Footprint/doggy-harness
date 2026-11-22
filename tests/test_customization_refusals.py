import json
import os

from customization_case import CustomizationCase
from test_installer import SKILLS, run_installer

EDITED = (
    "{path}: edited in place; harness files are not edited. Move the change to a customization (see README), "
    "delete {path}, and run update again to restore it"
)
CONFIG_FORMS = {"truncated json": '{"auto_install": false,', "array": "[]", "string": '"x"'}
SHADOW = ("{path} already exists and is not the harness link; rename the repository's own skill and run update "
          "again")


class RefusalCase(CustomizationCase):
    def fresh(self):
        return self.installed_copy("--no-ci")[0]

    def state(self, repo):
        return (self.snapshot(repo), self.porcelain(repo), (repo / ".harness" / "manifest.json").read_bytes())

    def conflict_lines(self, result):
        self.assertIn("== conflict ==", result.stdout)
        section = result.stdout.split("== conflict ==", 1)[1].split("\n== ", 1)[0]
        return [line.strip().removeprefix("- ") for line in section.splitlines()]

    def assert_refused(self, repo, result, line, before):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(line, self.conflict_lines(result))
        self.assertEqual(self.state(repo), before)


class TestEditedFiles(RefusalCase):
    PATHS = (".harness/hooks/spec_gate.py", ".harness/customization.json", ".claude/agents/implementer.md",
             ".harness/skills/doggy-workflow/phases.json")

    def test_an_edited_owned_file_stops_update_and_dry_run_before_any_write(self):
        for rel in self.PATHS:
            for args in ((), ("--dry-run",)):
                with self.subTest(file=rel, args=args):
                    repo = self.fresh()
                    path = repo / rel
                    path.write_bytes(path.read_bytes() + b"\n local edit \n")
                    edited = path.read_bytes()
                    before = self.state(repo)
                    result = run_installer("update", str(repo), *args)
                    self.assert_refused(repo, result, EDITED.format(path=rel), before)
                    self.assertEqual(path.read_bytes(), edited)

    def test_every_edited_file_gets_its_own_line(self):
        repo = self.fresh()
        for rel in self.PATHS[:2]:
            (repo / rel).write_bytes((repo / rel).read_bytes() + b"\nedit\n")
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 1)
        for rel in self.PATHS[:2]:
            self.assertIn(EDITED.format(path=rel), self.conflict_lines(result))

    def test_a_file_edited_to_exactly_the_new_content_is_not_a_conflict(self):
        repo = self.fresh()
        rel = ".harness/hooks/spec_gate.py"
        new = (repo / rel).read_bytes()
        self.write_owned(repo, rel, b"# an older release's text\n")
        (repo / rel).write_bytes(new)
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("edited in place", result.stdout)
        self.assertEqual((repo / rel).read_bytes(), new)

    def test_a_deleted_owned_file_is_written_again_without_a_conflict(self):
        repo = self.fresh()
        rel = ".harness/hooks/spec_gate.py"
        original = (repo / rel).read_bytes()
        (repo / rel).unlink()
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("== conflict ==", result.stdout)
        self.assertEqual((repo / rel).read_bytes(), original)

    def test_a_deleted_owned_file_is_not_a_conflict_in_dry_run_either(self):
        repo = self.fresh()
        (repo / ".harness" / "hooks" / "spec_gate.py").unlink()
        result = run_installer("update", str(repo), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("== conflict ==", result.stdout)

    def test_an_edited_file_that_the_new_version_no_longer_ships_is_a_conflict(self):
        repo = self.fresh()
        rel = ".harness/hooks/dropped_hook.py"
        self.write_owned(repo, rel, "# shipped once\n")
        (repo / rel).write_text("# shipped once\n# and then edited\n")
        before = self.state(repo)
        result = run_installer("update", str(repo))
        self.assert_refused(repo, result, EDITED.format(path=rel), before)
        self.assertEqual((repo / rel).read_text(), "# shipped once\n# and then edited\n")

    def test_an_unedited_file_that_the_new_version_no_longer_ships_is_not_a_conflict(self):
        repo = self.fresh()
        rel = ".harness/hooks/dropped_hook.py"
        self.write_owned(repo, rel, "# shipped once\n")
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("edited in place", result.stdout)


class TestShadowingSkills(RefusalCase):
    def other_skill(self):
        return next(s for s in SKILLS if s != "doggy-workflow")

    def test_a_repository_skill_that_shadows_a_shipped_skill_stops_update(self):
        name = self.other_skill()
        repo = self.fresh()
        link = repo / ".claude" / "skills" / name
        self.assertTrue(link.is_symlink())
        link.unlink()
        self.write(repo, f".claude/skills/{name}/SKILL.md", "my own skill\n")
        before = self.state(repo)
        result = run_installer("update", str(repo))
        self.assert_refused(repo, result, SHADOW.format(path=f".claude/skills/{name}"), before)
        self.assertEqual((repo / ".claude" / "skills" / name / "SKILL.md").read_text(), "my own skill\n")

    def test_the_shadowing_skill_stops_a_dry_run_too(self):
        name = self.other_skill()
        repo = self.fresh()
        (repo / ".claude" / "skills" / name).unlink()
        self.write(repo, f".claude/skills/{name}/SKILL.md", "my own skill\n")
        before = self.state(repo)
        result = run_installer("update", str(repo), "--dry-run")
        self.assert_refused(repo, result, SHADOW.format(path=f".claude/skills/{name}"), before)

    def test_a_symlink_that_points_elsewhere_is_not_the_harness_link(self):
        name = self.other_skill()
        repo = self.fresh()
        link = repo / ".claude" / "skills" / name
        link.unlink()
        link.symlink_to("../../somewhere-else")
        before = self.state(repo)
        result = run_installer("update", str(repo))
        self.assert_refused(repo, result, SHADOW.format(path=f".claude/skills/{name}"), before)

    def test_the_harness_symlink_is_no_conflict(self):
        repo = self.fresh()
        for name in SKILLS:
            self.assertEqual(os.readlink(repo / ".claude" / "skills" / name), f"../../.agents/skills/{name}")
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("already exists and is not the harness link", result.stdout)


class TestInvalidConfig(RefusalCase):
    LINE = ".harness/config.json: not a JSON object ("

    def assert_config_line(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        lines = self.conflict_lines(result)
        self.assertTrue(any(l.startswith(self.LINE) and l.endswith(")") for l in lines), lines)

    def test_install_stops_before_writing_on_each_invalid_config(self):
        for name, raw in CONFIG_FORMS.items():
            with self.subTest(config=name):
                repo = self.make_repo()
                self.write(repo, ".harness/config.json", raw)
                before = self.snapshot(repo)
                result = run_installer("install", str(repo), "--no-ci")
                self.assert_config_line(result)
                self.assertEqual(self.snapshot(repo), before)
                self.assertFalse((repo / ".harness" / "manifest.json").exists())

    def test_update_and_dry_run_stop_before_writing_on_each_invalid_config(self):
        for name, raw in CONFIG_FORMS.items():
            for args in ((), ("--dry-run",)):
                with self.subTest(config=name, args=args):
                    repo = self.fresh()
                    self.write(repo, ".harness/config.json", raw)
                    before = self.state(repo)
                    result = run_installer("update", str(repo), *args)
                    self.assert_config_line(result)
                    self.assertEqual(self.state(repo), before)

    def test_a_valid_config_is_no_conflict_for_install_and_update(self):
        repo = self.make_repo()
        self.write(repo, ".harness/config.json", json.dumps({"agent_model": "opus"}))
        result = run_installer("install", str(repo), "--no-ci")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        updated = run_installer("update", str(repo))
        self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
        self.assertEqual(json.loads((repo / ".harness" / "config.json").read_text()), {"agent_model": "opus"})

    def test_an_unknown_key_alone_is_no_conflict(self):
        repo = self.fresh()
        self.write(repo, ".harness/config.json", json.dumps({"auto_instal": False}))
        result = run_installer("update", str(repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
