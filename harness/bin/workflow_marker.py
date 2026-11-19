#!/usr/bin/env python3
import argparse
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import config  # noqa: E402
import telemetry  # noqa: E402


SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "doggy-workflow"
RECORDED_PHASES = ("implement_test", "verify", "amend")
PHASES = ("brief", "draft", "approve", *RECORDED_PHASES, "step", "close", "resume")
RUN_ID_ISSUED = (
    "Run id of this run: {run_id}\n"
    "Write it as a literal value in every later marker command and in the spec file name."
)
NOT_RECORDED = (
    "Not recorded in telemetry: no run is active for run id {run_id}. A run is active between `start` and `end`; "
    "after a nonterminal stop, emit `start` again before the next phase. Carry on with this phase either way."
)
PRINTED_AGAIN = "Printed again: nothing was recorded."
LEFT_OUT = "Left out: {parts}. `--all` prints everything."
# Why a part does not apply, by the condition its manifest entry names.
NOT_APPLICABLE = {
    "stepped": "the spec has no steps",
    "not-stepped": "the spec already has steps",
    "fuzzing": "the spec declares no fuzzing",
    "mutation-tool": "the spec declares no mutation tool",
    "fuzzing-or-mutation-tool": "the spec declares neither fuzzing nor a mutation tool",
}
MARKERS_HEADING = "## Markers of this phase"
MARKERS_MISSING = (
    "The marker commands of this phase could not be read; they are in .harness/skills/doggy-workflow/markers.json.\n"
)
RULES_MISSING = (
    "The rules of this phase could not be read. Read the files that "
    ".harness/skills/doggy-workflow/phases.json lists for it, in .harness/skills/doggy-workflow/phases/.\n"
)
PHASE_USAGE = (
    "doggy-workflow: unknown phase arguments. Use `phase --phase brief`, "
    "`phase --run-id ID --phase draft|approve|implement_test|verify|amend|step|close|resume` "
    "(amend takes `--reason intent_mismatch|brief_change|contract_change|correction`), "
    "or add `--again` to print a phase's rules again and `--all` to print the parts a phase leaves out.\n"
)
VERIFICATION_COUNTS = ("fuzz_execs", "fuzz_violations", "mutants", "killed", "survived", "equivalent", "overturned")


class _QuietParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)

    def exit(self, status=0, message=None):
        raise ValueError(message or str(status))


def _non_negative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise ValueError(value)
    return number


def _parser() -> argparse.ArgumentParser:
    parser = _QuietParser(add_help=False)
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start", add_help=False)
    start.add_argument("--run-id", required=True)
    start.add_argument("--spec", required=True)
    start.add_argument("--spec-version", required=True, type=_non_negative)

    phase = commands.add_parser("phase", add_help=False)
    phase.add_argument("--run-id")
    phase.add_argument("--phase", required=True, choices=PHASES)
    phase.add_argument("--again", action="store_true")
    phase.add_argument("--all", action="store_true")
    phase.add_argument("--reason", choices=("intent_mismatch", "brief_change", "contract_change", "correction"))

    # Parsed only for argv compatibility: the PostToolUse hook emits the brief
    # line, because this process has no session id or tool_use_id.
    brief = commands.add_parser("brief", add_help=False)
    brief.add_argument("--run-id", required=True)
    brief.add_argument("--stage", required=True, choices=("understanding", "decision", "approval", "quiz", "closing"))
    brief.add_argument("--round", required=True, type=_non_negative)
    brief.add_argument("--fact-questions", type=_non_negative)
    brief.add_argument("--user-decisions", type=_non_negative)
    brief.add_argument("--split", choices=("none", "proposed", "accepted", "declined"))
    brief.add_argument("--picks-differ", type=_non_negative)
    brief.add_argument("--quiz-of", choices=("approval", "closing"))
    brief.add_argument("--quiz-questions", type=_non_negative)
    brief.add_argument("--quiz-answered", type=_non_negative)
    brief.add_argument("--quiz-differ", type=_non_negative)
    brief.add_argument("--completion-invalid", type=_non_negative)
    brief.add_argument("--completion-differ", type=_non_negative)

    verifier = commands.add_parser("verifier", add_help=False)
    verifier.add_argument("--run-id", required=True)
    verifier.add_argument("--round", required=True, type=_non_negative)
    verifier.add_argument("--result", required=True, choices=("pass", "retry", "limit"))
    verifier.add_argument("--findings", required=True, type=_non_negative)
    verifier.add_argument("--seeds-run", required=True, type=_non_negative)
    verifier.add_argument("--seeds-detected", required=True, type=_non_negative)

    verification = commands.add_parser("verification", add_help=False)
    verification.add_argument("--run-id", required=True)
    verification.add_argument("--fuzz-execs", required=True, type=_non_negative)
    verification.add_argument("--fuzz-violations", required=True, type=_non_negative)
    verification.add_argument("--mutants", required=True, type=_non_negative)
    verification.add_argument("--killed", required=True, type=_non_negative)
    verification.add_argument("--survived", required=True, type=_non_negative)
    verification.add_argument("--equivalent", required=True, type=_non_negative)
    verification.add_argument("--overturned", required=True, type=_non_negative)

    end = commands.add_parser("end", add_help=False)
    end.add_argument("--run-id", required=True)
    end.add_argument("--status", required=True, choices=("complete", "limit", "handoff", "aborted"))
    return parser


