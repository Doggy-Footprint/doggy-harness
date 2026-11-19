#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE.parent / "brief_facts" / "cases"
S = {"type": "string"}
B = {"type": "boolean"}
NB = {"type": ["boolean", "null"]}
QUOTES = {"type": "array", "items": S}
# Bumped whenever grader_a.md or the schema changes what a field means; score_a.py reads it from each judgement.
GRADER = 3


def kinds(*names: str, key: str = "quote") -> dict:
    return {"type": "array", "items": {"type": "object", "properties": {
        key: S, "kind": {"type": "string", "enum": list(names)}}, "required": [key, "kind"]}}


SCHEMA = {
    "type": "object",
    "properties": {
        "unknowns": {"type": "array", "items": {"type": "object", "properties": {
            "id": S,
            "status": {"type": "string", "enum": ["asked", "assumed", "decided", "dismissed", "absent"]},
            "form": {"type": ["string", "null"], "enum": ["fact", "decision", None]},
            "evidence": S}, "required": ["id", "status", "form", "evidence"]}},
        "questions": {"type": "array", "items": {"type": "object", "properties": {
            "text": S, "targets": {"type": "array", "items": S},
            "form": {"type": "string", "enum": ["fact", "decision"]},
            "names_decision": B, "names_branches": B, "guess": B, "useful": NB},
            "required": ["text", "targets", "form", "names_decision", "names_branches", "guess", "useful"]}},
        "understood": {"type": "object", "properties": {"project": B, "place": B, "success": B, "not_doing": B},
                       "required": ["project", "place", "success", "not_doing"]},
        "decisions_as_assumptions": QUOTES,
        "not_asked": {"type": "object", "properties": {"present": B, "single_line": NB, "repo_silence_reason": NB},
                      "required": ["present", "single_line", "repo_silence_reason"]},
        "invitation": {"type": "object", "properties": {"present": B, "examples": NB},
                       "required": ["present", "examples"]},
        "design_decisions": kinds("mechanism", "added_work", "open_case", "pointed", "outcome", "requested", "not_doing"),
        "search_notes": kinds("process", "silence", "missing_record", "product"),
        "project_detail": kinds("user_facing", "path", "identifier", "spec_id", "record_path"),
        "undefined_terms": kinds("specialist", "coined", "project_part", "general", key="term"),
        "exclusions_listed": QUOTES,
        "notes": S,
    },
    "required": ["unknowns", "questions", "understood", "decisions_as_assumptions", "not_asked", "invitation",
                 "design_decisions", "search_notes", "project_detail", "undefined_terms", "exclusions_listed",
                 "notes"],
}


def load_case(case_id: str) -> dict:
    case = json.loads((CASES / f"{case_id}.json").read_text(encoding="utf-8"))
    keys = json.loads((HERE / "case_keys.json").read_text(encoding="utf-8"))
    case.update(keys.get(case_id, {}))
    return case


def judge(run_dir: Path, case: dict, model: str) -> None:
    prompt = (
        (HERE / "grader_a.md").read_text(encoding="utf-8")
        + "\n\n# CASE\n" + json.dumps(case, ensure_ascii=False, indent=1)
        + "\n\n# MESSAGE\n" + (run_dir / "outputs" / "output.md").read_text(encoding="utf-8")
        + "\n\nReturn only the JSON object."
    )
    command = ["claude", "-p", "--model", model, "--tools", "", "--no-session-persistence",
               "--strict-mcp-config", "--setting-sources", "project", "--disable-slash-commands",
               "--output-format", "json", "--json-schema", json.dumps(SCHEMA)]
    done = subprocess.run(command, input=prompt, capture_output=True, text=True, cwd=run_dir, timeout=900)
    reply = json.loads(done.stdout)
    (run_dir / "judgement.json").write_text(
        json.dumps({**reply["structured_output"], "grader": GRADER}, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "judge_cost.json").write_text(
        json.dumps({"cost_usd": reply.get("total_cost_usd") or 0}), encoding="utf-8")


def attempt(run_dir: Path, case: dict, model: str) -> str | None:
    try:
        judge(run_dir, case, model)
    except (json.JSONDecodeError, KeyError, subprocess.TimeoutExpired) as failure:
        return f"{run_dir}: {type(failure).__name__}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("iteration", type=Path)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--config", action="append", help="judge only this arm; repeat for several")
    args = parser.parse_args()

    work = []
    for output in sorted(args.iteration.glob("eval-*/*/run-*/outputs/output.md")):
        run_dir = output.parent.parent
        if args.config and run_dir.parent.name not in args.config:
            continue
        if (run_dir / "judgement.json").exists() and not args.force:
            continue
        if not output.read_text(encoding="utf-8").strip():
            print(f"empty output: {run_dir}", file=sys.stderr)
            continue
        work.append((run_dir, load_case(run_dir.parent.parent.name.removeprefix("eval-"))))
    with ThreadPoolExecutor(args.jobs) as pool:
        failures = [item for item in pool.map(lambda job: attempt(job[0], job[1], args.model), work) if item]
    for failure in failures:
        print(f"judge failed: {failure}", file=sys.stderr)
    print(f"judged {len(work) - len(failures)} of {len(work)} runs")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
