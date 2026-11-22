import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from hook_case import HookCase
from old_release import release_source
from test_installer import IMPORT_BLOCK, REPO_ROOT, run_git, run_installer

AGENTS = "AGENTS.md"
FIVE = [
    ".harness/instructions/harness-block.md",
    ".harness/instructions/index-and-staleness.md",
    ".harness/instructions/try-n-fail.md",
    ".harness/instructions/todos.md",
    ".harness/instructions/synced-comments.md",
]
PREFIX = "harness customization: "
INSTRUCTION = (
    PREFIX + "before other work, tell the user about each line below. Where a customization disagrees with "
    "harness text, the customization is followed: read both and name each disagreement. Run the confirm "
    "command for an item only after the user confirms it."
)
CONFIRM = "python3 .harness/bin/customization.py confirm"
DEFINITION = "# Project Definition\n\nA widget CLI.\n\nAlways use tabs.\n\n"
PHASES = ("brief", "draft", "approve", "step", "close", "resume", "implement_test", "verify", "amend")
GIT_NAMES = (
    "applypatch-msg", "pre-applypatch", "post-applypatch", "pre-commit", "pre-merge-commit",
    "prepare-commit-msg", "commit-msg", "post-commit", "pre-rebase", "post-checkout", "post-merge",
    "pre-push", "pre-auto-gc", "post-rewrite",
)
AGENT_NAMES = ("code-explorer", "implementer", "mutant-triager", "test-implementer", "test-verifier")
ITEM = re.compile(r"(unconfirmed|harness-changed|confirmed|unrecognized) (\S+?)(?: — compare with (.+))?")
SKILL_DIR = ".harness/skills/doggy-workflow"


def split_paths(text):
    return re.split(r"\s*,\s*", text.strip())


def parse_status(lines):
    items, rest = [], []
    for line in lines:
        found = ITEM.fullmatch(line)
        if found:
            items.append((found[1], found[2], split_paths(found[3]) if found[3] else None))
        else:
            rest.append(line)
    return items, rest


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def today_candidates():
    return {date.today().isoformat(), datetime.now(timezone.utc).date().isoformat()}


def copy_source(dest, edit=None):
    dest = Path(dest)
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(REPO_ROOT / "harness", dest / "harness", ignore=ignore)
    shutil.copytree(REPO_ROOT / "installer", dest / "installer", ignore=ignore)
    if edit is not None:
        path = dest / "harness" / "customization.json"
        data = json.loads(path.read_text())
        edit(data)
        path.write_text(json.dumps(data, indent=2) + "\n")
    return dest


def tree(repo, rel):
    root = Path(repo) / rel
    files, dirs = {}, set()
    if not root.exists():
        return files, dirs
    for path in sorted(root.rglob("*")):
        name = str(path.relative_to(repo))
        if path.is_dir():
            dirs.add(name)
        else:
            files[name] = (path.read_bytes(), path.stat().st_mode & 0o7777)
    return files, dirs


class CustomizationCase(HookCase):
    def project(self, outside=DEFINITION):
        repo = self.installed_copy("--no-ci")[0]
        (repo / AGENTS).write_text(outside + IMPORT_BLOCK)
        run_git(repo, "config", "core.hooksPath", ".harness/git")
        return repo

    def temp_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def write(self, repo, rel, data, mode=None):
        path = Path(repo) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            data = data.encode()
        path.write_bytes(data)
        if mode is not None:
            path.chmod(mode)
        return path

    def run_py(self, repo, rel, *args, stdin="", env=None, cwd=None):
        return subprocess.run([sys.executable, str(Path(repo) / rel), *args], input=stdin, capture_output=True,
                              text=True, cwd=cwd or repo, env=env if env is not None else self.env())

    def customization(self, repo, *args):
        return self.run_py(repo, ".harness/bin/customization.py", *args)

    def status_lines(self, repo):
        result = self.customization(repo, "status")
        self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
        return result.stdout.splitlines()

    def status(self, repo):
        return parse_status(self.status_lines(repo))

    def confirm(self, repo, *paths):
        result = self.customization(repo, "confirm", *paths)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def notice(self, repo, **kwargs):
        return self.run_py(repo, ".harness/hooks/customization_notice.py", **kwargs)

    def notice_lines(self, repo):
        result = self.notice(repo)
        self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
        return result.stdout.splitlines()

    def review(self, repo):
        path = repo / ".harness" / "customization-review.json"
        return json.loads(path.read_text()) if path.exists() else None

    def version(self, repo):
        return (repo / ".harness" / "VERSION").read_text().strip()

    def declaration(self, repo):
        return json.loads((repo / ".harness" / "customization.json").read_text())

    def phase_fragments(self, repo, phase):
        entries = json.loads((repo / SKILL_DIR / "phases.json").read_text())[phase]
        return [e if isinstance(e, str) else e["name"] for e in entries]

    def phase_compare(self, repo, phase):
        return [f"{SKILL_DIR}/phases.json"] + [f"{SKILL_DIR}/phases/{n}.md" for n in self.phase_fragments(repo, phase)]

    def item_line(self, state, path, compare):
        return f"{state} {path} — compare with " + ", ".join(compare)

    def assert_items(self, repo, expected):
        items, _ = self.status(repo)
        self.assertEqual([(s, p) for s, p, _ in items], [(s, p) for s, p, _ in expected], items)
        for (state, path, compare), (_, _, want) in zip(items, expected):
            with self.subTest(item=path):
                if want is not None:
                    self.assertEqual(compare, want)
                elif state in ("confirmed", "unrecognized"):
                    self.assertIsNone(compare)

    def set_manifest_version(self, repo, version):
        path = repo / ".harness" / "manifest.json"
        data = json.loads(path.read_text())
        data["version"] = version
        path.write_text(json.dumps(data, indent=2) + "\n")

    def write_owned(self, repo, rel, data):
        # keeps the manifest entry in step so the file reads as an older release's file, not as an edit
        path = self.write(repo, rel, data)
        manifest_path = repo / ".harness" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][rel] = sha256(path.read_bytes())
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        return path

    def install_old(self, commit):
        source = release_source(commit)
        repo = self.make_repo()
        result = subprocess.run([sys.executable, str(source / "installer" / "harness.py"), "install", str(repo),
                                 "--no-ci"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return repo

    def set_definition(self, repo, outside=DEFINITION):
        text = (repo / AGENTS).read_text()
        block = re.search(r"<!-- harness:begin -->.*?<!-- harness:end -->\n?", text, re.S).group(0)
        (repo / AGENTS).write_text(outside + block)

    def section(self, stdout, name):
        marker = f"== {name} ==\n"
        if marker not in stdout:
            return None
        return stdout.split(marker, 1)[1].split("\n== ", 1)[0]

    def update(self, repo, *args, installer=None):
        command = [sys.executable, str(installer or REPO_ROOT / "installer" / "harness.py"), "update", str(repo), *args]
        return subprocess.run(command, input="y\n" * 80, capture_output=True, text=True)

    def porcelain(self, repo):
        return run_git(repo, "status", "--porcelain").stdout
