import json
import re
import subprocess
import sys
from pathlib import Path

from test_installer import InstallerTestCase, run_git, run_installer

SPEC_NAME = "0123456789abcdef-sample.md"
SPEC_TEXT = """---
version: 1
run_id: 0123456789abcdef
status: active
---

# Version Log
## v1
- Initial.
"""


class DocRecordsTestCase(InstallerTestCase):
    def installed(self, *args):
        return self.installed_copy("--no-ci", *args)

    def commit_all(self, repo, message="base"):
        run_git(repo, "add", "-A")
        return subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", message], capture_output=True, text=True
        )

    def head(self, repo):
        return run_git(repo, "rev-parse", "HEAD").stdout.strip()

    def run_doc_hook(self, repo, file_path, tool="Write"):
        payload = {"hook_event_name": "PostToolUse", "tool_name": tool, "cwd": str(repo),
                   "tool_input": {"file_path": str(file_path)}}
        return subprocess.run(
            [sys.executable, str(repo / ".harness" / "hooks" / "doc_commit.py")],
            input=json.dumps(payload), capture_output=True, text=True,
        )


class TestCommitStamp(DocRecordsTestCase):
    def test_new_document_gets_frontmatter_with_head(self):
        repo, _ = self.installed()
        self.assertEqual(self.commit_all(repo).returncode, 0)
        doc = repo / "agent-docs" / "try-n-fail" / "1111111111111111-task.md"
        doc.write_text("# Task\n")
        self.assertEqual(self.run_doc_hook(repo, doc).returncode, 0)
        self.assertEqual(doc.read_text(), f"---\ncommit: {self.head(repo)}\n---\n\n# Task\n")

    def test_existing_frontmatter_gains_or_replaces_commit_only(self):
        repo, _ = self.installed()
        self.assertEqual(self.commit_all(repo).returncode, 0)
        spec = repo / "agent-docs" / "specs" / SPEC_NAME
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("---\nversion: 1\n---\n\n# Body\n")
        self.run_doc_hook(repo, spec, tool="Edit")
        head = self.head(repo)
        self.assertEqual(spec.read_text(), f"---\nversion: 1\ncommit: {head}\n---\n\n# Body\n")
        spec.write_text("---\ncommit: deadbeef\nversion: 2\n---\n\n# Body\n")
        self.run_doc_hook(repo, spec, tool="Edit")
        self.assertEqual(spec.read_text(), f"---\ncommit: {head}\nversion: 2\n---\n\n# Body\n")

    def test_unstamped_paths_are_left_alone(self):
        repo, _ = self.installed()
        self.assertEqual(self.commit_all(repo).returncode, 0)
        index = repo / "agent-docs" / "try-n-fail" / "index.md"
        stale = repo / "agent-docs" / "try-n-fail" / "stale.md"
        outside = repo / "notes.md"
        text_file = repo / "agent-docs" / "try-n-fail" / "data.txt"
        for path in (outside, text_file):
            path.write_text("# X\n")
        before = {path: path.read_text() for path in (index, stale, outside, text_file)}
        for path in before:
            self.run_doc_hook(repo, path)
        self.assertEqual({path: path.read_text() for path in before}, before)

    def test_vo8_fr9_former_progress_directory_is_stamped_like_any_record(self):
        repo, _ = self.installed()
        self.assertEqual(self.commit_all(repo).returncode, 0)
        record = repo / "agent-docs" / "progress" / "1111111111111111-task.md"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("---\nsession: S1\n---\n\n# Task\n")

        self.assertEqual(self.run_doc_hook(repo, record).returncode, 0)

        self.assertEqual(record.read_text(), f"---\nsession: S1\ncommit: {self.head(repo)}\n---\n\n# Task\n")

    def test_repository_without_commits_is_left_alone(self):
        repo, _ = self.installed()
        doc = repo / "agent-docs" / "try-n-fail" / "1111111111111111-task.md"
        doc.write_text("# Task\n")
        self.assertEqual(self.run_doc_hook(repo, doc).returncode, 0)
        self.assertEqual(doc.read_text(), "# Task\n")

    def test_claude_settings_register_the_hook_for_file_edits(self):
        repo, _ = self.installed()
        settings = json.loads((repo / ".claude" / "settings.json").read_text())
        groups = [g for g in settings["hooks"]["PostToolUse"] if "doc_commit.py" in g["hooks"][0]["command"]]
        self.assertEqual([g["matcher"] for g in groups], ["Write|Edit|MultiEdit"])


