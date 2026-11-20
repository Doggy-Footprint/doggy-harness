import functools
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_installer import INSTALLER, REPO_ROOT, InstallerTestCase, run_git, run_installer

FIXTURE = Path(__file__).resolve().parent / "data" / "harness-block-0.40.0.md"
INSTRUCTIONS = ".harness/instructions"

S6_LABEL = "move hook-backed rules into their own instruction files"
S6_PLAN = [
    "the Progress, Try-n-Fail, Todo, Index & Staleness, and Synced Comment rules move from .harness/instructions/harness-block.md to their own files in .harness/instructions/",
    "the managed block lists each rule file and when to read it; hook and pre-commit messages name the file of a violated rule",
    "a session's first project change without a progress prints a one-time reminder to write one",
    "no data is migrated; AGENTS.md is unchanged",
]

S7 = """## Rule Files

These rules live in separate files under `.harness/instructions/`. A hook adds a rule's text to the session at its first Write or Edit in the rule's directory; read the file yourself before other work it covers. Hook and pre-commit messages name the file of a rule they find violated.

| file | read before |
| --- | --- |
| `index-and-staleness.md` | adding, renaming, or marking stale a record in `agent-docs/` |
| `try-n-fail.md` | proposing a try-n-fail record |
| `todos.md` | writing a todo |
| `synced-comments.md` | keeping one comment identical in several places, or editing code tagged `synced id:` |
"""

KEPT_HEADINGS = [
    "# Documentation Guide",
    "## Principles",
    "## Commit Stamp",
    "## Rule Files",
    "# Task Guide",
    "## User Decision",
    "## Reporting to the User",
    "## Editing Skills and Prompts",
    "## Commit & PR Messages",
]
NO_BASE_COUNTERPART = ("## Rule Files", "## Editing Skills and Prompts")
PRINCIPLE_NOTE = "Principles 2 and 3 will be replaced by a new approach; until then, following them is not required."
MOVED = {
    "## Index & Staleness Management": "index-and-staleness.md",
    "## Shared Comment & Docstring Synchronization Rules": "synced-comments.md",
    "## Try-n-Fail Rule": "try-n-fail.md",
    "## Todo Rule": "todos.md",
}
RULE_FILE_ORDER = [
    f"{INSTRUCTIONS}/index-and-staleness.md",
    f"{INSTRUCTIONS}/synced-comments.md",
    f"{INSTRUCTIONS}/try-n-fail.md",
    f"{INSTRUCTIONS}/todos.md",
]
MOVED_REGEX = re.compile(r"(Progress|Try-n-Fail|Todo) Rule in `?AGENTS\.md")


def split_sections(text):
    sections = []
    fenced = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,2} \S", line):
            sections.append([line.rstrip("\n"), ""])
        if not sections:
            sections.append(["", ""])
        sections[-1][1] += line
    return [(heading, body) for heading, body in sections]


def base_sections():
    return dict(split_sections(FIXTURE.read_text()))


def without_second_principle(body):
    lines = [line for line in body.split("\n") if line != PRINCIPLE_NOTE and not line.startswith("2. **")]
    collapsed = []
    for line in lines:
        if line == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(line)
    return "\n".join(collapsed)


@functools.lru_cache(maxsize=1)
def shared_install():
    tmp = tempfile.TemporaryDirectory()
    shared_install.tmp = tmp
    repo = Path(tmp.name)
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@test.com")
    run_git(repo, "config", "user.name", "test")
    result = run_installer("install", str(repo), "--no-ci")
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return repo


def read_block(repo):
    return (repo / ".harness" / "instructions" / "harness-block.md").read_text()


