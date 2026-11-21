#!/usr/bin/env python3
"""Drive one doggy-workflow run: a headless Claude Code subject and a simulated user."""
import argparse
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SUBJECT_MODEL = os.environ.get("PC_SUBJECT_MODEL", "claude-sonnet-5-5")
SUBJECT_EFFORT = os.environ.get("PC_SUBJECT_EFFORT", "medium")
SIMUSER_MODEL = "claude-opus-5-5"
SIMUSER_EFFORT = "medium"
END_TOKEN = "[[END]]"
NODE_DIR = str(Path(shutil.which("node") or "/usr/local/bin/node").parent)
PYTHON_DIR = str(Path(shutil.which("python3") or "/usr/bin/python3").parent)
CLAUDE_BIN = shutil.which("claude") or "claude"


def load_case(case_dir: Path) -> dict:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    case["dir"] = str(case_dir)
    return case


def fill(value: str, work: Path, run_dir: Path | None = None) -> str:
    value = (value.replace("{work}", str(work)).replace("{eval}", str(Path(__file__).resolve().parent))
             .replace("{home}", os.environ["HOME"]))
    return value.replace("{run}", str(run_dir)) if run_dir is not None else value


def run(cmd, cwd=None, env=None, log=None, check=True, stdin=subprocess.DEVNULL, timeout=1800):
    result = subprocess.run(cmd, cwd=cwd, env=env, stdin=stdin, capture_output=True, text=True, timeout=timeout)
    if log is not None:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(f"$ {' '.join(map(str, cmd))}\n{result.stdout}{result.stderr}\n[exit {result.returncode}]\n")
    if check and result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(map(str, cmd))}\n{result.stderr[-2000:]}")
    return result


def base_path(case: dict, work: Path) -> str:
    extra = [fill(p, work) for p in case.get("path_tools", [])]
    return ":".join(extra + [NODE_DIR, PYTHON_DIR, "/usr/bin", "/bin", "/usr/sbin", "/sbin"])


def ensure_cache(case: dict, work: Path) -> Path:
    cache = work / "src-cache" / case["id"]
    if cache.exists():
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    log = work / f"cache-{case['id']}.log"
    run(["git", "clone", "-q", case["repo"], str(cache)], log=log)
    run(["git", "-C", str(cache), "checkout", "-q", case["commit"]], log=log)
    env = {**os.environ, "PATH": base_path(case, work) + ":" + os.environ.get("PATH", ""),
           "XDG_CACHE_HOME": str(work / "cache"), "npm_config_cache": str(work / "cache" / "npm")}
    for cmd in case.get("cache_setup", []):
        run([fill(part, work) for part in cmd], cwd=cache, env=env, log=log)
    return cache


def run_env(run_dir: Path, case: dict, work: Path) -> dict:
    return {
        "HOME": os.environ["HOME"],
        "USER": os.environ.get("USER", ""),
        "LANG": "en_US.UTF-8",
        "TERM": "dumb",
        "PATH": base_path(case, work),
        "TMPDIR": str(run_dir / "tmp"),
        "XDG_CACHE_HOME": str(run_dir / "tmp" / "cache"),
        "HARNESS_TELEMETRY_DIR": str(run_dir / "telemetry"),
        "HARNESS_PREFERENCES_FILE": str(run_dir / "harness-preferences.json"),
        "HARNESS_TARGETS_FILE": str(run_dir / "harness-targets.json"),
        "CLAUDE_CODE_SUBAGENT_MODEL": SUBJECT_MODEL,
        "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1",
        "CLAUDE_CODE_EFFORT_LEVEL": SUBJECT_EFFORT,
        **{key: fill(value, work, run_dir) for key, value in case.get("env", {}).items()},
    }


def write_settings(run_dir: Path) -> Path:
    tmp = run_dir / "tmp"
    settings = {
        "autoMemoryEnabled": False,
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "autoAllowBashIfSandboxed": True,
            "filesystem": {"allowWrite": [str(tmp), str(run_dir / "telemetry")]},
            "network": {"allowedDomains": [], "allowAllUnixSockets": True, "allowLocalBinding": True},
        },
        "permissions": {
            "allow": ["Read", "Glob", "Grep", "Bash", "Agent", "Task", "Skill",
                      "Edit(./**)", "Write(./**)", f"Edit(/{tmp}/**)", f"Write(/{tmp}/**)"],
        },
    }
    path = run_dir / "settings.json"
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return path


