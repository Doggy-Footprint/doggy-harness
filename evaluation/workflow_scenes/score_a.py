#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from judge_a import load_case  # noqa: E402

# trycompai/crm's own AGENTS.md makes every message end with an Issues list,
# which A17 and A19 would count against the skill.
OWN_MESSAGE_RULES = "trycompai/crm"
DECISION_KINDS = ("chosen", "mechanism", "added_work", "open_case")
TEXT = {
    "A06": "이해한 내용의 네 요소가 모두 있다",
    "A07": "가정에 소프트웨어의 동작이나 고른 선택지가 없다",
    "A10": "사실 질문이 사실을 묻고, 가르는 결정과 답마다의 방향을 밝힌다",
    "A10a": "질문이 설계 선택이 아니라 사실을 묻는다",
    "A10b": "질문이 가르는 결정을 밝힌다",
    "A10c": "질문이 답마다 이어지는 방향을 밝힌다",
    "A10cq": "답마다 이어지는 방향을 밝힌 질문 (질문 하나가 칸 하나)",
    "A11": "질문에 답의 추측을 붙이지 않는다",
    "A12": "저장소가 답하는 것을 묻지 않는다",
    "A13": "중요한 unknown을 사실 질문으로 묻는다",
    "A14": "덜 중요한 unknown을 가정이나 질문으로 드러낸다",
    "A15": "Not asked가 한 줄이고 저장소의 침묵을 이유로 들지 않는다",
    "A16": "초대 문장이 있고 후보 예시가 없다",
    "A17": "결정과 탐색 메모가 없다",
    "A17a": "사용자가 요청하지 않은 설계 결정을 적지 않는다",
    "A17b": "무엇을 찾아봤는지, 무엇이 없는지 적지 않는다",
    "A17m": "구현 방식을 적지 않는다",
    "A17o": "요청이 열어 둔 경우의 동작을 정해 적지 않는다",
    "A17w": "요청에 없는 작업을 덧붙이지 않는다",
    "A19": "프로젝트 세부가 없고 용어를 풀이한다",
    "A19a": "파일 경로, 코드 이름, spec id가 없다",
    "A19b": "풀이 없는 전문 용어가 없다",
    "A20": "되돌릴 수 없는 제외를 하지 않는 것에 나열하지 않는다",
    "A21": "연쇄 끝의 unknown을 드러낸다",
    "A22": "어떻게 정해도 되는 것을 묻지 않는다",
    "A23": "기록이나 파일이 없다는 말을 적지 않는다",
}


def counted(entries: list, kinds: tuple[str, ...], key: str = "quote") -> list[str]:
    """A judgement made before the judge named kinds holds plain strings; all of those count, as they did then."""
    return [entry if isinstance(entry, str) else entry[key] for entry in entries
            if isinstance(entry, str) or entry["kind"] in kinds]


def targets(question: dict) -> list[str]:
    return question.get("targets") or []


