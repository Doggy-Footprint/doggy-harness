#!/usr/bin/env python3
"""Not installed into target repositories."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = "harness/customization.json"
PHASES = "harness/skills/doggy-workflow/phases.json"
FRAGMENTS = "harness/skills/doggy-workflow/phases"
DEFAULTS = "harness/config.default.json"
INSTALLER = "installer/harness.py"
VERSION_FILE = "harness/VERSION"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True)


class Tree:
    def __init__(self, staged: bool):
        self.staged = staged

    def read(self, path: str) -> bytes | None:
        if self.staged:
            result = git("show", f":{path}")
            return result.stdout if result.returncode == 0 else None
        try:
            return (ROOT / path).read_bytes()
        except OSError:
            return None

    def listing(self, directory: str) -> list[str]:
        if self.staged:
            result = git("ls-files", "-z", "--", directory)
            return sorted(p for p in result.stdout.decode("utf-8", "replace").split("\0") if p)
        base = ROOT / directory
        return sorted(p.relative_to(ROOT).as_posix() for p in base.rglob("*") if p.is_file()) if base.is_dir() else []

    def changed(self) -> list[str]:
        if self.staged:
            result = git("diff", "--cached", "--name-only", "-z")
        else:
            result = git("diff", "--name-only", "-z", "HEAD")
        changed = [p for p in result.stdout.decode("utf-8", "replace").split("\0") if p]
        if not self.staged:
            untracked = git("ls-files", "-z", "--others", "--exclude-standard")
            changed += [p for p in untracked.stdout.decode("utf-8", "replace").split("\0") if p]
        return sorted(set(changed))


def head_bytes(path: str) -> bytes | None:
    result = git("show", f"HEAD:{path}")
    return result.stdout if result.returncode == 0 else None


def parse_json(data: bytes | None):
    try:
        return json.loads(data.decode("utf-8"))
    except (AttributeError, ValueError):
        return None


def valid_declaration(data) -> bool:
    if not isinstance(data, dict) or not isinstance(data.get("points"), list):
        return False
    for point in data["points"]:
        if not isinstance(point, dict) or not isinstance(point.get("id"), str) or not isinstance(point.get("path"), str):
            return False
        if not isinstance(point.get("compare", []), list) or not isinstance(point.get("names", []), list):
            return False
    return isinstance(data.get("config_keys", []), list) and isinstance(data.get("retired", []), list)


def mapped(path: str) -> str:
    agent = re.fullmatch(r"\.claude/agents/(.+\.md)", path)
    if agent:
        return f"harness/agents/{agent.group(1)}"
    return "harness/" + path[len(".harness/"):] if path.startswith(".harness/") else path


def phase_fragments(phases, name: str) -> list[str]:
    entries = phases.get(name, []) if isinstance(phases, dict) else []
    found = []
    for entry in entries if isinstance(entries, list) else []:
        fragment = entry if isinstance(entry, str) else entry.get("name") if isinstance(entry, dict) else None
        if isinstance(fragment, str):
            found.append(f"{FRAGMENTS}/{fragment}.md")
    return found


def point_compare_paths(point: dict, phases, with_name: bool = False) -> list[tuple]:
    names = point.get("names") or [None]
    result = []
    for name in names:
        for compare in point.get("compare", []):
            if not isinstance(compare, str):
                continue
            path = compare.replace("{name}", name) if name else compare
            result.append((mapped(path), path, name) if with_name else (mapped(path), path))
        if point.get("compare_phase_fragments") and name:
            result += [
                (fragment, fragment, name) if with_name else (fragment, fragment)
                for fragment in phase_fragments(phases, name)
            ]
    return result


def migration_versions(text: str) -> set[str]:
    start = text.find("MIGRATIONS = (")
    return set(re.findall(r'parse_version\("(\d+\.\d+\.\d+)"\)', text[start:])) if start >= 0 else set()


def version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def structure_failures(tree: Tree, declaration: dict) -> list[str]:
    failures = []
    phases = parse_json(tree.read(PHASES))
    points = {point["id"]: point for point in declaration["points"]}

    failed_names: set[tuple[str, str]] = set()
    for name in (points.get("git-hook") or {}).get("names", []):
        if tree.read(f"harness/git/{name}") is None:
            failed_names.add(("git-hook", name))
            failures.append(
                f"customization: git-hook name {name} has no harness/git/{name}; add the script or remove the name "
                "from harness/customization.json and retire it"
            )

    if "phase-rules" in points:
        declared = set(points["phase-rules"].get("names", []))
        actual = set(phases) if isinstance(phases, dict) else set()
        for name in sorted(actual - declared):
            failures.append(
                f"customization: phase {name} of {PHASES} is not in the phase-rules names; "
                "add it to harness/customization.json"
            )
        for name in sorted(declared - actual):
            failures.append(
                f"customization: phase-rules name {name} is not a key of {PHASES}; "
                "remove it from harness/customization.json and add a retired entry"
            )

    if "agent-instructions" in points:
        declared = set(points["agent-instructions"].get("names", []))
        actual = set()
        for path in tree.listing("harness/agents"):
            found = re.search(r"(?m)^name:\s*(\S+)\s*$", (tree.read(path) or b"").decode("utf-8", "replace"))
            if path.endswith(".md") and found:
                actual.add(found.group(1))
        for name in sorted(actual - declared):
            failures.append(
                f"customization: agent {name} of harness/agents/ is not in the agent-instructions names; "
                "add it to harness/customization.json"
            )
        for name in sorted(declared - actual):
            failed_names.add(("agent-instructions", name))
            failures.append(
                f"customization: agent-instructions name {name} is not an agent in harness/agents/; "
                "remove it from harness/customization.json and add a retired entry"
            )

    for point in declaration["points"]:
        for path, installed, name in point_compare_paths(point, phases, with_name=True):
            if (point["id"], name) in failed_names:
                continue
            if tree.read(path) is None:
                failures.append(
                    f"customization: point {point['id']} compares {installed}, but {path} does not exist; "
                    "fix compare in harness/customization.json"
                )

    defaults = parse_json(tree.read(DEFAULTS))
    for key in sorted(defaults) if isinstance(defaults, dict) else []:
        if key not in declaration.get("config_keys", []):
            failures.append(
                f"customization: config key {key} of {DEFAULTS} is not in config_keys; "
                "add it to harness/customization.json"
            )
    return failures


def removed_items(old: dict, new: dict) -> list[tuple[str, str, str]]:
    now = {point["id"]: point for point in new["points"]}
    removed = []
    for point in old["points"]:
        current = now.get(point["id"])
        if current is None:
            removed.append((f"point {point['id']}", point["path"], "point"))
            continue
        gone = [n for n in point.get("names", []) if n not in current.get("names", [])]
        for name in gone:
            removed.append((
                f"name {name} of point {point['id']}", point["path"].replace("{name}", name), "name",
            ))
    for key in old.get("config_keys", []):
        if key not in new.get("config_keys", []):
            removed.append((f"config key {key}", key, "key"))
    return removed


def retirement_failures(tree: Tree, old: dict, new: dict) -> list[str]:
    installer_text = (tree.read(INSTALLER) or b"").decode("utf-8", "replace")
    versions = migration_versions(installer_text)
    current = (tree.read(VERSION_FILE) or b"").decode("utf-8", "replace").strip()
    retired = [entry for entry in new.get("retired", []) if isinstance(entry, dict)]
    failures = []
    for description, path, _kind in removed_items(old, new):
        entries = [entry for entry in retired if entry.get("path") == path]
        if not entries:
            failures.append(
                f"customization: {description} is in HEAD's {DECLARATION} and gone now; add a retired entry "
                f'{{"path": "{path}", "version": "<release version>", "note": "<what happens to repositories using it>"}} '
                f"and a MIGRATIONS entry for that version in {INSTALLER}"
            )
            continue
        for entry in entries:
            version = entry.get("version")
            ok = isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version) and version in versions
            if ok and re.fullmatch(r"\d+\.\d+\.\d+", current):
                ok = version_tuple(version) <= version_tuple(current)
            if not ok:
                failures.append(
                    f"customization: retired entry {path} names version {version}, which is not a version in MIGRATIONS "
                    f"of {INSTALLER} or is above {VERSION_FILE}; add the migration entry or correct the version"
                )
    return failures


def review_warnings(tree: Tree, declaration: dict) -> list[str]:
    phases = parse_json(tree.read(PHASES))
    changed = set(tree.changed())
    warnings = []
    for point in declaration["points"]:
        touched = sorted(changed & {path for path, _installed in point_compare_paths(point, phases)})
        if touched:
            warnings.append(
                f"customization: changes to {', '.join(touched)} will ask repositories with a customization "
                f"at {point['id']} to review it after update"
            )
    return warnings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="customization_check.py")
    parser.add_argument("--staged", action="store_true", help="check the index instead of the working tree")
    args = parser.parse_args(argv)
    tree = Tree(args.staged)

    declaration = parse_json(tree.read(DECLARATION))
    if not valid_declaration(declaration):
        print(f"customization: {DECLARATION} is missing or not a valid declaration; fix it")
        return 1

    failures = structure_failures(tree, declaration)
    previous = parse_json(head_bytes(DECLARATION))
    if valid_declaration(previous):
        failures += retirement_failures(tree, previous, declaration)
    for line in failures:
        print(line)
    for line in review_warnings(tree, declaration):
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
