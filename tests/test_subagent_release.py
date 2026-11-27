import json
import re
import unittest

from legacy_migrations import skip_legacy_update
from test_installer import REPO_ROOT, InstallerTestCase, load_installer_module, run_installer

HOOK = "subagent_comments.py"
IMPLEMENTER_BULLET = (
    "- **Comments** — each comment or docstring you added, as `path:line — category`, where category is the one it "
    "records: design constraint, external-system behavior, safety/security invariant, or reason for an odd "
    "implementation; `none` if you added none. A comment that fits no category restates the code: delete it "
    "instead of listing it."
)
TEST_IMPLEMENTER_BULLET = (
    "- Comments added in Tests, each as `path:line — category` (design constraint, external-system behavior, "
    "safety/security invariant, or reason for an odd implementation), or `none`. A comment that fits no category "
    "restates the test: delete it instead of listing it."
)
BULLETS = {"implementer.md": IMPLEMENTER_BULLET, "test-implementer.md": TEST_IMPLEMENTER_BULLET}
WORKFLOW = REPO_ROOT / "harness" / "ci" / "harness-comment-warning.yml"


class InstalledHookTests(InstallerTestCase):
    def hook_commands(self, groups):
        return [(g.get("matcher"), h["command"]) for g in groups for h in g["hooks"] if HOOK in h["command"]]

    def test_o12_g1_claude_settings_register_the_hook_for_three_events(self):
        repo = self.install()
        hooks = json.loads((repo / ".claude" / "settings.json").read_text())["hooks"]
        for event in ("SubagentStart", "SubagentStop"):
            with self.subTest(event=event):
                self.assertEqual(len(self.hook_commands(hooks.get(event, []))), 1)
        pre = self.hook_commands(hooks.get("PreToolUse", []))
        self.assertEqual([matcher for matcher, _ in pre], ["SubagentHandback"])
        total = sum(len(self.hook_commands(groups)) for groups in hooks.values())
        self.assertEqual(total, 3)

    def test_o12_g2_codex_files_do_not_mention_the_hook(self):
        repo = self.install()
        for path in (repo / ".codex").rglob("*"):
            if path.is_file():
                with self.subTest(path=str(path.relative_to(repo))):
                    self.assertNotIn("subagent_comments", path.read_text(errors="replace"))

    def last_report_bullet(self, text):
        report = text.split("## Report", 1)[1]
        bullets = [l for l in report.splitlines() if l.startswith("- ")]
        return bullets[-1]

    def test_o12_g3_agent_files_end_report_with_the_comments_bullet(self):
        repo = self.install()
        for name, bullet in BULLETS.items():
            for label, path in (
                ("source", REPO_ROOT / "harness" / "agents" / name),
                ("installed", repo / ".claude" / "agents" / name),
            ):
                with self.subTest(file=name, copy=label):
                    text = path.read_text()
                    self.assertEqual(self.last_report_bullet(text), bullet)
                    self.assertEqual([l for l in text.splitlines() if l.strip()][-1], bullet)

    def test_o12_g4_version_file_and_migration_entry(self):
        self.assertEqual((REPO_ROOT / "harness" / "VERSION").read_text().strip(), "0.57.0")
        module = load_installer_module()
        entries = [m for m in module.MIGRATIONS if m[0] == module.parse_version("0.57.0")]
        self.assertEqual(len(entries), 1)
        self.assertEqual(module.MIGRATIONS[-1][0], module.parse_version("0.57.0"))
        label = entries[0][1]
        for word in ("implementer", "test-implementer", "once", "comment", "tree-sitter", "uv", "PATH", "CI"):
            with self.subTest(word=word):
                self.assertIn(word, label)

    def test_o12_g4_update_from_0560_announces_the_migration_and_installs_the_hook(self):
        repo = self.install()
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = "0.56.0"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        skip_legacy_update(("update", str(repo)))
        result = run_installer("update", str(repo), "--no-ci", "--no-commit", input="y\n" * 10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(re.findall(r"^migration (\d+\.\d+\.\d+):", result.stdout, re.MULTILINE), ["0.57.0"])
        self.assertEqual(json.loads(manifest_path.read_text())["version"], "0.57.0")
        hooks = json.loads((repo / ".claude" / "settings.json").read_text())["hooks"]
        self.assertEqual(sum(len(self.hook_commands(groups)) for groups in hooks.values()), 3)
        self.assertTrue((repo / ".harness" / "hooks" / HOOK).is_file())

    def test_o12_g4_readme_describes_the_check_and_the_uv_requirement(self):
        lines = (REPO_ROOT / "README.md").read_text().splitlines()
        role = re.compile(r"implementer|test-implementer")
        comment = re.compile(r"주석|Comments", re.I)
        self.assertTrue([l for l in lines if role.search(l) and comment.search(l)])
        self.assertTrue([l for l in lines if re.search(r"\buv\b", l) and comment.search(l)])


class WorkflowOrderTests(unittest.TestCase):
    def steps(self):
        parts = re.split(r"^\s*-\s+(?=name:|uses:|run:|id:|if:)", WORKFLOW.read_text(), flags=re.MULTILINE)
        return parts[1:]

    def index_of(self, steps, predicate, what):
        found = [i for i, s in enumerate(steps) if predicate(s)]
        self.assertEqual(len(found), 1, f"{what}: {found}")
        return found[0]

    def test_o13_y1_y2_y3_setup_uv_step_sits_between_checkout_and_gate(self):
        steps = self.steps()
        setup = self.index_of(steps, lambda s: re.search(r"uses:\s*astral-sh/setup-uv@v10\s*$", s, re.M), "setup-uv")
        checkout = self.index_of(steps, lambda s: "actions/checkout@" in s, "checkout")
        gate = self.index_of(steps, lambda s: "warn_new_comments.py" in s and "--approved" in s, "gate")
        self.assertLess(checkout, setup)
        self.assertLess(setup, gate)