def prepare(case_dir: Path, harness_src: Path, run_dir: Path, work: Path) -> None:
    case = load_case(case_dir)
    cache = ensure_cache(case, work)
    if run_dir.exists():
        raise SystemExit(f"run dir exists: {run_dir}")
    for sub in ("tmp", "telemetry", "artifacts"):
        (run_dir / sub).mkdir(parents=True)
    repo = run_dir / "repo"
    # APFS clones (`cp -c`) keep per-run copies of large dependency trees nearly free on disk.
    run(["cp", "-c", "-R", str(cache), str(repo)])
    for source, destination in case.get("clone_dirs", []):
        target = Path(fill(destination, work, run_dir))
        target.parent.mkdir(parents=True, exist_ok=True)
        run(["cp", "-c", "-R", fill(source, work, run_dir), str(target)])
    log = run_dir / "prepare.log"
    git = ["git", "-C", str(repo)]
    run(git + ["remote", "remove", "origin"], log=log, check=False)
    run(git + ["config", "user.name", "eval-user"], log=log)
    run(git + ["config", "user.email", "eval-user@example.invalid"], log=log)
    run(git + ["checkout", "-q", "-B", "main"], log=log)
    env = {**os.environ, **run_env(run_dir, case, work)}
    run(["python3", str(harness_src / "installer" / "harness.py"), "install", str(repo), "--no-ci", "--model", "sonnet"],
        env=env, log=log)
    if run(git + ["status", "--porcelain"], log=log).stdout.strip():
        run(git + ["add", "-A"], log=log)
        run(git + ["commit", "-q", "--no-verify", "-m", "Install harness"], log=log)
    base = run(git + ["rev-parse", "HEAD"], log=log).stdout.strip()
    version = (harness_src / "harness" / "VERSION").read_text(encoding="utf-8").strip()
    write_settings(run_dir)
    meta = {"case": case["id"], "case_dir": str(case_dir), "harness_src": str(harness_src), "harness_version": version,
            "base_commit": base, "subject_model": SUBJECT_MODEL, "subject_effort": SUBJECT_EFFORT,
            "simuser_model": SIMUSER_MODEL, "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


class Subject:
    def __init__(self, run_dir: Path, case: dict, work: Path, budget_usd: float):
        self.run_dir = run_dir
        self.session_id = str(uuid.uuid4())
        cmd = [CLAUDE_BIN, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--include-hook-events", "--forward-subagent-text", "--replay-user-messages",
               "--model", SUBJECT_MODEL, "--effort", SUBJECT_EFFORT,
               "--setting-sources", "project,local", "--strict-mcp-config",
               "--settings", str(run_dir / "settings.json"), "--permission-mode", "dontAsk",
               "--add-dir", str(run_dir / "tmp"), "--session-id", self.session_id,
               "--max-budget-usd", str(budget_usd)]
        self.events = open(run_dir / "events.jsonl", "a", encoding="utf-8")
        self.proc = subprocess.Popen(cmd, cwd=run_dir / "repo", env=run_env(run_dir, case, work),
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=open(run_dir / "subject.stderr", "a", encoding="utf-8"),
                                     text=True, bufsize=1)
        self.lines: queue.Queue = queue.Queue()
        self.background: list = []
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, text: str) -> None:
        message = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def read_until_idle(self, turn_timeout: float, grace: float, background_wait: float) -> dict:
        texts, results, started = [], [], time.time()
        deadline = started + turn_timeout
        waiting_after_result = None
        while True:
            now = time.time()
            if now > deadline:
                return {"texts": texts, "results": results, "status": "turn_timeout", "seconds": now - started}
            if waiting_after_result is not None and now > waiting_after_result:
                return {"texts": texts, "results": results, "status": "idle", "seconds": now - started}
            try:
                line = self.lines.get(timeout=1.0)
            except queue.Empty:
                continue
            if line is None:
                return {"texts": texts, "results": results, "status": "exited", "seconds": time.time() - started}
            self.events.write(line)
            self.events.flush()
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "system" and event.get("subtype") == "background_tasks_changed":
                self.background = [t for t in event.get("tasks", []) if t.get("task_type") == "local_agent"]
                if waiting_after_result is not None and not self.background:
                    waiting_after_result = time.time() + grace
            if event.get("type") == "assistant" and not event.get("parent_tool_use_id"):
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "text" and block.get("text", "").strip():
                        texts.append(block["text"])
                waiting_after_result = None
            elif event.get("type") == "result":
                results.append(event)
                busy = bool(self.background) or pending_background(event)
                waiting_after_result = time.time() + (background_wait if busy else grace)
            elif waiting_after_result is not None and event.get("type") in ("assistant", "user", "system"):
                waiting_after_result = time.time() + grace

    def close(self, timeout: float = 300) -> int:
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        end = time.time() + timeout
        while time.time() < end:
            try:
                line = self.lines.get(timeout=1.0)
            except queue.Empty:
                if self.proc.poll() is not None:
                    break
                continue
            if line is None:
                break
            self.events.write(line)
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=30)
        self.events.close()
        return self.proc.returncode


