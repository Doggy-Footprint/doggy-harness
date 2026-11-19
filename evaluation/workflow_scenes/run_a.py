#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIEF_FACTS = HERE.parent / "brief_facts"
FIRST_MESSAGE_CASES = ("batch-cli", "cache", "tsv-control", "log-retention", "logs-filter-control",
                       "mail-backfill", "no-email-filter-control")


def run(job: tuple[Path, Path, Path, Path], model: str, effort: str) -> str | None:
    skill, case, repo, run_dir = job
    done = subprocess.run(
        [sys.executable, str(BRIEF_FACTS / "run_model.py"), "--model", model, "--effort", effort,
         "--skill", str(skill), "--case", str(case), "--repo", str(repo), "--run-dir", str(run_dir)],
        capture_output=True, text=True)
    return None if done.returncode == 0 else f"{run_dir}: exit {done.returncode}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("iteration", type=Path)
    parser.add_argument("--repos", required=True, type=Path, help="directory holding one clone per repository name")
    parser.add_argument("--config", action="append", required=True, metavar="NAME=SKILL.md")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()

    jobs = []
    for case_id in FIRST_MESSAGE_CASES:
        case_path = BRIEF_FACTS / "cases" / f"{case_id}.json"
        repo_name = json.loads(case_path.read_text(encoding="utf-8"))["repo"].split("@")[0].split("/")[1]
        for config in args.config:
            name, skill = config.split("=", 1)
            for number in range(1, args.runs + 1):
                run_dir = args.iteration / f"eval-{case_id}" / name / f"run-{number}"
                output = run_dir / "outputs" / "output.md"
                if output.exists() and output.read_text(encoding="utf-8").strip():
                    continue
                jobs.append((Path(skill), case_path, args.repos / repo_name, run_dir))
    with ThreadPoolExecutor(args.jobs) as pool:
        failures = [item for item in pool.map(lambda job: run(job, args.model, args.effort), jobs) if item]
    for failure in failures:
        print(f"run failed: {failure}", file=sys.stderr)
    print(f"ran {len(jobs) - len(failures)} of {len(jobs)} runs")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
