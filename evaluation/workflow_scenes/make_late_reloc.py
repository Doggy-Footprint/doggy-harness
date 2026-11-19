#!/usr/bin/env python3
"""Build the `late-reloc` overlay: the brief rules (Voice, Decision sweep, Rounds) move, word for word,
out of SKILL.md into a file that `workflow_marker.py phase --phase brief` prints. Nothing is reworded,
so a run_live.py comparison against the unchanged skill isolates the delivery mechanism.
The command also mints the run id: in the first pilot the model generated the id and passed it to the
command through a shell variable, which the marker rules forbid and the runner's permissions deny."""
import argparse
import sys
from pathlib import Path

SKILL = Path("harness/skills/doggy-workflow/SKILL.md")
MARKER = Path("harness/bin/workflow_marker.py")
PHASE_FILE = Path("harness/skills/doggy-workflow/phases/brief.md")
POINTER = """The rules of the brief are not in this file. As the first action of the workflow, before reading the repository, run

```sh
python3 .harness/bin/workflow_marker.py phase --phase brief
```

and read its whole output: it prints the run id of this run, then the brief's purpose and the sections Voice, Decision sweep, and Rounds, which every message to the user follows. Do not redirect or discard that output. If the command prints nothing, read `.harness/skills/doggy-workflow/phases/brief.md` instead. Follow what it prints as if it were written here; other sections of this file refer to those sections by name.

"""
BEST_EFFORT = "Telemetry commands are best-effort: never inspect their result or let failure change the workflow."
BEST_EFFORT_NEW = BEST_EFFORT + " The one exception is `phase --phase brief`, whose output is the run id and the brief's rules (see Brief)."
CHOOSE_ID = "Choose the run id before the understanding round."
CHOOSE_ID_NEW = "The run id is the one `phase --phase brief` prints (see Brief); write it as a literal value wherever a command or file name takes it."
PRINTER = r'''
def _print_instructions(phase: str) -> None:
    import secrets

    path = Path(__file__).resolve().parents[1] / "skills" / "doggy-workflow" / "phases" / f"{phase}.md"
    try:
        sys.stdout.write(
            f"Run id of this run: {secrets.token_hex(8)}\n"
            "Write it as a literal value in every later marker command and in the spec file name.\n\n"
        )
        sys.stdout.write(path.read_text(encoding="utf-8"))
        sys.stdout.flush()
    except OSError:
        pass

'''


def swap(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"anchor not found exactly once: {old[:60]!r}")
    return text.replace(old, new)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("overlay", type=Path)
    parser.add_argument("--root", type=Path, required=True,
                        help="directory holding the harness/ of 0.52.0, the last release with the single-file skill")
    args = parser.parse_args()

    skill = (args.root / SKILL).read_text(encoding="utf-8")
    start = skill.index("\n# Brief\n") + len("\n# Brief\n\n")
    end = skill.index("\n## Quiz\n") + 1
    moved = skill[start:end]
    skill = swap(skill[:start] + POINTER + skill[end:], BEST_EFFORT, BEST_EFFORT_NEW)
    skill = swap(skill, CHOOSE_ID, CHOOSE_ID_NEW)

    marker = (args.root / MARKER).read_text(encoding="utf-8")
    marker = swap(marker, 'choices=("implement_test", "verify", "amend"))',
                  'choices=("brief", "implement_test", "verify", "amend"))')
    marker = swap(marker, "\ndef main(", PRINTER + "\ndef main(")
    marker = swap(marker, '''    phase = commands.add_parser("phase", add_help=False)
    phase.add_argument("--run-id", required=True)''', '''    phase = commands.add_parser("phase", add_help=False)
    phase.add_argument("--run-id")''')
    marker = swap(marker, "        if not args.run_id:\n            return 0\n",
                  '        if args.command == "phase" and args.phase == "brief":\n'
                  "            _print_instructions(args.phase)\n            return 0\n"
                  "        if not args.run_id:\n            return 0\n")

    for relative, text in ((SKILL, skill), (PHASE_FILE, moved), (MARKER, marker)):
        path = args.overlay / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"moved {len(moved.split())} words ({len(moved)} characters); "
          f"SKILL.md is now {len(skill.split())} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
