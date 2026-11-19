#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE.parent / "brief_facts" / "cases"
FIRST_MESSAGE_CASES = ("batch-cli", "cache", "tsv-control", "log-retention", "logs-filter-control",
                       "mail-backfill", "no-email-filter-control")
TOOLS = "Read,Grep,Glob,Bash,Write,Edit"
# Shell commands outside Claude Code's read-only set are denied unless listed:
# the run copy is disposable, the machine around it is not.
ALLOWED = [
    "Read", "Grep", "Glob", "Write", "Edit",
    "Bash(python3 .harness/bin/workflow_marker.py *)",
    "Bash(python3 .harness/bin/spec_lifecycle.py *)",
    "Bash(openssl rand *)", "Bash(uuidgen)", "Bash(date *)",
    # The usual way a model draws a run id; without it the denial costs a retry.
    'Bash(python3 -c "import secrets*)',
]
GIT_IDENTITY = ["-c", "user.name=eval", "-c", "user.email=eval@example.invalid"]
# Runs draw on the same five-hour subscription window as the person's own sessions,
# so the batch stops launching once the window or the spend limit is reached.
GUARD = {"five_hour": 0.0, "seven_day": 0.0, "resets_at": None, "spent": 0.0, "usage_cap": 1.0,
         "weekly_cap": 1.0, "spend_cap": float("inf")}
GUARD_LOCK = threading.Lock()


def note_usage(trace: list[dict], cost: float) -> None:
    unified = [(event.get("rate_limit_info") or {}).get("unifiedWindows")
               for event in trace if event.get("type") == "rate_limit_event"]
    unified = [windows for windows in unified if isinstance(windows, dict)]
    with GUARD_LOCK:
        GUARD["spent"] += cost
        if unified:
            five_hour, seven_day = unified[-1].get("five_hour") or {}, unified[-1].get("seven_day") or {}
            GUARD["five_hour"] = five_hour.get("utilization") or 0.0
            GUARD["resets_at"] = five_hour.get("resetsAt")
            GUARD["seven_day"] = seven_day.get("utilization") or 0.0


def probe_usage() -> None:
    done = subprocess.run(
        ["claude", "-p", "--model", "haiku", "--tools", "", "--strict-mcp-config", "--setting-sources", "project",
         "--no-session-persistence", "--output-format", "stream-json", "--verbose"],
        input="Reply with the single word: ok", capture_output=True, text=True, timeout=120)
    trace = []
    for line in done.stdout.splitlines():
        try:
            trace.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    note_usage(trace, 0.0)


def over_limit() -> str | None:
    with GUARD_LOCK:
        if GUARD["five_hour"] >= GUARD["usage_cap"]:
            return f"five-hour window at {GUARD['five_hour']:.2f}"
        if GUARD["seven_day"] >= GUARD["weekly_cap"]:
            return f"seven-day window at {GUARD['seven_day']:.2f}"
        if GUARD["spent"] >= GUARD["spend_cap"]:
            return f"batch spend at ${GUARD['spent']:.2f}"
    return None


def sh(command: list[str], cwd: Path, **extra) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, **extra)