def verdicts(case: dict, judgement: dict) -> list[tuple[str, str, bool, str]]:
    rows = []

    def add(item: str, passed: bool, evidence, cell: str = "") -> None:
        if isinstance(evidence, list):
            evidence = "; ".join(evidence)
        rows.append((item, cell, passed, evidence or "none"))

    status = {entry["id"]: entry for entry in judgement.get("unknowns", [])}
    questions = judgement.get("questions", [])
    own_rules = case.get("repo", "").startswith(OWN_MESSAGE_RULES)

    understood = judgement["understood"]
    add("A06", all(understood.values()), [name for name, present in understood.items() if not present])
    add("A07", not judgement["decisions_as_assumptions"], judgement["decisions_as_assumptions"])
    if questions:
        not_fact = [q["text"] for q in questions if q["form"] != "fact"]
        no_decision = [q["text"] for q in questions if not q["names_decision"]]
        no_branches = [q["text"] for q in questions if not q["names_branches"]]
        add("A10a", not not_fact, not_fact)
        add("A10b", not no_decision, no_decision)
        add("A10c", not no_branches, no_branches)
        for index, q in enumerate(questions, 1):
            add("A10cq", bool(q["names_branches"]), q["text"], f"q{index}")
        add("A10", not (not_fact or no_decision or no_branches),
            list(dict.fromkeys(not_fact + no_decision + no_branches)))
        add("A11", not any(q["guess"] for q in questions), [q["text"] for q in questions if q["guess"]])
    repo_ids = {item["id"] for item in case.get("repo_answerable", [])}
    from_repo = [q["text"] for q in questions if repo_ids & set(targets(q))]
    add("A12", not from_repo, from_repo)
    for unknown in case.get("unknowns", []):
        entry = status.get(unknown["id"], {"status": "absent", "form": None, "evidence": ""})
        add("A13", entry["status"] == "asked" and entry["form"] == "fact",
            f"{entry['status']}/{entry['form']}: {entry['evidence']}", unknown["id"])
    for unknown in case.get("minor_unknowns") or []:
        entry = status.get(unknown["id"], {"status": "absent", "evidence": ""})
        add("A14", entry["status"] in ("asked", "assumed"), f"{entry['status']}: {entry['evidence']}", unknown["id"])
    not_asked = judgement["not_asked"]
    dismissed = [key for key, entry in status.items() if entry["status"] == "dismissed"]
    add("A15", bool(not_asked["present"] and not_asked["single_line"] and not not_asked["repo_silence_reason"]
                    and not dismissed), json.dumps({**not_asked, "dismissed": dismissed}))
    invitation = judgement["invitation"]
    add("A16", bool(invitation["present"] and invitation["examples"] is False), json.dumps(invitation))
    if not own_rules:
        decisions = counted(judgement["design_decisions"], DECISION_KINDS)
        notes = counted(judgement["search_notes"], ("process", "silence"))
        detail = counted(judgement["project_detail"], ("path", "identifier", "spec_id"))
        terms = counted(judgement["undefined_terms"], ("specialist", "coined"), "term")
        add("A17a", not decisions, decisions)
        add("A17b", not notes, notes)
        add("A17", not (decisions or notes), decisions + notes)
        add("A19a", not detail, detail)
        add("A19b", not terms, terms)
        add("A19", not (detail or terms), detail + terms)
        if judgement.get("grader", 1) >= 2:
            missing = counted(judgement["search_notes"], ("missing_record",))
            add("A23", not missing, missing)
        if judgement.get("grader", 1) >= 3:
            for item, kind in (("A17m", "mechanism"), ("A17o", "open_case"), ("A17w", "added_work")):
                found = counted(judgement["design_decisions"], (kind,))
                add(item, not found, found)
    if case.get("irreversible_exclusions"):
        add("A20", not judgement["exclusions_listed"], judgement["exclusions_listed"])
    for unknown_id in case.get("chain_unknowns", []):
        entry = status.get(unknown_id, {"status": "absent", "evidence": ""})
        add("A21", entry["status"] in ("asked", "assumed"), f"{entry['status']}: {entry['evidence']}", unknown_id)
    noise = [q["text"] for q in questions
             if targets(q) == ["dont_care"] or (targets(q) == ["other"] and q.get("useful") is False)]
    add("A22", not noise, noise)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("iteration", type=Path)
    args = parser.parse_args()

    tally: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    by_case: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    statuses: dict[str, Counter] = defaultdict(Counter)
    graders: dict[str, Counter] = defaultdict(Counter)
    extras: dict[str, list[dict]] = defaultdict(list)
    for eval_dir in sorted(args.iteration.glob("eval-*")):
        case = load_case(eval_dir.name.removeprefix("eval-"))
        important = {item["id"] for item in case.get("unknowns", [])}
        for run_dir in sorted(eval_dir.glob("*/run-*")):
            path = run_dir / "judgement.json"
            if not path.exists():
                print(f"missing {path}", file=sys.stderr)
                continue
            judgement = json.loads(path.read_text(encoding="utf-8"))
            config = run_dir.parent.name
            graders[config][judgement.get("grader", 1)] += 1
            rows = verdicts(case, judgement)
            expectations = [{"text": f"{item}{' ' + cell if cell else ''} {TEXT[item]}", "passed": passed,
                             "evidence": evidence} for item, cell, passed, evidence in rows]
            passed_count = sum(1 for row in rows if row[2])
            (run_dir / "grading.json").write_text(json.dumps({
                "expectations": expectations,
                "summary": {"passed": passed_count, "failed": len(rows) - passed_count, "total": len(rows),
                            "pass_rate": round(passed_count / len(rows), 4)},
            }, indent=2, ensure_ascii=False), encoding="utf-8")
            for item, _cell, passed, _evidence in rows:
                tally[(item, config)][0] += passed
                tally[(item, config)][1] += 1
                by_case[(item, case["id"], config)][0] += passed
                by_case[(item, case["id"], config)][1] += 1
            for entry in judgement.get("unknowns", []):
                if entry["id"] in important:
                    statuses[config][entry["status"]] += 1
            meta_path = run_dir / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            extras[config].append({
                "words": len((run_dir / "outputs" / "output.md").read_text(encoding="utf-8").split()),
                "cost_usd": meta.get("total_cost_usd") or 0,
                "turns": meta.get("num_turns") or 0,
                "questions": len(judgement.get("questions", [])),
                **{f"sentences_{kind}": len(counted(judgement["design_decisions"], (kind,)))
                   for kind in ("pointed", "outcome") if judgement.get("grader", 1) >= 3 and
                   not case.get("repo", "").startswith(OWN_MESSAGE_RULES)},
            })

    configs = sorted({config for _item, config in tally})
    items = sorted({item for item, _config in tally})
    print("item\t" + "\t".join(f"{config}\tn" for config in configs) + "\tgap\ttext")
    summary = {}
    for item in items:
        rates = []
        cells = []
        for config in configs:
            passed, total = tally[(item, config)]
            rates.append(passed / total if total else None)
            cells.append(f"{passed / total:.2f}\t{total}" if total else "-\t0")
        known = [rate for rate in rates if rate is not None]
        gap = max(known) - min(known) if len(known) > 1 else 0.0
        summary[item] = {config: tally[(item, config)] for config in configs}
        print(f"{item}\t" + "\t".join(cells) + f"\t{gap:.2f}\t{TEXT[item]}")
    print()
    for config in configs:
        runs = extras[config]
        keys = dict.fromkeys(key for run in runs for key in run)
        mean = {key: sum(run[key] for run in runs if key in run) / sum(key in run for run in runs) for key in keys}
        print(f"{config}: runs {len(runs)}, " + ", ".join(f"{key} {value:.2f}" for key, value in mean.items())
              + f", unknown statuses {dict(statuses[config])}, grader version: runs {dict(graders[config])}")
    (args.iteration / "items.json").write_text(json.dumps({
        "items": summary,
        "by_case": {f"{item}|{case_id}|{config}": value for (item, case_id, config), value in by_case.items()},
        "statuses": {config: dict(counter) for config, counter in statuses.items()},
        "extras": extras,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
