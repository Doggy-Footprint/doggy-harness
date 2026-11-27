#!/usr/bin/env python3
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tokenize
from collections import defaultdict
from pathlib import Path
from typing import Callable

COMMENT_PATTERN = re.compile(r"\s*(?://|/\*|#|'''|\"\"\")")
APPROVAL_LABEL = "comments-approved"
CODE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js",
    ".jsx", ".kt", ".php", ".py", ".rb", ".rs", ".sh", ".swift", ".ts",
    ".tsx", ".yaml", ".yml", ".mts", ".cts", ".mjs", ".cjs",
}
GRAMMAR_BY_EXTENSION = {
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".tsx": "tsx", ".js": "tsx", ".jsx": "tsx", ".mjs": "tsx", ".cjs": "tsx",
}
SCANNER = Path(__file__).resolve().with_name("ts_comments.py")
SCANNER_PACKAGES = ("tree-sitter==0.27.0", "tree-sitter-typescript==0.23.2")
STATEMENT_START_TOKENS = {tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING}
SKIPPED_TOKENS = {tokenize.NL, tokenize.COMMENT}
TOOL_DIRECTIVE_PATTERN = re.compile(r"#\s*(?:noqa(?::|\s|$)|(?:type|pragma|pylint|mypy|pyright|fmt|isort):)")


class CommentScanError(Exception):
    pass


def _new_content(revision: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout if result.returncode == 0 else None


def _python_comment_lines(source: str) -> set[int] | None:
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError):
        return None
    lines = {
        token.start[0]
        for token in tokens
        if token.type == tokenize.COMMENT and not TOOL_DIRECTIVE_PATTERN.match(token.string)
    }
    significant = [token for token in tokens if token.type not in SKIPPED_TOKENS]
    index = 0
    while index < len(significant):
        if significant[index].type != tokenize.STRING:
            index += 1
            continue
        first = index
        while index < len(significant) and significant[index].type == tokenize.STRING:
            index += 1
        starts_statement = first == 0 or significant[first - 1].type in STATEMENT_START_TOKENS
        ends_statement = index == len(significant) or significant[index].type in (tokenize.NEWLINE, tokenize.ENDMARKER)
        if starts_statement and ends_statement:
            lines.update(range(significant[first].start[0], significant[index - 1].end[0] + 1))
    return lines


def _is_comment(line_number: int, content: str, python_lines: set[int] | None) -> bool:
    if line_number == 1 and content.startswith("#!"):
        return False
    if python_lines is not None:
        return line_number in python_lines
    return bool(COMMENT_PATTERN.match(content))


def _grammar(path: str) -> str | None:
    return GRAMMAR_BY_EXTENSION.get(os.path.splitext(path)[1])


def _scan_typescript(sources: dict[str, tuple[str, str]]) -> dict[str, set[int]]:
    names = ", ".join(sources)
    uv = shutil.which("uv")
    if uv is None:
        raise CommentScanError(f"{names}: uv not found on PATH")
    request = json.dumps({path: {"grammar": grammar, "source": source} for path, (grammar, source) in sources.items()})
    command = [uv, "run", "--no-project", "--offline"]
    for package in SCANNER_PACKAGES:
        command += ["--with", package]
    command += ["python", "-I", str(SCANNER)]
    result = None
    for attempt in (command, [part for part in command if part != "--offline"]):
        try:
            result = subprocess.run(attempt, input=request, capture_output=True, encoding="utf-8", errors="replace")
        except OSError as error:
            raise CommentScanError(f"{names}: could not start uv: {error}") from error
        if result.returncode == 0:
            break
    else:
        stderr = result.stderr.strip().splitlines()
        raise CommentScanError(
            f"{names}: uv exited with code {result.returncode}" + (f": {stderr[0]}" if stderr else "")
        )
    try:
        parsed = json.loads(result.stdout)
    except ValueError:
        parsed = None
    valid = isinstance(parsed, dict) and all(
        isinstance(parsed.get(path), list)
        and all(isinstance(line, int) and not isinstance(line, bool) for line in parsed[path])
        for path in sources
    )
    if not valid:
        raise CommentScanError(f"{names}: unexpected scanner output")
    return {path: set(parsed[path]) for path in sources}


def _detect_comments(
    files: list[tuple[str, list[tuple[int, str]], Callable[[], str | None]]],
) -> list[tuple[str, int, str]]:
    checked = [entry for entry in files if any(entry[0].endswith(ext) for ext in CODE_EXTENSIONS)]
    contents = {path: load() if path.endswith(".py") or _grammar(path) else None for path, _, load in checked}
    typescript = {}
    for path, added, _ in checked:
        if _grammar(path) and added:
            if contents[path] is None:
                raise CommentScanError(f"{path}: could not read the new content")
            typescript[path] = (_grammar(path), contents[path])
    scanned = _scan_typescript(typescript) if typescript else {}
    findings = []
    for path, added, _ in checked:
        python_lines = None
        if path.endswith(".py") and contents[path] is not None:
            python_lines = _python_comment_lines(contents[path])
        for line_number, content in added:
            if path in scanned:
                is_comment = line_number in scanned[path]
            else:
                is_comment = _is_comment(line_number, content, python_lines)
            if is_comment:
                findings.append((path, line_number, content.strip()))
    return findings


