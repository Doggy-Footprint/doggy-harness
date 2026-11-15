---
name: doggy-workflow
description: Spec-first implementation and test workflow with implementer, test-implementer, and test-verifier subagents. Use before feature/fix level implementation or debugging. Not for typo fixes, renames, config or doc edits, or local bug fixes.
---

# Spec

A spec is the approved, versioned source of truth for one workflow run. The main agent alone creates and amends it. Subagents consume the assigned version and never choose missing behavior.

## Identity and lifecycle

1. Active path: `agent-docs/specs/<16-hex-run-id>-<kebab-name>.md`.
2. Archived path: `agent-docs/spec-logs/<same-file-name>`.
3. `specs/` and `spec-logs/` are excluded from Index & Staleness Management. An archived spec is never edited. Specs from before harness 0.51.0 may hold a `# Retrospective` section and lack `# Alternatives` and `# Open Questions`, and specs from before 0.33.0 may hold a `handoff` field; leave them as they are.
4. Frontmatter fields are `version`, `run_id`, `status`, `base_commit`, and `max_verifier_invocations`. Status is `draft`, `active`, `complete`, `limit`, or `aborted`.
5. Amendment increments `version` and adds a Version Log entry, prefixed `[intent-mismatch]` when an intent mismatch found after approval forced it. When it changes a brief item (understanding, an assumption or fact the user confirmed, an engineer call as Decision sweep defines it, the plain-words quality list, or the step cut), re-brief before continuing: show current → proposed, why it must change, and its impact. Log contract-only changes such as a technique, coverage-item naming, or an obligation split without interrupting the user.
6. Choose the run id before the understanding round. Before drafting, run the understanding round, then the decision round when a decision is the user's. Before dispatch, present the approval brief and obtain approval; approval covers the linked spec version, including every default the user did not veto. Pause on unanswered fact questions, user decisions, and conflicts.
7. Main chooses a default only by recording it in `# Assumptions and Defaults` before approval, and never for a *Your decision* item or for an unknown behind a significant decision. Prefer general good practice unless the user or project states otherwise, and preserve safety, security, compatibility, data, and existing observable behavior in that order. Record each choice, its evidence and uncertainty, with approval as `brief v<n> — approved`, `vetoed → <answer>`, `user answer`, `user decision (main: <own option>)`, or `facts.md: <first words of the entry>` for an entry already in the file. A default that is not an engineer call counts as stated to the user once it is recorded there and the approval brief points to the table. Optional quality characteristics may be excluded with a recorded reason.

## Required format

````
---
version: <positive integer>
run_id: <16 lowercase hexadecimal characters>
status: draft|active|complete|limit|aborted
base_commit: <full commit id at workflow start>
max_verifier_invocations: 2
---

# User Intent
| id | stakeholder | intention | observable goal |
| --- | --- | --- | --- |

# Scope
In scope: <behavior and product boundary>
Out of scope: <explicit exclusions>

# Paths
Implementation: <comma-separated repo paths>
Tests: <comma-separated repo paths>
Test command: <one shell command covering all automated functional and quality checks, including the project's lint gate when it has one; fails when a structure-based coverage target is missed>
Review evidence: <named procedure/output, or none — reason>
Fuzzing: <tool, harness, surface, oracle (crash / property / differential), seed, budget — or none — reason>
Mutation tool: <tool and command, sample cap and seed, survival threshold (default 40%) — or none>

# Signatures
<signature per line>

# Functional Requirements
| id | requirement | priority | source |
| --- | --- | --- | --- |

# Errors
<failure condition — observable signal, including non-exception failures — post-failure state>

# Cases
| id | level | input / state | expected result |
| --- | --- | --- | --- |

# Quality Applicability
| ISO/IEC 25010:2023 characteristic | applicable | rationale |
| --- | --- | --- |
| Functional suitability | yes / no | ... |
| Performance efficiency | yes / no | ... |
| Compatibility | yes / no | ... |
| Interaction capability | yes / no | ... |
| Reliability | yes / no | ... |
| Security | yes / no | ... |
| Maintainability | yes / no | ... |
| Flexibility | yes / no | ... |
| Safety | yes / no | ... |

# Quality Requirements
| id | characteristic / subcharacteristic | target and context | measure method / inputs / unit | threshold and direction | evidence: automated, review, mutation | source |
| --- | --- | --- | --- | --- | --- | --- |

# Verification Obligations
| id | parent requirement/Case ids | variant and target surface | test layer and selection policy | ISO/IEC/IEEE 29119-4 technique | coverage items | coverage target | observation and expected result | evidence procedure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

# Assumptions and Defaults
| id | decision | evidence and uncertainty | brief v<n> — approved / vetoed → <answer> / user answer / user decision (main: <own option>) / facts.md: <first words of the entry> |
| --- | --- | --- | --- |

# Alternatives
| decision id | option not taken | what it gains and what it costs | reversal condition: the state of the world in which it wins |
| --- | --- | --- | --- |

# Open Questions
| id | question | requirement, decision, or step it affects | what would settle it | open / settled v<n> — <answer> / deferred — <reason> |
| --- | --- | --- | --- | --- |

# Traceability
| requirement id | Case ids | obligation ids | evidence procedure |
| --- | --- | --- | --- |

# Workflow Control
| item | value |
| --- | --- |
| correction batches used | 0 |
| verifier invocations | 0 |
| open finding ids | none |

Audit state (one entry per obligation; retain prior decisions in the execution ledger):
| obligation id | spec version | evidence references and revision | accepted / open / invalidated / pending | rationale and mutation outcome | dependencies and reopening evidence |
| --- | --- | --- | --- | --- | --- |

