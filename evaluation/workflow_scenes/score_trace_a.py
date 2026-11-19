#!/usr/bin/env python3
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TEXT = {
    "A01": "첫 메시지 전에 facts.md를 읽으려 한다",
    "A01r": "facts.md를 범위 제한(head, limit) 없이 읽는다",
    "A02": "첫 메시지 전에 agent-docs/specs를 확인한다",
    "A03": "첫 메시지 전에 try-n-fail 기록을 읽거나 검색하지 않는다 (폴더 목록만 본 것은 통과)",
    "A03l": "try-n-fail 폴더를 목록으로도 건드리지 않는다 (2026-11-18 이전의 A03)",
    "A04": "이해 라운드 brief 이벤트가 telemetry에 기록된다",
    "A04c": "이해 라운드 brief 마커 명령을 실행한다 (기록 여부와 무관)",
    "A05": "마커의 fact-questions가 메시지의 질문 수와 같고 split이 none이다",
    "A18": "첫 메시지 뒤 spec이나 구현 파일을 만들거나 고치지 않는다",
    "L01": "phase 명령을 실행한다",
    "L02": "phase 명령의 출력이 끝까지 전달된다",
    "L03": "phase 명령의 출력을 버리지 않는다 (리다이렉션 없음)",
}
MARKER = ".harness/bin/workflow_marker.py"
RECORDS = "try-n-fail"
LISTING = re.compile(r"\s*(?:ls|tree)\b[^|]*(?:\|\s*(?:head|tail|wc|sort)\b[^|]*)*")


def text_of(call: dict) -> str:
    return json.dumps(call.get("input") or {}, ensure_ascii=False)


def record_uses(calls: list[dict]) -> tuple[list[str], list[str]]:
    listings, reads = [], []
    for call in calls:
        if RECORDS not in text_of(call):
            continue
        if call["name"] == "Glob":
            listings.append(text_of(call)[:200])
        elif call["name"] != "Bash":
            reads.append(f"{call['name']} {text_of(call)[:200]}")
        else:
            for segment in re.split(r"(?:;|&&|\|\||\n)+", (call["input"] or {}).get("command", "")):
                if RECORDS in segment:
                    (listings if LISTING.fullmatch(segment) else reads).append(segment.strip()[:200])
    return listings, reads


def flag(command: str, name: str) -> str | None:
    found = re.search(rf"{re.escape(name)}\s+(\S+)", command)
    return found.group(1) if found else None


