"""Every reporter computes customization states with this module, so a state never differs between
them. `overrides` maps a repository-relative path to the bytes the file will have (None: the file will
be absent), which lets the installer judge a target against the harness files it is about to write.
"""
import datetime
import hashlib
import json
import os
import posixpath
import re
from pathlib import Path

import config

MANAGED_BLOCK_RE = re.compile(r"<!-- harness:begin [^\n]*-->\n(.*?)<!-- harness:end -->\n?", re.DOTALL)

DECLARATION = ".harness/customization.json"
REVIEW = ".harness/customization-review.json"
CONFIG = ".harness/config.json"
LOCAL = ".harness/local"
SETTINGS = ".claude/settings.json"
PHASES_JSON = ".harness/skills/doggy-workflow/phases.json"
PHASE_FRAGMENTS = ".harness/skills/doggy-workflow/phases"
AGENTS_MD = "AGENTS.md"

UNCONFIRMED = "unconfirmed"
HARNESS_CHANGED = "harness-changed"
CONFIRMED = "confirmed"
UNRECOGNIZED = "unrecognized"
RETIRED = "retired"

DECLARATION_MISSING_LINE = f"customization declaration missing or invalid: {DECLARATION}"
INSTRUCTION_LINE = (
    "before other work, tell the user about each line below. Where a customization disagrees with harness text, "
    "the customization is followed: read both and name each disagreement. "
    "Run the confirm command for an item only after the user confirms it."
)
CONFIRM_COMMAND = "python3 .harness/bin/customization.py confirm"
LOCAL_REFERENCE_RE = re.compile(r"\.harness/local/([^\s\"'`$;&|()<>\\]+)")


def _is_str_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def parse_declaration(data: bytes | None) -> dict | None:
    try:
        raw = json.loads(data.decode("utf-8"))
    except (AttributeError, ValueError):
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("points"), list):
        return None
    points = []
    for point in raw["points"]:
        if not isinstance(point, dict) or not isinstance(point.get("id"), str) or not isinstance(point.get("path"), str):
            return None
        names = point.get("names")
        compare = point.get("compare", [])
        if not _is_str_list(compare) or (names is not None and not _is_str_list(names)):
            return None
        if "{name}" in point["path"] and names is None:
            return None
        points.append({
            "id": point["id"],
            "path": point["path"],
            "names": names,
            "compare": compare,
            "phase_fragments": point.get("compare_phase_fragments") is True,
        })
    keys = raw.get("config_keys", [])
    retired = raw.get("retired", [])
    if not _is_str_list(keys) or not isinstance(retired, list):
        return None
    for entry in retired:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) for k in ("path", "version", "note")):
            return None
    return {"points": points, "config_keys": keys, "retired": retired}


def read_bytes(root: Path, rel: str, overrides: dict | None = None) -> bytes | None:
    if overrides is not None and rel in overrides:
        return overrides[rel]
    try:
        return (root / rel).read_bytes()
    except OSError:
        return None


def load_declaration(root: Path, overrides: dict | None = None) -> dict | None:
    return parse_declaration(read_bytes(root, DECLARATION, overrides))


def git_hook_names(declaration: dict | None) -> list[str]:
    for point in (declaration or {}).get("points", []):
        if point["id"] == "git-hook":
            return list(point["names"] or [])
    return []


def _regex(pattern: str) -> re.Pattern:
    if pattern.endswith("/**"):
        return re.compile(re.escape(pattern[:-2]) + r".+", re.DOTALL)
    before, found, after = pattern.partition("{name}")
    if not found:
        return re.compile(re.escape(pattern))
    return re.compile(re.escape(before) + r"(?P<name>[^/]+)" + re.escape(after))


def match_pattern(pattern: str, rel: str, names: list[str] | None) -> tuple[bool, str | None]:
    found = _regex(pattern).fullmatch(rel)
    if not found:
        return False, None
    name = found.groupdict().get("name")
    if name is not None and names is not None and name not in names:
        return False, None
    return True, name


def recognize(declaration: dict | None, rel: str) -> tuple[dict, str | None] | None:
    for point in (declaration or {}).get("points", []):
        matched, name = match_pattern(point["path"], rel, point["names"])
        if matched:
            return point, name
    return None


