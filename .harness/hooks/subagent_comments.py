#!/usr/bin/env python3
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

# Runs on every subagent start and finish: a bug here must never block a subagent, so every error except a
# failed scan prints nothing and exits 0. A failed scan is reported to the subagent, never treated as clean.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "git"))
    import config  # noqa: E402
    import isolation  # noqa: E402
    import telemetry  # noqa: E402
    import warn_new_comments  # noqa: E402
except Exception:
    sys.exit(0)

REPO_ROOT = config.REPO_ROOT
RECORDS_DIR = REPO_ROOT / ".harness" / "sessions" / "subagent-comments"
ROLES = {"implementer": "implementation", "test-implementer": "tests"}
ENTRY_LIMIT = 50
CATEGORY_SENTENCE = (
    "Keep a comment only when it records a non-obvious design constraint, external-system behavior, "
    "safety/security invariant, or reason a seemingly odd implementation is necessary. Delete every other comment "
    "above. List each comment you keep under Comments in your report, with its category, then hand back."
)


def record_name(payload: dict) -> str:
    key = payload.get("agent_id") or payload.get("agent_type") or ""
    return re.sub(r"[^A-Za-z0-9._-]", "_", key)


def role_paths(payload: dict) -> list[str]:
    role = payload.get("agent_type")
    if role not in ROLES or not config.load_paths().specs.is_dir():
        return []
    specs = isolation._read_specs(config.load_paths().specs)
    return [path for spec in specs for path in spec[ROLES[role]]]


def scan(paths: list[str]) -> list[tuple[str, int, str]]:
    os.chdir(REPO_ROOT)
    return warn_new_comments.working_tree_comments(paths)


def on_start(payload: dict) -> None:
    paths = role_paths(payload)
    if not paths:
        return
    entries, scan_ok = [], True
    try:
        entries = [[path, text] for path, _, text in scan(paths)]
    except warn_new_comments.CommentScanError:
        scan_ok = False
    baseline = {"failed": not scan_ok, "entries": entries}
    if telemetry.write_json_atomic(RECORDS_DIR / f"{record_name(payload)}.json", baseline):
        telemetry.emit(payload, "subagent_comments", stage="start", trigger="start", new_comments=0,
                       scan_ok=scan_ok, blocked=False)


def read_baseline(name: str) -> Counter:
    try:
        baseline = json.loads((RECORDS_DIR / f"{name}.json").read_text(encoding="utf-8"))
        if baseline["failed"] is not False:
            return Counter()
        return Counter((path, text) for path, text in baseline["entries"])
    except (OSError, ValueError, KeyError, TypeError):
        return Counter()


def new_comments(paths: list[str], name: str) -> list[tuple[str, int, str]]:
    remaining = read_baseline(name)
    fresh = []
    for path, line, text in scan(paths):
        if remaining[(path, text)] > 0:
            remaining[(path, text)] -= 1
        else:
            fresh.append((path, line, text))
    return fresh


def reason_for(fresh: list[tuple[str, int, str]]) -> str:
    lines = ["harness: comment check before you hand back."]
    lines += [f"{path}:{line}: {text}" for path, line, text in fresh[:ENTRY_LIMIT]]
    if len(fresh) > ENTRY_LIMIT:
        lines.append(f"... and {len(fresh) - ENTRY_LIMIT} more")
    lines.append(CATEGORY_SENTENCE)
    return "\n".join(lines)


def first_stop(name: str) -> bool | None:
    try:
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        os.close(os.open(RECORDS_DIR / f"{name}.stopped", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False
    except OSError:
        return None


def on_finish(payload: dict, trigger: str) -> None:
    name = record_name(payload)
    paths = role_paths(payload)
    if not paths:
        if trigger == "stop":
            clean_up(name)
        return
    fresh, scan_ok, reason = [], True, None
    try:
        fresh = new_comments(paths, name)
        if fresh:
            reason = reason_for(fresh)
    except warn_new_comments.CommentScanError as error:
        scan_ok = False
        reason = (
            f"harness: the comment check could not run: {error}. "
            "Write this under Comments in your report, then hand back."
        )
    stop = reason is not None and first_stop(name)
    if reason is not None and stop is None:
        return
    telemetry.emit(payload, "subagent_comments", stage="finish", trigger=trigger, new_comments=len(fresh),
                   scan_ok=scan_ok, blocked=bool(stop))
    if stop:
        if trigger == "handback":
            output = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}
        else:
            output = {"decision": "block", "reason": reason}
        sys.stdout.write(json.dumps(output))
        sys.stdout.flush()
    elif trigger == "stop":
        clean_up(name)


def clean_up(name: str) -> None:
    for suffix in ("json", "stopped"):
        (RECORDS_DIR / f"{name}.{suffix}").unlink(missing_ok=True)


def main() -> int:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict) or payload.get("agent_type") not in ROLES:
        return 0
    event = payload.get("hook_event_name")
    if event == "SubagentStart":
        on_start(payload)
    elif event == "SubagentStop":
        on_finish(payload, "stop")
    elif event == "PreToolUse" and payload.get("tool_name") == "SubagentHandback":
        on_finish(payload, "handback")
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
