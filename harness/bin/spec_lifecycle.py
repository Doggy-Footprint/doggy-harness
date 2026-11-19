#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import spec_state  # noqa: E402

PATHS = spec_state.PATHS
REPO_ROOT = spec_state.REPO_ROOT
SPECS_DIR = spec_state.SPECS_DIR
SPEC_LOGS_DIR = spec_state.SPEC_LOGS_DIR
SEED_DIR = spec_state.SEED_DIR
frontmatter = spec_state.frontmatter
seed_files = spec_state.seed_files
TERMINAL = spec_state.TERMINAL
RUN_ID_RE = re.compile(r"[0-9a-f]{16}")
NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TEMPLATE = Path(__file__).resolve().parents[1] / "skills" / "doggy-workflow" / "spec-template.md"
TEMPLATE_FRONTMATTER = (
    ("version: <positive integer>", "version: 1"),
    ("run_id: <16 lowercase hexadecimal characters>", "run_id: {run_id}"),
    ("status: draft|active|complete|limit|aborted", "status: draft"),
    ("base_commit: <full commit id at workflow start>", "base_commit: {base_commit}"),
)
COMMIT_RE = re.compile(r"[0-9a-f]{40,64}")
QUALITY_CHARACTERISTICS = (
    "functional suitability",
    "performance efficiency",
    "compatibility",
    "interaction capability",
    "reliability",
    "security",
    "maintainability",
    "flexibility",
    "safety",
)
REQUIRED_HEADINGS = (
    "# User Intent",
    "# Scope",
    "# Paths",
    "# Signatures",
    "# Functional Requirements",
    "# Errors",
    "# Cases",
    "# Quality Applicability",
    "# Quality Requirements",
    "# Verification Obligations",
    "# Assumptions and Defaults",
    "# Alternatives",
    "# Open Questions",
    "# Traceability",
    "# Workflow Control",
    "# Version Log",
)


def fail(message: str) -> int:
    print(f"spec lifecycle: {message}", file=sys.stderr)
    return 1


def validate(path: Path) -> list[str]:
    errors = []
    if path.parent.resolve() != SPECS_DIR or path.suffix != ".md":
        return ["spec must be a direct .md child of agent-docs/specs"]
    values = frontmatter(path)
    try:
        if int(values.get("version", "")) < 1:
            errors.append("version must be a positive integer")
    except ValueError:
        errors.append("version must be a positive integer")
    run_id = values.get("run_id", "")
    if not RUN_ID_RE.fullmatch(run_id):
        errors.append("run_id must be 16 lowercase hexadecimal characters")
    elif not path.name.startswith(run_id + "-"):
        errors.append("filename must start with run_id")
    if values.get("status") not in {"draft", "active", *TERMINAL}:
        errors.append("status must be draft, active, complete, limit, or aborted")
    if not COMMIT_RE.fullmatch(values.get("base_commit", "")):
        errors.append("base_commit must be a 40-64 character hexadecimal commit id")
    if values.get("max_verifier_invocations") != "2":
        errors.append("max_verifier_invocations must be 2")
    if "max_correction_rounds" in values:
        errors.append("max_correction_rounds is obsolete; migrate the spec")
    if values.get("handoff", "none") != "none":
        handoff = Path(values["handoff"])
        try:
            (REPO_ROOT / handoff).resolve().relative_to(REPO_ROOT)
        except ValueError:
            errors.append("handoff must be a repo-relative path")
        if handoff.is_absolute():
            errors.append("handoff must be a repo-relative path")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return errors + ["spec cannot be read"]
    headings = set(text.splitlines())
    errors.extend(f"missing heading {heading}" for heading in REQUIRED_HEADINGS if heading not in headings)
    lower = text.lower()
    errors.extend(
        f"Quality Applicability is missing {name}"
        for name in QUALITY_CHARACTERISTICS
        if name not in lower
    )
    return errors


def cmd_validate(args) -> int:
    path = Path(args.spec).resolve()
    errors = validate(path)
    if errors:
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    return 0