Execution ledger (append attempts; preserve failed approaches):
| attempt | finding / failure signature | cause hypothesis | changed approach / new evidence | result / disposition |
| --- | --- | --- | --- | --- |

# Version Log
## v<n>
- <what changed and the evidence or decision that forced it>

# Steps
| id | outcome the user can observe when it is done | requirement ids | obligation ids | depends on | held decisions | pending / active / done <YYYY-MM-DD> | verifier invocations |
| --- | --- | --- | --- | --- | --- | --- | --- |

# Session Memory
## Failed Attempts & Reasons
| step | recorded: <YYYY-MM-DD>, <HEAD> | attempt | failure evidence | cause — verified / hypothesis | how to re-check |
| --- | --- | --- | --- | --- | --- |

## Decisions & Reasons & Alternatives
| step | recorded: <YYYY-MM-DD>, <HEAD> | decision | reason and evidence | alternative not taken | what would reopen it |
| --- | --- | --- | --- | --- | --- |

## Unresolved Questions & Uncertainties
| step | recorded: <YYYY-MM-DD>, <HEAD> | question or uncertainty | what is known, with evidence | what would settle it |
| --- | --- | --- | --- | --- |
````

`# Steps` and `# Session Memory` exist only in a stepped spec (see Stepped specs); every other spec ends at the Version Log.

Every intent, requirement, Case, quality requirement, obligation, assumption, and open question has a stable id. Each applicable quality characteristic has at least one quality requirement. Each quality requirement defines the measured property and context, method and input quantities, unit, threshold and pass direction, evidence procedure, and source. ISO/IEC 25023 supplies measure concepts and ISO/IEC/IEEE 29119-4 supplies test design techniques with their coverage measures; neither supplies project-specific pass thresholds or coverage targets. Main sets both as defaults in `# Assumptions and Defaults`.

`level` is `normal`, `boundary`, `error`, or `edge`; include every level or a `none — <reason>` row. Error rows name both signal and post-failure state. Implementation and Tests paths are disjoint. The implementer never reads Tests; test roles never read Implementation.

`# Alternatives` holds one row for each significant decision's option that a reasonable engineer could have picked, whoever decided. `# Open Questions` holds what approval left unknown and what the work turns up later; write `none` when there is nothing. Both are plan content: they change only by amendment. At completion every open question is `settled` or `deferred`.

# Memory

What a later session may rely on lives in three places, each with its own scope. Nothing else from a run is saved: briefs, quizzes, and closing reports exist only in chat, so later sessions read facts and decisions, not conversations.

| place | holds | written | read |
| --- | --- | --- | --- |
| `agent-docs/facts.md` | what the repository cannot show: the execution environment, the user's intent and plans, the world outside | only after the user approves the entry's exact text | whole, before the understanding round |
| `agent-docs/try-n-fail/` | approaches that failed after real work, and proposals the user rejected | after the user confirms a draft from the closing report | by search, at two moments only (see Try-n-fail search) |
| `# Session Memory` of a stepped spec | failed attempts, decisions, and unresolved questions of that one task | by main at the end of each session | by the next session of the same task |

A mistake that keeps recurring is not written down by the agent. Each closing report states the session's mistakes to the user; a user who sees the same one in several reports corrects it through `facts.md` or the project instructions.

## Facts

`agent-docs/facts.md` follows principle 2 of the project's Documentation Guide: one bullet per fact, written as a sentence that is true or false whatever gets built, with `source:` and `re-check:`. In this workflow:

- Read the whole file before the understanding round. A fact bears on a decision only when it settles that decision's reversal condition; a fact about one thing does not shift an unrelated choice. A fact you rely on appears in the understanding round as an assumption with its date, so the user can correct it; facts about load and plans go out of date first.
- A user's answer to a fact question, and any such fact that surfaces later (an environment quirk, an external system's behavior, an intent the user states in passing), becomes a proposed entry. Show the exact bullet under *Records to approve* in the approval brief or the closing report, whichever comes first, and write it only after the user approves that text. An answer is not approval of the wording. Until the entry is written, the spec cites the fact as `user answer`.
- It holds no decisions, instructions, task state, failed attempts, or anything the code shows.

## Try-n-fail search

Do not read `agent-docs/try-n-fail/` while understanding the task or sweeping decisions: an old attempt read before an approach exists anchors the design on it. Search at two moments:

- **Before carrying out the approach**: once the spec draft fixes it and before the approval brief; in a stepped spec, again before each later step's dispatch, for that step's approach.
- **At the first failure**: the first failing Test command, blocked subagent, or verifier finding of the run, and of each step in a stepped spec, before choosing the correction; again later only when a failure signature is new.

Search `index.md` for the Implementation paths, the symbols, and the nouns of the approach or failure signature, in English and in the user's language, and open only the records that match. A matching attempt whose revisit condition does not hold goes to the implementer as an excluded approach; one that contradicts the drafted approach changes the draft or appears in the approval brief as an alternative already tried. A record states what was observed; re-check it against the current code before relying on it.

# Brief

The brief is how the user approves intent, makes the engineering decisions that are theirs, and comes to understand what will be built; the spec is the contract for subagents. Briefs exist only in chat: never write them into the spec or any other file.

## Voice

Everything this workflow says to the user (the rounds, the approval brief, the quiz, the closing report) follows these rules. A summary that reads easily is approved without being understood; the aim is a user who could explain the result and defend its decisions without the brief in front of them.