class TestNoRetrospectiveWarning(DocRecordsTestCase):
    WARNING = "# Retrospective"

    def test_spec_change_commits_without_a_retrospective_warning(self):
        repo, _ = self.installed()
        spec = repo / "agent-docs" / "specs" / SPEC_NAME
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(SPEC_TEXT)
        result = self.commit_all(repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(self.WARNING, result.stderr)
        spec.write_text(SPEC_TEXT.replace("- Initial.", "- Initial.\n- Changed."))
        result = self.commit_all(repo, "change")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(self.WARNING, result.stderr)

    def test_retrospective_hook_is_not_installed(self):
        repo, _ = self.installed()
        self.assertFalse((repo / ".harness" / "git" / "warn_retrospective.py").exists())
        self.assertNotIn("warn_retrospective", (repo / ".harness" / "git" / "pre-commit").read_text())


class TestRecordRules(DocRecordsTestCase):
    def test_retired_record_dirs_are_not_checked(self):
        repo, _ = self.installed()
        for name in ("adr", "rejections"):
            directory = repo / "agent-docs" / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "0123456789abcdef-x.md").write_text("# X\n")
        result = self.run_verify_rules(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_try_n_fail_record_requires_its_headings(self):
        repo, _ = self.installed()
        directory = repo / "agent-docs" / "try-n-fail"
        name = "0123456789abcdef-cache-warmup.md"
        (directory / name).write_text("# Cache warmup\n\n## Goal\nx\n")
        (directory / "index.md").write_text(
            f"File: {name}\nSummary: s\nRelated Files: none\nRelated Symbols: none\n"
        )
        result = self.run_verify_rules(repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("'## Attempts', '## Revisit Condition'", result.stderr)
        (directory / name).write_text("# Cache warmup\n\n## Goal\nx\n\n## Attempts\n| a | b | c |\n\n## Revisit Condition\ny\n")
        result = self.run_verify_rules(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TestAgentModel(DocRecordsTestCase):
    SELECTABLE = ("code-explorer", "implementer", "test-implementer", "test-verifier")

    def models(self, repo):
        values = {}
        for path in (repo / ".claude" / "agents").glob("*.md"):
            line = next(line for line in path.read_text().splitlines() if line.startswith("model: "))
            values[path.stem] = line.split(": ", 1)[1]
        return values

    def test_default_install_uses_sonnet_and_writes_no_config(self):
        repo, result = self.installed()
        models = self.models(repo)
        self.assertEqual({models[name] for name in self.SELECTABLE}, {"sonnet"})
        self.assertEqual(models["mutant-triager"], "haiku")
        self.assertFalse((repo / ".harness" / "config.json").exists())
        self.assertIn("workflow subagent model: sonnet", result.stdout)

    def test_model_choice_is_stored_and_kept_by_update(self):
        repo, _ = self.installed("--model", "opus")
        self.assertEqual(json.loads((repo / ".harness" / "config.json").read_text()), {"agent_model": "opus"})
        self.assertEqual({self.models(repo)[name] for name in self.SELECTABLE}, {"opus"})
        self.assertEqual(self.models(repo)["mutant-triager"], "haiku")

        update = run_installer("update", str(repo), "--no-ci")
        self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
        self.assertEqual({self.models(repo)[name] for name in self.SELECTABLE}, {"opus"})
        doctor = run_installer("doctor", str(repo))
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

        back = run_installer("update", str(repo), "--no-ci", "--model", "sonnet")
        self.assertEqual(back.returncode, 0, back.stdout + back.stderr)
        self.assertEqual({self.models(repo)[name] for name in self.SELECTABLE}, {"sonnet"})
        self.assertEqual(json.loads((repo / ".harness" / "config.json").read_text()), {"agent_model": "sonnet"})

    def test_model_flag_is_rejected_outside_install_and_update(self):
        repo, _ = self.installed()
        result = run_installer("doctor", str(repo), "--model", "opus")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--model is only valid with install or update", result.stderr)


class TestMigration0290(DocRecordsTestCase):
    def test_update_from_0280_keeps_retired_dirs_and_announces_them(self):
        repo, _ = self.installed()
        adr = repo / "agent-docs" / "adr"
        (adr / "stale").mkdir(parents=True)
        record = adr / "0123456789abcdef-x.md"
        record.write_text("# X\n")
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = "0.28.0"
        manifest_path.write_text(json.dumps(manifest))

        result = run_installer("update", str(repo), "--no-ci", input="y\n" * 18)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("migration 0.29.0:", result.stdout)
        self.assertIn("keep agent-docs/adr/ untouched", result.stdout)
        self.assertNotIn("agent-docs/rejections/", result.stdout)
        self.assertEqual(record.read_text(), "# X\n")
        self.assertEqual(json.loads(manifest_path.read_text())["version"], "0.54.0")
        block = (repo / ".harness" / "instructions" / "harness-block.md").read_text()
        self.assertNotIn("## Try-n-Fail Rule", block)
        self.assertIn("## Try-n-Fail Rule", (repo / ".harness" / "instructions" / "try-n-fail.md").read_text())
        self.assertNotIn("## Architecture Decision Record Rule", block)
        self.assertIn("## Reporting to the User", block)

    def set_version(self, repo, version):
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = version
        manifest_path.write_text(json.dumps(manifest))

    def handoffs(self, repo):
        return sorted((repo / "agent-docs" / "handoff").rglob("*-adr-rejection-to-try-n-fail.md"))

    def test_update_with_retired_records_leaves_one_indexed_handoff(self):
        repo, _ = self.installed()
        self.assertEqual(self.commit_all(repo).returncode, 0)
        rejections = repo / "agent-docs" / "rejections"
        (rejections / "stale").mkdir(parents=True)
        (rejections / "0123456789abcdef-x.md").write_text("# X\n")
        (rejections / "stale" / "fedcba9876543210-y.md").write_text("# Y\n")
        self.set_version(repo, "0.28.0")

        dry = run_installer("update", str(repo), "--no-ci", "--dry-run")
        self.assertIn("record(s) to try-n-fail", dry.stdout)
        self.assertEqual(self.handoffs(repo), [])

        result = run_installer("update", str(repo), "--no-ci", input="y\n" * 21 + "n\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        [handoff] = self.handoffs(repo)
        text = handoff.read_text()
        self.assertTrue(text.startswith(f"---\ncommit: {self.head(repo)}\n---\n"))
        self.assertIn("- `agent-docs/rejections/0123456789abcdef-x.md`", text)
        self.assertIn("- `agent-docs/rejections/stale/fedcba9876543210-y.md`", text)
        self.assertIn(f"File: {handoff.name}", (handoff.parent / "index.md").read_text())
        verify = self.run_verify_rules(repo)
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

        self.set_version(repo, "0.28.0")
        again = run_installer("update", str(repo), "--no-ci", input="y\n" * 21 + "n\n")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(len(self.handoffs(repo)), 1)

    def test_update_without_retired_records_writes_no_handoff(self):
        repo, _ = self.installed()
        (repo / "agent-docs" / "adr").mkdir(parents=True)
        self.set_version(repo, "0.28.0")
        result = run_installer("update", str(repo), "--no-ci", input="y\n" * 18)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.handoffs(repo), [])


TODO_INDEX_BLOCK = "File: {name}\nSummary: s\nRelated Files: none\nRelated Symbols: none\n"


class RecordRulesTestCase(DocRecordsTestCase):
    def verify(self, repo):
        result = self.run_verify_rules(repo)
        return result, result.stdout + result.stderr


class TestRecordRules(RecordRulesTestCase):
    def test_retired_facts_directory_is_not_checked(self):
        repo, _ = self.installed()
        facts = repo / "agent-docs" / "facts"
        facts.mkdir(parents=True)
        (facts / "0123456789abcdef-load-peak-rps.md").write_text(
            "dimension: load\nfact: peak is 40 requests per second\nsource: user, 2026-11-13\n"
            "asked for: queue or inline\nre-check: ask the user\n"
        )
        result, output = self.verify(repo)
        self.assertEqual(result.returncode, 0, output)
        for leftover in ("index.md", "stale.md", "stale"):
            self.assertFalse((facts / leftover).exists())

    def todo(self, repo, text, name="1111111111111111-legacy.md", indexed=True):
        directory = repo / "agent-docs" / "todos"
        (directory / name).write_text(text)
        if indexed:
            (directory / "index.md").write_text(TODO_INDEX_BLOCK.format(name=name))
        return directory / name

    def test_o8_fr20_todos_accepts_legacy_handoff_record(self):
        repo, _ = self.installed()
        legacy = (
            "# Resume parser work\n\n## User Query\nfix it\n\n## State\nbranch x\n\n"
            "## Failed Attempts\n| attempt | failure evidence | cause |\n\n## Next Step\nfinish\n\n"
            "## Open Questions\nnone\n\n## Spec\nnone\n\n## Execution Ledger\nnone\n"
        )
        self.todo(repo, legacy)
        result, output = self.verify(repo)
        self.assertEqual(result.returncode, 0, output)

    def test_o8_fr16_todos_accepts_extra_sections_and_requires_only_title_and_next_step(self):
        repo, _ = self.installed()
        self.todo(repo, "# Todo\n\n## Next Step\ndo it\n\n## Whatever Else\nx\n\n### Deep\ny\n")
        result, output = self.verify(repo)
        self.assertEqual(result.returncode, 0, output)
        self.todo(repo, "# Todo\n\n## Next Step\ndo it\n")
        result, output = self.verify(repo)
        self.assertEqual(result.returncode, 0, output)

    def test_o8_fr16_todos_without_next_step_or_title_fails(self):
        for label, text in (
            ("no next step", "# Todo\n\n## Goal\ng\n"),
            ("no title", "## Next Step\ndo it\n"),
        ):
            with self.subTest(case=label):
                repo, _ = self.installed()
                self.todo(repo, text)
                result, output = self.verify(repo)
                self.assertEqual(result.returncode, 1, output)

    def test_o8_fr16_todos_is_a_managed_directory_requiring_an_index_entry(self):
        repo, _ = self.installed()
        self.todo(repo, "# Todo\n\n## Next Step\ndo it\n", indexed=False)
        result, output = self.verify(repo)
        self.assertEqual(result.returncode, 1, output)

    def test_o8_fr16_handoff_directory_is_not_checked(self):
        repo, _ = self.installed()
        handoff = repo / "agent-docs" / "handoff"
        handoff.mkdir(parents=True, exist_ok=True)
        (handoff / "1234567890abcdef-x.md").write_text("# X\n\n## Next Stepx\nbad\n")
        (handoff / "not-a-record-name.md").write_text("no heading\n")
        result, output = self.verify(repo)
        self.assertEqual(result.returncode, 0, output)