class TestBlockSplit(unittest.TestCase):
    def test_v1_fixture_has_the_twelve_base_sections_in_order(self):
        headings = [h for h, _ in split_sections(FIXTURE.read_text())]
        self.assertEqual(
            headings,
            ["# Documentation Guide", "## Principles", "## Commit Stamp", "## Index & Staleness Management",
             "## Shared Comment & Docstring Synchronization Rules", "## Try-n-Fail Rule", "## Progress Rule",
             "## Todo Rule", "# Task Guide", "## User Decision", "## Reporting to the User",
             "## Commit & PR Messages"],
        )

    def test_v1_kept_sections_are_byte_equal_to_base_and_in_order(self):
        base = base_sections()
        actual = split_sections(read_block(shared_install()))
        self.assertEqual([h for h, _ in actual], KEPT_HEADINGS)
        for heading, body in actual:
            if heading in NO_BASE_COUNTERPART:
                continue
            with self.subTest(section=heading):
                if heading == "## Principles":
                    self.assertNotIn(PRINCIPLE_NOTE, body)
                    second = [line for line in body.split("\n") if line.startswith("2. **")]
                    self.assertEqual(len(second), 1, second)
                    self.assertTrue(second[0].startswith("2. **Memory Has a Scope**"), second[0])
                    self.assertEqual(without_second_principle(body).rstrip("\n"),
                                     without_second_principle(base[heading]).rstrip("\n"))
                else:
                    self.assertEqual(body.rstrip("\n"), base[heading].rstrip("\n"))

    def test_v1_s7_sits_between_commit_stamp_and_task_guide(self):
        headings = [h for h, _ in split_sections(read_block(shared_install()))]
        self.assertEqual(headings.index("## Rule Files"), headings.index("## Commit Stamp") + 1)
        self.assertEqual(headings.index("# Task Guide"), headings.index("## Rule Files") + 1)

    def test_v1_moved_sections_keep_their_base_heading_as_the_first_line_of_their_files(self):
        repo = shared_install()
        for heading, name in MOVED.items():
            with self.subTest(section=heading, file=name):
                actual = (repo / ".harness" / "instructions" / name).read_text()
                self.assertEqual(actual.split("\n", 1)[0], heading)

    def test_v1_moved_headings_are_absent_from_the_block(self):
        lines = read_block(shared_install()).splitlines()
        for heading in MOVED:
            with self.subTest(section=heading):
                self.assertNotIn(heading, lines)
        self.assertNotIn("### Hook Behavior", lines)

    def test_v2_rule_files_section_matches_s7_exactly(self):
        sections = dict(split_sections(read_block(shared_install())))
        self.assertEqual(sections["## Rule Files"].rstrip("\n"), S7.rstrip("\n"))

    def test_v2_four_rule_files_exist_in_a_fresh_install_and_progress_md_does_not(self):
        repo = shared_install()
        for name in MOVED.values():
            with self.subTest(file=name):
                self.assertTrue((repo / ".harness" / "instructions" / name).is_file())
        self.assertTrue((repo / ".harness" / "instructions" / "harness-block.md").is_file())
        self.assertFalse((repo / ".harness" / "instructions" / "progress.md").exists())

    def test_v12_block_size_is_at_most_4500_bytes(self):
        size = len(read_block(shared_install()).encode())
        self.assertLessEqual(size, 4500)
        self.assertGreater(size, len(S7.encode()))


