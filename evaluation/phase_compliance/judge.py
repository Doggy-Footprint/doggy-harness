#!/usr/bin/env python3
"""LLM-judge (rubric methods J and G) for one run; writes judge-<repeat>.json in the run dir."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_script  # noqa: E402
import timeline  # noqa: E402

HERE = Path(__file__).resolve().parent
JUDGE_MODEL = "claude-opus-5-5"
JUDGE_EFFORT = "high"
CLAUDE_BIN = shutil.which("claude") or "claude"
NODE_DIR = str(Path(shutil.which("node") or "/usr/local/bin/node").parent)
SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "verdict": {"type": "string", "enum": ["pass", "fail", "na", "unobservable"]},
            "measure": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "object", "properties": {
                "turn": {"type": "string"}, "quote": {"type": "string"}}, "required": ["turn", "quote"]}},
            "rationale": {"type": "string"},
        },
        "required": ["id", "verdict", "evidence", "rationale"]}}},
    "required": ["items"],
}


def dialogue_text(run_dir: Path) -> str:
    dialogue = json.loads((run_dir / "dialogue.json").read_text(encoding="utf-8"))
    return "\n\n".join(f"### Turn {k} — {'USER' if t['role'] == 'user' else 'AGENT'}\n{t['text']}"
                       for k, t in enumerate(dialogue, start=1))


def spec_text(run_dir: Path) -> str:
    docs = run_dir / "artifacts" / "agent-docs"
    specs = sorted(list((docs / "specs").glob("*.md")) + list((docs / "spec-logs").glob("*.md"))) if docs.exists() else []
    return "\n\n".join(f"=== {p.name}\n{p.read_text(encoding='utf-8')}" for p in specs) or "(no spec file)"


def dialogue_turn_of_item(run_dir: Path, items) -> dict:
    dialogue = json.loads((run_dir / "dialogue.json").read_text(encoding="utf-8"))
    return timeline.dialogue_index(items, dialogue)


def agent_roles(run_dir: Path) -> dict:
    roles = {}
    for meta in (run_dir / "artifacts" / "session" / "subagents").glob("*.meta.json"):
        roles[meta.name[len("agent-"):-len(".meta.json")]] = json.loads(meta.read_text(encoding="utf-8")).get("agentType")
    return roles


def dispatch_text(items, turn_map, roles: dict) -> str:
    parts = []
    for item in items:
        if item.kind == "tool_use" and item.actor == "main" and item.tool in ("Agent", "Task"):
            role = item.input.get("subagent_type") or "general-purpose"
            parts.append(f"=== dispatch to {role} (during dialogue turn {turn_map.get(item.index)}; model={item.input.get('model', 'default')})\n"
                         f"{item.input.get('prompt', '')}")
        elif item.kind == "tool_use" and item.actor == "main" and item.tool == "SendMessage":
            target = item.input.get("to") or item.input.get("recipient")
            parts.append(f"=== follow-up message (redispatch) to the running {roles.get(target, target)} "
                         f"(during dialogue turn {turn_map.get(item.index)})\n{item.input.get('message', '')}")
    return "\n\n".join(parts) or "(no subagent dispatches)"


def marker_text(items, turn_map) -> str:
    lines = []
    for item in timeline.bash_commands(items):
        command = item.input.get("command", "")
        if "workflow_marker.py" in command or "spec_lifecycle.py" in command or "seed.py" in command:
            lines.append(f"[dialogue turn {turn_map.get(item.index)}] {command[:400]}")
    return "\n".join(lines) or "(none)"


def failure_text(items, run_dir: Path, turn_map) -> str:
    lines = []
    for item in items:
        if item.kind == "tool_result" and item.is_error and item.actor == "main":
            use = next((u for u in items if u.kind == "tool_use" and u.tool_id == item.tool_id), None)
            what = (use.input.get("command") or use.input.get("file_path") or use.tool) if use else "?"
            lines.append(f"[dialogue turn {turn_map.get(item.index)}] tool error: {str(what)[:200]} -> {item.text[:300]}")
    for path in sorted((run_dir / "telemetry").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") in ("gate_block", "isolation_candidate") or (
                    event.get("event") == "test_command" and event.get("exit_code") not in (0, None)):
                lines.append(f"telemetry: {json.dumps(event, ensure_ascii=False)[:300]}")
    return "\n".join(lines) or "(no failure events)"


def checklist(group: dict) -> str:
    rows = []
    for item in group["items"]:
        na = f" (na when: {item['na']})" if item.get("na") else ""
        rows.append(f"- {item['id']}: {item['criterion']}{na}")
    return f"Scope: {group['applies_to']}\n\n" + "\n".join(rows)


def build_prompt(group: dict, material: dict, answer_key: str | None) -> str:
    sections = [f"# Checklist ({group['group']})\n\n{checklist(group)}", f"# Dialogue\n\n{material['dialogue']}"]
    name = group["group"]
    if name in ("spec", "approval", "close", "dispatch", "facts_protocol", "ground_truth"):
        sections.append(f"# Spec file(s), final state\n\n{material['spec']}")
    if name in ("dispatch", "close"):
        sections.append(f"# Subagent dispatch prompts\n\n{material['dispatch']}")
    if name in ("marker_counts", "close", "decision_round", "approval"):
        sections.append(f"# Marker and lifecycle commands the agent ran\n\n{material['markers']}")
    if name == "close":
        sections.append(f"# Failure events in the run\n\n{material['failures']}")
    if answer_key:
        sections.append(f"# Answer key for this scenario (grader only)\n\n{answer_key}")
    sections.append("Return one entry per checklist item id, in checklist order.")
    return "\n\n".join(sections)


def call_judge(prompt: str, system: str, log: Path) -> list:
    env = {"HOME": os.environ["HOME"], "USER": os.environ.get("USER", ""), "LANG": "en_US.UTF-8", "TERM": "dumb",
           "PATH": f"{NODE_DIR}:/usr/bin:/bin"}
    cwd = log.parent / "judge-cwd"
    cwd.mkdir(exist_ok=True)
    cmd = [CLAUDE_BIN, "-p", "--model", JUDGE_MODEL, "--effort", JUDGE_EFFORT, "--tools", "",
           "--system-prompt", system, "--setting-sources", "local", "--strict-mcp-config",
           "--no-session-persistence", "--output-format", "json", "--json-schema", json.dumps(SCHEMA)]
    for attempt in range(3):
        result = subprocess.run(cmd, cwd=cwd, env=env, input=prompt, capture_output=True, text=True, timeout=1800)
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"attempt": attempt, "exit": result.returncode, "stdout": result.stdout[-30000:],
                                     "stderr": result.stderr[-3000:]}, ensure_ascii=False) + "\n")
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            time.sleep(15)
            continue
        payload = data.get("structured_output")
        if payload is None:
            match = re.search(r"\{.*\}", data.get("result", ""), re.S)
            payload = json.loads(match.group(0)) if match else None
        if payload and payload.get("items"):
            return payload["items"]
        time.sleep(15)
    return []


def judge_run(run_dir: Path, repeat: int, groups_filter: set | None) -> dict:
    rubric = json.loads((HERE / "rubric_j.json").read_text(encoding="utf-8"))
    system = (HERE / "judge.md").read_text(encoding="utf-8")
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    key_path = Path(meta["case_dir"]) / "answer_key.md"
    answer_key = key_path.read_text(encoding="utf-8") if key_path.exists() else None
    items = timeline.load(run_dir)
    turn_map = dialogue_turn_of_item(run_dir, items)
    material = {"dialogue": dialogue_text(run_dir), "spec": spec_text(run_dir), "dispatch": dispatch_text(items, turn_map, agent_roles(run_dir)),
                "markers": marker_text(items, turn_map), "failures": failure_text(items, run_dir, turn_map)}
    groups = list(rubric["groups"]) + [{"group": "ground_truth", "phase": "various",
                                        "applies_to": "The whole run, compared with the answer key.",
                                        "items": rubric["ground_truth"]}]
    groups = [g for g in groups if not groups_filter or g["group"] in groups_filter]
    log = run_dir / f"judge-{repeat}.log.jsonl"

    def one(group):
        key = answer_key if group["group"] == "ground_truth" else None
        verdicts = call_judge(build_prompt(group, material, key), system, log)
        for v in verdicts:
            v["group"], v["phase"] = group["group"], group["phase"]
            v["method"] = "G" if group["group"] == "ground_truth" else "J"
        return verdicts

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [v for batch in pool.map(one, groups) for v in batch]
    path = run_dir / f"judge-{repeat}.json"
    if groups_filter and path.exists():
        kept = [v for v in json.loads(path.read_text(encoding="utf-8"))["items"] if v["group"] not in groups_filter]
        results = kept + results
    out = {"repeat": repeat, "model": JUDGE_MODEL, "effort": JUDGE_EFFORT, "items": results}
    (run_dir / f"judge-{repeat}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--groups", default="")
    args = parser.parse_args()
    groups = set(filter(None, args.groups.split(",")))
    out = judge_run(args.run_dir.resolve(), args.repeat, groups or None)
    for v in out["items"]:
        print(f"{v['id']:<6} {v['verdict']:<13} {v.get('measure', ''):<6} {v['rationale'][:140]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