def retired_note(declaration: dict | None, rel: str) -> str | None:
    for entry in (declaration or {}).get("retired", []):
        if match_pattern(entry["path"], rel, None)[0]:
            return entry["note"]
    return None


def _phase_fragments(root: Path, name: str, overrides: dict | None) -> list[str]:
    try:
        entries = json.loads(read_bytes(root, PHASES_JSON, overrides).decode("utf-8"))[name]
    except (AttributeError, ValueError, KeyError, TypeError):
        return []
    fragments = []
    for entry in entries if isinstance(entries, list) else []:
        fragment = entry if isinstance(entry, str) else entry.get("name") if isinstance(entry, dict) else None
        if isinstance(fragment, str):
            fragments.append(f"{PHASE_FRAGMENTS}/{fragment}.md")
    return fragments


def compare_paths(root: Path, point: dict, name: str | None, overrides: dict | None = None) -> list[str]:
    paths = [path.replace("{name}", name) if name else path for path in point["compare"]]
    if point["phase_fragments"] and name:
        paths += _phase_fragments(root, name, overrides)
    return list(dict.fromkeys(paths))


def compare_hash(root: Path, paths: list[str], overrides: dict | None = None) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.encode("utf-8") + b"\0")
        data = read_bytes(root, path, overrides)
        digest.update(b"missing" if data is None else b"file" + hashlib.sha256(data).digest())
        digest.update(b"\0")
    return digest.hexdigest()


def content_hash(root: Path, rel: str) -> str | None:
    try:
        data = (root / rel).read_bytes()
    except OSError:
        return None
    if rel == AGENTS_MD:
        text = data.decode("utf-8", "surrogateescape")
        found = MANAGED_BLOCK_RE.search(text)
        if found:
            text = text[: found.start()] + text[found.end():]
        data = text.encode("utf-8", "surrogateescape")
    return hashlib.sha256(data).hexdigest()


def config_problem(root: Path) -> str | None:
    return config.read_override(root / CONFIG)[1]


def _read_review(root: Path) -> tuple[dict, bool]:
    path = root / REVIEW
    if not os.path.lexists(path):
        return {}, False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, True
    if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
        return {}, True
    return data["items"], False


def _problem(kind: str, text: str, notice: str | None = None) -> dict:
    return {"kind": kind, "text": text, "notice": notice or text}


def _local_files(root: Path) -> list[str]:
    found = []
    base = root / LOCAL
    for directory, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if path.is_file():
                found.append(path.relative_to(root).as_posix())
    return sorted(found)


def _referenced_local_paths(root: Path) -> list[str]:
    try:
        settings = json.loads((root / SETTINGS).read_text(encoding="utf-8"))
        groups = [group for event in settings["hooks"].values() for group in event]
        commands = [hook["command"] for group in groups for hook in group["hooks"]]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []
    referenced = []
    for command in commands:
        if isinstance(command, str):
            referenced += LOCAL_REFERENCE_RE.findall(command)
    return list(dict.fromkeys(referenced))


def _state(record, content: str | None, compare: str) -> str:
    if not isinstance(record, dict) or content is None or record.get("content") != content:
        return UNCONFIRMED
    return CONFIRMED if record.get("compare") == compare else HARNESS_CHANGED


