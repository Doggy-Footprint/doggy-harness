#!/usr/bin/env python3
"""Combine script, judge, and telemetry verdicts of runs into per-phase compliance rates."""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

PHASES = ["brief", "draft", "approve", "implement_test", "verify", "amend", "close", "cross"]
SCRIPT_PHASE = {
    "B1": "brief", "PH-pipe": "cross", "B2": "brief", "B3": "brief", "B12": "brief", "D2": "brief",
    "D2-revise": "brief", "R9": "draft", "R1": "draft", "A6": "approve", "A12": "approve", "I1": "implement_test",
    "E1": "verify", "E3": "verify", "E7": "verify", "X2": "close", "M2": "cross", "F1": "cross", "ISO": "implement_test",
}
GROUP_PHASE = {"understanding": "brief", "decision_round": "brief", "spec": "draft", "approval": "approve",
               "voice": "cross", "facts_protocol": "cross", "close": "close", "marker_counts": "cross"}
GROUND_PHASE = {"G-B1": "brief", "G-B2": "brief", "G-B3": "brief", "G-D1": "brief", "G-H1": "approve", "G-P": "cross"}
CRITICAL = {"A12", "F1", "ISO"}


def phase_of(item: dict) -> str:
    if item["method"] == "S":
        return SCRIPT_PHASE.get(item["id"], "cross")
    if item["method"] == "G":
        return GROUND_PHASE.get(item["id"], "cross")
    if item.get("group") == "dispatch":
        return {"I": "implement_test", "E": "verify", "C": "amend"}[item["id"][0]]
    return GROUP_PHASE.get(item.get("group"), "cross")


def telemetry_items(run_dir: Path) -> list[dict]:
    counts = defaultdict(int)
    for path in sorted((run_dir / "telemetry").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                counts[json.loads(line).get("event")] += 1
            except json.JSONDecodeError:
                pass
    reached = counts["subagent_start"] > 0
    out = []
    for item_id, event in (("H-gate", "gate_block"),):
        verdict = ("fail" if counts[event] else "pass") if reached else "na"
        out.append({"id": item_id, "method": "H", "verdict": verdict, "evidence": f"{counts[event]} {event} events"})
    return out


def run_items(run_dir: Path, repeat: int) -> list[dict]:
    items = []
    script = run_dir / "score_script.json"
    if script.exists():
        items += [i for i in json.loads(script.read_text(encoding="utf-8")) if i["verdict"] != "info"]
    judge = run_dir / f"judge-{repeat}.json"
    if judge.exists():
        items += json.loads(judge.read_text(encoding="utf-8"))["items"]
    items += telemetry_items(run_dir)
    for item in items:
        item["phase"] = phase_of(item) if item["id"].startswith(("H-",)) is False else "implement_test"
    return items


def rates(items: list[dict]) -> dict:
    table = {}
    for phase in PHASES:
        scored = [i for i in items if i["phase"] == phase and i["verdict"] in ("pass", "fail")]
        passed = sum(1 for i in scored if i["verdict"] == "pass")
        table[phase] = {"pass": passed, "scored": len(scored),
                        "na": sum(1 for i in items if i["phase"] == phase and i["verdict"] == "na"),
                        "unobservable": sum(1 for i in items if i["phase"] == phase and i["verdict"] == "unobservable"),
                        "rate": round(passed / len(scored), 3) if scored else None}
    return table


def agreement(run_dir: Path) -> dict | None:
    paths = sorted(run_dir.glob("judge-*.json"))
    if len(paths) < 2:
        return None
    a, b = (json.loads(p.read_text(encoding="utf-8"))["items"] for p in paths[:2])
    va, vb = {i["id"]: i["verdict"] for i in a}, {i["id"]: i["verdict"] for i in b}
    shared = sorted(set(va) & set(vb))
    same = [k for k in shared if va[k] == vb[k]]
    return {"items": len(shared), "agree": len(same), "rate": round(len(same) / len(shared), 3) if shared else None,
            "disagreements": {k: [va[k], vb[k]] for k in shared if va[k] != vb[k]}}


def bootstrap(per_run: list[float], n: int = 2000, seed: int = 7) -> list[float] | None:
    values = [v for v in per_run if v is not None]
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(n))
    return [round(means[int(0.025 * n)], 3), round(means[int(0.975 * n)], 3)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    runs = {}
    for run_dir in args.run_dirs:
        items = run_items(run_dir.resolve(), args.repeat)
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        runs[run_dir.name] = {"meta": {k: meta.get(k) for k in ("case", "harness_version", "harness_src", "end_reason",
                                                                  "turns", "cost_usd", "started_at", "ended_at")},
                              "rates": rates(items), "critical_failures": [i["id"] for i in items
                                                                           if i["id"] in CRITICAL and i["verdict"] == "fail"],
                              "judge_agreement": agreement(run_dir), "items": items}
    summary = {}
    for phase in PHASES:
        per_run = [r["rates"][phase]["rate"] for r in runs.values()]
        values = [v for v in per_run if v is not None]
        summary[phase] = {"mean": round(sum(values) / len(values), 3) if values else None, "runs_scored": len(values),
                          "ci95": bootstrap(per_run)}
    report = {"summary": summary, "runs": runs}
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'phase':<16}" + "".join(f"{name[:18]:>20}" for name in runs) + f"{'mean':>8}")
    for phase in PHASES:
        cells = []
        for r in runs.values():
            x = r["rates"][phase]
            cells.append(f"{x['pass']}/{x['scored']}" + (f" ({x['rate']:.0%})" if x["rate"] is not None else ""))
        mean = summary[phase]["mean"]
        print(f"{phase:<16}" + "".join(f"{c:>20}" for c in cells) + (f"{mean:>8.0%}" if mean is not None else f"{'-':>8}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
