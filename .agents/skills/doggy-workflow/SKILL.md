---
name: doggy-workflow
description: Spec-first implementation and test workflow with implementer, test-implementer, and test-verifier subagents. Use before feature/fix level implementation or debugging. Not for typo fixes, renames, config or doc edits, or local bug fixes.
---

# Phases

This file holds what every phase needs. The phase command prints each phase's own rules when the phase begins, so they arrive when needed and can be printed again after a long session is compacted:

```sh
python3 .harness/bin/workflow_marker.py phase --phase brief
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase draft|approve|implement_test|verify|amend|step|close|resume
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase NAME --again
```

Run the command on its own as the first action of the phase, and read its whole output. Never redirect, pipe, or discard it: the output is the instructions, and a phase entered without them runs from memory. Follow what it prints as if it were written here.

When a phase's rules are no longer in view (after compaction, or in a later session), print them again with `--again`: that form records nothing and issues no run id. When a rule refers to a section that is not in view, find the phase that prints it in the table below and print that phase with `--again`. A phase leaves out what does not apply to the spec of the run (stepped-spec, fuzzing, or mutation-tool rules) and says what it left out; `--all` prints everything. If the command cannot print the rules, it names the files to read instead: `.harness/skills/doggy-workflow/phases.json` lists them for each phase, and they are in `.harness/skills/doggy-workflow/phases/`.

| phase | run it | it prints |
| --- | --- | --- |
| `brief` | first, before reading the repository; it issues the run id | Workflow item 1, Voice, Decision sweep, Rounds |
| `draft` | after the user has answered the rounds, before writing the spec | Workflow item 2, Required format, Verification model, Stepped specs (the cut, held decisions), Subagent model, Quiz (its rules, the completion questions) |
| `approve` | after the spec draft and its try-n-fail search, before the approval brief | Workflow item 2, Voice, Rounds (decision round, approval brief), Quiz (its rules) |
| `implement_test` | after approval and lifecycle start, before each dispatch of the two roles | Workflow items 3 and 4, Stepped specs (running a step), Subagent model |
| `verify` | after a passing Test command, before each verifier dispatch | Verification model, Workflow items 5, 6, and 8, Subagent model |
| `amend` | before every amendment or correction batch, with `--reason` | Workflow item 7 |
| `step` | in a stepped spec, before each step after the first, in the same or a later session | Stepped specs (running a step, held decisions), Voice, Rounds (decision round), Quiz (its rules, the completion questions, across sessions) |
| `close` | when the run meets the stop condition or has to stop | Workflow items 8 and 9, Quiz (its rules, the completion questions, the completion check and closing quiz, across sessions), Closing report, Voice, Stepped specs (ending a session) |
| `resume` | in a later session, when the user asks to resume an active spec | Workflow item 1, Stepped specs (resuming, running a step, the cut, held decisions), Quiz (across sessions), Voice |

`implement_test`, `verify`, and `amend` are also telemetry markers (see Telemetry): one command records the phase and prints its rules, so print their rules a second time with `--again`.

# Terms

Every phase uses these terms in this sense; their rules stay in the sections named.

- **Sweep**: the Decision sweep, run before each round to sort the task's decisions.
- **Significant**: meeting at least one significance criterion of Decision sweep: hard to reverse, load-bearing, different outcomes, answerable for.
- ***Your decision***: a decision the user makes: a significant one that no fact settles because its options trade one quality for another, or one the user listed as theirs in the understanding round.
- ***Decided for you***: a decision main settles: it has no reasonable alternative, follows a project convention, makes no observable difference, is settled by a citation, or trades qualities without being significant.
- **Engineer call**: a significant decision, whoever made it: every *Your decision*, and every significant *Decided for you*.
- **Fact question**: a question for an unknown fact behind a significant decision.
- **Assumption**: a sentence about the world, true or false whatever gets built, standing for an unknown behind a decision that is not significant, or for a recorded fact the work relies on.
- **Picks file**: `<run-id>-picks.md`, outside the repository (the session scratchpad when there is one, otherwise the system temporary directory). It holds main's pick for each *Your decision* and the expected answer to each new quiz question.
- **Brief item**: what the user approves through a brief: the understanding, an assumption or fact the user confirmed, an engineer call, the plain-words quality list, or the step cut.
- **Amendment**: a change to the approved spec (Identity and lifecycle rule 5). A **contract-only** amendment changes no brief item.
- **Correction batch**: the corrections queued together after a failing Test command or a verifier audit, carried out by Workflow item 7.

# Spec

A spec is the approved, versioned source of truth for one workflow run. Only main, the main agent, creates and amends it. Subagents work from the version they are assigned and never choose missing behavior.

## Identity and lifecycle