- **Reader.** An engineer who owns the project and will answer for the result, and who has not read the code this task touches. Write for a developer with 4 years of experience and explain anything beyond that in a sentence.
- **Less project detail.** Describe behavior, structure, data and control flow, and consequences. Leave out file paths, function and variable names, spec ids, and table rows, unless the user must act on that exact name (a command they run, a flag they type, a setting they change). Leave out decisions that do not shape the result and that the user did not make, such as a convention followed, a library reused, a name, a test technique, a threshold: they stay in the spec. Link the spec path and version once for whoever wants them.
- **More engineering.** For each decision that shapes the result, say what was chosen, what it costs, what it rules out, and in which state of the world it would be the wrong choice. Describe the result as a thing that exists: what is there afterwards that was not before, how the parts connect, what happens on the main path and when something fails, and what the person or system using it observes.
- **Judge from what is in front of you.** Decide what counts as project detail from the current code and the spec alone. Do not keep a record of what the user knows about the project, and do not research or ask in order to find out.
- Full sentences, terms defined at first use, no label the user cannot resolve from the message itself.

## Decision sweep

Run the sweep before each round. It sorts decisions by what would settle them. The user holds facts the repository does not (load, environment, plans), and a decision made without them is a guess presented as a default.

**Context pass.** Before listing decisions, go through the dimensions once for the task as a whole: `load` (volume, peak, growth), `data` (size, shape, sensitivity), `concurrency` (parallel callers, processes, instances), `environment` (where and how it runs or is deployed, and who or what starts it), `consumers` (who calls or reads this and what they already depend on), `roadmap` (planned work this must not block), `failure` (what a failure costs and what loss is tolerable), `cost` (money, quota, latency budget). For each, note what a citation says about it for this task, or that it is unknown. Judge each dimension by everything the change sets off, not only by the code it edits: follow the records it creates or changes to the events they emit, the jobs those queue, the metered calls those jobs make, and the people or automations that react, until the chain ends or reaches something the repository cannot show (a configured automation, a plan's quota). New data reaching old machinery is where `consumers` and `cost` are most often decided. The chain also ends at an addition that existing callers never see unless they opt in (a new filter option, an optional field, an extra enum value nobody else matches on): it sets off nothing for them, so it raises no question about them. For an unknown dimension, picture the task at both ends of it (ten items or ten million; a laptop or a memory-limited container; a person at a terminal or a scheduled pipeline; one caller or a second one already planned) and add every decision that comes out differently at the two ends. Decisions nobody lists hide in the dimensions nobody looked at.

**Per decision.** For every decision the spec depends on, including those the context pass added:

1. Write the decision as a question, your leading option, one alternative a reasonable engineer could pick, and the **reversal condition**: the state of the world in which the alternative wins.
2. Place the reversal condition in the dimension it belongs to.
3. Settle the reversal condition with a citation: a repository `path:line`, an entry of `agent-docs/facts.md`, or a statement by the user. A condition you cannot cite is unknown. Do not settle it from what is typical for such projects.
4. Classify:
   - No reasonable alternative, an existing project convention, or no observable difference between the options → *Decided for you*.
   - Settled by a citation → *Decided for you*, with the citation.
   - Unknown, and a fact would settle it → *Fact question* when the decision is significant, a stated assumption otherwise.
   - No fact would settle it, because the options trade one quality for another → *Your decision* when it is significant, *Decided for you* otherwise.

A decision is **significant** when at least one holds:
- *hard to reverse*: persisted data, schemas or formats; interfaces others depend on (CLI flags, API fields, file formats); external side effects (sending, deleting, publishing); security boundaries; money;
- *load-bearing*: other code or later decisions build on it, such as a data model, module boundary, state ownership, concurrency or consistency model, new dependency, or failure policy;
- *different outcomes*: the options differ in what users see, operating cost, behavior at the expected load, or how it fails;
- *answerable for*: the user would have to explain the choice in a design review or after an incident.

An **engineer call** is a significant decision, whoever made it: every *Your decision*, and every *Decided for you* that meets a criterion above. Engineer calls are what the approval brief explains and the quiz asks about; the remaining *Decided for you* items stay in the spec.

Example, for the task "add CSV export of orders":
- "Run the export inside the request or as a background job?" Leading: inside the request. Alternative: background job. Reversal condition: an export can outlast the request timeout (`data`). The repository gives the timeout (`server/config.ts:12`, 30 s) but not how many orders one customer has, so the condition is unknown, and the choice is load-bearing → *Fact question*: "How many orders does the largest customer export at once? Up to tens of thousands it runs inside the request; beyond that it needs a background job and a way to deliver the file."
- "Which CSV library?" The project already uses one (`package.json:18`) → *Decided for you*, cited, and not an engineer call.
- "Timestamps in UTC or in the customer's time zone?" No fact settles it, users see the difference, and files already parsed by customers are hard to change → *Your decision*.

## Rounds

**1. Understanding round.** Before drafting, state "Here's what I understood": what the project is, where this task fits, what success looks like, and what this task will NOT do. Build it from every available source (project definition, README, docs, code, history, prior specs, `agent-docs/facts.md`, the conversation), not from any single required file. An exclusion is a decision too: one that drops a safeguard or cannot be added back later ("no archive before deletion", "existing rows are not migrated") goes through the sweep like any other decision instead of being listed under what the task will not do. Then list:
- *Assumptions about the world*: each unknown behind a decision that is not significant, and each recorded fact you rely on with its date. Write each as one sentence that is true or false whatever gets built ("assumed: one process, no concurrent writers"). The user corrects a wrong assumption faster than the decisions built on it. A sentence about what the software will do ("unsupported files are skipped") is a decision, not an assumption: state the fact it rests on instead ("assumed: a person watches the run and can retry a file"), and keep the decision for the approval brief. The same holds for an existing safeguard applied to new input ("the current filters also apply to the imported data"): it decides that the safeguard is enough, so state or ask what the new input contains instead. A decision confirmed under the name of an assumption is approved without being seen as one.
- *Fact questions*: each unknown behind a significant decision. Ask for the fact, not for the decision: name the fact, the decision it settles, and where each answer leads. Add no guess of the answer, because a guess anchors the reply. Do not move such an unknown to the assumptions to save a question: an assumption the user skims past decides a significant choice without them. There is no cap, since a fact costs the user a few words; ask nothing the repository or `agent-docs/facts.md` answers.
- *Not asked*: a single line, not a list, naming each dimension on which you ask nothing and assume nothing, with a few words of why the design is the same wherever the project stands on it ("Not asked: cost (no paid service or quota), concurrency (read-only lookup)"). That the repository is silent is not such a reason; silence is what makes a dimension unknown, and `roadmap` and `consumers` are rarely written down anywhere. Nor is it a reason that the code you edit does not change for that dimension: the reason must also hold for what the change sets off (see Context pass). The user knows where the line is wrong, and it is the only place a dimension you misjudged becomes visible.
- One invitation, with no examples: "If you already see decisions you want to make yourself, list them." Answering is optional. Naming candidates turns the invitation into a hint; the decision round names them after the user has had the chance to see them unaided.

The round holds these parts and nothing else: no decisions, chosen or pending, and no notes on what you searched or found missing.

Continue only after the user confirms or corrects the round. Propose a `facts.md` entry for each answered fact (see Facts).

**2. Decision round.** Re-run the sweep with the answers: a fact usually settles the decision it was asked for, which becomes *Decided for you* with the fact cited. Present each remaining *Your decision* as a neutral question, with the significance criteria it meets and the facts it rests on. Give no options, no trade-offs, and no recommendation. The user thinks first without a hint; that is how they keep their engineering judgment and a working model of the project, which reading a finished choice does not give. When the user asks, give the options with a concrete consequence of each, still without a recommendation. A decision the user listed in the understanding round is *Your decision* even if the sweep classified it otherwise. Before sending the round, write your own pick for each item, with one line of reason, to a file outside the repository (the session scratchpad when there is one, otherwise the system temporary directory) named `<run-id>-picks.md`, adding to it in later rounds and never revising an entry. A pick formed after reading the user's choice tends to match it, and the comparison in the approval brief then shows the user nothing. Skip the round when no *Your decision* remains.

Count *Your decision* items over the whole task: those already presented in earlier rounds plus the new ones, with each part the user chooses separately counted as its own item (a question with three independently chosen parts is three). When the count first exceeds 3, the task is too large to decide well in one sitting: before asking the new items, recommend splitting it and propose the cut, either into separate tasks with a spec each or, when the work has to stay one spec, into steps with the decisions no earlier step depends on held for their own step (see Stepped specs). Proceed with all of them only when the user declines.

**3. Approval brief.** After drafting the spec and searching try-n-fail, present, in this order:
- *What will exist*: the result as a thing, in the terms of Voice, and what it deliberately leaves out.
- *Your decisions*: the user's choice, your pick and reason as written in the picks file before the user answered, what differs, and what the choice costs and rules out. When they differ, ask what the user's choice rested on, and propose a `facts.md` entry when the answer is a fact.
- *Decided for you*: the engineer calls only. For each: the choice, what it trades away, the option not taken and the state of the world in which that option wins, and how to change it later. Close with one sentence saying that the remaining defaults (conventions followed, thresholds, coverage targets, test techniques, the installed role models) are recorded in the spec's `# Assumptions and Defaults` and that approval covers them.
- *Still open*: each open question, what will settle it, and what the work does until then.
- *Conflict*: a choice that contradicts what the user or project stated. Show both sides and ask.
- *New concept*: a decision that depends on knowledge the user may lack. First ask whether the user already knows the concept; ask fresh every run. Then give one sentence on what it is and why it matters here. For a *Decided for you* item add a concrete consequence of each option and the choice; for a *Your decision* item add neither.
- When the user answered the invitation: which decisions both lists share, which only the user named, and which only the sweep found.
- For a stepped spec: the steps, what the user can observe after each, and which decisions wait for which step.
- Quality expectations in plain words for applicable characteristics only (for example "must not crash on a broken log line"); mention a non-applicable one only when that may surprise the user. ISO terms stay in the spec.
- *Records to approve*: the exact text of each proposed `facts.md` entry.
- *Quiz*, then the request for approval (see Quiz).

## Quiz

Reading a brief costs the user so little that it leaves no working model of the result. The quiz makes the user produce that model, on the three things they must be able to answer for: the core trade-off, the engineer calls, and the final shape.

- Ask 2 to 4 questions under the heading *Quiz* at the end of the approval brief, and 1 to 3 at the end of each closing report. Cover the trade-off that most shapes the result, at least one engineer call, and the final shape.
- Each question asks the user to predict or apply, not to recall: what happens when a named situation occurs, what would have to change if a named fact turned out different, which condition would reverse a named decision. A question whose answer is a sentence of the brief above it is not a quiz question. Give no options, no hints, and no answers in the same message.
- Before sending, write the expected answer to each question in the picks file. An expectation formed after reading the user's answer bends toward it.
- When the answers arrive, compare each with the spec and the expected answer, and say in one line each which matched. For an answer that differs, find out which of three it is: a misunderstanding (explain that part again, starting from the user's answer, in other words than before); the user's intent, which the spec does not meet (change the spec, as a draft revision before approval and as an `[intent-mismatch]` amendment after it, and re-brief the changed part); or a fact the repository does not show (propose a `facts.md` entry).
- A quiz answer is never recorded and is never a decision or an instruction. Only an amendment the user approves changes the spec. The user's answers are written nowhere, and neither questions nor answers enter the spec or any file in the repository. The picks file holds only the expected answers, and a later session does not read it. Telemetry carries counts only.
- Ask for approval in the same message as the quiz. An approval that arrives together with an answer that differs is not yet approval: resolve the difference, then ask again.
- The user may skip the quiz by saying so. Main never skips or shortens it on its own, and no score is required to pass. When a reply approves without answering, ask once for the answers or an explicit skip; a second reply without answers counts as a skip.

## Closing report

Every session that worked on a spec ends with a closing report in chat, whether the run completed, hit the verifier limit, stopped nonterminally, or was aborted. It replaces a saved retrospective: the user reads it, and nothing in it is written to a file except the records the user approves. It follows Voice and holds, in this order:

- *What exists now*: the result as built, or the state the work stopped in, each way it differs from the approval brief with the reason, and each open question left deferred.
- *Calls made during the work*: each decision taken after approval that shapes the result (an amendment, a changed approach, a dropped or added safeguard), with what it costs and rules out.
- *What went wrong*: approaches that failed and why, signals that misled, and main's own mistakes with what each cost, small ones included. This is the user's only view of a mistake that repeats across sessions.
- *Records to approve*: the exact text of each proposed `facts.md` entry, and a draft of each try-n-fail record, taken from the execution ledger or from a proposal the user rejected in conversation (an attempt whose failure took real work to discover, or a concrete rejected proposal, that a later task could plausibly try again). Write only what the user approves.
- For a stepped spec: which steps are done, what the next session starts with, and the rows this session added to `# Session Memory`, in plain words.
- *Quiz* on the result as built (see Quiz). When an answer shows that a completed result is not what the user intended, say what would have to change and ask whether to start a follow-up task; an archived spec is not reopened. While the spec is still active, handle the answer as Quiz describes. Either way, the turn that handles the reply emits the `quiz` telemetry marker with `--quiz-of closing`, so a mismatch found at closing is counted like one found at approval.
- *Numbers*, last and in a few lines: spec path and version, verifier invocations, correction batches and their causes, mutation, fuzz, and mutation-tool outcomes, and anything still blocked.

# Stepped specs

A task that one session cannot finish runs as one spec cut into steps, each of which passes the whole verification structure on its own. Recommend the cut when at least one holds:

- *size*: after drafting, `# Verification Obligations` has 15 rows or more (the number is `step_split_obligations` in `.harness/config.json` when that key is set);
- *order dependence*: an open question can be settled only by building or running an earlier part;
- *outside wait*: the work has to wait for something outside the session, such as a deployment, an action by the user, or a long measurement;
- *too many decisions*: the decision round counted more than 3 *Your decision* items and the user wants the work kept in one spec;
- *a stopped session*: a session of a spec without steps ended with a nonterminal stop.

The first three are recommended in the approval brief. *Too many decisions* is proposed in outline in the decision round (which decisions can wait for which part) and fixed in the approval brief. *A stopped session* is proposed by the next session, before it continues, as an amendment with a re-brief; verifier invocations already used count against the first remaining step. The cut is a brief item: the user approves it, and changing it later is an amendment with a re-brief.

**Cutting.** Each step delivers an outcome the user can observe and owns its requirement and obligation ids; every id belongs to exactly one step, and an obligation that spans steps belongs to the last step that completes it. After each step the Test command passes and no behavior is left half-switched, so the work can be committed or stopped at any step boundary. Order steps by dependency, and put a step that settles an open question before the steps that depend on the answer.

**Held decisions.** A *Your decision* that no earlier step depends on may be held for its step. Until that step starts, the spec carries it as an open question naming the step, the step's row names it under `held decisions`, and the requirements that depend on it are not written. When the step starts, ask it in a decision round, then add the dependent requirements, Cases, and obligations to that step by an amendment the user approves through a re-brief that includes the picks comparison.

**Running a step.** Before each step after the first, give the user a short step brief in the terms of Voice: what this step adds to what already exists, and its held decisions. Search try-n-fail for the step's approach. Mark the step `active`, then run items 3 to 8 of the Workflow for its requirements and obligations only; dispatch instructions name the step and its ids. `max_verifier_invocations` bounds each step separately: count invocations in the step's `verifier invocations` cell and the run total in Workflow Control, and use the run total for telemetry `--round`. Obligations of earlier steps stay in the audit state as accepted and are reopened only through the change-impact rule of the verification model. When the stop condition holds for the step, mark it `done` with the date and go on to the next step, unless the user asks to stop or the session cannot continue (an outside wait, or too little context left to finish another step). A step that exhausts its verifier budget ends the run with status `limit`.

**Ending a session.** Ending before the last step is done, at a step boundary or mid-step, is a nonterminal stop: the spec stays `active` and Workflow item 9 applies. Before the closing report, append to `# Session Memory` what the next session would otherwise rediscover by repeating work or making a wrong move:

- *Failed Attempts & Reasons*: an approach that was implemented, run, or investigated and failed, and that a later session could plausibly try again, with its evidence and whether the cause is verified or a hypothesis. The execution ledger stays the working log of the verification loop; a row here is the part of it a new session needs, with the evidence and re-check the ledger lacks.
- *Decisions & Reasons & Alternatives*: a choice main made during the work that is neither an engineer call nor another brief item, why, and the option not taken. An engineer call goes into `# Assumptions and Defaults` and `# Alternatives` by amendment instead.
- *Unresolved Questions & Uncertainties*: what is not known or not confirmed about the state of the work (an unverified cause, a behavior seen once, a check not yet run), what is known so far, and what would settle it. A question that affects a requirement, an engineer call, or a step goes into `# Open Questions` by amendment instead.

Every row is objective and reproducible: an observation, evidence a reader can re-run or open (a command and its output, a `path:line`, a commit), and how to re-check it. No recommendations, preferences, or instructions; no row that only repeats what the code, git history, or another section of the spec shows. Rows are appended, never edited; a row that no longer holds gets a new row saying so. Write `none` in a section with nothing to add. These sections serve this task only: when it ends, they are archived with the spec, and what should outlive it goes through the closing report into `facts.md` or try-n-fail.

**Resuming.** The next session reads `# Steps` and `# Session Memory` first, compares each row's recorded commit with HEAD, re-checks the rows that touch code changed since, runs the Test command to confirm the finished steps still pass, and emits telemetry `start` again with the same run id and the current spec version, because `end handoff` closed the telemetry run. It then continues as Running a step describes. A row is an observation: the session re-checks and decides for itself.

# Verification model

Define a finite set of independently checkable obligations before dispatch. Each row identifies the required variant, observable target surface, test layer, selection policy, and one ISO/IEC/IEEE 29119-4 test design technique with its coverage items and approved coverage target. Coverage is exercised coverage items divided by declared coverage items. Distinguish test layer (unit, integration, end-to-end) from Case `level`. Define lifecycle boundaries such as same-process re-import versus restart. Resolve ambiguous selection or boundary terms before approval; never let a test role choose missing policy.

- Specification-based: equivalence partitioning, classification tree, boundary value analysis (2- or 3-value), syntax, combinatorial (each choice, base choice, pairwise, all combinations), decision table, cause-effect graphing, state transition, scenario, random, and metamorphic testing. Enumerate coverage items finitely as stable ids or an explicit list; listing targets and variants does not imply their Cartesian product. A target below 100% names the selected items and the rationale.
- Structure-based: statement, branch, decision, branch-condition, branch-condition combination, MC/DC, and data flow testing. The spec names the measuring tool and the Implementation scope; main measures coverage through the Test command and maps each shortfall to behavior. Unexercised code for undeclared behavior is a spec gap or implementation defect; for declared behavior it is a test defect. Test roles receive only that behavior and measured values, never Implementation locations.
- Experience-based (error guessing): coverage items are the guessed defects; the target is `none — experience-based`.

Derive obligations from every in-scope requirement, including errors and quality requirements. Select the techniques the behavior or approved risk policy requires; justify excluded techniques and dimensions. A finite map does not excuse a missing user requirement. Such omissions are spec challenges, not permission to expand test scope silently.

Evidence is sufficient when it observes the required behavior at the declared surface and layer, uses an independent expected result, distinguishes the specified failure from success, and meets the approved coverage target. A test name or filled map is not proof. Additional examples alone do not establish a gap: a blocking finding must identify a required obligation and a concrete violating behavior the current evidence fails to reject, or cite a precise conflict or omission in the approved requirements.

Prefer automated evidence. Review evidence needs a repeatable procedure, inputs, observation, expected result and named artifact. Mutation evidence supplements these checks. Main selects the 8–10 strongest distinct defect classes from the audit, or all if fewer, including on an initial pass with no findings, and records why they are strongest. A mutation counts only if it executes and the intended assertion detects it; setup failures and unrelated failures are inconclusive.

Main runs a declared fuzz harness for its full budget with the recorded seed. Each crash or oracle violation becomes a finding whose minimized reproducer reaches test roles as input and observed behavior only. Early stops, timeouts, and setup failures are inconclusive.

The mutation tool, when the spec declares one, complements the hand mutations and runs after them; with `Mutation tool: none` this step is skipped. Declare only installed tools, otherwise `none`; `harness.py install` and `update` offer to install them. It mutates only Implementation lines changed since `base_commit`, sampling with the recorded seed above the cap. Survival rate is survived over executed mutants. Above the threshold (default 40%, Stryker's low mark), skip triage and record one non-blocking advisory finding with the rate. Otherwise restore every file and send survivors in batches to `mutant-triager` with the spec path and each mutant's id, diff, file and line. Verdicts route as follows: `declared` is an obligation evidence gap, `undeclared` a spec challenge, and `insufficient context` main resolves itself. Main rechecks `equivalent` verdicts on obligation-tied code plus a random sample of the rest; one overturned verdict reopens every `equivalent` in that batch. Timeouts and tool failures are inconclusive.

Carry audit state between fresh verifiers. Acceptance is scoped to the spec version, evidence revision and dependencies, not a permanent exemption. Main marks affected entries invalidated after changes to requirements, tests, helpers, procedures or implementation behavior; record the impact and why other entries remain valid. Changed shared helpers can invalidate several obligations. A verifier checks this impact assessment against the Tests diff file and reopens acceptance only with new evidence of a defect, changed dependency or missed requirement. Never inherit acceptance blindly or restart scope derivation merely because the verifier is fresh.

# Subagent model

Installed agent definitions carry the repository's default model, chosen with `harness.py install|update --model sonnet|opus` (`mutant-triager` keeps its own), and their effort. Propose a different model for a role only with a task-specific reason, such as concurrency, a security boundary, or a cross-module change for `implementer`, or a large obligation map for `test-verifier`; list such a proposal under *Decided for you* in the approval brief, and pass the approved model as the Agent tool's model override for that role's dispatches. A model the user names overrides both.

# Telemetry

Telemetry commands are best-effort: never inspect their result or let failure change the workflow.

```sh
python3 .harness/bin/workflow_marker.py brief --run-id ID --stage understanding|decision|approval|quiz|closing --round N [--fact-questions N] [--user-decisions N] [--split none|proposed|accepted|declined] [--picks-differ N] [--quiz-questions N] [--quiz-of approval|closing] [--quiz-answered N] [--quiz-differ N]
python3 .harness/bin/spec_lifecycle.py start --spec PATH --run-id ID && python3 .harness/bin/workflow_marker.py start --run-id ID --spec NAME --spec-version N
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase implement_test
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase verify
python3 .harness/bin/workflow_marker.py phase --run-id ID --phase amend --reason intent_mismatch|brief_change|contract_change|correction
python3 .harness/bin/workflow_marker.py verifier --run-id ID --round N --result pass|retry|limit --findings N --seeds-run N --seeds-detected N
python3 .harness/bin/workflow_marker.py verification --run-id ID --fuzz-execs N --fuzz-violations N --mutants N --killed N --survived N --equivalent N --overturned N
python3 .harness/bin/workflow_marker.py end --run-id ID --status complete|limit|handoff|aborted
```

Emit `brief` in the same turn as each understanding round, decision round, and approval brief, with `--stage` naming it and `--round N` counting rounds of that stage from 1. `--fact-questions` counts the fact questions asked in that round; `--user-decisions` is the *Your decision* count over the whole task so far, as the cap counts it; `--split` is `proposed` in the round that proposes a split, `accepted` or `declined` in the next round after the user answers, and `none` otherwise; on the approval brief, `--picks-differ` counts the decisions where the user's choice differs from the picks file. A step cut recommended in the approval brief counts as a proposed split. Emit `brief` with stage `closing` in the same turn as each closing report. On an approval brief and on a closing report, `--quiz-questions` counts the quiz questions that message asks. Emit `brief` with stage `quiz` in the turn that handles the user's reply to a quiz, after an approval brief and after a closing report alike, counting quizzes of the run from 1: `--quiz-of` is `approval` or `closing`, naming the message that asked the quiz; `--quiz-answered` is how many questions the user answered (0 when the user skipped the quiz), and `--quiz-differ` is how many of those answers differed from the expected answers written beforehand. Emit `start` before the initial dispatch, and again when a later session resumes the run. Emit `implement_test` before the parallel roles. Emit `verify` before dispatching a verifier. Emit one `verifier` marker after every verifier result. Emit one `verification` marker after each fuzz and mutation-tool pass; `--equivalent` counts accepted `equivalent` verdicts and `--overturned` reversed ones. Emit `amend` before every amendment or correction, with `--reason intent_mismatch` for an amendment forced by an intent mismatch found after approval, `brief_change` for another amendment that changes a brief item, `contract_change` for a contract-only amendment, and `correction` for a correction batch that does not change the spec. Emit `end complete` after completion, `end limit` when the verifier budget is exhausted, `end handoff` for a nonterminal stop (the status token keeps its name), and `end aborted` after an approved recovery abort. Write every marker argument as a literal value: the telemetry hook reads the command text and does not expand shell variables, so a marker whose run id is a variable such as `$ID` is not recorded. Do not emit markers for ordinary tool activity.

# Workflow

1. **Recover or ground (main).** Read `agent-docs/facts.md`. Before creating a spec, inspect `specs/`. If an active spec exists, do not start another workflow. Resume it only when the user asks; otherwise compare `base_commit` to HEAD, summarize the work done and the drift, and ask the user whether to resume or abort it. Resume a stepped spec as Stepped specs describes. To abort, in this order: (1) restore any seed with `python3 .harness/bin/seed.py restore`; (2) run `python3 .harness/bin/spec_lifecycle.py abort --spec PATH`; (3) if it refuses because of other live sessions, ask the user whether any of them runs this workflow, and re-run with `--other-sessions-confirmed` only after the user confirms none does; (4) emit `python3 .harness/bin/workflow_marker.py end --run-id ID --status aborted`; (5) give the closing report. Read deciding code yourself; delegate only location discovery. For pre-0.10 specs, reconcile obligations and audit state with the verification model before dispatch, giving each obligation a technique, coverage items and target. Do not infer prior acceptance from a passing suite. Apply Identity and lifecycle rule 5 to changed verification policy, and preserve invocation counts and history.
2. **Understand, draft, and approve (main).** Run the understanding round and wait for the user's confirmation or correction, then the decision round when the sweep leaves a decision to the user. Derive functional requirements and all nine quality applicability decisions. Define measures, thresholds, 29119-4 techniques, coverage items and targets, evidence, and traceability with `max_verifier_invocations: 2`. Fill `# Alternatives` and `# Open Questions` from the sweep. Search try-n-fail for the drafted approach. Decide whether to recommend steps. Present the approval brief with its quiz, resolve the answers, and obtain approval; set status `active`, then run and check: `python3 .harness/bin/spec_lifecycle.py start --spec PATH --run-id ID`. Emit telemetry start only after lifecycle start succeeds.
3. **Implement + test (parallel).** Emit `implement_test`; dispatch both roles on the same spec version without sharing outputs. Instructions are task-specific and complete:
   - implementer: path/version, implementation direction, quality constraints, risks, allowed non-Test checks, and excluded approaches, including those a try-n-fail record rules out;
   - test-implementer: path/version, conventions, risk model, 29119-4 techniques and coverage items, independent oracle, automated and review evidence, test level, allowed load checks, and excluded approaches. Allowed load checks are only collecting, listing, or type-checking Tests paths; never instruct it to execute tests, the Test command, or Implementation code.
4. **Reconcile (main).** Collect both reports using bounded waits. If a subagent stalls, interrupt and diagnose before retrying. Resolve challenges with spec/code evidence; amend or reject each with a reason. Reopen prior spec decisions only with new evidence, and leave dependent work blocked until the user resolves any required decision. When unblocked, run the exact Test command with a finite timeout suited to its expected runtime. Classify failures as implementation defect, test defect, evidence defect, or spec gap and queue one correction batch. A timeout is a failure to investigate, never a pass or a reason for an unchanged automatic retry.
5. **Verify (fresh test-verifier).** The verifier has no shell, so after a passing Test command main writes the Tests diff file: `git diff <base_commit> -- <Tests paths>` followed by the list from `git ls-files --others --exclude-standard -- <Tests paths>` as new files, saved outside the working tree (the session scratchpad when there is one) so it is neither committed nor counted as a project change. Rewrite it for every dispatch. Dispatch a fresh verifier with the spec path/version, complete coverage/evidence map, audit state, change-impact assessment, finding ledger, and the Tests diff file's path. Check every obligation has a current disposition; audit pending and invalidated evidence and assess any new challenge to retained acceptance. Before dispatch, check and persist the incremented `verifier invocations` count in Workflow Control. At most two invocations are allowed per run, or per step in a stepped spec, including the initial audit and failed, interrupted, or incomplete audits. Resume and spec amendments preserve the count; replacement runs must not evade the limit. Use the invocation count for telemetry `--round`. Apply the stop condition if the required audit would exceed the budget.
6. **Triage and mutate (main).** Resolve findings with stable ids, spec versions, affected obligations/variants, evidence, dispositions, and mutation outcomes. Classify each item as an obligation evidence gap, a spec challenge, or advisory. A spec challenge cites the conflicting or missing requirement and routes to an amendment/user decision; optional strengthening is advisory and does not block completion. Do not downgrade an actual requirement gap to advisory. Update audit state with evidence-backed dispositions. Exercise the selected strongest defect classes, prioritizing blocking findings, one mutation at a time, without exposing implementation or injected diffs to test roles:
   1. `python3 .harness/bin/seed.py backup <every edited file>`.
   2. Inject the violating behavior and run Test command with a finite timeout suited to its expected runtime.
   3. `python3 .harness/bin/seed.py restore` before continuing or handing off; stop if restore fails and record the outstanding backup.
   4. Run declared fuzzing, then the declared mutation tool (if any), backing up and restoring every file it may edit.
   5. Triage survivors as above, record fuzz and survivor outcomes in the ledger, and emit `verification`.

   Green confirms a gap only when the mutation executed; failure rejects a finding only when the intended assertion detects the violation. For an inconclusive result, retry with a changed probe that distinguishes execution from the observed failure, or mark the finding blocked and stop nonterminally if none is available. Triage every finding before redispatch or closure, including the final audit: evidence-backed rejections need no further audit when tests, evidence procedures, and approved expectations are unchanged.
7. **Correct as one batch (main).** Before the first correction batch, and again when a failure signature is new, search try-n-fail (see Try-n-fail search). Ordinary implementation, test, evidence, and spec corrections have no count limit. For each retry, record the failure signature, cause hypothesis, changed approach or new evidence, and observed result in the execution ledger. Continue only with a concrete diagnostic or justified correction; never repeat a failed approach without new evidence. When a resolved finding recurs or edits oscillate, compare prior attempts and re-evaluate the cause before editing again. Apply the stop condition when no next step is available or the correction requires an audit beyond the budget.

   Emit `amend` and increment the correction count for history. Redispatch complete replacement instructions, continuing existing agents where possible. Implementation defects receive ids and observable behavior, never test code. Test/evidence defects receive rules, variants, and sanitized evidence, never implementation diffs. Correct the cause across all declared obligations sharing the defective pattern or helper; report the full affected set, including checked siblings needing no change. Do not add undeclared combinations during this sweep. Update evidence references and invalidate affected acceptance before redispatch. A spec gap increments spec version after required approval and redispatches both roles. Reconcile, rerun the restored Test command, repeat confirming mutations, then return to Verify for a fresh audit.
8. **Stop condition.** Complete only when every required functional and quality obligation passes at its approved coverage target, review artifacts exist, the verifier audit is complete with no open blocking finding, every obligation has current accepted evidence, the selected confirming mutations fail for the intended assertion, declared fuzzing completed with no open violation, every triaged survivor of a declared mutation tool has a disposition, and every open question is settled or deferred. In a stepped spec this condition is checked for the active step, and the run completes when the last step is done. Advisory suggestions may remain; unresolved spec challenges may not. If further verification is required after two invocations, stop with status `limit` before making corrections that require that audit. For ordinary corrections blocked on a user decision or external change, finish independent work and request what is missing, keeping the spec active for a nonterminal stop. Stop the same way when no new discriminating check or justified correction is available.
9. **Close or stop (main).** In a stepped spec, first write the session's `# Session Memory` rows. For success, set status `complete`, archive with `python3 .harness/bin/spec_lifecycle.py archive --spec PATH --status complete`, then emit end complete. For verifier-budget exhaustion, set status `limit`, archive with `--status limit`, then emit end limit. For a nonterminal stop, keep the spec `active` and emit end handoff without archiving. Then give the closing report with its quiz, and write the `facts.md` entries and try-n-fail records the user approves.