def _spec_facts(run_id: str | None) -> dict:
    """What the run's spec says about itself; empty when there is no single readable spec for the run id."""
    if not run_id:
        return {}
    try:
        (path,) = config.load_paths().specs.glob(f"{run_id}-*.md")
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError, UnicodeDecodeError, KeyError, TypeError):
        return {}

    def declared(prefix: str) -> bool:
        values = [line[len(prefix):] for line in lines if line.startswith(prefix)]
        return not values or not values[0].strip().lower().startswith("none")

    rows = 0
    inside = False
    for line in lines:
        if line.startswith("# "):
            inside = line.rstrip() == "# Steps"
        elif inside and line.startswith("|"):
            rows += 1
    return {"stepped": rows > 2, "fuzzing": declared("Fuzzing:"), "mutation-tool": declared("Mutation tool:")}


def _applies(when: str | None, facts: dict) -> bool:
    # Unknown facts print everything: a rule printed needlessly costs words, a rule withheld wrongly costs the run.
    if when is None or not facts:
        return True
    if when == "stepped":
        return facts["stepped"]
    if when == "not-stepped":
        return not facts["stepped"]
    if when == "fuzzing-or-mutation-tool":
        return facts["fuzzing"] or facts["mutation-tool"]
    return facts.get(when, True)


def _select(entries: list, facts: dict) -> tuple[list[str], list[str]]:
    kept, left_out = [], []
    for entry in entries:
        name, when = (entry, None) if isinstance(entry, str) else (entry["name"], entry.get("when"))
        if _applies(when, facts):
            kept.append(name)
        else:
            left_out.append(f"{name} ({NOT_APPLICABLE.get(when, when)})")
    return kept, left_out


def _phase_rules(phase: str, facts: dict) -> tuple[str, list[str]]:
    try:
        entries = json.loads((SKILL_DIR / "phases.json").read_text(encoding="utf-8"))[phase]
        names, left_out = _select(entries, facts)
        return "\n".join((SKILL_DIR / "phases" / f"{name}.md").read_text(encoding="utf-8")
                         for name in names), left_out
    except (OSError, ValueError, KeyError, TypeError):
        return RULES_MISSING, []


def _phase_markers(phase: str, run_id: str | None, facts: dict) -> tuple[str, list[str]]:
    try:
        markers = json.loads((SKILL_DIR / "markers.json").read_text(encoding="utf-8"))
        mine = markers["phases"].get(phase)
        if mine is None:
            return "", []
        commands, without_commands = _select(mine["commands"], facts)
        rules, _ = _select(mine["rules"], facts)
        known = dict(markers["commands"])
        known["start-marker"] = known["start"].split(" && ", 1)[1]
        sentences = dict(markers["rules"])
        lines = [known[name] for name in commands]
        if run_id:
            lines = [line.replace("--run-id ID", f"--run-id {run_id}") for line in lines]
        return (f"\n{MARKERS_HEADING}\n\n```sh\n" + "\n".join(lines) + "\n```\n\n"
                + " ".join(sentences[name] for name in rules) + "\n"), without_commands
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return f"\n{MARKERS_HEADING}\n\n{MARKERS_MISSING}", []


def _write(text: str) -> None:
    # Bytes, because the rules hold characters that a non-UTF-8 terminal encoding cannot print.
    try:
        sys.stdout.flush()
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.flush()
    except (OSError, ValueError, AttributeError):
        pass


def _run_is_active(run_id: str | None) -> bool:
    try:
        workflow = telemetry.active_workflow()
    except Exception:
        return False
    return bool(run_id) and workflow is not None and workflow["workflow_run_id"] == run_id


def _phase(args) -> None:
    # The output is the phase's instructions, so it is printed whatever happens to the telemetry line.
    lines = [f"doggy-workflow phase: {args.phase}"]
    run_id = args.run_id
    if args.again:
        lines.append(PRINTED_AGAIN)
    elif args.phase == "brief" and not args.run_id:
        run_id = secrets.token_hex(8)
        lines.append(RUN_ID_ISSUED.format(run_id=run_id))
    elif args.phase in RECORDED_PHASES:
        # A failed write stays silent like every telemetry failure; only a missing run is worth telling,
        # because the next phases would go unrecorded too.
        if not _run_is_active(args.run_id):
            lines.append(NOT_RECORDED.format(run_id=args.run_id or "(none given)"))
        else:
            try:
                telemetry.workflow_phase(args.run_id, args.phase, args.reason)
            except Exception:
                pass
    facts = {} if args.all else _spec_facts(args.run_id)
    rules, left_out = _phase_rules(args.phase, facts)
    markers, without_commands = _phase_markers(args.phase, run_id, facts)
    if left_out or without_commands:
        lines.append(LEFT_OUT.format(parts=", ".join(left_out + without_commands)))
    _write("\n".join(lines) + "\n\n" + rules + markers)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    try:
        args = _parser().parse_args(arguments)
    except Exception:
        if arguments[:1] == ["phase"]:
            _write(PHASE_USAGE)
        return 0
    try:
        if args.command == "phase":
            _phase(args)
            return 0
        if not args.run_id:
            return 0
        if args.command == "start":
            telemetry.workflow_start(args.run_id, args.spec, args.spec_version)
        elif args.command == "verifier":
            telemetry.verifier_result(
                args.run_id,
                args.round,
                args.result,
                args.findings,
                args.seeds_run,
                args.seeds_detected,
            )
        elif args.command == "verification":
            telemetry.verification_result(args.run_id, **{name: getattr(args, name) for name in VERIFICATION_COUNTS})
        elif args.command == "end":
            telemetry.workflow_end(args.run_id, args.status)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
