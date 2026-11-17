#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import config  # noqa: E402

APPROVAL_LABEL = "facts-approved"


def facts_relpath() -> str:
    return config.load_paths().facts.relative_to(config.REPO_ROOT).as_posix()


def changed_lines(base: str, head: str, path: str) -> list[tuple[str, int, str]]:
    diff = subprocess.run(
        ["git", "-C", str(config.REPO_ROOT), "diff", "--no-color", "--no-ext-diff", "--unified=0", f"{base}...{head}", "--", path],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", errors="replace")
    changes = []
    old_line = new_line = 0
    for line in diff.split("\n"):
        if line.startswith("@@"):
            old_part, new_part = line.split(" ")[1:3]
            old_line = int(old_part[1:].split(",")[0])
            new_line = int(new_part[1:].split(",")[0])
        elif line.startswith(("+++", "---")):
            continue
        elif line.startswith("+"):
            changes.append(("+", new_line, line[1:]))
            new_line += 1
        elif line.startswith("-"):
            changes.append(("-", old_line, line[1:]))
            old_line += 1
    return changes


def _escape_annotation(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def usage() -> int:
    print("usage: check_facts_change.py <base-sha> <head-sha> --approved yes|no", file=sys.stderr)
    return 2


def main() -> int:
    args = sys.argv[1:]
    if len(args) != 4 or args[2] != "--approved" or args[3] not in ("yes", "no") or args[0].startswith("--"):
        return usage()
    base, head, approved = args[0], args[1], args[3] == "yes"
    path = facts_relpath()
    try:
        changes = changed_lines(base, head, path)
    except (subprocess.CalledProcessError, OSError) as error:
        message = f"could not diff {path}: {error}"
        print(f"::error title=Facts check failed::{_escape_annotation(message)}")
        return 1
    if not changes:
        print(f"No changes to {path}.")
        return 0
    added = [(number, text) for sign, number, text in changes if sign == "+"]
    removed = [(number, text) for sign, number, text in changes if sign == "-"]
    print(f"## Changes to {path}")
    for title, entries in (("Added", added), ("Removed", removed)):
        if not entries:
            continue
        print()
        print(f"{title} ({len(entries)} line(s)):")
        for number, text in entries:
            print(f"  {number}: {text}")
    print()
    if approved:
        print(f"The `{APPROVAL_LABEL}` label is present.")
        return 0
    for number, text in added:
        print(f"::error file={path},line={number},title=Unapproved facts line::{_escape_annotation(text)}")
    for number, text in removed:
        print(f"::error file={path},title=Unapproved facts removal (old line {number})::{_escape_annotation(text)}")
    message = (
        f"Changes to {path} require approval: check every line above against what the user approved, "
        f"then add the `{APPROVAL_LABEL}` label to this pull request. A new push removes the label; "
        f"add it again after reviewing the new commits."
    )
    print(message)
    print(f"::error title=Missing {APPROVAL_LABEL} label::{_escape_annotation(message)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