def pending_background(result: dict) -> bool:
    stats = result.get("subagent_stats") or {}
    killed = stats.get("killed") or {}
    done = (stats.get("completed") or 0) + (stats.get("failed") or 0) + sum(v or 0 for v in killed.values())
    return (stats.get("started_in_background") or 0) > done


def render_dialogue(dialogue: list) -> str:
    parts = []
    for turn in dialogue:
        who = "사용자(당신)" if turn["role"] == "user" else "에이전트"
        parts.append(f"[{who}]\n{turn['text']}")
    return "\n\n".join(parts)


def simulate_user(persona: str, dialogue: list, run_dir: Path) -> str:
    system = (persona + "\n\n# 출력 형식\n\n사용자로서 보낼 답장 본문만 출력한다. 설명, 따옴표, 머리말을 붙이지 않는다.")
    prompt = ("아래는 지금까지 당신(사용자)과 AI 코딩 에이전트의 대화다. 에이전트의 마지막 메시지에 사용자로서 답하라.\n\n"
              + render_dialogue(dialogue))
    cwd = run_dir / "simuser"
    cwd.mkdir(exist_ok=True)
    env = {"HOME": os.environ["HOME"], "USER": os.environ.get("USER", ""), "LANG": "en_US.UTF-8", "TERM": "dumb",
           "PATH": f"{NODE_DIR}:/usr/bin:/bin"}
    cmd = [CLAUDE_BIN, "-p", "--model", SIMUSER_MODEL, "--effort", SIMUSER_EFFORT, "--tools", "",
           "--system-prompt", system, "--setting-sources", "local", "--strict-mcp-config",
           "--no-session-persistence", "--output-format", "json"]
    for attempt in range(3):
        result = subprocess.run(cmd, cwd=cwd, env=env, input=prompt, capture_output=True, text=True, timeout=900)
        with open(run_dir / "simuser.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"attempt": attempt, "exit": result.returncode, "stdout": result.stdout[-20000:],
                                     "stderr": result.stderr[-4000:]}, ensure_ascii=False) + "\n")
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            time.sleep(10)
            continue
        if not data.get("is_error") and data.get("result", "").strip():
            return data["result"].strip()
        time.sleep(10)
    raise SystemExit("simulated user failed three times")


