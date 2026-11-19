#!/usr/bin/env python3
"""Compare two scored scene A arms that may live in different iteration directories.

Each arm is DIRECTORY:CONFIG. The rate of an item is the sum over cases of the mean passes per run,
divided by the sum over cases of the mean cells per run, so that an arm with unequal runs per case
is not pulled toward the cases it ran most; with equal runs per case it equals the pooled rate.
The interval resamples runs within each case of each arm, drawing one run fewer than the case has:
drawing as many as it has understates the variance by the factor (n-1)/n, which at 5 runs per case
makes 6 to 7% of same-against-same intervals exclude zero, and at 2 or 3 runs 12 to 17%.
A case with a single run has no variance to estimate, so an arm with such a case gets no interval."""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

Runs = dict[str, list[dict[str, tuple[int, int]]]]


def load(arm: str, cases: set[str] | None) -> tuple[Runs, list[dict]]:
    directory, _, config = arm.rpartition(":")
    runs: Runs = defaultdict(list)
    extras = []
    for run_dir in sorted(Path(directory).expanduser().glob(f"eval-*/{config}/run-*")):
        if cases and run_dir.parent.parent.name.removeprefix("eval-") not in cases:
            continue
        grading, trace = run_dir / "grading.json", run_dir / "trace_grading.json"
        if not (grading.exists() and trace.exists()):
            print(f"not scored: {run_dir}", file=sys.stderr)
            continue
        cells: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        rows = json.loads(grading.read_text(encoding="utf-8"))["expectations"]
        for row in rows + json.loads(trace.read_text(encoding="utf-8")):
            item = row["text"].split()[0]
            cells[item][0] += bool(row["passed"])
            cells[item][1] += 1
        runs[run_dir.parent.parent.name].append({item: (passed, total) for item, (passed, total) in cells.items()})
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        extras.append({"cost": meta.get("total_cost_usd") or 0, "turns": meta.get("num_turns") or 0,
                       "denials": len(meta.get("permission_denials") or []), "error": bool(meta.get("is_error")),
                       "words": len((run_dir / "outputs" / "output.md").read_text(encoding="utf-8").split())})
    return runs, extras


def rate(runs: Runs, item: str) -> tuple[float | None, int]:
    passed = total = 0.0
    cells = 0
    for case_runs in runs.values():
        passed += sum(run.get(item, (0, 0))[0] for run in case_runs) / len(case_runs)
        total += sum(run.get(item, (0, 0))[1] for run in case_runs) / len(case_runs)
        cells += sum(run.get(item, (0, 0))[1] for run in case_runs)
    return (passed / total if total else None), cells


def resampled(runs: Runs, rng: random.Random) -> Runs:
    return {case: rng.choices(case_runs, k=len(case_runs) - 1) for case, case_runs in runs.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("new")
    parser.add_argument("--draws", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cases", help="comma-separated case ids; compare only these in both arms")
    args = parser.parse_args()

    cases = set(args.cases.split(",")) if args.cases else None
    base, base_extras = load(args.base, cases)
    new, new_extras = load(args.new, cases)
    for name, runs, extras in (("base", base, base_extras), ("new", new, new_extras)):
        count = len(extras)
        per_case = ", ".join(f"{case.removeprefix('eval-')} {len(case_runs)}" for case, case_runs in sorted(runs.items()))
        print(f"{name}: {count} runs ({per_case}); "
              f"cost/run ${sum(e['cost'] for e in extras) / count:.3f}, total ${sum(e['cost'] for e in extras):.2f}, "
              f"turns {sum(e['turns'] for e in extras) / count:.1f}, words {sum(e['words'] for e in extras) / count:.0f}, "
              f"denials {sum(e['denials'] for e in extras)}, errors {sum(e['error'] for e in extras)}")

    items = sorted({item for runs in (base, new) for case_runs in runs.values() for run in case_runs for item in run})
    rng = random.Random(args.seed)
    draws: dict[str, list[float]] = defaultdict(list)
    single = [f"{name} {case.removeprefix('eval-')}" for name, runs in (("base", base), ("new", new))
              for case, case_runs in sorted(runs.items()) if len(case_runs) < 2]
    if single:
        print(f"no interval: one run only in {', '.join(single)}")
    for _ in range(0 if single else args.draws):
        base_draw, new_draw = resampled(base, rng), resampled(new, rng)
        for item in items:
            low, high = rate(base_draw, item)[0], rate(new_draw, item)[0]
            if low is not None and high is not None:
                draws[item].append(high - low)

    print("item\tbase\tcells\tnew\tcells\tdiff\tlow\thigh\tverdict")
    for item in items:
        (low_rate, low_cells), (high_rate, high_cells) = rate(base, item), rate(new, item)
        if low_rate is None or high_rate is None:
            shown = "-" if low_rate is None else f"{low_rate:.2f}"
            other = "-" if high_rate is None else f"{high_rate:.2f}"
            print(f"{item}\t{shown}\t{low_cells}\t{other}\t{high_cells}")
            continue
        if single:
            print(f"{item}\t{low_rate:.2f}\t{low_cells}\t{high_rate:.2f}\t{high_cells}\t{high_rate - low_rate:+.2f}")
            continue
        ordered = sorted(draws[item])
        low = ordered[int(0.025 * len(ordered))]
        high = ordered[min(len(ordered) - 1, int(0.975 * len(ordered)))]
        verdict = "better" if low > 0 else "worse" if high < 0 else ""
        print(f"{item}\t{low_rate:.2f}\t{low_cells}\t{high_rate:.2f}\t{high_cells}\t{high_rate - low_rate:+.2f}"
              f"\t{low:+.2f}\t{high:+.2f}\t{verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
