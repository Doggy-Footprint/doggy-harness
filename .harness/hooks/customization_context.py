#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path

# A hook must never fail the tool call or the subagent start, so an import error also exits 0 silently.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    import config  # noqa: E402
    import customization  # noqa: E402
    import rule_injection  # noqa: E402
except Exception:
    sys.exit(0)

REPO_ROOT = config.REPO_ROOT
WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}
LOCAL_PREFIX = customization.LOCAL + "/"


def relative_path(payload: dict) -> str | None:
    path = rule_injection.edited_path(payload)
    if path is None:
        return None
    try:
        rel = path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return None
    return rel if rel == customization.AGENTS_MD or rel.startswith(LOCAL_PREFIX) else None


def first_in_session(session_id: str, rel: str) -> bool:
    markers = rule_injection.marker_dir(session_id)
    markers.mkdir(parents=True, exist_ok=True)
    try:
        # Exclusive creation keeps two parallel tool calls from both speaking.
        fd = os.open(markers / f"customization-{hashlib.sha256(rel.encode('utf-8')).hexdigest()[:16]}",
                     os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def written_file_context(payload: dict) -> str | None:
    session_id = payload.get("session_id")
    if payload.get("tool_name") not in WRITE_TOOLS or not isinstance(session_id, str) or not session_id:
        return None
    rel = relative_path(payload)
    if rel is None or not rule_injection.in_git_work_tree():
        return None
    declaration = customization.load_declaration(REPO_ROOT)
    found = customization.recognize(declaration, rel)
    if not first_in_session(session_id, rel):
        return None
    if found is None:
        paths = ", ".join(point["path"] for point in (declaration or {}).get("points", []))
        return f"harness customization: the harness does not read {rel}. Recognized customization paths: {paths}."
    point, name = found
    compare = ", ".join(customization.compare_paths(REPO_ROOT, point, name))
    return (
        f"harness customization: {rel} is a customization ({point['id']}). It is followed where it disagrees with "
        f"{compare}. Read those files, tell the user each disagreement before you finish, and run "
        f"{customization.CONFIRM_COMMAND} {rel} only after the user confirms."
    )


def subagent_context(payload: dict) -> str | None:
    agent = payload.get("agent_type")
    if not isinstance(agent, str):
        return None
    rel = f"{customization.LOCAL}/agents/{agent}.md"
    found = customization.recognize(customization.load_declaration(REPO_ROOT), rel)
    if found is None or found[0]["id"] != "agent-instructions":
        return None
    try:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return (
        f"## Project instructions for this agent\nFrom {rel}. "
        f"Where these disagree with your instructions above, follow these.\n\n{text}"
    )


def main() -> int:
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        return 0
    if payload.get("hook_event_name") == "SubagentStart":
        event, context = "SubagentStart", subagent_context(payload)
    else:
        event, context = "PostToolUse", written_file_context(payload)
    if context is not None:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    # A hook must never fail the tool call or the subagent start: any internal error prints nothing and exits 0.
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