def collect(run_dir: Path, session_id: str) -> None:
    repo = (run_dir / "repo").resolve()
    art = run_dir / "artifacts"
    project = Path(os.environ["HOME"]) / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    transcript = project / f"{session_id}.jsonl"
    if transcript.exists():
        shutil.copy2(transcript, art / "session.jsonl")
    if (project / session_id).is_dir():
        shutil.copytree(project / session_id, art / "session", dirs_exist_ok=True)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    base = meta["base_commit"]
    diff = run(["git", "-C", str(repo), "diff", base], check=False).stdout
    untracked = run(["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"], check=False).stdout
    log = run(["git", "-C", str(repo), "log", "--format=%H %s", f"{base}..HEAD"], check=False).stdout
    (art / "final.diff").write_text(diff, encoding="utf-8")
    (art / "untracked.txt").write_text(untracked, encoding="utf-8")
    (art / "commits.txt").write_text(log, encoding="utf-8")
    if (repo / "agent-docs").is_dir():
        shutil.copytree(repo / "agent-docs", art / "agent-docs", dirs_exist_ok=True)
    picks = art / "outside-writes"
    for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            path = (block.get("input") or {}).get("file_path") if block.get("type") == "tool_use" else None
            if path and not str(Path(path).resolve()).startswith(str(repo)) and Path(path).is_file():
                picks.mkdir(exist_ok=True)
                shutil.copy2(path, picks / Path(path).name)


def drive(run_dir: Path, work: Path, budget_usd: float, turn_timeout: float, max_turns: int | None) -> None:
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    case = load_case(Path(meta["case_dir"]))
    case_dir = Path(case["dir"])
    issue = (case_dir / "issue.md").read_text(encoding="utf-8") if (case_dir / "issue.md").exists() else ""
    first = case["prompt"].replace("{issue}", issue)
    persona = (case_dir / "persona.md").read_text(encoding="utf-8")
    limit = max_turns or case.get("max_turns", 40)
    subject = Subject(run_dir, case, work, budget_usd)
    meta.update({"session_id": subject.session_id, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    dialogue, turns, reason = [{"role": "user", "text": first}], [], "max_turns"
    message = first
    for index in range(limit):
        subject.send(message)
        outcome = subject.read_until_idle(turn_timeout=turn_timeout, grace=20, background_wait=1200)
        text = "\n\n".join(outcome["texts"]).strip() or "(에이전트가 텍스트 없이 턴을 끝냈다.)"
        dialogue.append({"role": "assistant", "text": text})
        last = outcome["results"][-1] if outcome["results"] else {}
        turns.append({"turn": index + 1, "status": outcome["status"], "seconds": round(outcome["seconds"], 1),
                      "cost_usd": last.get("total_cost_usd"), "result_subtype": last.get("subtype"),
                      "terminal_reason": last.get("terminal_reason"), "is_error": last.get("is_error")})
        (run_dir / "dialogue.json").write_text(json.dumps(dialogue, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "turns.json").write_text(json.dumps(turns, indent=2), encoding="utf-8")
        if outcome["status"] in ("exited", "turn_timeout"):
            reason = outcome["status"]
            break
        if last.get("is_error") and last.get("subtype") not in ("success",):
            reason = f"error:{last.get('subtype')}"
            break
        reply = simulate_user(persona, dialogue, run_dir)
        if reply.strip() == END_TOKEN:
            reason = "simulated_user_end"
            break
        dialogue.append({"role": "user", "text": reply})
        message = reply
    exit_code = subject.close()
    meta.update({"ended_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "end_reason": reason, "subject_exit": exit_code,
                 "turns": len(turns), "cost_usd": turns[-1]["cost_usd"] if turns else None})
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (run_dir / "dialogue.json").write_text(json.dumps(dialogue, ensure_ascii=False, indent=2), encoding="utf-8")
    collect(run_dir, subject.session_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--case", required=True, type=Path)
    p.add_argument("--harness-src", required=True, type=Path)
    p.add_argument("--run-dir", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path)
    d = sub.add_parser("drive")
    d.add_argument("--run-dir", required=True, type=Path)
    d.add_argument("--work", required=True, type=Path)
    d.add_argument("--budget-usd", type=float, default=60.0)
    d.add_argument("--turn-timeout", type=float, default=5400.0)
    d.add_argument("--max-turns", type=int)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.case.resolve(), args.harness_src.resolve(), args.run_dir.resolve(), args.work.resolve())
    else:
        drive(args.run_dir.resolve(), args.work.resolve(), args.budget_usd, args.turn_timeout, args.max_turns)
    return 0


if __name__ == "__main__":
    sys.exit(main())