def verdicts(run_dir: Path, phase_tail: str | None) -> list[tuple[str, bool, str]]:
    calls = json.loads((run_dir / "tools.json").read_text(encoding="utf-8"))
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    rows = []

    facts = [call for call in calls if "agent-docs/facts.md" in text_of(call)]
    rows.append(("A01", bool(facts), text_of(facts[0])[:200] if facts else "no call names agent-docs/facts.md"))
    if facts:
        limited = [call for call in facts
                   if re.search(r"facts\.md(?:\s+2>&1)?[^;&]*\|\s*(head|tail|sed)", text_of(call))
                   or (call["name"] == "Read" and {"offset", "limit"} & set(call.get("input") or {}))]
        rows.append(("A01r", len(limited) < len(facts), text_of(facts[0])[:200]))
    specs = [call for call in calls if "agent-docs/specs" in text_of(call)]
    rows.append(("A02", bool(specs), text_of(specs[0])[:200] if specs else "no call names agent-docs/specs"))
    listings, reads = record_uses(calls)
    rows.append(("A03", not reads, "; ".join(reads)[:400] or "none"))
    rows.append(("A03l", not (reads or listings), "; ".join(reads + listings)[:400] or "none"))

    events = []
    for path in (run_dir / "telemetry").glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    recorded = [event for event in events if event.get("event") == "brief" and event.get("stage") == "understanding"
                and event.get("round") == 1 and re.fullmatch(r"[0-9a-f]{16}", event.get("workflow_run_id") or "")]
    rows.append(("A04", bool(recorded), f"{len(recorded)} matching brief events"))
    commands = [(call["input"] or {}).get("command", "") for call in calls if call["name"] == "Bash"]
    markers = [command for command in commands
               if MARKER in command and re.search(r"\bbrief\b.*--stage\s+understanding", command)]
    rows.append(("A04c", bool(markers), markers[0][-260:] if markers else "no brief marker command"))
    judgement_path = run_dir / "judgement.json"
    if markers and judgement_path.exists():
        asked = len(json.loads(judgement_path.read_text(encoding="utf-8")).get("questions", []))
        claimed, split = flag(markers[-1], "--fact-questions"), flag(markers[-1], "--split")
        rows.append(("A05", claimed == str(asked) and split == "none",
                     f"marker says {claimed} questions, split {split}; the message asks {asked}"))

    touched = [line for line in meta.get("changed_paths") or []
               if "agent-docs/specs/" in line or not re.search(r"\s(agent-docs/|\.harness/|\.claude/)", line)]
    rows.append(("A18", not touched, "; ".join(touched) or "no spec or project file changed"))

    if phase_tail is not None:
        phase = [call for call in calls if call["name"] == "Bash"
                 and re.search(r"workflow_marker\.py\s+phase\b", (call["input"] or {}).get("command", ""))]
        rows.append(("L01", bool(phase), (phase[0]["input"]["command"])[:200] if phase else "no phase command"))
        if phase:
            rows.append(("L02", any(phase_tail in (call.get("result") or "") for call in phase),
                         f"result lengths {[len(call.get('result') or '') for call in phase]}"))
            segment = re.search(r"workflow_marker\.py\s+phase[^;&|]*", phase[0]["input"]["command"]).group(0)
            piped = re.search(r"workflow_marker\.py\s+phase[^;&]*\|", phase[0]["input"]["command"])
            rows.append(("L03", ">" not in segment and not piped, segment[:200]))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("iteration", type=Path)
    args = parser.parse_args()

    tally: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for run_dir in sorted(args.iteration.glob("eval-*/*/run-*")):
        if not (run_dir / "tools.json").exists():
            print(f"missing {run_dir / 'tools.json'}", file=sys.stderr)
            continue
        config = run_dir.parent.name
        skill_dir = args.iteration / "payloads" / config / "harness/skills/doggy-workflow"
        phase_file = skill_dir / "phases" / "brief.md"
        if (skill_dir / "phases.json").exists():
            last = json.loads((skill_dir / "phases.json").read_text(encoding="utf-8"))["brief"][-1]
            phase_file = skill_dir / "phases" / f"{last}.md"
        phase_tail = phase_file.read_text(encoding="utf-8").rstrip()[-80:] if phase_file.exists() else None
        rows = verdicts(run_dir, phase_tail)
        (run_dir / "trace_grading.json").write_text(json.dumps(
            [{"text": f"{item} {TEXT[item]}", "passed": passed, "evidence": evidence}
             for item, passed, evidence in rows], indent=2, ensure_ascii=False), encoding="utf-8")
        for item, passed, _evidence in rows:
            tally[(item, config)][0] += passed
            tally[(item, config)][1] += 1

    configs = sorted({config for _item, config in tally})
    print("item\t" + "\t".join(f"{config}\tn" for config in configs) + "\ttext")
    for item in TEXT:
        cells = []
        for config in configs:
            passed, total = tally.get((item, config), (0, 0))
            cells.append(f"{passed / total:.2f}\t{total}" if total else "-\t0")
        if any(tally.get((item, config)) for config in configs):
            print(f"{item}\t" + "\t".join(cells) + f"\t{TEXT[item]}")
    (args.iteration / "trace_items.json").write_text(json.dumps(
        {f"{item}|{config}": value for (item, config), value in tally.items()}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
