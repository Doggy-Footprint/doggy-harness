#!/usr/bin/env python3
"""Item-level A/A and A/B comparison: A1 vs A2 sets the noise floor, B vs both A runs is the candidate difference."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate  # noqa: E402


def stable_items(run_dir: Path) -> dict:
    """Verdict per item id; judge items count only when repeats 1 and 2 agree, otherwise 'judge-split'."""
    out = {}
    script = run_dir / "score_script.json"
    if script.exists():
        for item in json.loads(script.read_text(encoding="utf-8")):
            if item["verdict"] != "info":
                out[item["id"]] = (item["verdict"], aggregate.SCRIPT_PHASE.get(item["id"], "cross"))
    repeats = [json.loads((run_dir / f"judge-{n}.json").read_text(encoding="utf-8"))["items"]
               for n in (1, 2) if (run_dir / f"judge-{n}.json").exists()]
    if repeats:
        by_id = [{i["id"]: i for i in r} for r in repeats]
        for item_id, first in by_id[0].items():
            verdicts = {r[item_id]["verdict"] for r in by_id if item_id in r}
            phase = aggregate.phase_of({**first, "method": first.get("method", "J")})
            out[item_id] = (verdicts.pop() if len(verdicts) == 1 else "judge-split", phase)
    for item in aggregate.telemetry_items(run_dir):
        out[item["id"]] = (item["verdict"], "implement_test")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", nargs=2, type=Path, required=True)
    parser.add_argument("--b", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    a1, a2, b = (stable_items(p.resolve()) for p in (*args.a, args.b))
    rows, aa_diff, ab_diff, comparable = [], [], [], 0
    for item_id in sorted(set(a1) | set(a2) | set(b)):
        va, vb, vc = (x.get(item_id, ("-", None))[0] for x in (a1, a2, b))
        phase = next(x[item_id][1] for x in (a1, a2, b) if item_id in x)
        scored = {"pass", "fail"}
        if va in scored and vb in scored:
            comparable += 1
            if va != vb:
                aa_diff.append(item_id)
            elif vc in scored and vc != va:
                ab_diff.append(item_id)
        rows.append((phase, item_id, va, vb, vc))
    lines = [f"# A/A vs A/B, item level\n",
             f"Items scored pass/fail in both A runs (judge items only when both judge repeats agree): {comparable}",
             f"A1 ≠ A2 (run-to-run noise): {len(aa_diff)} — {', '.join(aa_diff) or 'none'}",
             f"A1 = A2 but B differs: {len(ab_diff)} — {', '.join(ab_diff) or 'none'}\n",
             "| phase | item | A1 | A2 | B |", "| --- | --- | --- | --- | --- |"]
    order = {p: k for k, p in enumerate(aggregate.PHASES)}
    for phase, item_id, va, vb, vc in sorted(rows, key=lambda r: (order.get(r[0], 99), r[1])):
        mark = " **(A≠A)**" if item_id in aa_diff else (" **(B≠A)**" if item_id in ab_diff else "")
        lines.append(f"| {phase} | {item_id}{mark} | {va} | {vb} | {vc} |")
    text = "\n".join(lines) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print("\n".join(lines[:4]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
