---
name: doggy-workflow
description: Spec-first implementation and test workflow with implementer, test-implementer, and test-verifier subagents. Use before feature/fix level implementation or debugging. Not for typo fixes, renames, config or doc edits, or local bug fixes.
---

# Phases

This file holds only what every stretch of the workflow needs: how a run moves through its phases, the spec's identity and lifecycle, where memory lives, and the telemetry markers. The rules of each phase are not here. The phase command prints them when the phase begins, so that they arrive when they are needed and can be printed again after a long session is compacted:

```sh
python3 .harness/bin/workflow_marker.py phase --phase brief
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase draft|approve|implement_test|verify|amend|step|close|resume
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase NAME --again
```

Run the command on its own as the first action of the phase and read its whole output. Never redirect, pipe, or discard it: the output is the instructions, and a phase entered without them is run from memory. Follow what it prints as if it were written here. The sections it prints (Voice, Decision sweep, Rounds, Quiz, Closing report, Required format, Stepped specs, Verification model, Subagent model, and the numbered Workflow items) are the ones the rest of this workflow refers to by name.

When a phase's rules are no longer in view, after compaction or in a later session, print them again with `--again`: that form records nothing and issues no run id. When a rule refers to a section that is not in view, find the phase that prints it in the table below and print that phase with `--again`. A phase leaves out what does not apply to the spec of the run (the stepped-spec rules for a spec without steps, the fuzzing and mutation-tool rules when the spec declares none) and says what it left out; `--all` prints everything. If the command cannot print the rules, it names the files to read instead: `.harness/skills/doggy-workflow/phases.json` lists them for each phase, and they are in `.harness/skills/doggy-workflow/phases/`.

| phase | run it | it prints | Workflow items |
| --- | --- | --- | --- |
| `brief` | first, before reading the repository; it issues the run id | recover or ground, Voice, Decision sweep, Rounds | 1 |
| `draft` | after the user has answered the rounds, before writing the spec | understand, draft, and approve; Required format (the spec template is a file to copy); Verification model; Stepped specs (the cut, held decisions); Subagent model; Quiz (its rules, the completion questions) | 2 |
| `approve` | after the spec draft and its try-n-fail search, before the approval brief | understand, draft, and approve; Voice; Rounds (decision round, approval brief); Quiz (its rules) | 2 |
| `implement_test` | after approval and lifecycle start, before each dispatch of the two roles | implement + test, reconcile, Stepped specs (running a step), Subagent model | 3, 4 |
| `verify` | after a passing Test command, before each verifier dispatch | Verification model, verify, triage and mutate, the stop condition | 5, 6, 8 |
| `amend` | before every amendment or correction batch, with `--reason` | correct as one batch | 7 |
| `step` | in a stepped spec, before each step after the first, in the same or a later session | Stepped specs (running a step, held decisions), Voice, Rounds (decision round), Quiz (its rules, the completion questions, across sessions) | 3 to 8 |
| `close` | when the run meets the stop condition or has to stop | the stop condition, close or stop, Quiz (its rules, the completion questions, the completion check and closing quiz, across sessions), Closing report, Voice, Stepped specs (ending a session) | 8, 9 |
| `resume` | in a later session, when the user asks to resume an active spec | recover or ground, Stepped specs (resuming, running a step, the cut, held decisions), Quiz (across sessions), Voice | 1 |

`implement_test`, `verify`, and `amend` are also telemetry markers (see Telemetry): one command both records the phase and prints its rules, which is why a second look at their rules uses `--again`.

# Spec

A spec is the approved, versioned source of truth for one workflow run. The main agent alone creates and amends it. Subagents consume the assigned version and never choose missing behavior.

## Identity and lifecycle

1. Active path: `agent-docs/specs/<16-hex-run-id>-<kebab-name>.md`.
2. Archived path: `agent-docs/spec-logs/<same-file-name>`.
3. `specs/` and `spec-logs/` are excluded from Index & Staleness Management. An archived spec is never edited.
4. Frontmatter fields are `version`, `run_id`, `status`, `base_commit`, and `max_verifier_invocations`. Status is `draft`, `active`, `complete`, `limit`, or `aborted`.
5. Amendment increments `version` and adds a Version Log entry, prefixed `[intent-mismatch]` when an intent mismatch found after approval forced it. When it changes a brief item (understanding, an assumption or fact the user confirmed, an engineer call as Decision sweep defines it, the plain-words quality list, or the step cut), re-brief before continuing: show current → proposed, why it must change, and its impact. Log contract-only changes such as a technique, coverage-item naming, or an obligation split without interrupting the user.
6. The run id is issued by `phase --phase brief` before the understanding round (see Phases); write it as a literal value wherever a command or a file name takes it. Before drafting, run the understanding round, then the decision round when a decision is the user's. Before dispatch, present the approval brief and obtain approval; approval covers the linked spec version, including every default the user did not veto, and never a `facts.md` entry (see Facts). Pause on unanswered fact questions, user decisions, and conflicts.
7. Main chooses a default only by recording it in `# Assumptions and Defaults` before approval, and never for a *Your decision* item or for an unknown behind a significant decision. Prefer general good practice unless the user or project states otherwise, and preserve safety, security, compatibility, data, and existing observable behavior in that order. Record each choice, its evidence and uncertainty, with approval as `brief v<n> — approved`, `vetoed → <answer>`, `user answer`, `user decision (main: <own option>)`, or `facts.md: <first words of the entry>` for an entry already in the file. A default that is not an engineer call counts as stated to the user once it is recorded there and the approval brief points to the table. Optional quality characteristics may be excluded with a recorded reason.