def _diff_files(diff_text: str) -> list[tuple[str, list[tuple[int, str]]]]:
    files = []
    added = None
    line_number = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            line_number = None
            if line.startswith("+++ b/"):
                added = []
                files.append((line[6:], added))
            else:
                added = None
            continue
        if line.startswith("@@ "):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            line_number = int(match.group(1)) if match else None
            continue
        if added is None or line_number is None or not line.startswith("+"):
            continue
        added.append((line_number, line[1:]))
        line_number += 1
    return files


def _added_comments(diff_args: list[str], revision: str) -> list[tuple[str, int, str]]:
    result = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", *diff_args, "--"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return _detect_comments([
        (path, added, lambda path=path: _new_content(revision, path)) for path, added in _diff_files(result.stdout)
    ])


def changed_lines(base: str, head: str) -> list[tuple[str, int, str]]:
    return _added_comments([f"{base}...{head}"], head)


def staged_lines() -> list[tuple[str, int, str]]:
    return _added_comments(["--cached"], "")


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True, encoding="utf-8", errors="replace")
    except OSError as error:
        raise CommentScanError(f"git could not run: {error}") from error


def _git_checked(root: str, *args: str) -> str:
    result = _git(root, *args)
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines()
        raise CommentScanError(f"git {args[0]} failed" + (f": {lines[0]}" if lines else ""))
    return result.stdout


def working_tree_comments(paths: list[str]) -> list[tuple[str, int, str]]:
    root = _git_checked(".", "rev-parse", "--show-toplevel").strip()
    has_commit = _git(root, "rev-parse", "--verify", "--quiet", "HEAD").returncode == 0

    def selected(path: str) -> bool:
        for wanted in paths:
            wanted = wanted[2:] if wanted.startswith("./") else wanted
            if wanted.endswith("/") or (Path(root) / wanted).is_dir():
                if path.startswith(wanted.rstrip("/") + "/"):
                    return True
            elif path == wanted:
                return True
        return False

    def read(path: str) -> str | None:
        try:
            return (Path(root) / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    by_path: dict[str, list[tuple[int, str]]] = {}
    if has_commit:
        for path, added in _diff_files(_git_checked(root, "diff", "--unified=0", "--no-color", "HEAD", "--")):
            by_path[path] = added
        listing = _git_checked(root, "ls-files", "-z", "--others", "--exclude-standard")
    else:
        listing = _git_checked(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for path in filter(None, listing.split("\0")):
        if not selected(path) or not path.endswith(tuple(CODE_EXTENSIONS)):
            continue
        content = read(path)
        if content is None:
            continue
        lines = content.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        by_path[path] = list(enumerate(lines, 1))
    return _detect_comments([
        (path, added, lambda path=path: read(path)) for path, added in by_path.items() if selected(path)
    ])


def usage() -> int:
    print(
        "usage: warn_new_comments.py --staged | "
        "<base-sha> <head-sha> [--approved yes|no]",
        file=sys.stderr,
    )
    return 2


def staged_main() -> int:
    try:
        findings = staged_lines()
    except CommentScanError as error:
        print(f"comment check could not run for {error}", file=sys.stderr)
        print(
            "If you are an AI agent, report every added comment above to the user.",
            file=sys.stderr,
        )
        return 0
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"warn_new_comments: could not read staged diff: {error}", file=sys.stderr)
        return 0
    if not findings:
        return 0
    for path, line, content in findings:
        print(f"{path}:{line}: {content}", file=sys.stderr)
    print(
        "If you are an AI agent, report every added comment above to the user.",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args == ["--staged"]:
        return staged_main()
    approved = None
    if len(args) == 4 and args[2] == "--approved":
        if args[3] not in ("yes", "no"):
            return usage()
        approved = args[3] == "yes"
        args = args[:2]
    if len(args) != 2 or any(arg.startswith("--") for arg in args):
        return usage()
    try:
        findings = changed_lines(args[0], args[1])
    except CommentScanError as error:
        if approved is None:
            print(f"::warning title=Comment check could not run::{error}")
            return 0
        print(f"::error title=Comment check could not run::{error}")
        return 1
    grouped = defaultdict(list)
    for path, line, content in findings:
        grouped[path].append((line, content))
        message = "New comment or docstring: confirm it records non-obvious rationale."
        print(f"::warning file={path},line={line}::{message}")
    if not grouped:
        print("No added comments or docstrings detected.")
        return 0
    print("## Comment review reminders")
    print()
    print("New comments or docstrings were added. Review whether each is necessary.")
    print()
    for path, entries in grouped.items():
        lines = ", ".join(str(line) for line, _ in entries)
        print(f"- `{path}`: line(s) {lines}")
    if approved is not False:
        return 0
    message = (
        f"New comments or docstrings require approval: review them, then add the "
        f"`{APPROVAL_LABEL}` label to this pull request. A new push removes the label; "
        f"add it again after reviewing the new commits."
    )
    print()
    print(message)
    print(f"::error title=Missing {APPROVAL_LABEL} label::{message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