def build_payload(root: Path, overlay: Path | None, destination: Path) -> str:
    if destination.exists():
        shutil.rmtree(destination)
    for part in ("harness", "installer"):
        shutil.copytree(root / part, destination / part, ignore=shutil.ignore_patterns("__pycache__"))
    if overlay:
        shutil.copytree(overlay, destination, dirs_exist_ok=True)
    digest = hashlib.sha256()
    for path in sorted((destination / "harness").rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(destination).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def build_template(payload: Path, source_repo: Path, template: Path, targets_file: Path) -> None:
    if template.exists():
        shutil.rmtree(template)
    template.parent.mkdir(parents=True, exist_ok=True)
    steps = [
        (["git", "clone", "-q", "--no-hardlinks", str(source_repo), str(template)], template.parent),
        # No remote: nothing run in a copy can reach the upstream repository.
        (["git", "remote", "remove", "origin"], template),
    ]
    for command, cwd in steps:
        done = sh(command, cwd)
        if done.returncode:
            raise RuntimeError(f"{' '.join(command)}: {done.stderr.strip()}")
    done = sh([sys.executable, str(payload / "installer" / "harness.py"), "install", str(template),
               "--no-ci", "--model", "sonnet"], template, stdin=subprocess.DEVNULL,
              env={**os.environ, "HARNESS_TARGETS_FILE": str(targets_file)})
    if done.returncode:
        raise RuntimeError(f"install into {template}: {done.stdout[-800:]} {done.stderr[-800:]}")
    sh(["git", "add", "-A"], template)
    done = sh(["git", *GIT_IDENTITY, "commit", "-q", "--no-verify", "-m", "install harness"], template)
    if done.returncode:
        raise RuntimeError(f"commit in {template}: {done.stderr.strip()}")


def tool_calls(trace: list[dict]) -> list[dict]:
    calls: dict[str, dict] = {}
    ordered = []
    for event in trace:
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                call = {"name": block.get("name"), "input": block.get("input"), "result": None, "is_error": None}
                calls[block.get("id")] = call
                ordered.append(call)
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                body = block.get("content")
                if isinstance(body, list):
                    body = "\n".join(part.get("text", "") for part in body if isinstance(part, dict))
                calls[block["tool_use_id"]].update(result=body, is_error=bool(block.get("is_error")))
    return ordered


def user_message(trace: list[dict], final: str) -> str:
    # The model sometimes writes the round, then emits its marker, then adds a closing line;
    # the result field holds only that last line, while the user reads all of it.
    texts = []
    for event in trace:
        message = event.get("message")
        if event.get("type") != "assistant" or event.get("parent_tool_use_id") or not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text" and (block.get("text") or "").strip():
                texts.append(block["text"])
    if not texts:
        return final
    longest = max(range(len(texts)), key=lambda index: len(texts[index]))
    return "\n\n".join(texts[longest:])


def run_one(job: dict, model: str, effort: str, timeout: int, budget: float) -> str | None:
    try:
        if job.get("redigest"):
            return digest(job["run_dir"], (job["run_dir"] / "trace.jsonl").read_text(encoding="utf-8"), "")
        reason = over_limit()
        if reason:
            return f"{job['run_dir']}: deferred ({reason})"
        return execute(job, model, effort, timeout, budget)
    except Exception as failure:  # one broken run must not end the batch
        (job["run_dir"] / "meta.json").write_text(json.dumps({"error": repr(failure)}), encoding="utf-8")
        return f"{job['run_dir']}: {failure!r}"


def execute(job: dict, model: str, effort: str, timeout: int, budget: float) -> str | None:
    run_dir: Path = job["run_dir"]
    repo = run_dir / "repo"
    if repo.exists():
        shutil.rmtree(repo)
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(job["template"], repo, symlinks=True)
    telemetry = run_dir / "telemetry"
    telemetry.mkdir(exist_ok=True)
    command = [
        "claude", "-p", "--model", model, "--effort", effort, "--tools", TOOLS,
        "--allowedTools", *ALLOWED, "--strict-mcp-config", "--setting-sources", "project",
        "--no-session-persistence", "--output-format", "stream-json", "--verbose",
        "--max-budget-usd", str(budget),
    ]
    try:
        done = subprocess.run(command, input=f"/doggy-workflow {job['task']}", capture_output=True, text=True,
                              cwd=repo, timeout=timeout,
                              env={**os.environ, "HARNESS_TELEMETRY_DIR": str(telemetry)})
    except subprocess.TimeoutExpired:
        (run_dir / "meta.json").write_text(json.dumps({"error": "timeout"}), encoding="utf-8")
        return f"{run_dir}: timeout"
    (run_dir / "trace.jsonl").write_text(done.stdout, encoding="utf-8")
    return digest(run_dir, done.stdout, done.stderr or " ")


def digest(run_dir: Path, stdout: str, stderr: str) -> str | None:
    repo = run_dir / "repo"
    trace = []
    for line in stdout.splitlines():
        try:
            trace.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    result = next((event for event in reversed(trace) if event.get("type") == "result"), None)
    if stderr != "":
        note_usage(trace, (result or {}).get("total_cost_usd") or 0.0)
    if result is None:
        (run_dir / "meta.json").write_text(
            json.dumps({"error": "no result", "stderr": stderr[-2000:]}), encoding="utf-8")
        return f"{run_dir}: no result"
    (run_dir / "outputs").mkdir(exist_ok=True)
    (run_dir / "outputs" / "output.md").write_text(user_message(trace, result.get("result") or ""), encoding="utf-8")
    (run_dir / "tools.json").write_text(json.dumps(tool_calls(trace), ensure_ascii=False, indent=1), encoding="utf-8")
    changed = sh(["git", "status", "--porcelain", "--untracked-files=all"], repo).stdout.splitlines()
    meta = {key: result.get(key) for key in ("is_error", "subtype", "num_turns", "duration_ms", "total_cost_usd",
                                             "usage", "permission_denials")}
    meta["changed_paths"] = changed
    meta["denied"] = [{"tool_use_id": event.get("tool_use_id"), "reason": event.get("message")}
                      for event in trace if event.get("subtype") == "permission_denied"]
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    usage = result.get("usage") or {}
    tokens = sum(usage.get(key) or 0 for key in (
        "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    duration = result.get("duration_ms") or 0
    (run_dir / "timing.json").write_text(json.dumps({
        "total_tokens": tokens, "duration_ms": duration, "total_duration_seconds": round(duration / 1000, 1),
    }), encoding="utf-8")
    return f"{run_dir}: {result.get('subtype')}" if result.get("is_error") else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("iteration", type=Path)
    parser.add_argument("--repos", required=True, type=Path, help="directory holding one clone per repository name")
    parser.add_argument("--config", action="append", required=True, metavar="NAME=ROOT[+OVERLAY]",
                        help="ROOT holds harness/ and installer/; OVERLAY is copied over them")
    parser.add_argument("--cases", default=",".join(FIRST_MESSAGE_CASES))
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--budget", type=float, default=3.0, help="spend cap per run, USD")
    parser.add_argument("--usage-cap", type=float, default=0.75,
                        help="stop launching runs once the five-hour window reaches this share")
    parser.add_argument("--weekly-cap", type=float, default=1.0,
                        help="stop launching runs once the seven-day window reaches this share")
    parser.add_argument("--spend-cap", type=float, default=float("inf"), help="stop launching once the batch spent this, USD")
    args = parser.parse_args()

    GUARD.update(usage_cap=args.usage_cap, weekly_cap=args.weekly_cap, spend_cap=args.spend_cap)
    probe_usage()
    iteration = args.iteration.resolve()
    iteration.mkdir(parents=True, exist_ok=True)
    cases = {case_id: json.loads((CASES / f"{case_id}.json").read_text(encoding="utf-8"))
             for case_id in args.cases.split(",")}
    repo_names = {case_id: case["repo"].split("@")[0].split("/")[1] for case_id, case in cases.items()}
    payloads = {}
    for config in args.config:
        name, spec = config.split("=", 1)
        root, _, overlay = spec.partition("+")
        payload = iteration / "payloads" / name
        digest = build_payload(Path(root).resolve(), Path(overlay).resolve() if overlay else None, payload)
        payloads[name] = {"payload": payload, "sha256_16": digest, "root": root, "overlay": overlay or None}
        for repo_name in sorted(set(repo_names.values())):
            build_template(payload, args.repos / repo_name, iteration / "templates" / name / repo_name,
                           iteration / "targets.json")
    recorded = iteration / "configs.json"
    known = json.loads(recorded.read_text(encoding="utf-8")) if recorded.exists() else {}
    for name, entry in known.items():
        if name in payloads and entry["sha256_16"] != payloads[name]["sha256_16"]:
            raise SystemExit(f"config {name} changed since this iteration began: "
                             f"{entry['sha256_16']} -> {payloads[name]['sha256_16']}")
    known.update({name: {key: str(value) if value else None for key, value in entry.items()}
                  for name, entry in payloads.items()})
    recorded.write_text(json.dumps(known, indent=2), encoding="utf-8")

    jobs = []
    for case_id, case in cases.items():
        for name in payloads:
            for number in range(1, args.runs + 1):
                run_dir = iteration / f"eval-{case_id}" / name / f"run-{number}"
                output = run_dir / "outputs" / "output.md"
                if output.exists() and output.read_text(encoding="utf-8").strip():
                    if not (run_dir / "tools.json").exists() and (run_dir / "trace.jsonl").exists():
                        jobs.append({"run_dir": run_dir, "redigest": True})
                    continue
                jobs.append({"run_dir": run_dir, "task": case["task"],
                             "template": iteration / "templates" / name / repo_names[case_id]})
    with ThreadPoolExecutor(args.jobs) as pool:
        failures = [item for item in pool.map(
            lambda job: run_one(job, args.model, args.effort, args.timeout, args.budget), jobs) if item]
    deferred = [item for item in failures if "deferred (" in item]
    for failure in failures:
        if failure not in deferred:
            print(f"run failed: {failure}", file=sys.stderr)
    resets = GUARD["resets_at"]
    print(f"ran {len(jobs) - len(failures)} of {len(jobs)} runs, deferred {len(deferred)}, spent ${GUARD['spent']:.2f}, "
          f"five-hour window {GUARD['five_hour']:.2f}, seven-day window {GUARD['seven_day']:.2f}"
          + (f", resets {time.strftime('%Y-%m-%d %H:%M %Z', time.localtime(resets))}" if resets else ""))
    if deferred:
        print(f"deferred: {deferred[0].split(': deferred ')[1]}; rerun the same command to continue")
        return 2
    return 1 if len(failures) > len(deferred) else 0


if __name__ == "__main__":
    sys.exit(main())
