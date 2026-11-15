#!/usr/bin/env python3
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import config  # noqa: E402

REPO_ROOT = config.REPO_ROOT
RULE_TOOLS = {"Write", "Edit", "MultiEdit"}
RULE_DIR = ".harness/instructions"
INDEX_RULE = "index-and-staleness.md"
GIT_TIMEOUT = 10


def safe_session_id(session_id: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id):
        return session_id
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", session_id)[:32]
    digest = hashlib.sha256(session_id.encode("utf-8", "surrogatepass")).hexdigest()[:16]
    return f"{safe}-{digest}"


def marker_dir(session_id: str) -> Path:
    return REPO_ROOT / ".harness" / "sessions" / f"rules-{safe_session_id(session_id)}.d"


def in_git_work_tree() -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def edited_path(payload: dict) -> Path | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    path = Path(file_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def rule_files_for(path: Path, paths: config.Paths) -> tuple[str, list[str]] | None:
    docs = paths.docs_root.resolve()
    if not path.is_relative_to(docs):
        return None
    parts = path.relative_to(docs).parts
    if len(parts) < 2:
        return None
    name = parts[0]
    directory = docs / name
    if name == paths.try_n_fail.name:
        files = ["try-n-fail.md", INDEX_RULE]
    elif name == paths.todos.name:
        files = ["todos.md", INDEX_RULE]
    elif name == paths.synced_comments.name:
        files = ["synced-comments.md"]
    elif name in (paths.specs.name, paths.spec_logs.name) or not (directory / "index.md").is_file():
        return None
    else:
        files = [INDEX_RULE]
    return rel(directory), files


def already_injected(marker: Path) -> bool:
    try:
        return marker.exists()
    except OSError:
        return False


def rule_injection(payload: dict) -> None:
    if payload.get("tool_name") not in RULE_TOOLS:
        return
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return
    path = edited_path(payload)
    if path is None:
        return
    mapped = rule_files_for(path, config.load_paths())
    if mapped is None or not in_git_work_tree():
        return
    directory, files = mapped
    markers = marker_dir(session_id)
    sections = []
    for name in files:
        marker = markers / f"rule-{Path(name).stem}"
        if already_injected(marker):
            continue
        try:
            content = (REPO_ROOT / RULE_DIR / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            markers.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            pass
        sections.append(f"harness: rule text of {RULE_DIR}/{name} for writing in {directory}/:\n\n{content}")
    if sections:
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "\n\n".join(sections)}
        }))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except (ValueError, UnicodeDecodeError, OSError):
        return 0
    if isinstance(payload, dict):
        rule_injection(payload)
    return 0


if __name__ == "__main__":
    # A traceback or nonzero exit here would block or confuse the agent's tool call.
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