def cmd_new(args) -> int:
    if RUN_ID_RE.fullmatch(args.run_id) is None:
        return fail("run id must be 16 lowercase hexadecimal characters")
    if NAME_RE.fullmatch(args.name) is None:
        return fail("name must be lowercase letters and digits joined by single hyphens")
    path = SPECS_DIR / f"{args.run_id}-{args.name}.md"
    taken = sorted(SPECS_DIR.glob(f"{args.run_id}-*.md")) + sorted(SPEC_LOGS_DIR.glob(f"{args.run_id}-*.md"))
    if taken:
        return fail(f"run id {args.run_id} already has a spec: {taken[0].relative_to(REPO_ROOT)}")
    try:
        text = TEMPLATE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return fail(f"spec template not readable: {TEMPLATE}")
    try:
        head = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        head = ""
    if COMMIT_RE.fullmatch(head) is None:
        return fail("cannot read the current commit for base_commit; the repository needs at least one commit")
    for placeholder, value in TEMPLATE_FRONTMATTER:
        if text.count(placeholder) != 1:
            return fail(f"spec template has no line `{placeholder}`")
        text = text.replace(placeholder, value.format(run_id=args.run_id, base_commit=head))
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(text)
    except OSError as error:
        return fail(f"cannot create {path.relative_to(REPO_ROOT)}: {error.strerror}")
    print(path.relative_to(REPO_ROOT).as_posix())
    return 0


def seed_refusal() -> str:
    return f"{SEED_DIR} holds an unrestored seed backup; run `{spec_state.SEED_RESTORE}`"


def live_session_refusal(path: Path, confirmed: bool) -> str | None:
    if confirmed:
        return None
    others = spec_state.other_live_sessions()
    if not others:
        return None
    return (
        f"keeping {path.name}; other harness session(s) are running against this repo: "
        f"{spec_state.format_sessions(others)}. Ask the user whether any of them runs this workflow, "
        "then re-run with --other-sessions-confirmed only after the user confirms none does"
    )


def cmd_start(args) -> int:
    path = Path(args.spec).resolve()
    errors = validate(path)
    if errors:
        return fail("invalid spec: " + "; ".join(errors))
    values = frontmatter(path)
    if values.get("status") != "active":
        return fail("start requires spec status active")
    if values.get("run_id") != args.run_id:
        return fail("--run-id does not match spec frontmatter")
    if seed_files():
        return fail(f"cannot start; {seed_refusal()}")
    other_active = [
        candidate.name
        for candidate in SPECS_DIR.glob("*.md")
        if candidate != path and frontmatter(candidate).get("status") in {"draft", "active"}
    ]
    if other_active:
        return fail("another workflow is active: " + ", ".join(sorted(other_active)))
    return 0


def archive(path: Path, expected_status: str, confirmed: bool = False) -> int:
    if seed_files():
        return fail(f"keeping {path}; {seed_refusal()}")
    values = frontmatter(path)
    if values.get("status") != expected_status or expected_status not in TERMINAL:
        return fail(f"archive requires matching terminal status, got {values.get('status')!r}")
    if path.parent.resolve() != SPECS_DIR or path.suffix != ".md":
        return fail(f"refusing to archive a path outside {spec_state.rel(SPECS_DIR)}")
    if expected_status == "aborted":
        refusal = live_session_refusal(path, confirmed)
        if refusal:
            return fail(refusal)
    destination = SPEC_LOGS_DIR / path.name
    if destination.exists():
        return fail(f"archive destination already exists: {destination}")
    SPEC_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path.rename(destination)
    print(destination.relative_to(REPO_ROOT))
    return 0


def cmd_archive(args) -> int:
    return archive(Path(args.spec).resolve(), args.status, args.other_sessions_confirmed)


STATUS_LINE_RE = re.compile(rb"([ \t]*status[ \t]*:[ \t]*)(.*?)([ \t\r\n]*)\Z", re.S)