def analyze(root: Path | str | None = None, overrides: dict | None = None) -> dict:
    root = Path(root) if root is not None else config.REPO_ROOT
    declaration = load_declaration(root, overrides)
    reviewed, review_invalid = _read_review(root)
    items = []
    problems = []

    candidates = []
    if (root / AGENTS_MD).is_file():
        candidates.append(AGENTS_MD)
    candidates += _local_files(root)
    for rel in candidates:
        found = recognize(declaration, rel)
        if found is None:
            note = retired_note(declaration, rel)
            state = RETIRED if note is not None else UNRECOGNIZED
            items.append({"path": rel, "point": None, "state": state, "compare": [], "note": note})
            continue
        point, name = found
        paths = compare_paths(root, point, name, overrides)
        content = content_hash(root, rel)
        compare = compare_hash(root, paths, overrides)
        items.append({
            "path": rel,
            "point": point["id"],
            "state": _state(reviewed.get(rel), content, compare),
            "compare": paths,
            "note": None,
            "content": content,
            "compare_hash": compare,
        })
        if point["id"] == "git-hook" and not os.access(root / rel, os.X_OK):
            problems.append(_problem(
                "not-executable", f"not-executable {rel}",
                f"not-executable {rel}; the git hook does not run until you run chmod +x {rel}",
            ))
    items.sort(key=lambda item: item["path"])

    ordered = []
    if declaration is None:
        ordered.append(_problem("declaration", DECLARATION_MISSING_LINE))
    reason = config_problem(root)
    if reason is not None:
        ordered.append(_problem(
            "config-invalid", f"config-invalid {CONFIG}: {reason}",
            f"config-invalid {CONFIG}; harness defaults are used until it is fixed",
        ))
    elif declaration is not None:
        override = config.read_override(root / CONFIG)[0] or {}
        for key in sorted(set(override) - set(declaration["config_keys"])):
            ordered.append(_problem(
                "unknown-config-key", f"unknown-config-key {key}",
                f"unknown-config-key {key} in {CONFIG}; the harness ignores it",
            ))
    if review_invalid:
        ordered.append(_problem(
            "review-file-invalid", f"review-file-invalid {REVIEW}",
            f"review-file-invalid {REVIEW}; every customization counts as unconfirmed",
        ))
    ordered += problems
    for referenced in _referenced_local_paths(root):
        if not (root / LOCAL / referenced).exists():
            line = f"missing {LOCAL}/{referenced} (referenced by {SETTINGS})"
            ordered.append(_problem("missing", line, f"{line}; restore the file or remove the hook from {SETTINGS}"))
    return {"items": items, "problems": ordered, "declaration": declaration}


def item_line(item: dict) -> str:
    if item["state"] == RETIRED:
        return f"retired {item['path']}: {item['note']}"
    return f"{item['state']} {item['path']}"


def status_lines(result: dict) -> list[str]:
    lines = []
    for item in result["items"]:
        line = item_line(item)
        if item["state"] in (UNCONFIRMED, HARNESS_CHANGED):
            line += " — compare with " + ", ".join(item["compare"])
        lines.append(line)
    lines += [problem["text"] for problem in result["problems"]]
    return lines or ["no customizations"]


def notice_lines(result: dict) -> list[str]:
    body = []
    for item in result["items"]:
        state = item["state"]
        if state == CONFIRMED:
            continue
        if state == RETIRED:
            body.append(item_line(item))
        elif state == UNRECOGNIZED:
            body.append(f"unrecognized {item['path']}; the harness does not read this file")
        else:
            body.append(
                f"{state} {item['path']}; compare with {', '.join(item['compare'])}; "
                f"confirm: {CONFIRM_COMMAND} {item['path']}"
            )
    body += [problem["notice"] for problem in result["problems"]]
    return [INSTRUCTION_LINE] + body if body else []


def pending_lines(result: dict) -> list[str]:
    return [item_line(item) for item in result["items"] if item["state"] != CONFIRMED] + [
        problem["text"] for problem in result["problems"]
    ]


def _normalize(root: Path, argument: str) -> str:
    path = Path(argument)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(root.resolve())
        except ValueError:
            return argument
    return posixpath.normpath(path.as_posix())


def confirm(root: Path | str | None, arguments: list[str], today: str | None = None) -> tuple[list[str], int]:
    root = Path(root) if root is not None else config.REPO_ROOT
    result = analyze(root)
    recognized = {item["path"]: item for item in result["items"] if item["point"] is not None}
    bad = []
    chosen = {}
    for argument in arguments:
        rel = _normalize(root, argument)
        item = recognized.get(rel)
        if not (root / rel).exists() or (item is not None and item["content"] is None):
            bad.append(f"{argument}: not found")
        elif item is None:
            bad.append(f"{argument}: not a recognized customization")
        else:
            chosen[rel] = item
    if bad:
        return bad, 1

    version = (read_bytes(root, ".harness/VERSION") or b"").decode("utf-8", "replace").strip()
    reviewed, _invalid = _read_review(root)
    records = dict(reviewed)
    date = today or datetime.date.today().isoformat()
    for rel, item in chosen.items():
        records[rel] = {
            "content": item["content"],
            "compare": item["compare_hash"],
            "harness_version": version,
            "confirmed": date,
        }
    target = root / REVIEW
    temporary = target.with_name(f".customization-review.json.{os.getpid()}.tmp")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps({"items": records}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return [f"confirmed {rel}" for rel in chosen], 0