class TestVerifyRulesMessages(InstallerTestCase):
    def installed(self):
        repo = self.installed_copy("--no-ci")[0]
        return repo

    def verify(self, repo):
        return self.run_verify_rules(repo)

    def track(self, repo, *paths):
        run_git(repo, "add", "-f", "--", *paths)

    def break_index(self, repo):
        notes = repo / "agent-docs" / "notes"
        notes.mkdir(parents=True)
        (notes / "1234567890abcdef-x.md").write_text("# X\n")
        self.track(repo, "agent-docs/notes")

    def break_synced(self, repo):
        tag = "synced" " id: aabbccddeeff, version: 2, count: 2"
        (repo / "a.py").write_text(f"# {tag}\nx = 1\n")
        (repo / "b.py").write_text(f"# {tag}\ny = 2\n")
        directory = repo / "agent-docs" / "synced-comments"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "aabbccddeeff.md").write_text(
            "---\nversion: 1\ncount: 3\ncode_hash: 0000\n---\n\n# Content\nshared\n\n# Version Log\n## v1 Log\n- Initial creation.\n"
        )
        self.track(repo, "a.py", "b.py", "agent-docs/synced-comments/aabbccddeeff.md")

    def break_try_n_fail(self, repo):
        directory = repo / "agent-docs" / "try-n-fail"
        name = "0123456789abcdef-cache-warmup.md"
        (directory / name).write_text("# Cache warmup\n\n## Goal\nx\n")
        (directory / "index.md").write_text(f"File: {name}\nSummary: s\nRelated Files: none\nRelated Symbols: none\n")
        self.track(repo, "agent-docs/try-n-fail")

    def break_todos(self, repo):
        directory = repo / "agent-docs" / "todos"
        name = "0123456789abcdef-add-flag.md"
        (directory / name).write_text("# Add flag\n\n## Goal\nx\n")
        (directory / "index.md").write_text(f"File: {name}\nSummary: s\nRelated Files: none\nRelated Symbols: none\n")
        self.track(repo, "agent-docs/todos")

    GROUPS = {
        "index": ("break_index", RULE_FILE_ORDER[0:1]),
        "synced": ("break_synced", RULE_FILE_ORDER[1:2]),
        "try_n_fail": ("break_try_n_fail", RULE_FILE_ORDER[2:3]),
        "todos": ("break_todos", RULE_FILE_ORDER[3:4]),
    }

    def assert_layout(self, stderr, files):
        self.assertTrue(stderr.endswith("\n"), repr(stderr))
        lines = stderr[:-1].split("\n")
        self.assertEqual(lines[0], "harness rule violations found:")
        self.assertEqual(lines[1], "")
        errors = lines[2:-3]
        self.assertTrue(errors, stderr)
        self.assertTrue(all(line.startswith("  - ") for line in errors), stderr)
        self.assertEqual(lines[-3], "")
        self.assertEqual(lines[-2], "Rule files: " + ", ".join(files))
        self.assertEqual(lines[-1], f"{len(errors)} violation(s). Commit blocked.")
        self.assertEqual(stderr.count("Rule files:"), 1)

    def test_v7_clean_repo_exits_0_with_empty_output(self):
        repo = self.installed()
        result = self.verify(repo)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_v7_each_violated_group_alone_names_only_its_file(self):
        for label, (method, files) in self.GROUPS.items():
            with self.subTest(group=label):
                repo = self.installed()
                getattr(self, method)(repo)
                result = self.verify(repo)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assert_layout(result.stderr, files)

    def test_v7_all_four_groups_list_every_file_once_in_fixed_order(self):
        repo = self.installed()
        for method in ("break_index", "break_synced", "break_try_n_fail", "break_todos"):
            getattr(self, method)(repo)
        result = self.verify(repo)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assert_layout(result.stderr, RULE_FILE_ORDER)
        for path in RULE_FILE_ORDER:
            self.assertEqual(result.stderr.count(path), 1, path)

    def test_v7_pre_commit_blocks_a_todo_without_next_step_and_names_todos_md_before_the_count(self):
        repo = self.installed()
        self.break_todos(repo)
        run_git(repo, "add", "-f", "agent-docs/todos")
        result = subprocess.run(["git", "-C", str(repo), "commit", "-m", "t"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        rule_line = f"Rule files: {INSTRUCTIONS}/todos.md"
        self.assertIn(rule_line, result.stderr)
        self.assertLess(result.stderr.index(rule_line), result.stderr.index("violation(s). Commit blocked."))


class TestMigration0410(InstallerTestCase):
    def sha(self, data):
        return hashlib.sha256(data).hexdigest()

    def install_0400(self):
        repo = self.install()
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        block_rel = f"{INSTRUCTIONS}/harness-block.md"
        block_path = repo / block_rel
        sha_scheme_matches = manifest["files"].get(block_rel) == self.sha(block_path.read_bytes())
        block_path.write_bytes(FIXTURE.read_bytes())
        for name in MOVED.values():
            (repo / INSTRUCTIONS / name).unlink()
            manifest["files"].pop(f"{INSTRUCTIONS}/{name}", None)
        if sha_scheme_matches:
            manifest["files"][block_rel] = self.sha(FIXTURE.read_bytes())
        manifest["version"] = "0.40.0"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        return repo, manifest_path

    def test_v6_update_from_0400_announces_0410_last_with_plan_lines_and_leaves_agents_md_alone(self):
        repo, manifest_path = self.install_0400()
        agents_before = (repo / "AGENTS.md").read_bytes()

        result = run_installer("update", str(repo), "--no-ci", "--no-commit", input="y\n" * 20, exact=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        announced = re.findall(r"^migration (\d+\.\d+\.\d+):", result.stdout, re.MULTILINE)
        self.assertEqual(announced[-1], "0.54.0")
        self.assertEqual(announced, ["0.41.0", "0.42.0", "0.43.0", "0.44.0", "0.45.0", "0.47.0", "0.48.0", "0.49.0", "0.49.1", "0.50.0", "0.51.0", "0.52.0", "0.53.0", "0.54.0"])
        self.assertIn(f"migration 0.41.0: {S6_LABEL}", result.stdout)
        start = result.stdout.index("migration 0.41.0:")
        positions = []
        for line in S6_PLAN:
            self.assertIn(line, result.stdout[start:])
            positions.append(result.stdout.index(line, start))
        self.assertEqual(positions, sorted(positions))
        self.assertEqual((repo / "AGENTS.md").read_bytes(), agents_before)
        self.assertEqual(json.loads(manifest_path.read_text())["version"], "0.54.0")
        for name in MOVED.values():
            self.assertTrue((repo / INSTRUCTIONS / name).is_file(), name)
        block_headings = [h for h, _ in split_sections(read_block(repo))]
        self.assertEqual(block_headings, KEPT_HEADINGS)
        doctor = run_installer("doctor", str(repo))
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

    def test_v6_dry_run_from_0400_changes_nothing_in_agents_md_or_instruction_files(self):
        repo, _ = self.install_0400()
        agents_before = (repo / "AGENTS.md").read_bytes()
        result = run_installer("update", str(repo), "--no-ci", "--dry-run", forbid_input=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((repo / "AGENTS.md").read_bytes(), agents_before)
        self.assertIn(f"migration 0.41.0: {S6_LABEL}", result.stdout)


class TestDuplicateHeadings(InstallerTestCase):
    def review_items(self, stdout):
        if "== manual review ==\n" not in stdout:
            return []
        section = stdout.split("== manual review ==\n", 1)[1].split("\n== ", 1)[0]
        return [line[2:] for line in section.splitlines() if line.startswith("- ")]

    def test_v8_moved_rule_and_rule_files_headings_outside_the_block_are_flagged_other_heading_is_not(self):
        repo = self.make_repo()
        old_block = (
            "<!-- harness:begin 0.39.0 -->\n# Documentation Guide\n\nold full rule body\n\n"
            "## Principles\n\nold text\n<!-- harness:end -->\n"
        )
        (repo / "AGENTS.md").write_text(
            "# Local Rules\n\n## Todo Rule\n\nown\n\n## Rule Files\n\nown\n\n"
            "## Zebra Crossing Notes Unique 7731\n\nown\n\n" + old_block
        )

        result = run_installer("install", str(repo))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        items = self.review_items(result.stdout)
        for title, flagged in (("Todo Rule", True), ("Rule Files", True),
                               ("Zebra Crossing Notes Unique 7731", False)):
            with self.subTest(heading=title):
                hits = [item for item in items if f"'{title}'" in item]
                self.assertEqual(bool(hits), flagged, result.stdout)


class TestWordingReplacements(InstallerTestCase):
    def installed_text(self, repo, name):
        return (repo / ".agents" / "skills" / name / "SKILL.md").read_text()

    def test_v9_no_moved_rule_is_said_to_live_in_agents_md_in_the_installed_tree_or_installer(self):
        repo = shared_install()
        roots = [repo / ".harness", repo / ".claude", repo / ".agents", repo / ".codex"]
        files = [repo / "AGENTS.md", INSTALLER]
        for root in roots:
            if root.exists():
                files += [p for p in root.rglob("*") if p.is_file() and ".running" not in p.parts]
        scanned = 0
        for path in files:
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            scanned += 1
            with self.subTest(file=str(path.name)):
                self.assertIsNone(MOVED_REGEX.search(text))
        self.assertGreater(scanned, 20)

    def test_v9_installer_handoff_template_points_at_the_rule_files(self):
        text = INSTALLER.read_text()
        self.assertIn("following the Try-n-Fail Rule in `.harness/instructions/try-n-fail.md`", text)
        self.assertIn(
            "under the Index & Staleness Management rule in `.harness/instructions/index-and-staleness.md`.", text
        )
        self.assertNotIn("following the Try-n-Fail Rule in `AGENTS.md`", text)
        self.assertNotIn("under the Index & Staleness Management rule.", text)

    def test_v9_readme_wording(self):
        text = (REPO_ROOT / "README.md").read_text()
        self.assertIn("항상 읽는 규칙은 [`harness-block.md`](harness/instructions/harness-block.md)에 있습니다.", text)
        self.assertNotIn("hook이 위반을 잡는 progress,", text)
        self.assertNotIn("규칙 전문은 [`harness-block.md`](harness/instructions/harness-block.md)에 있습니다.", text)
        self.assertNotIn("파일을 바꾼 세션이 progress 없이 끝나려 하면 한 번 막음", text)


if __name__ == "__main__":
    unittest.main()
