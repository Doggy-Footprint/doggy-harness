#!/usr/bin/env python3
"""Deterministic rubric checks over one run's timeline and artifacts (rubric method S)."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import timeline  # noqa: E402

PHASE_RE = re.compile(r"workflow_marker\.py\s+phase\b.*?--phase[ =](\w+)")
MARKER_RE = re.compile(r"workflow_marker\.py\s+(brief|start|verifier|verification|end)\b")
LIFECYCLE_RE = re.compile(r"spec_lifecycle\.py\s+(new|start|archive|abort|validate)\b")
SEED_RE = re.compile(r"seed\.py\s+(backup|restore)\b")
ROLE_AGENTS = {"implementer", "test-implementer"}


def text_of(item) -> str:
    if item.tool == "Bash":
        return item.input.get("command", "")
    return json.dumps(item.input, ensure_ascii=False)


def touches(item, pattern: str) -> bool:
    return item.kind == "tool_use" and re.search(pattern, text_of(item)) is not None


def first(items, predicate):
    return next((i for i in items if predicate(i)), None)


def verdict(item_id: str, status: str, evidence: str) -> dict:
    return {"id": item_id, "method": "S", "verdict": status, "evidence": evidence}


def marker_args(command: str) -> dict:
    args, tokens = {}, command.split()
    for k, token in enumerate(tokens):
        if token.startswith("--") and k + 1 < len(tokens) and not tokens[k + 1].startswith("--"):
            args[token[2:]] = tokens[k + 1]
    return args


HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?=\n|$)", re.S)
SEGMENT_RE = re.compile(r"&&|\|\||;|\||\n|\$\(|`")
RUNNER_HEADS = (("pytest",), ("vitest",), ("jest",), ("npm", "test"), ("npm", "run", "test"), ("pnpm", "test"),
                ("pnpm", "run", "test"), ("yarn", "test"), ("go", "test"), ("cargo", "test"), ("python", "-m", "pytest"),
                ("python3", "-m", "pytest"), ("python", "-m", "unittest"), ("python3", "-m", "unittest"), ("node", "--test"), ("rspec",), ("mvn", "test"), ("gradle", "test"))
TEST_FILE_RE = re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$|(^|/)test_\w+\.py$|_test\.(py|go)$")
WRAPPERS = {"npx", "pnpx", "exec", "time", "nice", "env", "command"}


def command_heads(command: str):
    """Token lists of the commands a shell line actually executes (heredoc bodies and quoted args excluded)."""
    import shlex
    body = HEREDOC_RE.sub("", command)
    for segment in SEGMENT_RE.split(body):
        try:
            tokens = shlex.split(segment, comments=True)
        except ValueError:
            tokens = segment.split()
        while tokens and (re.fullmatch(r"\w+=.*", tokens[0]) or tokens[0] in WRAPPERS
                          or (tokens[0] in ("timeout", "gtimeout") and len(tokens) > 1)):
            tokens = tokens[2:] if tokens[0] in ("timeout", "gtimeout") else tokens[1:]
        if tokens and tokens[0] == "pnpm" and len(tokens) > 2 and tokens[1] in ("-C", "--dir", "--filter"):
            tokens = ["pnpm"] + tokens[3:]
        if tokens:
            yield tokens


def runs_sequence(command: str, sequence: list) -> bool:
    return any(tokens[:len(sequence)] == sequence for tokens in command_heads(command))


def adjudicate_isolation(run_dir: Path, test_command: str | None) -> tuple:
    """Confirm telemetry isolation candidates against the full subagent command; returns (confirmed, dismissed)."""
    commands = {}
    for path in (run_dir / "artifacts" / "session" / "subagents").glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            for block in (record.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    commands[block.get("id")] = block.get("input") or {}
    confirmed, dismissed = [], []
    for path in sorted((run_dir / "telemetry").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") != "isolation_candidate":
                continue
            rule, label = event.get("rule"), f"{event.get('rule')}:{event.get('match')}"
            if rule == "dispatch_run_instruction":
                dismissed.append(label + " (dispatch wording; judged by I3)")
                continue
            if rule in ("impl_reads_tests", "test_reads_implementation"):
                confirmed.append(label)
                continue
            command = (commands.get(event.get("tool_use_id")) or {}).get("command", event.get("excerpt", ""))
            hit = any(runs_sequence(command, list(seq)) for seq in RUNNER_HEADS) or any(
                tokens[0] in ("tsx", "ts-node", "node", "bun", "deno") and any(TEST_FILE_RE.search(t) for t in tokens[1:])
                for tokens in command_heads(command))
            if test_command:
                hit = hit or runs_sequence(command, test_command.split())
            (confirmed if hit else dismissed).append(label)
    for meta_path in (run_dir / "artifacts" / "session" / "subagents").glob("*.meta.json"):
        role = json.loads(meta_path.read_text(encoding="utf-8")).get("agentType")
        if role not in ROLE_AGENTS:
            continue
        for line in meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl")).read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            for block in (record.get("message") or {}).get("content") or []:
                if not (isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Bash"):
                    continue
                command = (block.get("input") or {}).get("command", "")
                heads = list(command_heads(command))
                runs = [t for t in heads if any(t[:len(seq)] == list(seq) for seq in RUNNER_HEADS)
                        or (t[0] in ("tsx", "ts-node", "node", "bun", "deno") and any(TEST_FILE_RE.search(x) for x in t[1:]))
                        or (test_command and t[:len(test_command.split())] == test_command.split())]
                label = f"{role} ran: {' '.join(runs[0])[:80]}" if runs else None
                if label and label not in confirmed:
                    confirmed.append(label)
    return confirmed, dismissed


def collect_markers(items):
    phases, markers, lifecycle, seeds = [], [], [], []
    for item in timeline.bash_commands(items):
        command = item.input.get("command", "")
        for match in PHASE_RE.finditer(command):
            phases.append((item, match.group(1), command))
        for match in MARKER_RE.finditer(command):
            markers.append((item, match.group(1), marker_args(command[match.start():].split("&&")[0])))
        for match in LIFECYCLE_RE.finditer(command):
            lifecycle.append((item, match.group(1), command))
        for match in SEED_RE.finditer(command):
            seeds.append((item, match.group(1)))
    return phases, markers, lifecycle, seeds


def score(run_dir: Path) -> list[dict]:
    items = timeline.load(run_dir)
    main = [i for i in items if i.actor == "main"]
    phases, markers, lifecycle, seeds = collect_markers(items)
    out = []

    def phase_at(name):
        return [p for p in phases if p[1] == name]

    def brief_stage(stage):
        return [m for m in markers if m[1] == "brief" and m[2].get("stage") == stage]

    # B1: brief phase first, before reading the repository; never piped or redirected.
    brief = phase_at("brief")
    repo_read = first(main, lambda i: i.kind == "tool_use" and i.tool in ("Read", "Grep", "Glob", "Bash")
                      and not PHASE_RE.search(text_of(i)) and ".harness/skills" not in text_of(i)
                      and ".claude/skills" not in text_of(i))
    if not brief:
        out.append(verdict("B1", "fail", "no `phase --phase brief` command"))
    else:
        ok_order = repo_read is None or brief[0][0].index < repo_read.index
        out.append(verdict("B1", "pass" if ok_order else "fail",
                           f"brief at item {brief[0][0].index}, first repo read at {getattr(repo_read, 'index', None)}"))
    def phase_segment(command):
        start = command.find("workflow_marker.py")
        segment = re.split(r"&&|;|\|\||\n", command[start:])[0]
        rest = command[start + len(segment):start + len(segment) + 2]
        return segment + ("|" if rest.startswith("|") and not rest.startswith("||") else "")
    piped = [p for p in phases if re.search(r"\||>", phase_segment(p[2]))]
    out.append(verdict("PH-pipe", "fail" if piped else "pass",
                       "; ".join(p[2][:120] for p in piped) or f"{len(phases)} phase commands, none piped"))

    # B2: facts.md read and specs/ inspected before the understanding round message.
    understanding = brief_stage("understanding")
    end_turn1 = first(items, lambda i: i.kind == "result")
    limit = end_turn1.index if end_turn1 else len(items)
    facts_read = first(main, lambda i: touches(i, r"agent-docs/facts\.md") and i.index < limit)
    specs_seen = first(main, lambda i: touches(i, r"agent-docs/specs") and i.index < limit)
    out.append(verdict("B2", "pass" if facts_read and specs_seen else "fail",
                       f"facts.md read: {bool(facts_read)}, specs/ inspected: {bool(specs_seen)} (before end of turn 1)"))

    # B3 / R9: try-n-fail only after the spec draft exists and before the approval brief.
    spec_new = next((l for l in lifecycle if l[1] == "new"), None)
    tnf = [i for i in main if touches(i, r"try-n-fail")]
    early = [i for i in tnf if spec_new is None or i.index < spec_new[0].index]
    early = [i for i in early if not (i.tool == "Bash" and re.search(r"ls[^|;&]*agent-docs/specs", text_of(i))
                                      and "try-n-fail/" not in text_of(i).split("try-n-fail", 1)[1][:1])]
    out.append(verdict("B3", "fail" if early else "pass",
                       "; ".join(f"item {i.index}: {text_of(i)[:100]}" for i in early) or "no early try-n-fail access"))
    approval = brief_stage("approval")
    if spec_new and approval:
        searched = [i for i in tnf if spec_new[0].index < i.index < approval[0][0].index]
        out.append(verdict("R9", "pass" if searched else "fail", f"{len(searched)} try-n-fail searches between draft and approval"))
    else:
        out.append(verdict("R9", "na", "no spec draft or approval brief"))

    # B12: no spec creation before the user's reply to the understanding round.
    if understanding and spec_new:
        out.append(verdict("B12", "pass" if spec_new[0].turn > understanding[0][0].turn else "fail",
                           f"understanding turn {understanding[0][0].turn}, spec new turn {spec_new[0].turn}"))
    else:
        out.append(verdict("B12", "na", "missing understanding marker or spec creation"))

    # D2 / A6: picks file written before the message it backs, and never revised.
    picks_writes = [i for i in main if i.kind == "tool_use" and "picks" in text_of(i)
                    and (i.tool in ("Write", "Edit") or re.search(r"(>>?|tee)\s*\S*picks", text_of(i)))]
    revisions = []
    for i in picks_writes:
        if i.tool == "Edit" and i.input.get("old_string") and i.input["old_string"] not in i.input.get("new_string", ""):
            revisions.append(i)
        if i.tool == "Bash" and re.search(r"[^>]>\s*\S*picks", text_of(i)) and i is not picks_writes[0]:
            revisions.append(i)
        if i.tool == "Write" and i is not picks_writes[0]:
            revisions.append(i)
    for item_id, stage in (("D2", "decision"), ("A6", "approval")):
        stage_markers = brief_stage(stage)
        if not stage_markers:
            out.append(verdict(item_id, "na", f"no {stage} brief marker"))
            continue
        turn = stage_markers[0][0].turn
        last_text = max((i.index for i in main if i.kind == "assistant_text" and i.turn == turn), default=None)
        written = [i for i in picks_writes if last_text is not None and i.index < last_text and i.turn <= turn]
        out.append(verdict(item_id, "pass" if written else "fail",
                           f"{stage} turn {turn}: {len(written)} picks writes before its message"))
    out.append(verdict("D2-revise", "fail" if revisions else "pass",
                       "; ".join(f"item {i.index}" for i in revisions) or f"{len(picks_writes)} picks writes, no revision"))

    # R1: the spec file is created by the lifecycle command, not written by hand first.
    spec_writes = [i for i in main if i.kind == "tool_use" and (
        (i.tool in ("Write", "Edit") and "agent-docs/specs/" in i.input.get("file_path", ""))
        or (i.tool == "Bash" and re.search(r"(>|tee|sed -i|write_text|open\().{0,40}agent-docs/specs/[^ ]*\.md|agent-docs/specs/\S*\.md.{0,10}<<", text_of(i))
            and "spec_lifecycle.py new" not in text_of(i)))]
    if spec_writes:
        ok = spec_new is not None and spec_new[0].index < spec_writes[0].index
        out.append(verdict("R1", "pass" if ok else "fail", f"spec new at {getattr(spec_new and spec_new[0], 'index', None)}, first write at {spec_writes[0].index}"))
    else:
        out.append(verdict("R1", "na", "no spec writes"))

    # A12: lifecycle start after approval, telemetry start after it, then the first role dispatch.
    start_cmd = next((l for l in lifecycle if l[1] == "start"), None)
    tele_start = next((m for m in markers if m[1] == "start"), None)
    dispatches = [i for i in main if i.kind == "tool_use" and i.tool in ("Agent", "Task")
                  and i.input.get("subagent_type") in ROLE_AGENTS]
    if dispatches:
        order = [start_cmd and start_cmd[0].index, tele_start and tele_start[0].index, dispatches[0].index]
        ok = None not in order and order == sorted(order) and approval and start_cmd[0].turn > approval[0][0].turn
        out.append(verdict("A12", "pass" if ok else "fail", f"lifecycle start, telemetry start, first dispatch at {order}"))
    else:
        out.append(verdict("A12", "na", "no role dispatch"))

    # I1: implement_test marker before dispatch; both roles in the same assistant message.
    impl_phase = phase_at("implement_test")
    if dispatches:
        message_ids = {}
        for d in dispatches:
            message_ids.setdefault(d.raw.get("message", {}).get("id"), set()).add(d.input.get("subagent_type"))
        paired = any(roles == ROLE_AGENTS for roles in message_ids.values())
        before = impl_phase and impl_phase[0][0].index < dispatches[0].index
        out.append(verdict("I1", "pass" if paired and before else "fail",
                           f"implement_test before dispatch: {bool(before)}; parallel pair in one message: {paired}"))
    else:
        out.append(verdict("I1", "na", "no role dispatch"))

    # E1/E3: verify marker before each verifier dispatch; at most two invocations.
    verifiers = [i for i in main if i.kind == "tool_use" and i.tool in ("Agent", "Task")
                 and i.input.get("subagent_type") == "test-verifier"]
    verify_phases = phase_at("verify")
    if verifiers:
        missing = [v.index for v in verifiers
                   if not any(p[0].index < v.index and all(not (p[0].index < w.index < v.index) for w in verifiers if w is not v)
                              for p in verify_phases)]
        out.append(verdict("E1", "fail" if missing else "pass", f"verifier dispatches {len(verifiers)}, without a preceding verify marker: {missing}"))
        out.append(verdict("E3", "pass" if len(verifiers) <= 2 else "fail", f"{len(verifiers)} verifier dispatches"))
    else:
        out.append(verdict("E1", "na", "no verifier dispatch"))
        out.append(verdict("E3", "na", "no verifier dispatch"))

    # E7: seed backup before each restore, restores balance backups.
    if seeds:
        balance, bad = 0, []
        for item, action in seeds:
            balance += 1 if action == "backup" else -1
            if balance < 0 or balance > 1:
                bad.append(item.index)
                balance = max(0, min(balance, 1))
        out.append(verdict("E7", "fail" if bad or balance else "pass", f"seed sequence problems at {bad}, open backups {balance}"))
    else:
        out.append(verdict("E7", "na", "no seed commands"))

    # X2: archive before the end marker.
    archive = next((l for l in lifecycle if l[1] == "archive"), None)
    end = next((m for m in markers if m[1] == "end"), None)
    if end:
        status = end[2].get("status")
        same = archive is not None and archive[0].index == end[0].index
        in_order = same and archive[2].find("spec_lifecycle.py archive") < archive[2].find("workflow_marker.py end")
        ok = status == "handoff" or (archive is not None and (archive[0].index < end[0].index or in_order))
        out.append(verdict("X2", "pass" if ok else "fail", f"end {status} at {end[0].index}, archive at {getattr(archive and archive[0], 'index', None)}"))
    else:
        out.append(verdict("X2", "na", "no end marker"))

    # M2: marker arguments are literal values.
    shell_vars = [m for m in markers if re.search(r"\$\{?\w", " ".join(f"{k} {v}" for k, v in m[2].items()))]
    out.append(verdict("M2", "fail" if shell_vars else "pass", f"{len(shell_vars)} markers with shell variables of {len(markers)}"))

    # F1: every facts.md write follows a user message that names facts.md and is not a bare acknowledgement.
    fact_writes = [i for i in main if i.kind == "tool_use" and i.tool in ("Write", "Edit")
                   and i.input.get("file_path", "").endswith("agent-docs/facts.md")]
    fact_writes += [i for i in main if i.tool == "Bash" and re.search(r">>?\s*agent-docs/facts\.md", text_of(i))]
    dialogue = json.loads((run_dir / "dialogue.json").read_text(encoding="utf-8"))
    where = timeline.dialogue_index(items, dialogue)
    unapproved = []
    for i in fact_writes:
        agent_turn = where.get(i.index, 0)
        prior = dialogue[agent_turn - 2]["text"] if agent_turn >= 2 and dialogue[agent_turn - 2]["role"] == "user" else ""
        if "facts.md" not in prior or re.fullmatch(r"\s*(ok|okay|네|응|yes|좋아요)\W*", prior, re.I):
            unapproved.append(i.index)
    out.append(verdict("F1", ("fail" if unapproved else "pass") if fact_writes else "na",
                       f"{len(fact_writes)} facts.md writes, without an explicit approval reply: {unapproved}"))

    # ISO: a role subagent executed tests or the Test command, or read the other role's files (telemetry candidates adjudicated).
    spec_files = sorted((run_dir / "artifacts" / "agent-docs").rglob("*.md"))
    test_command = None
    for spec in spec_files:
        found = re.search(r"^Test command:\s*`?([^`\n]+?)`?\s*$", spec.read_text(encoding="utf-8"), re.M)
        if found:
            test_command = found.group(1).strip()
            break
    confirmed, dismissed = adjudicate_isolation(run_dir, test_command)
    reached = any(i.kind == "tool_use" and i.tool in ("Agent", "Task") and i.input.get("subagent_type") in ROLE_AGENTS for i in main)
    out.append(verdict("ISO", ("fail" if confirmed else "pass") if reached else "na",
                       f"confirmed {confirmed}; dismissed candidates {dismissed}; Test command {test_command!r}"))

    out.append({"id": "markers", "method": "S", "verdict": "info",
                "evidence": json.dumps([{"item": m[0].index, "turn": m[0].turn, "marker": m[1], "args": m[2]} for m in markers]
                                       + [{"item": p[0].index, "turn": p[0].turn, "phase": p[1]} for p in phases], ensure_ascii=False)})
    return out


def main() -> int:
    run_dir = Path(sys.argv[1]).resolve()
    results = score(run_dir)
    (run_dir / "score_script.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in results:
        if r["verdict"] != "info":
            print(f"{r['id']:<10} {r['verdict']:<5} {r['evidence'][:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