1. Active path: `agent-docs/specs/<16-hex-run-id>-<kebab-name>.md`.
2. Archived path: `agent-docs/spec-logs/<same-file-name>`.
3. `specs/` and `spec-logs/` are excluded from Index & Staleness Management. Never edit an archived spec.
4. Frontmatter fields: `version`, `run_id`, `status`, `base_commit`, `max_verifier_invocations`. Status is `draft`, `active`, `complete`, `limit`, or `aborted`.
5. An amendment increments `version` and adds a Version Log entry, prefixed `[intent-mismatch]` when an intent mismatch found after approval forced it. When it changes a brief item, re-brief before continuing: show current → proposed, why it must change, and its impact. Log a contract-only amendment (a technique, coverage-item naming, an obligation split) without interrupting the user.
6. `phase --phase brief` issues the run id before the understanding round (see Phases). Write the run id as a literal value wherever a command or a file name takes it. Before drafting, run the understanding round, then the decision round when a decision is the user's. Before dispatch, present the approval brief and obtain approval. Approval covers the linked spec version, including every default the user did not veto, and never a `facts.md` entry (see Facts). Pause on unanswered fact questions, user decisions, and conflicts.
7. Choose a default only by recording it in `# Assumptions and Defaults` before approval, and never for a *Your decision* or for an unknown behind a significant decision. Prefer general good practice unless the user or project states otherwise, and preserve, in this order, safety, security, compatibility, data, and existing observable behavior. Record each default with its evidence, uncertainty, and approval: `brief v<n> — approved`, `vetoed → <answer>`, `user answer`, `user decision (main: <own option>)`, or, for an entry already in the file, `facts.md: <first words of the entry>`. A default that is not an engineer call counts as stated to the user once it is recorded there and the approval brief points to the table. An optional quality characteristic may be excluded with a recorded reason.

# Memory

What a later session may rely on lives in three places, each with its own scope. Save nothing else from a run: briefs, quiz answers, and closing reports exist only in chat, and the only quiz content a later session reads is the spec's `# Completion Questions`. Later sessions read facts and decisions, not conversations.

| place | holds | written | read |
| --- | --- | --- | --- |
| `agent-docs/facts.md` | what the repository cannot show: the execution environment, the user's intent and plans, the world outside | only after the user approves the entry's exact text | whole, before the understanding round |
| `agent-docs/try-n-fail/` | approaches that failed after real work, and proposals the user rejected | after the user confirms a draft from the closing report | by search, at two moments only (see Try-n-fail search) |
| `# Session Memory` of a stepped spec | failed attempts, decisions, and unresolved questions of that one task | by main at the end of each session | by the next session of the same task |

Do not write down a mistake that keeps recurring. Each closing report states the session's mistakes to the user; a user who sees the same one in several reports corrects it through `facts.md` or the project instructions.

## Facts

`agent-docs/facts.md` follows principle 2 of the project's Documentation Guide: one bullet per fact, a sentence that is true or false whatever gets built, with `source:` and `re-check:`. In this workflow:

- Read the whole file before the understanding round. A fact bears on a decision only when it settles that decision's reversal condition; it does not shift an unrelated choice. Show each fact you rely on in the understanding round as an assumption with its date, so the user can correct it; facts about load and plans go out of date first.
- Turn a user's answer to a fact question, and any such fact that surfaces later (an environment quirk, an external system's behavior, an intent the user states in passing), into a proposed entry. Show its exact bullet under *Records to approve* in the message that follows the resolved approval reply or in the closing report, whichever comes first, or at once when the user asks for the entry. Write it only after the user approves that text.
- Ask for each entry on its own: the exact bullet, then a direct question naming `facts.md`, apart from the request for spec approval and from the quiz. Only a reply that approves that entry, by naming `facts.md` or the entry, is approval; a bare "approve", "ok", or "yes" approves only the spec or the work. An answer is not approval of the wording, and neither is approval of the spec, brief, or work, nor the user's own request to record a fact: show the text even when the user asked for the entry. When a reply does not mention the entry, leave it unwritten and ask once more; drop it when the second reply does not mention it either. The same rule covers changing or removing an entry. A pending entry does not block the work: until it is written, the spec cites the fact as `user answer`.
- A pull request that changes `facts.md` fails the harness facts check, which prints the added and removed lines, until a person adds the `facts-approved` label. Never add that label yourself or ask a tool to add it.
- Write no decisions, instructions, task state, failed attempts, or anything the code shows into it.

## Try-n-fail search

Do not read `agent-docs/try-n-fail/` while understanding the task or sweeping decisions: an old attempt read before an approach exists anchors the design on it. Search at two moments:

- **Before carrying out the approach**: once the spec draft fixes it, before the approval brief; in a stepped spec, again before each later step's dispatch, for that step's approach.
- **At the first failure**: the first failing Test command, blocked subagent, or verifier finding of the run, and of each step in a stepped spec, before choosing the correction; later, again only when a failure signature is new.

Search `index.md` for the Implementation paths, symbols, and nouns of the approach or failure signature, in English and in the user's language, and open only the records that match. Pass a matching attempt whose revisit condition does not hold to the implementer as an excluded approach. When a match contradicts the drafted approach, change the draft or show the match in the approval brief as an alternative already tried. A record states what was observed: re-check it against the current code before relying on it.

# Telemetry

Telemetry commands are best-effort: never inspect their result or let a failure change the workflow. The `phase` command is the exception: its output is the phase's rules (see Phases).

Each phase prints, under *Markers of this phase*, the marker commands that belong to it, with the run id filled in, and what their flags count. Copy a command as printed and fill in only its numbers and choices. Write every marker argument as a literal value: the telemetry hook reads the command text and does not expand shell variables, so a marker whose run id is a variable such as `$ID` is not recorded. Emit no markers for ordinary tool activity.

Three phase commands are markers themselves:

```sh
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase implement_test
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase verify
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase amend --reason intent_mismatch|brief_change|contract_change|correction
```

Emit `implement_test` before the parallel roles and `verify` before dispatching a verifier. Emit `amend` before every amendment or correction, with `--reason intent_mismatch` for an amendment forced by an intent mismatch found after approval, `brief_change` for another amendment that changes a brief item, `contract_change` for a contract-only amendment, and `correction` for a correction batch that does not change the spec.