def with_status_aborted(data: bytes) -> bytes | None:
    lines = data.splitlines(keepends=True)
    if not lines or lines[0].strip() != b"---":
        return None
    index = None
    for number, line in enumerate(lines[1:], start=1):
        if line.strip() == b"---":
            if index is None:
                return None
            match = STATUS_LINE_RE.match(lines[index])
            lines[index] = match.group(1) + b"aborted" + match.group(3)
            return b"".join(lines)
        if b":" in line and line.split(b":", 1)[0].strip() == b"status":
            index = number
    return None


def cmd_abort(args) -> int:
    path = Path(args.spec).resolve()
    if path.parent != SPECS_DIR or path.suffix != ".md" or not path.is_file():
        return fail(f"abort requires an existing direct .md child of {spec_state.rel(SPECS_DIR)}")
    try:
        data = path.read_bytes()
    except OSError as error:
        return fail(f"cannot read {path.name}: {error.strerror}")
    rewritten = with_status_aborted(data)
    if rewritten is None:
        return fail(f"{path.name} needs a frontmatter block with a status line")
    status = frontmatter(path).get("status")
    if status in {"complete", "limit"}:
        return fail(f"{path.name} is {status}; use archive --status {status}")
    if status not in {"draft", "active", "aborted"}:
        return fail(f"{path.name} has status {status!r}; abort needs draft, active, or aborted")
    if seed_files():
        return fail(f"cannot abort; {seed_refusal()}")
    refusal = live_session_refusal(path, args.other_sessions_confirmed)
    if refusal:
        return fail(refusal)
    destination = SPEC_LOGS_DIR / path.name
    if destination.exists():
        return fail(f"archive destination already exists: {destination}")
    SPEC_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        return fail(f"archive destination already exists: {destination}")
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(rewritten)
    except OSError as error:
        destination.unlink(missing_ok=True)
        return fail(f"cannot write {destination}: {error.strerror}")
    path.unlink()
    print(destination.relative_to(REPO_ROOT))
    return 0


def cmd_notice(_args) -> int:
    spec_state.print_notice()
    return 0


def cmd_session(_args) -> int:
    if not SPECS_DIR.is_dir():
        return 0
    if seed_files():
        print(
            f"spec lifecycle: keeping active specs; {SEED_DIR} holds an unrestored seed backup. "
            "Run `python3 .harness/bin/seed.py restore`.",
            file=sys.stderr,
        )
        return 0
    for path in sorted(SPECS_DIR.glob("*.md")):
        values = frontmatter(path)
        status = values.get("status")
        if status in TERMINAL:
            archive(path, status)
            continue
        if status in {"draft", "active"}:
            print(
                f"spec lifecycle: {path.relative_to(REPO_ROOT)} is {status}; compare base commit "
                f"{values.get('base_commit', 'unknown')} with HEAD before resuming or aborting",
                file=sys.stderr,
            )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)
    validate_command = commands.add_parser("validate")
    validate_command.add_argument("--spec", required=True)
    validate_command.set_defaults(handler=cmd_validate)
    new = commands.add_parser("new")
    new.add_argument("--run-id", required=True)
    new.add_argument("--name", required=True)
    new.set_defaults(handler=cmd_new)
    start = commands.add_parser("start")
    start.add_argument("--spec", required=True)
    start.add_argument("--run-id", required=True)
    start.add_argument("--resume", action="store_true")
    start.set_defaults(handler=cmd_start)
    archive_command = commands.add_parser("archive")
    archive_command.add_argument("--spec", required=True)
    archive_command.add_argument("--status", required=True, choices=sorted(TERMINAL))
    archive_command.add_argument("--other-sessions-confirmed", action="store_true")
    archive_command.set_defaults(handler=cmd_archive)
    abort = commands.add_parser("abort")
    abort.add_argument("--spec", required=True)
    abort.add_argument("--other-sessions-confirmed", action="store_true")
    abort.set_defaults(handler=cmd_abort)
    notice = commands.add_parser("notice")
    notice.set_defaults(handler=cmd_notice)
    session = commands.add_parser("session")
    session.set_defaults(handler=cmd_session)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