# Memory

What a later session may rely on lives in three places, each with its own scope. Nothing else from a run is saved: briefs, quiz answers, and closing reports exist only in chat, and the only quiz content in a file is the spec's `# Completion Questions`, so later sessions read facts and decisions, not conversations.

| place | holds | written | read |
| --- | --- | --- | --- |
| `agent-docs/facts.md` | what the repository cannot show: the execution environment, the user's intent and plans, the world outside | only after the user approves the entry's exact text | whole, before the understanding round |
| `agent-docs/try-n-fail/` | approaches that failed after real work, and proposals the user rejected | after the user confirms a draft from the closing report | by search, at two moments only (see Try-n-fail search) |
| `# Session Memory` of a stepped spec | failed attempts, decisions, and unresolved questions of that one task | by main at the end of each session | by the next session of the same task |

A mistake that keeps recurring is not written down by the agent. Each closing report states the session's mistakes to the user; a user who sees the same one in several reports corrects it through `facts.md` or the project instructions.

## Facts

`agent-docs/facts.md` follows principle 2 of the project's Documentation Guide: one bullet per fact, written as a sentence that is true or false whatever gets built, with `source:` and `re-check:`. In this workflow:

- Read the whole file before the understanding round. A fact bears on a decision only when it settles that decision's reversal condition; a fact about one thing does not shift an unrelated choice. A fact you rely on appears in the understanding round as an assumption with its date, so the user can correct it; facts about load and plans go out of date first.
- A user's answer to a fact question, and any such fact that surfaces later (an environment quirk, an external system's behavior, an intent the user states in passing), becomes a proposed entry. Show the exact bullet under *Records to approve* in the approval brief or the closing report, whichever comes first, or at once when the user asks for the entry, and write it only after the user approves that text.
- Ask for each entry on its own: the exact bullet, then a direct question naming `facts.md`, apart from the request for spec approval and from the quiz. Only a reply that approves that entry, by naming `facts.md` or the entry, is approval; a bare "approve", "ok", or "yes" approves the spec or the work only. An answer is not approval of the wording, and neither is approval of the spec, of the brief, or of the work, nor the user's own request to record a fact: show the text even when the user asked for the entry. A reply that does not mention the entry leaves it unwritten; ask once more, and drop it unwritten when the second reply does not mention it either. Changing or removing an entry follows the same rule. A pending entry does not block the work: until it is written, the spec cites the fact as `user answer`.
- A pull request that changes `facts.md` fails the harness facts check, which prints the added and removed lines, until a person adds the `facts-approved` label. Never add, or ask a tool to add, that label yourself.
- It holds no decisions, instructions, task state, failed attempts, or anything the code shows.

## Try-n-fail search

Do not read `agent-docs/try-n-fail/` while understanding the task or sweeping decisions: an old attempt read before an approach exists anchors the design on it. Search at two moments:

- **Before carrying out the approach**: once the spec draft fixes it and before the approval brief; in a stepped spec, again before each later step's dispatch, for that step's approach.
- **At the first failure**: the first failing Test command, blocked subagent, or verifier finding of the run, and of each step in a stepped spec, before choosing the correction; again later only when a failure signature is new.

Search `index.md` for the Implementation paths, the symbols, and the nouns of the approach or failure signature, in English and in the user's language, and open only the records that match. A matching attempt whose revisit condition does not hold goes to the implementer as an excluded approach; one that contradicts the drafted approach changes the draft or appears in the approval brief as an alternative already tried. A record states what was observed; re-check it against the current code before relying on it.

# Telemetry

Telemetry commands are best-effort: never inspect their result or let failure change the workflow. The `phase` command is the exception: its output is the phase's rules (see Phases).

Each phase prints, under *Markers of this phase*, the marker commands that belong to it, with the run id filled in, and what their flags count. Copy a command as printed and fill in only its numbers and choices. Write every marker argument as a literal value: the telemetry hook reads the command text and does not expand shell variables, so a marker whose run id is a variable such as `$ID` is not recorded. Do not emit markers for ordinary tool activity.

Three phase commands are markers themselves:

```sh
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase implement_test
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase verify
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase amend --reason intent_mismatch|brief_change|contract_change|correction
```

Emit `implement_test` before the parallel roles. Emit `verify` before dispatching a verifier. Emit `amend` before every amendment or correction, with `--reason intent_mismatch` for an amendment forced by an intent mismatch found after approval, `brief_change` for another amendment that changes a brief item, `contract_change` for a contract-only amendment, and `correction` for a correction batch that does not change the spec.
