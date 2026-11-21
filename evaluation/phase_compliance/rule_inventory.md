# doggy-workflow rule inventory (harness 0.55.0)

Source files: `harness/skills/doggy-workflow/` — `SKILL.md`, `phases/*.md`, `markers.json` (`rules`), `phases.json`, `spec-template.md` (normative sentences only).

Column notes:
- `source`: `SKILL.md:<line>`, `<phase file>:<line>` (files under `phases/`, one paragraph per line), `markers.json:<line>`, `spec-template.md:<line>`.
- `phases`: phases whose printed output contains the rule, computed from `phases.json`; `[cond]` = printed only when that `when` condition holds; `skill` = `SKILL.md`, in context from skill load (no phase prints it). Marker rules use `markers.json` `phases`.
- `observable_by`: H = an existing hook/lifecycle/telemetry check enforces or records it (see footnotes); S = deterministic script over session JSONL + repository files; J = LLM judge over transcript text; G = planted scenario ground truth or simulated-user probe; U = not observable. Two letters = both needed; the first is primary.
- `rubric_draft_item`: item id in the draft rubric (`rubric.md`), `new` = no draft item covers it, `-` = U or definitional.

| rule_id | source | actor | when | rule | phases | observable_by | rubric_draft_item |
| --- | --- | --- | --- | --- | --- | --- | --- |
| skill.phases.01 | SKILL.md:16 | main | entering any phase | Run the phase command on its own as the first action of the phase. | skill | S | B1, R1, A1; new for step/close/resume |
| skill.phases.02 | SKILL.md:16 | main | phase command ran | Read the whole phase output. | skill | U | - |
| skill.phases.03 | SKILL.md:16 | main | running a phase command | Never redirect, pipe, or discard the phase command output. | skill | S | B1 (brief only); new for other phases |
| skill.phases.04 | SKILL.md:16 | main | always | Follow the printed rules as if they were written in SKILL.md. | skill | U | - |
| skill.phases.05 | SKILL.md:18 | main | phase rules no longer in view (compaction, later session) | Print the phase rules again with `--again` before continuing the phase. | skill | S | new |
| skill.phases.06 | SKILL.md:18 | definition | - | `--again` records nothing and issues no run id. | skill | H[h7] | - |
| skill.phases.07 | SKILL.md:18 | main | a rule refers to a section not in view | Find the phase that prints it in the table and print that phase with `--again`. | skill | U | - |
| skill.phases.08 | SKILL.md:18 | definition | - | A phase leaves out non-applicable parts and says so; `--all` prints everything. | skill | H[h7] | - |
| skill.phases.09 | SKILL.md:18 | main | phase command cannot print rules | Read the files the command names (`phases.json`, `phases/`). | skill | S | new |
| skill.phases.10 | SKILL.md:22 | main | task start | Run `brief` first, before reading the repository; it issues the run id. | skill | S | B1 |
| skill.phases.11 | SKILL.md:23 | main | rounds answered | Run `draft` after the user has answered the rounds and before writing the spec. | skill | S | R1, B12 |
| skill.phases.12 | SKILL.md:24 | main | spec drafted | Run `approve` after the spec draft and its try-n-fail search, before the approval brief. | skill | S | A1, R9 |
| skill.phases.13 | SKILL.md:25 | main | approval and lifecycle start done | Run `implement_test` before each dispatch of the two roles (including redispatch). | skill | H[h7] S | I1 |
| skill.phases.14 | SKILL.md:26 | main | Test command passed | Run `verify` after a passing Test command, before each verifier dispatch. | skill | H[h7] S | E1 |
| skill.phases.15 | SKILL.md:27 | main | amendment or correction batch | Run `amend` with `--reason` before every amendment or correction batch. | skill | H[h7] | C1 |
| skill.phases.16 | SKILL.md:28 | main | stepped spec, each step after the first | Run `step` before each step after the first, in the same or a later session. | skill | S | P1 |
| skill.phases.17 | SKILL.md:29 | main | stop condition met or run has to stop | Run `close`. | skill | S | new |
| skill.phases.18 | SKILL.md:30 | main | later session, user asks to resume | Run `resume`. | skill | S | P4 |
| skill.phases.19 | SKILL.md:32 | main | re-reading rules of implement_test/verify/amend | Use `--again` so the marker is not recorded twice. | skill | S | new |
| skill.spec.01 | SKILL.md:36 | main | always | Only main creates and amends the spec. | skill | S | new |
| skill.spec.02 | SKILL.md:36 | implementer, test-implementer, test-verifier | always | Subagents consume the assigned spec version and never choose missing behavior. | skill | J | new |
| skill.lifecycle.01 | SKILL.md:40 | definition | - | Active spec path is `agent-docs/specs/<16-hex-run-id>-<kebab-name>.md`. | skill | H[h1][h13] | - |
| skill.lifecycle.02 | SKILL.md:41 | definition | - | Archived path is `agent-docs/spec-logs/<same-file-name>`. | skill | H[h3] | - |
| skill.lifecycle.03 | SKILL.md:42 | main | spec archived | Never edit an archived spec. | skill | S | new |
| skill.lifecycle.04 | SKILL.md:43 | definition | - | Frontmatter fields and allowed status values. | skill | H[h1] | - |
| skill.lifecycle.05 | SKILL.md:44 | main | amendment | Increment `version` and add a Version Log entry. | skill | S | new |
| skill.lifecycle.06 | SKILL.md:44 | main | amendment forced by an intent mismatch found after approval | Prefix the Version Log entry with `[intent-mismatch]`. | skill | S J | C5 |
| skill.lifecycle.07 | SKILL.md:44 | main | amendment changes a brief item | Re-brief before continuing: current → proposed, why it must change, its impact. | skill | J G | C5 |
| skill.lifecycle.08 | SKILL.md:44 | definition | - | Brief items: understanding, a user-confirmed assumption or fact, an engineer call, the plain-words quality list, the step cut. | skill | - | - |
| skill.lifecycle.09 | SKILL.md:44 | main | contract-only amendment | Log it without interrupting the user. | skill | J | new |
| skill.lifecycle.10 | SKILL.md:45 | main | a command or file name takes the run id | Write the run id as a literal value. | skill | S | M2 (markers only) |
| skill.lifecycle.11 | SKILL.md:45 | main | before drafting | Run the understanding round, then the decision round when a decision is the user's. | skill | S | B12 |
| skill.lifecycle.12 | SKILL.md:45 | main | before dispatch | Present the approval brief and obtain approval. | skill | S J | A12 |
| skill.lifecycle.13 | SKILL.md:45 | definition | - | Approval covers the linked spec version and every unvetoed default, never a `facts.md` entry. | skill | - | F1 |
| skill.lifecycle.14 | SKILL.md:45 | main | unanswered fact question, user decision, or conflict | Pause; do not proceed past it. | skill | S J | new |
| skill.lifecycle.15 | SKILL.md:46 | main | choosing a default | Choose a default only by recording it in `# Assumptions and Defaults` before approval. | skill | S J | R3 |
| skill.lifecycle.16 | SKILL.md:46 | main | *Your decision* item or unknown behind a significant decision | Never choose a default for it. | skill | G | R3, G-B1 |
| skill.lifecycle.17 | SKILL.md:46 | main | choosing a default | Prefer general good practice unless stated otherwise; preserve safety, security, compatibility, data, observable behavior in that order. | skill | J | new |
| skill.lifecycle.18 | SKILL.md:46 | main | recording a default | Record choice, evidence, uncertainty, and approval with one of the fixed labels. | skill | S | R3 |
| skill.lifecycle.19 | SKILL.md:46 | definition | - | A non-engineer-call default counts as stated once recorded and the approval brief points to the table. | skill | - | A3 |
| skill.lifecycle.20 | SKILL.md:46 | main | optional quality characteristic excluded | Record the reason. | skill | S | R5 |
| skill.memory.01 | SKILL.md:50 | main | always | Save nothing from a run beyond the three memory places; briefs, quiz answers, closing reports exist only in chat. | skill | S | new |
| skill.memory.02 | SKILL.md:50 | main | always | The only quiz content in a file is the spec's `# Completion Questions`. | skill | S | new |
| skill.memory.03 | SKILL.md:54 | main | writing `facts.md` | Write only after the user approves the entry's exact text. | skill | S J H[h9] | F1 |
| skill.memory.04 | SKILL.md:54, SKILL.md:64 | main | before the understanding round | Read the whole `facts.md`. | skill | S | B2 |
| skill.memory.05 | SKILL.md:55 | main | writing try-n-fail | Write only after the user confirms a draft from the closing report. | skill | S J | new |
| skill.memory.06 | SKILL.md:55 | main | reading try-n-fail | Read by search, at the two moments only. | skill | S | B3, R9, C2 |
| skill.memory.07 | SKILL.md:56 | main | stepped spec, end of each session | Write `# Session Memory`. | skill | S | P3 |
| skill.memory.08 | SKILL.md:56 | main | next session of the same task | Read `# Session Memory`. | skill | S | P4 |
| skill.memory.09 | SKILL.md:58 | main | a mistake recurs | Do not write it down; state it in the closing report instead. | skill | S J | new |
| skill.memory.10 | SKILL.md:58 | user-facing message | each closing report | State the session's mistakes. | skill | J | X3, X4 |
| skill.facts.01 | SKILL.md:62 | main | writing a fact entry | One bullet per fact, a sentence true or false whatever gets built, with `source:` and `re-check:`. | skill | S J | new |
| skill.facts.02 | SKILL.md:64 | main | using a fact | A fact bears on a decision only when it settles that decision's reversal condition. | skill | J G | new |
| skill.facts.03 | SKILL.md:64 | user-facing message | relying on a fact | Show it in the understanding round as an assumption with its date. | skill | J | B7 |
| skill.facts.04 | SKILL.md:65 | main | fact answer or fact surfacing later | Turn it into a proposed entry. | skill | G | new |
| skill.facts.05 | SKILL.md:65 | user-facing message | proposed entry exists | Show the exact bullet under *Records to approve* in the approval brief or closing report, whichever comes first, or at once when the user asks. | skill | S J | A11, F2 |
| skill.facts.06 | SKILL.md:66 | user-facing message | asking for an entry | Ask for each entry on its own: exact bullet, then a direct question naming `facts.md`, apart from spec approval and the quiz. | skill | J | F2 |
| skill.facts.07 | SKILL.md:66 | main | reply arrives | Treat only a reply naming `facts.md` or the entry as approval; a bare "approve/ok/yes" approves only the spec or work. | skill | G | F1 |
| skill.facts.08 | SKILL.md:66 | main | user asked to record a fact, or answered it | Still show the text and ask; neither the answer nor spec/brief/work approval approves the wording. | skill | G J | F1, F2 |
| skill.facts.09 | SKILL.md:66 | main | reply does not mention the entry | Leave it unwritten, ask once more, drop it if the second reply does not mention it. | skill | G | new |
| skill.facts.10 | SKILL.md:66 | main | changing or removing an entry | Same approval rule. | skill | S J | F1 |
| skill.facts.11 | SKILL.md:66 | main | entry pending | Do not block the work; cite the fact as `user answer` in the spec. | skill | S | new |
| skill.facts.12 | SKILL.md:67 | definition | - | A PR changing `facts.md` fails the facts check until a person adds `facts-approved`. | skill | H[h12] | - |
| skill.facts.13 | SKILL.md:67 | main | always | Never add, or ask a tool to add, the `facts-approved` label. | skill | S | new |
| skill.facts.14 | SKILL.md:68 | main | writing `facts.md` | No decisions, instructions, task state, failed attempts, or code-derivable content. | skill | J | new |
| skill.tnf.01 | SKILL.md:72 | main | understanding the task or sweeping decisions | Do not read `agent-docs/try-n-fail/`. | skill | S | B3 |
| skill.tnf.02 | SKILL.md:74 | main | spec draft fixes the approach | Search try-n-fail before the approval brief. | skill | S | R9 |
| skill.tnf.03 | SKILL.md:74 | main | stepped spec, each later step | Search again before that step's dispatch, for that step's approach. | skill | S | P1 |
| skill.tnf.04 | SKILL.md:75 | main | first failing Test command, blocked subagent, or verifier finding (run, and each step) | Search before choosing the correction. | skill | S | C2 |
| skill.tnf.05 | SKILL.md:75 | main | later failures | Search again only when the failure signature is new. | skill | S J | C2 |
| skill.tnf.06 | SKILL.md:77 | main | searching | Search `index.md` for Implementation paths, symbols, and nouns, in English and the user's language. | skill | S | new |
| skill.tnf.07 | SKILL.md:77 | main | searching | Open only the records that match. | skill | S | new |
| skill.tnf.08 | SKILL.md:77 | main | match whose revisit condition does not hold | Pass it to the implementer as an excluded approach. | skill | J | I2 |
| skill.tnf.09 | SKILL.md:77 | main | match contradicting the drafted approach | Change the draft, or show it in the approval brief as an alternative already tried. | skill | J | new |
| skill.tnf.10 | SKILL.md:77 | main | before relying on a record | Re-check it against the current code. | skill | J | new |
| skill.telemetry.01 | SKILL.md:81 | main | after a telemetry command | Never inspect its result or let its failure change the workflow (phase command excepted). | skill | S J | new |
| skill.telemetry.02 | SKILL.md:83 | main | emitting a marker | Copy the command as printed and fill in only numbers and choices. | skill | S | new |
| skill.telemetry.03 | SKILL.md:83 | main | emitting a marker | Write every marker argument as a literal value (no shell variables). | skill | S | M2 |
| skill.telemetry.04 | SKILL.md:83 | main | ordinary tool activity | Do not emit markers for it. | skill | S | new |
| skill.telemetry.05 | SKILL.md:93 | main | before the parallel roles | Emit `implement_test`. | skill | H[h7] | I1 |
| skill.telemetry.06 | SKILL.md:93 | main | before a verifier dispatch | Emit `verify`. | skill | H[h7] S | E1 |
| skill.telemetry.07 | SKILL.md:93 | main | before an amendment or correction | Emit `amend` with the reason matching the change kind. | skill | H[h7] J | C1 |
| brief.recover.01 | workflow-1-recover.md:1 | main | recover/ground | Read `agent-docs/facts.md`. | brief, resume | S | B2 |
| brief.recover.02 | workflow-1-recover.md:1 | main | before creating a spec | Inspect `specs/`. | brief, resume | S | B2 |
| brief.recover.03 | workflow-1-recover.md:1 | main | an active spec exists | Do not start another workflow. | brief, resume | H[h2] S | new |
| brief.recover.04 | workflow-1-recover.md:1 | main | an active spec exists | Resume it only when the user asks. | brief, resume | G | new |
| brief.recover.05 | workflow-1-recover.md:1 | user-facing message | active spec, user did not ask to resume | Compare `base_commit` to HEAD, summarize work done and drift, ask resume or abort. | brief, resume | G J | new |
| brief.recover.06 | workflow-1-recover.md:1 | main | resuming a stepped spec | Resume as Stepped specs describes. | brief, resume | S | P4 |
| brief.recover.07 | workflow-1-recover.md:1 | main | aborting | In order: seed restore; lifecycle abort; on live-session refusal ask the user and re-run with `--other-sessions-confirmed` only after confirmation; `end --status aborted`; closing report. | brief, resume | S H[h4] | new |
| brief.recover.08 | workflow-1-recover.md:1 | main | recover/ground | Read deciding code yourself; delegate only location discovery. | brief, resume | S J | new |
| brief.recover.09 | workflow-1-recover.md:1 | main | recover/ground | Do not infer prior acceptance from a passing suite. | brief, resume | J | new |
| brief.recover.10 | workflow-1-recover.md:1 | main | verification policy changed | Apply lifecycle rule 5; preserve invocation counts and history. | brief, resume | S J | new |
| brief.purpose.01 | brief-purpose.md:3 | definition | - | The brief approves intent, carries user decisions, and builds understanding; the spec is the subagents' contract. | brief | - | - |
| brief.purpose.02 | brief-purpose.md:3 | main | always | Never write briefs into the spec or any other file. | brief | S J | new |
| voice.01 | voice.md:3 | definition | - | Voice governs everything said to the user (rounds, approval brief, quiz, closing report). | brief, approve, step, close, resume | - | - |
| voice.02 | voice.md:5 | user-facing message | always | Write for the owning engineer who has not read the code; 4-year developer; explain anything beyond in a sentence. | brief, approve, step, close, resume | J | V3 |
| voice.03 | voice.md:6 | user-facing message | always | Describe behavior, structure, data and control flow, and consequences. | brief, approve, step, close, resume | J | V2 |
| voice.04 | voice.md:6 | user-facing message | always | Leave out file paths, function/variable names, spec ids, table rows, unless the user must act on that exact name. | brief, approve, step, close, resume | J S | V1 |
| voice.05 | voice.md:6 | user-facing message | always | Leave out decisions that do not shape the result and that the user did not make (convention, library, name, technique, threshold). | brief, approve, step, close, resume | J | V4 |
| voice.06 | voice.md:6 | user-facing message | spec exists | Link the spec path and version once. | brief, approve, step, close, resume | S | V1 |
| voice.07 | voice.md:7 | user-facing message | decision shapes the result | Say what was chosen, what it costs, what it rules out, when it would be wrong. | brief, approve, step, close, resume | J | V2 |
| voice.08 | voice.md:7 | user-facing message | describing the result | Describe it as a thing: what exists afterwards, how parts connect, main path and failure, what the user/system observes. | brief, approve, step, close, resume | J | new |
| voice.09 | voice.md:8 | main | judging project detail | Judge from the current code and the spec alone. | brief, approve, step, close, resume | U | - |
| voice.10 | voice.md:8 | main | always | Keep no record of what the user knows; do not research or ask to find out. | brief, approve, step, close, resume | S J | new |
| voice.11 | voice.md:9 | user-facing message | always | Full sentences. | brief, approve, step, close, resume | J | V3 |
| voice.12 | voice.md:9 | user-facing message | always | Define terms at first use. | brief, approve, step, close, resume | J | V3 |
| voice.13 | voice.md:9 | user-facing message | always | No label the user cannot resolve from the message itself. | brief, approve, step, close, resume | J | V3 |
| brief.sweep.01 | decision-sweep.md:3 | main | before each round | Run the sweep. | brief | U | - |
| brief.sweep.02 | decision-sweep.md:5 | main | before listing decisions | Go through the 8 dimensions once for the task, noting a citation or unknown for each. | brief | G | G-B1, B9 |
| brief.sweep.03 | decision-sweep.md:5 | main | judging a dimension | Follow what the change sets off (records → events → jobs → metered calls → reactors) until the chain ends or leaves the repository. | brief | G | new |
| brief.sweep.04 | decision-sweep.md:5 | main | opt-in addition existing callers never see | Raise no question about existing callers. | brief | G | G-B2 |
| brief.sweep.05 | decision-sweep.md:5 | main | unknown dimension | Picture both ends and add every decision that comes out differently. | brief | G | G-B1 |
| brief.sweep.06 | decision-sweep.md:7 | main | per decision | Include context-pass decisions and inherited decisions whose reversal condition the task may change. | brief | G | G-B3 |
| brief.sweep.07 | decision-sweep.md:9 | main | per decision | Write question, leading option, one reasonable alternative, reversal condition. | brief | S J | R4 |
| brief.sweep.08 | decision-sweep.md:10 | main | per decision | Place the reversal condition in its dimension. | brief | U | - |
| brief.sweep.09 | decision-sweep.md:11 | main | per decision | Settle the reversal condition only with a citation (path:line, `facts.md` entry, user statement); never from what is typical. | brief | J G | new |
| brief.sweep.10 | decision-sweep.md:12 | main | per decision | Classify: no alternative/convention/no difference or cited → Decided for you; unknown + fact → Fact question (significant) or assumption; trade-off → Your decision (significant) or Decided for you. | brief | G | G-B1, G-D1 |
| brief.sweep.11 | decision-sweep.md:18 | definition | - | Significant = hard to reverse, load-bearing, different outcomes, or answerable for. | brief | - | - |
| brief.sweep.12 | decision-sweep.md:24 | definition | - | Engineer call = significant decision whoever made it: every Your decision and every significant Decided for you. | brief | - | - |
| brief.sweep.13 | decision-sweep.md:24 | main | approval brief and quiz | Explain and quiz engineer calls; other Decided-for-you items stay in the spec. | brief | J | A3, A5 |
| brief.understanding.01 | rounds-understanding.md:3 | user-facing message | understanding round | State "Here's what I understood": project, where the task fits, success, what the task will NOT do. | brief | J | B4 |
| brief.understanding.02 | rounds-understanding.md:3 | main | building the round | Use every available source, not a single required file. | brief | U | - |
| brief.understanding.03 | rounds-understanding.md:3 | main | an exclusion drops a safeguard or cannot be added back | Treat it as a decision through the sweep, not as "will not do". | brief | J G | B6 |
| brief.understanding.04 | rounds-understanding.md:4 | user-facing message | understanding round | *How it works today*: parts and main-path connections, where state lives, what happens when a step fails. | brief | J | B5 |
| brief.understanding.05 | rounds-understanding.md:4 | user-facing message | understanding round | List inherited decisions, each with what it buys, costs, when it stops holding, marked recorded/inferred. | brief | J G | B5, G-B3 |
| brief.understanding.06 | rounds-understanding.md:4 | user-facing message | task has no existing neighbor | One sentence on where it attaches. | brief | J | B5 |
| brief.understanding.07 | rounds-understanding.md:5 | user-facing message | understanding round | *Assumptions*: each unknown behind a non-significant decision, and each relied-on recorded fact with its date. | brief | J | B7 |
| brief.understanding.08 | rounds-understanding.md:5 | user-facing message | writing an assumption | One sentence true or false whatever gets built; not a software-behavior sentence; for a safeguard applied to new input, state the input fact. | brief | J | B7 |
| brief.understanding.09 | rounds-understanding.md:6 | user-facing message | unknown behind a significant decision | Ask it as a *Fact question*. | brief | G | G-B1 |
| brief.understanding.10 | rounds-understanding.md:6 | user-facing message | fact question | Ask for the fact, not the decision; name the fact, the decision it settles, and where each answer leads. | brief | J | B8 |
| brief.understanding.11 | rounds-understanding.md:6 | user-facing message | fact question | Add no guess of the answer. | brief | J | B8 |
| brief.understanding.12 | rounds-understanding.md:6 | main | significant unknown | Do not move it to the assumptions to save a question. | brief | G | G-B1 |
| brief.understanding.13 | rounds-understanding.md:6 | user-facing message | fact questions | Ask nothing the repository or `facts.md` answers (no cap otherwise). | brief | G | G-B2 |
| brief.understanding.14 | rounds-understanding.md:7 | user-facing message | understanding round | *Not asked*: one line naming each unasked dimension with a reason that also holds for what the change sets off; repository silence or unchanged edited code is not a reason. | brief | J | B9 |
| brief.understanding.15 | rounds-understanding.md:8 | user-facing message | understanding round | One invitation, verbatim, with no examples. | brief | J | B10 |
| brief.understanding.16 | rounds-understanding.md:10 | user-facing message | understanding round | Hold only these parts: no decisions of this task (chosen or pending), inherited decisions described as they stand, no notes on searching. | brief | J | B6, B11 |
| brief.understanding.17 | rounds-understanding.md:12 | main | after the round | Continue only after the user confirms or corrects it. | brief | S | B12 |
| brief.understanding.18 | rounds-understanding.md:12 | main | a fact was answered | Propose a `facts.md` entry for it. | brief | G J | new |
| brief.decision.01 | rounds-decision.md:1 | main | decision round | Re-run the sweep with the answers; a fact-settled decision becomes Decided for you with the fact cited. | brief, approve, step | J G | new |
| brief.decision.02 | rounds-decision.md:1 | user-facing message | decision round | Present each remaining Your decision as a neutral question with its significance criteria and the facts it rests on. | brief, approve, step | J | D1 |
| brief.decision.03 | rounds-decision.md:1 | user-facing message | decision round | Give no options, no trade-offs, no recommendation. | brief, approve, step | J | D1 |
| brief.decision.04 | rounds-decision.md:1 | user-facing message | user asks for options | Give options with a concrete consequence each, still no recommendation. | brief, approve, step | G | D5 |
| brief.decision.05 | rounds-decision.md:1 | main | user listed a decision in the understanding round | Treat it as Your decision. | brief, approve, step | G J | D3 |
| brief.decision.06 | rounds-decision.md:1 | main | before sending the round | Write own pick + one-line reason to `<run-id>-picks.md` outside the repository (scratchpad, else system temp). | brief, approve, step | S | D2 |
| brief.decision.07 | rounds-decision.md:1 | main | later rounds | Append to the picks file; never revise an entry. | brief, approve, step | S | D2 |
| brief.decision.08 | rounds-decision.md:1 | main | no Your decision remains | Skip the round. | brief, approve, step | S J | new |
| brief.decision.09 | rounds-decision.md:3 | main | counting | Count Your decision items over the whole task, each separately chosen part as one item. | brief, approve, step | J | M1 |
| brief.decision.10 | rounds-decision.md:3 | user-facing message | count first exceeds 3 | Before asking the new items, recommend splitting and propose the cut (separate specs or steps with held decisions). | brief, approve, step | S J G | D4 |
| brief.decision.11 | rounds-decision.md:3 | main | split recommended | Proceed with all items only when the user declines. | brief, approve, step | J | D4 |
| approve.brief.01 | rounds-approval.md:1 | main | approval brief | Present it after drafting the spec and searching try-n-fail. | brief, approve | S | A1, R9 |
| approve.brief.02 | rounds-approval.md:1 | user-facing message | approval brief | Present the listed parts in the listed order. | brief, approve | J | A2 |
| approve.brief.03 | rounds-approval.md:2 | user-facing message | approval brief | *What will exist*: the result as a thing, what it leaves out, starting from How it works today (what changes), each touched inherited decision kept or revisited and why. | brief, approve | J | A2 |
| approve.brief.04 | rounds-approval.md:3 | user-facing message | Your decisions | User's choice, main's pick and reason as written in the picks file, what differs, what the choice costs and rules out. | brief, approve | S J | A2 |
| approve.brief.05 | rounds-approval.md:3 | user-facing message | user choice differs from pick | Ask what the choice rested on; propose a facts entry when it is a fact. | brief, approve | J G | new |
| approve.brief.06 | rounds-approval.md:4 | user-facing message | Decided for you | Engineer calls only; each with choice, trade-away, option not taken and the state where it wins, how to change later. | brief, approve | J | A3 |
| approve.brief.07 | rounds-approval.md:4 | user-facing message | Decided for you | Close with one sentence that remaining defaults are in `# Assumptions and Defaults` and approval covers them. | brief, approve | J | A3 |
| approve.brief.08 | rounds-approval.md:5 | user-facing message | open question exists | *Still open*: each question, what settles it, what the work does until then. | brief, approve | J | A2 |
| approve.brief.09 | rounds-approval.md:6 | user-facing message | choice contradicts user/project statement | *Conflict*: show both sides and ask. | brief, approve | J G | A2 |
| approve.brief.10 | rounds-approval.md:7 | user-facing message | decision depends on knowledge the user may lack | First ask whether the user knows the concept, fresh every run. | brief, approve | J | A4 |
| approve.brief.11 | rounds-approval.md:7 | user-facing message | new concept | One sentence on what it is and why it matters; Decided-for-you adds a consequence of each option and the choice; Your decision adds neither. | brief, approve | J | A4 |
| approve.brief.12 | rounds-approval.md:8 | user-facing message | user answered the invitation | Say which decisions both lists share, which only the user named, which only the sweep found. | brief, approve | J G | new |
| approve.brief.13 | rounds-approval.md:9 | user-facing message | stepped spec | Steps, what the user observes after each, which decisions wait for which step. | brief, approve | J | A2 |
| approve.brief.14 | rounds-approval.md:10 | user-facing message | approval brief | Quality expectations in plain words for applicable characteristics only; ISO terms stay in the spec. | brief, approve | J | A2, V4 |
| approve.brief.15 | rounds-approval.md:11 | user-facing message | approval brief | End with the Quiz, then the request for approval. | brief, approve | J | A2, A7 |
| approve.brief.16 | rounds-approval.md:12 | user-facing message | proposed records exist | Send *Records to approve* in a separate message after the approval reply is resolved. | brief, approve | S J | A11 |
| draft.workflow.01 | workflow-2-draft.md:1 | main | item 2 | Run the understanding round, wait for confirmation or correction, then the decision round when the sweep leaves a user decision. | draft, approve | S | B12 |
| draft.workflow.02 | workflow-2-draft.md:1 | main | drafting | Derive functional requirements and all nine quality applicability decisions. | draft, approve | H[h1] J | R5 |
| draft.workflow.03 | workflow-2-draft.md:1 | main | drafting | Define measures, thresholds, 29119-4 techniques, coverage items and targets, evidence, traceability. | draft, approve | J | R5, R6 |
| draft.workflow.04 | workflow-2-draft.md:1 | main | drafting | Set `max_verifier_invocations: 2`. | draft, approve | H[h1] | - |
| draft.workflow.05 | workflow-2-draft.md:1 | main | drafting | Fill `# Alternatives` and `# Open Questions` from the sweep. | draft, approve | J | R4 |
| draft.workflow.06 | workflow-2-draft.md:1 | main | drafting | Search try-n-fail for the drafted approach. | draft, approve | S | R9 |
| draft.workflow.07 | workflow-2-draft.md:1 | main | drafting | Decide whether to recommend steps. | draft, approve | J | R10 |
| draft.workflow.08 | workflow-2-draft.md:1 | main | drafting | Write the completion questions. | draft, approve | S | R8 |
| draft.workflow.09 | workflow-2-draft.md:1 | main | approval | Present the approval brief with its quiz, resolve the answers, obtain approval. | draft, approve | S J | A7, A8 |
| draft.workflow.10 | workflow-2-draft.md:1 | main | approved | Set status `active`, then run `spec_lifecycle.py start` and check it succeeded. | draft, approve | H[h2] S | A12 |
| draft.workflow.11 | workflow-2-draft.md:1 | main | lifecycle start succeeded | Only then emit telemetry `start`. | draft, approve | S | A12 |
| draft.format.01 | spec-format.md:3 | main | creating the spec | Create it with `spec_lifecycle.py new`. | draft | S H[h13] | R1 |
| draft.format.02 | spec-format.md:9 | main | filling the spec | Keep every template heading, in its order. | draft | H[h1] S | new (order) |
| draft.format.03 | spec-format.md:9 | main | filling the spec | Replace every `<...>` placeholder; add rows under each table's header row. | draft | S | new |
| draft.format.04 | spec-format.md:11 | main | spec without steps | Delete `# Steps` and `# Session Memory`. | draft | S | new |
| draft.format.05 | spec-format.md:13 | main | spec content | Every intent, requirement, Case, quality requirement, obligation, assumption, open question has a stable id. | draft | S | new |
| draft.format.06 | spec-format.md:13 | main | applicable quality characteristic | At least one quality requirement. | draft | S | R5 |
| draft.format.07 | spec-format.md:13 | main | quality requirement | Define measured property and context, method and inputs, unit, threshold and direction, evidence procedure, source. | draft | J | R5 |
| draft.format.08 | spec-format.md:13 | main | thresholds and coverage targets | Set them as defaults in `# Assumptions and Defaults`. | draft | S J | R3 |
| draft.format.09 | spec-format.md:15 | main | Cases | Use levels normal/boundary/error/edge; include every level or a `none — <reason>` row. | draft | S | R7 |
| draft.format.10 | spec-format.md:15 | main | error Case rows | Name the signal and the post-failure state. | draft | J | R7 |
| draft.format.11 | spec-format.md:15 | main | Paths | Implementation and Tests paths are disjoint. | draft | S | R2 |
| draft.format.12 | spec-format.md:15 | implementer, test-implementer | always | Implementer never reads Tests; test roles never read Implementation. | draft | H[h8] | I6 |
| draft.format.13 | spec-format.md:17 | main | Alternatives | One row per reasonable alternative of each significant decision, whoever decided. | draft | J | R4 |
| draft.format.14 | spec-format.md:17 | main | Open Questions | Hold what approval left unknown and what the work turns up; `none` when empty. | draft | S | new |
| draft.format.15 | spec-format.md:17 | main | Completion Questions | Only main uses them; not a requirement, Case, or oracle; a requirement wins on conflict. | draft | J | I2, I3 |
| draft.format.16 | spec-format.md:17 | main | after approval | Alternatives, Open Questions, Completion Questions change only by amendment (except the `asked` column). | draft | S | new |
| draft.format.17 | spec-format.md:17 | main | completion | Every open question is settled or deferred. | draft | S | new |
| verify.design.01 | verification-design.md:3 | main | before dispatch | Define a finite set of independently checkable obligations. | draft, verify | S J | R6 |
| verify.design.02 | verification-design.md:3 | main | obligation row | Required variant, observable target surface, test layer, selection policy, one 29119-4 technique, coverage items, approved target. | draft, verify | S J | R6 |
| verify.design.03 | verification-design.md:3 | definition | - | Coverage = exercised coverage items / declared coverage items. | draft, verify | - | - |
| verify.design.04 | verification-design.md:3 | main | obligations | Distinguish test layer from Case level. | draft, verify | J | R6 |
| verify.design.05 | verification-design.md:3 | main | obligations | Define lifecycle boundaries (same-process re-import vs restart). | draft, verify | J | new |
| verify.design.06 | verification-design.md:3 | main | before approval | Resolve ambiguous selection or boundary terms; never let a test role choose missing policy. | draft, verify | J | new |
| verify.design.07 | verification-design.md:5 | main | specification-based technique | Enumerate coverage items finitely; no implied Cartesian product; a target below 100% names the selected items and rationale. | draft, verify | J | R6 |
| verify.design.08 | verification-design.md:6 | main | structure-based technique | Name the measuring tool and Implementation scope; measure through the Test command; map each shortfall to behavior. | draft, verify | J S | new |
| verify.design.09 | verification-design.md:6 | main | unexercised code | Undeclared behavior → spec gap or implementation defect; declared behavior → test defect. | draft, verify | J | new |
| verify.design.10 | verification-design.md:6 | main | instructing test roles | Give only behavior and measured values, never Implementation locations. | draft, verify | S J | C4 |
| verify.design.11 | verification-design.md:7 | main | experience-based technique | Coverage items are guessed defects; target `none — experience-based`. | draft, verify | S | R6 |
| verify.design.12 | verification-design.md:9 | main | obligations | Derive from every in-scope requirement, including errors and quality requirements. | draft, verify | S | new |
| verify.design.13 | verification-design.md:9 | main | technique selection | Select required techniques; justify excluded techniques and dimensions. | draft, verify | J | new |
| verify.design.14 | verification-design.md:9 | main | omission found | Treat it as a spec challenge, not silent scope expansion. | draft, verify | J | E5 |
| verify.design.15 | verification-design.md:11 | definition | - | Evidence sufficiency: observes behavior at the declared surface/layer, independent expected result, distinguishes failure from success, meets target. | draft, verify | - | - |
| verify.design.16 | verification-design.md:11 | main, test-verifier | judging evidence | A test name or filled map is not proof. | draft, verify | J | new |
| verify.design.17 | verification-design.md:11 | test-verifier | blocking finding | Identify a required obligation and a concrete violating behavior the evidence fails to reject, or a precise requirement conflict/omission. | draft, verify | J | E5 |
| verify.evidence.01 | verification-evidence.md:1 | main | evidence choice | Prefer automated evidence. | draft, verify | J | new |
| verify.evidence.02 | verification-evidence.md:1 | main | review evidence | Give a repeatable procedure, inputs, observation, expected result, named artifact. | draft, verify | J | new |
| verify.evidence.03 | verification-evidence.md:1 | main | mutation selection | Select the 8–10 strongest distinct defect classes (or all), including on a no-finding pass, and record why. | draft, verify | S J | E6 |
| verify.evidence.04 | verification-evidence.md:1 | main | mutation result | Count a mutation only if it executes and the intended assertion detects it; setup/unrelated failures are inconclusive. | draft, verify | J | E8 |
| verify.fuzz.01 | verification-fuzz.md:1 | main | fuzz harness declared | Run it for its full budget with the recorded seed. | draft, verify[fuzzing] | S | new |
| verify.fuzz.02 | verification-fuzz.md:1 | main | crash or oracle violation | Make it a finding; give test roles the minimized reproducer as input and observed behavior only. | draft, verify[fuzzing] | J | new |
| verify.fuzz.03 | verification-fuzz.md:1 | main | early stop, timeout, setup failure | Treat as inconclusive. | draft, verify[fuzzing] | J | new |
| verify.mutationtool.01 | verification-mutation-tool.md:1 | main | mutation tool declared | Run it after the hand mutations. | draft, verify[mutation-tool] | S | new |
| verify.mutationtool.02 | verification-mutation-tool.md:1 | main | declaring a tool | Declare only installed tools, otherwise `none`. | draft, verify[mutation-tool] | S | new |
| verify.mutationtool.03 | verification-mutation-tool.md:1 | main | running the tool | Mutate only Implementation lines changed since `base_commit`; sample with the recorded seed above the cap. | draft, verify[mutation-tool] | S | new |
| verify.mutationtool.04 | verification-mutation-tool.md:1 | main | survival above threshold (default 40%) | Skip triage; record one non-blocking advisory finding with the rate. | draft, verify[mutation-tool] | S J | new |
| verify.mutationtool.05 | verification-mutation-tool.md:1 | main | survival at or below threshold | Restore every file; send survivors in batches to `mutant-triager` with spec path and id, diff, file, line. | draft, verify[mutation-tool] | S | new |
| verify.mutationtool.06 | verification-mutation-tool.md:1 | main | triager verdicts | Route declared → evidence gap, undeclared → spec challenge, insufficient context → main resolves. | draft, verify[mutation-tool] | J | new |
| verify.mutationtool.07 | verification-mutation-tool.md:1 | main | `equivalent` verdicts | Recheck those on obligation-tied code plus a random sample; one overturned reopens the batch. | draft, verify[mutation-tool] | S J | new |
| verify.mutationtool.08 | verification-mutation-tool.md:1 | main | timeout or tool failure | Treat as inconclusive. | draft, verify[mutation-tool] | J | new |
| verify.audit.01 | verification-audit-state.md:1 | main | between verifiers | Carry audit state. | draft, verify | S | E4 |
| verify.audit.02 | verification-audit-state.md:1 | main | acceptance | Scope it to spec version, evidence revision, dependencies. | draft, verify | S J | new |
| verify.audit.03 | verification-audit-state.md:1 | main | requirements/tests/helpers/procedures/behavior changed | Mark affected entries invalidated; record the impact and why others stay valid. | draft, verify | J | new |
| verify.audit.04 | verification-audit-state.md:1 | test-verifier | audit | Check the impact assessment against the Tests diff; reopen acceptance only with new evidence. | draft, verify | J | new |
| verify.audit.05 | verification-audit-state.md:1 | main | fresh verifier | Never inherit acceptance blindly or restart scope derivation just because the verifier is fresh. | draft, verify | J | new |
| stepped.cut.01 | stepped-cut.md:3 | main | size, order dependence, outside wait, too many decisions, or stopped session | Recommend the step cut. | draft, resume[not-stepped] | S J | R10 |
| stepped.cut.02 | stepped-cut.md:11 | user-facing message | size/order/outside-wait trigger | Recommend the cut in the approval brief. | draft, resume[not-stepped] | J | R10, A2 |
| stepped.cut.03 | stepped-cut.md:11 | user-facing message | too-many-decisions trigger | Propose the cut in outline in the decision round; fix it in the approval brief. | draft, resume[not-stepped] | J | D4 |
| stepped.cut.04 | stepped-cut.md:11 | main | stopped-session trigger | The next session proposes it before continuing, as an amendment with a re-brief; used verifier invocations count against the first remaining step. | draft, resume[not-stepped] | G S | new |
| stepped.cut.05 | stepped-cut.md:11 | main | cut | The user approves it; changing it later is an amendment with a re-brief. | draft, resume[not-stepped] | J | C5 |
| stepped.cut.06 | stepped-cut.md:13 | main | cutting | Each step has an observable outcome and owns its ids; each id in exactly one step; a spanning obligation goes to the last step. | draft, resume[not-stepped] | S | new |
| stepped.cut.07 | stepped-cut.md:13 | main | after each step | Test command passes; no behavior half-switched. | draft, resume[not-stepped] | S J | new |
| stepped.cut.08 | stepped-cut.md:13 | main | ordering steps | Order by dependency; a step settling an open question precedes its dependents. | draft, resume[not-stepped] | J | new |
| stepped.held.01 | stepped-held.md:1 | main | Your decision no earlier step depends on | It may be held for its step. | draft, step, resume | J | new |
| stepped.held.02 | stepped-held.md:1 | main | held decision, step not started | Carry it as an open question naming the step, name it in the step's `held decisions`, write no dependent requirements. | draft, step, resume | S | new |
| stepped.held.03 | stepped-held.md:1 | main | held decision's step starts | Ask it in a decision round, then add dependent requirements/Cases/obligations by an amendment approved through a re-brief with the picks comparison. | draft, step, resume | J | P2 |
| stepped.run.01 | stepped-run.md:1 | user-facing message | each step after the first | Give a short step brief: what the step adds, its held decisions. | implement_test[stepped], step, resume[stepped] | J | P1 |
| stepped.run.02 | stepped-run.md:1 | main | each step after the first | Search try-n-fail for the step's approach. | implement_test[stepped], step, resume[stepped] | S | P1 |
| stepped.run.03 | stepped-run.md:1 | main | running a step | Mark it `active`; run items 3–8 for its ids only; dispatch instructions name the step and its ids. | implement_test[stepped], step, resume[stepped] | S J | new |
| stepped.run.04 | stepped-run.md:1 | main | verifier counting in a stepped spec | Bound each step separately; count in the step's cell and the run total in Workflow Control; use the run total for `--round`. | implement_test[stepped], step, resume[stepped] | S | E3 |
| stepped.run.05 | stepped-run.md:1 | main | earlier-step obligations | Keep them accepted; reopen only through the change-impact rule. | implement_test[stepped], step, resume[stepped] | J | new |
| stepped.run.06 | stepped-run.md:1 | main | stop condition holds for the step | Mark it `done` with the date and go on, unless the user asks to stop or the session cannot continue. | implement_test[stepped], step, resume[stepped] | S | new |
| stepped.run.07 | stepped-run.md:1 | main | step exhausts its verifier budget | End the run with status `limit`. | implement_test[stepped], step, resume[stepped] | S | new |
| stepped.end.01 | stepped-end.md:1 | main | session ends before the last step | It is a nonterminal stop: spec stays `active`, Workflow item 9 applies. | close[stepped] | S | new |
| stepped.end.02 | stepped-end.md:1 | main | before the closing report | Append Session Memory rows in the three sections. | close[stepped] | S | P3 |
| stepped.end.03 | stepped-end.md:3 | main | Failed Attempts row | A plausibly repeated failed approach with evidence and verified/hypothesis. | close[stepped] | J | P3 |
| stepped.end.04 | stepped-end.md:4 | main | Decisions row | Only choices that are neither engineer calls nor brief items; engineer calls go to Assumptions/Alternatives by amendment. | close[stepped] | J | P3 |
| stepped.end.05 | stepped-end.md:5 | main | Unresolved row | State what is unknown, known so far, what would settle it; requirement/engineer-call/step-affecting ones go to Open Questions by amendment. | close[stepped] | J | P3 |
| stepped.end.06 | stepped-end.md:7 | main | every row | Objective and reproducible (observation, re-runnable evidence, re-check); no recommendations or instructions; no repetition of code/history/spec. | close[stepped] | J | P3 |
| stepped.end.07 | stepped-end.md:7 | main | rows | Append, never edit; a superseded row gets a new row saying so. | close[stepped] | S | new |
| stepped.end.08 | stepped-end.md:7 | main | empty section | Write `none`. | close[stepped] | S | new |
| stepped.end.09 | stepped-end.md:7 | main | content that should outlive the task | Route it through the closing report into `facts.md` or try-n-fail. | close[stepped] | J | new |
| stepped.resume.01 | stepped-resume.md:1 | main | resuming | Read `# Steps` and `# Session Memory` first. | resume[stepped] | S | P4 |
| stepped.resume.02 | stepped-resume.md:1 | main | resuming | Compare each row's commit with HEAD; re-check rows touching changed code. | resume[stepped] | S J | P4 |
| stepped.resume.03 | stepped-resume.md:1 | main | resuming | Run the Test command to confirm finished steps pass. | resume[stepped] | S | P4 |
| stepped.resume.04 | stepped-resume.md:1 | main | resuming | Emit telemetry `start` with the same run id and current spec version. | resume[stepped] | H[h6] S | P4 |
| stepped.resume.05 | stepped-resume.md:1 | main | resuming | Treat rows as observations; re-check and decide. | resume[stepped] | J | new |
| subagent.model.01 | subagent-model.md:3 | main | role model | Propose a non-default model only with a task-specific reason. | draft, implement_test | J | new |
| subagent.model.02 | subagent-model.md:3 | user-facing message | model proposal | List it under *Decided for you* in the approval brief. | draft, implement_test | J | new |
| subagent.model.03 | subagent-model.md:3 | main | approved model | Pass it as the Agent tool model override for that role's dispatches. | draft, implement_test | S | new |
| subagent.model.04 | subagent-model.md:3 | main | user names a model | It overrides both. | draft, implement_test | S G | new |
| quiz.rules.01 | quiz-rules.md:5 | user-facing message | approval brief | Ask 2 to 4 questions under the heading *Quiz* at the end. | draft, approve, step, close | S J | A5 |
| quiz.rules.02 | quiz-rules.md:5 | user-facing message | approval quiz | Cover the main trade-off, at least one engineer call, and the final shape. | draft, approve, step, close | J | A5 |
| quiz.rules.03 | quiz-rules.md:6 | user-facing message | each question | Ask to predict or apply, not recall, in the form given for its target. | draft, approve, step, close | J | A5 |
| quiz.rules.04 | quiz-rules.md:6 | user-facing message | quiz message | No options, hints, or answers in the same message. | draft, approve, step, close | J | A5 |
| quiz.rules.05 | quiz-rules.md:7 | user-facing message | each question | Expected answer follows from the brief, never from spec-only values or threshold sides. | draft, approve, step, close | J | A5 |
| quiz.rules.06 | quiz-rules.md:7 | user-facing message | quiz | At most one failure/boundary question. | draft, approve, step, close | J | A5 |
| quiz.rules.07 | quiz-rules.md:8 | main | before sending a quiz | Write the expected answer of each new question in the picks file. | draft, approve, step, close | S | A6 |
| quiz.rules.08 | quiz-rules.md:9 | user-facing message | answers arrive | Compare each with the expected answer written beforehand; say in one line each which matched. | draft, approve, step, close | J | A8 |
| quiz.rules.09 | quiz-rules.md:9 | main | answer differs | Determine misunderstanding (re-explain from the user's answer in other words), intent (draft revision / `[intent-mismatch]` amendment + re-brief), or fact (propose `facts.md` entry). | draft, approve, step, close | J G | A8 |
| quiz.rules.10 | quiz-rules.md:10 | main | quiz answer | Never record it or treat it as a decision or instruction; only an approved amendment changes the spec. | draft, approve, step, close | S J | new |
| quiz.rules.11 | quiz-rules.md:10 | main | picks file | Write the user's answers nowhere; the picks file holds only main's picks and expected answers; a later session does not read it. | draft, approve, step, close | S | new |
| quiz.rules.12 | quiz-rules.md:11 | user-facing message | approval quiz | Ask for approval in the same message as the quiz. | draft, approve, step, close | J | A7 |
| quiz.rules.13 | quiz-rules.md:11 | main | approval arrives with a differing answer | Not yet approval: resolve the difference, then ask again. | draft, approve, step, close | G | A9 |
| quiz.rules.14 | quiz-rules.md:12 | main | always | Never skip or shorten the quiz on its own; the user may skip by saying so. | draft, approve, step, close | S J | new |
| quiz.rules.15 | quiz-rules.md:12 | main | reply approves without answering | Ask once for answers or an explicit skip; a second reply without answers is a skip. | draft, approve, step, close | G | A10 |
| quiz.completion.01 | quiz-completion-questions.md:1 | main | drafting, before the approval brief | Write 4–5 completion questions, each with expected answer and what it tests. | draft, step, close | S | R8 |
| quiz.completion.02 | quiz-completion-questions.md:1 | main | completion question set | Follow quiz rules; cover trade-off, ≥1 engineer call, final shape; ≤1 failure/boundary. | draft, step, close | J | R8 |
| quiz.completion.03 | quiz-completion-questions.md:1 | user-facing message | approval brief | Do not show completion questions in it. | draft, step, close | S J | new |
| quiz.completion.04 | quiz-completion-questions.md:1 | main | draft revision after the approval quiz | Replace invalidated questions; never edit an expected answer. | draft, step, close | S | new |
| quiz.completion.05 | quiz-completion-questions.md:1 | main | after approval | Change them only by amendment; a requirement-adding amendment adds the questions it needs. | draft, step, close | S | new |
| quiz.closing.01 | quiz-closing.md:1 | main | each closing | Judge each question invalid / not yet built / valid by the stated definitions. | close | J | new |
| quiz.closing.02 | quiz-closing.md:1 | main | marking | Only an amendment writes `invalid v<n> — <reason>`; never write *not yet built*. | close | S | new |
| quiz.closing.03 | quiz-closing.md:3 | main | run meets the stop condition | Run the completion check before setting `complete`, over every valid question. | close | S J | X1 |
| quiz.closing.04 | quiz-closing.md:3 | main | completion check | Answer each from the built result before rereading its expected answer, citing a code location or run. | close | J U | X1 |
| quiz.closing.05 | quiz-closing.md:3 | main | completion check differs from approved spec | Correct the result (Workflow item 7). | close | S J | X1 |
| quiz.closing.06 | quiz-closing.md:3 | main | expected answer misread the spec | Mark invalid by a contract-only amendment and report it; never rewrite an expected answer after approval. | close | S J | new |
| quiz.closing.07 | quiz-closing.md:3 | main | question only one test case could settle | Mark it invalid the same way. | close | J | new |
| quiz.closing.08 | quiz-closing.md:4 | user-facing message | every closing report | Ask up to 3 valid, unasked questions covering trade-off, engineer call, final shape as far as possible. | close | J | X5 |
| quiz.closing.09 | quiz-closing.md:4 | main | closing quiz asked | Write `closing <date>` into their `asked` cell. | close | S | X5 |
| quiz.closing.10 | quiz-closing.md:4 | main | limit, nonterminal, or aborted closing | Skip the completion check; ask only already-built questions. | close | S J | new |
| quiz.closing.11 | quiz-closing.md:4 | main | no question qualifies | Write one new question and its expected answer in the picks file before sending. | close | S | new |
| quiz.closing.12 | quiz-closing.md:4 | user-facing message | closing report | Report invalid questions and why in *Numbers*, with completion-check differences and their resolution. | close | J | X3 |
| quiz.across.01 | quiz-across-sessions.md:1 | main | completion check in a later session | State the code location or run for each answer; an answer without a citation counts as a difference. | step, close, resume | J | X1 |
| quiz.across.02 | quiz-across-sessions.md:1 | main | held decision's step opens | Add its questions in the opening amendment, `built by` naming the step. | step, close, resume | S | new |
| close.report.01 | closing-report.md:3 | user-facing message | session worked on a spec (complete, limit, nonterminal, aborted) | End with a closing report in chat. | close | S J | X3 |
| close.report.02 | closing-report.md:3 | main | closing report | Write nothing from it to a file except approved records. | close | S | new |
| close.report.03 | closing-report.md:3 | user-facing message | closing report | Follow Voice and the section order. | close | J | X3 |
| close.report.04 | closing-report.md:5 | user-facing message | *What exists now* | Result or stop state, each difference from the approval brief with reason, each deferred open question. | close | J | X3 |
| close.report.05 | closing-report.md:6 | user-facing message | *Calls made during the work* | Each post-approval decision that shapes the result, its cost and what it rules out. | close | J | X3 |
| close.report.06 | closing-report.md:7 | user-facing message | *What went wrong* | Failed approaches and why, misleading signals, main's own mistakes with cost, small ones included. | close | J S | X4 |
| close.report.07 | closing-report.md:8 | user-facing message | *Records to approve* | Exact text of each proposed facts entry with its own question; a draft of each qualifying try-n-fail record. | close | J | F2; new (try-n-fail) |
| close.report.08 | closing-report.md:8 | main | records | Write only what the user approves. | close | S J | F1; new (try-n-fail) |
| close.report.09 | closing-report.md:9 | user-facing message | stepped spec | Steps done, what the next session starts with, Session Memory rows added, in plain words. | close | J | new |
| close.report.10 | closing-report.md:10 | user-facing message | closing quiz answer shows a completed result is not intended | Say what would have to change and ask whether to start a follow-up task; do not reopen the archived spec. | close | G J | new |
| close.report.11 | closing-report.md:10 | main | handling the closing quiz reply | Emit `brief --stage quiz --quiz-of closing` in that turn. | close | H[h6] S | M1 |
| close.report.12 | closing-report.md:11 | user-facing message | *Numbers* | Last, in a few lines: spec path and version, invalid questions and why, verifier invocations, correction batches and causes, mutation/fuzz/mutation-tool outcomes, anything blocked. | close | J | X3 |
| implement.dispatch.01 | workflow-3-implement.md:1 | main | item 3 | Emit `implement_test`. | implement_test | H[h7] | I1 |
| implement.dispatch.02 | workflow-3-implement.md:1 | main | dispatching | Dispatch both roles on the same spec version without sharing outputs. | implement_test | S | I1; new (no sharing) |
| implement.dispatch.03 | workflow-3-implement.md:1 | main | dispatch instructions | Task-specific and complete. | implement_test | J | I2, I3 |
| implement.dispatch.04 | workflow-3-implement.md:1 | main | every subagent dispatch | Say that `# Completion Questions` is no requirement, Case, or oracle. | implement_test | S | I2, I3; new (verifier) |
| implement.dispatch.05 | workflow-3-implement.md:2 | main | implementer dispatch | Path/version, direction, quality constraints, risks, allowed non-Test checks, excluded approaches (incl. try-n-fail). | implement_test | J | I2 |
| implement.dispatch.06 | workflow-3-implement.md:3 | main | test-implementer dispatch | Path/version, conventions, risk model, techniques and coverage items, independent oracle, evidence, test level, allowed load checks, excluded approaches. | implement_test | J | I3 |
| implement.dispatch.07 | workflow-3-implement.md:3 | main | test-implementer dispatch | Allow only collecting/listing/type-checking Tests; never instruct it to run tests, the Test command, or Implementation code. | implement_test | H[h8] S | I3 |
| implement.reconcile.01 | workflow-4-reconcile.md:1 | main | collecting reports | Use bounded waits. | implement_test | S | new |
| implement.reconcile.02 | workflow-4-reconcile.md:1 | main | subagent stalls | Interrupt and diagnose before retrying. | implement_test | S J | new |
| implement.reconcile.03 | workflow-4-reconcile.md:1 | main | challenges | Resolve with spec/code evidence; amend or reject each with a reason. | implement_test | J | new |
| implement.reconcile.04 | workflow-4-reconcile.md:1 | main | prior decisions | Reopen only with new evidence; keep dependent work blocked until the user resolves a required decision. | implement_test | J | new |
| implement.reconcile.05 | workflow-4-reconcile.md:1 | main | unblocked | Run the exact Test command with a finite timeout (the gate blocks it while the roles run). | implement_test | S H[h5] | I4 |
| implement.reconcile.06 | workflow-4-reconcile.md:1 | main | Test command fails | Classify as implementation, test, evidence defect, or spec gap; queue one correction batch. | implement_test | J | I5 |
| implement.reconcile.07 | workflow-4-reconcile.md:1 | main | Test command times out | Investigate it as a failure; never treat it as a pass or retry unchanged. | implement_test | S J | I5 |
| verify.dispatch.01 | workflow-5-verify.md:1 | main | after a passing Test command | Write the Tests diff file (diff from `base_commit` + untracked Tests files) outside the working tree. | verify | S | E2 |
| verify.dispatch.02 | workflow-5-verify.md:1 | main | every verifier dispatch | Rewrite the Tests diff file. | verify | S | E2 |
| verify.dispatch.03 | workflow-5-verify.md:1 | main | verifier dispatch | Fresh verifier; spec path/version, coverage/evidence map, audit state, change-impact assessment, finding ledger, diff file path. | verify | J S | E4 |
| verify.dispatch.04 | workflow-5-verify.md:1 | main, test-verifier | audit | Every obligation has a current disposition; audit pending/invalidated evidence; assess new challenges to retained acceptance. | verify | J | new |
| verify.dispatch.05 | workflow-5-verify.md:1 | main | before dispatch | Check and persist the incremented `verifier invocations` count in Workflow Control. | verify | S | E3 |
| verify.dispatch.06 | workflow-5-verify.md:1 | main | verifier invocations | At most two per run (per step if stepped), counting failed/interrupted/incomplete audits. | verify | S | E3 |
| verify.dispatch.07 | workflow-5-verify.md:1 | main | resume, amendment, replacement run | Preserve the count; do not evade the limit. | verify | S | E3 |
| verify.dispatch.08 | workflow-5-verify.md:1 | main | `verifier` marker | Use the invocation count for `--round`. | verify | S | M1 |
| verify.dispatch.09 | workflow-5-verify.md:1 | main | required audit would exceed the budget | Apply the stop condition. | verify | S | new |
| verify.triage.01 | workflow-6-triage.md:1 | main | findings | Record stable ids, spec versions, affected obligations/variants, evidence, dispositions, mutation outcomes. | verify | S J | E5 |
| verify.triage.02 | workflow-6-triage.md:1 | main | each finding | Classify as obligation evidence gap, spec challenge, or advisory. | verify | J | E5 |
| verify.triage.03 | workflow-6-triage.md:1 | main | spec challenge | Cite the requirement; route to amendment/user decision. | verify | J | E5 |
| verify.triage.04 | workflow-6-triage.md:1 | main | optional strengthening | Advisory; does not block completion. | verify | J | E5 |
| verify.triage.05 | workflow-6-triage.md:1 | main | actual requirement gap | Do not downgrade to advisory. | verify | J | E5 |
| verify.triage.06 | workflow-6-triage.md:1 | main | dispositions | Update audit state with evidence-backed dispositions. | verify | S | new |
| verify.triage.07 | workflow-6-triage.md:1 | main | mutations | Exercise the selected classes, blocking findings first, one at a time, without exposing implementation or injected diffs to test roles. | verify | S | E7, C4 |
| verify.triage.08 | workflow-6-triage.md:2 | main | before injecting | `seed.py backup` every edited file. | verify | H[h10][h11] S | E7 |
| verify.triage.09 | workflow-6-triage.md:3 | main | injected | Run the Test command with a finite timeout. | verify | S | E7 |
| verify.triage.10 | workflow-6-triage.md:4 | main | after each mutation | `seed.py restore` before continuing or handing off; stop and record the backup if restore fails. | verify | H[h10] S | E7 |
| verify.triage.11 | workflow-6-triage.md:5 | main | fuzzing/mutation tool declared | Run fuzzing, then the mutation tool, backing up and restoring every file it may edit. | verify | S | new |
| verify.triage.12 | workflow-6-triage.md:6 | main | after fuzz/mutation-tool pass | Triage survivors, record outcomes in the ledger, emit `verification`. | verify | H[h6] S | new |
| verify.triage.13 | workflow-6-triage.md:8 | main | mutation outcome | Green confirms a gap only when the mutation executed; failure rejects only when the intended assertion detects it. | verify | J | E8 |
| verify.triage.14 | workflow-6-triage.md:8 | main | inconclusive result | Retry with a changed distinguishing probe, or mark blocked and stop nonterminally. | verify | J | new |
| verify.triage.15 | workflow-6-triage.md:8 | main | before redispatch or closure | Triage every finding, including the final audit's. | verify | S J | new |
| verify.triage.16 | workflow-6-triage.md:8 | main | evidence-backed rejection, nothing changed | No further audit needed. | verify | J | new |
| amend.correct.01 | workflow-7-correct.md:1 | main | first correction batch, or new failure signature | Search try-n-fail. | amend | S | C2 |
| amend.correct.02 | workflow-7-correct.md:1 | definition | - | Ordinary corrections have no count limit. | amend | - | - |
| amend.correct.03 | workflow-7-correct.md:1 | main | each retry | Record failure signature, cause hypothesis, changed approach or new evidence, observed result in the execution ledger. | amend | S | C3 |
| amend.correct.04 | workflow-7-correct.md:1 | main | retrying | Continue only with a concrete diagnostic or justified correction; never repeat a failed approach without new evidence. | amend | J | C3 |
| amend.correct.05 | workflow-7-correct.md:1 | main | resolved finding recurs or edits oscillate | Compare prior attempts and re-evaluate the cause before editing. | amend | J | new |
| amend.correct.06 | workflow-7-correct.md:1 | main | no next step, or audit beyond budget needed | Apply the stop condition. | amend | J | new |
| amend.correct.07 | workflow-7-correct.md:3 | main | correction | Emit `amend` and increment the correction count. | amend | H[h7] S | C1; new (count) |
| amend.correct.08 | workflow-7-correct.md:3 | main | redispatch | Send complete replacement instructions, continuing existing agents where possible. | amend | J S | new |
| amend.correct.09 | workflow-7-correct.md:3 | main | implementation defect | Give ids and observable behavior, never test code. | amend | S J | C4 |
| amend.correct.10 | workflow-7-correct.md:3 | main | test/evidence defect | Give rules, variants, sanitized evidence, never implementation diffs. | amend | S J | C4 |
| amend.correct.11 | workflow-7-correct.md:3 | main | correcting a pattern | Correct across all obligations sharing the pattern/helper; report the full affected set incl. unchanged siblings. | amend | J | new |
| amend.correct.12 | workflow-7-correct.md:3 | main | correction sweep | Add no undeclared combinations. | amend | J | new |
| amend.correct.13 | workflow-7-correct.md:3 | main | before redispatch | Update evidence references; invalidate affected acceptance. | amend | S | new |
| amend.correct.14 | workflow-7-correct.md:3 | main | spec gap | Increment spec version after required approval; redispatch both roles. | amend | S | new |
| amend.correct.15 | workflow-7-correct.md:3 | main | after correction | Reconcile, rerun the Test command, repeat confirming mutations, return to Verify. | amend | S | new |
| stop.01 | workflow-8-stop.md:1 | main | marking complete | Only when every obligation passes at target, review artifacts exist, audit complete with no open blocking finding, accepted evidence current, confirming mutations fail correctly, fuzzing clean, survivors dispositioned, open questions settled/deferred. | verify, close | S J | new |
| stop.02 | workflow-8-stop.md:1 | main | stepped spec | Check the condition per active step; the run completes when the last step is done. | verify, close | S | new |
| stop.03 | workflow-8-stop.md:1 | main | completing | Advisory suggestions may remain; unresolved spec challenges may not. | verify, close | J | new |
| stop.04 | workflow-8-stop.md:1 | main | further verification needed after two invocations | Stop with `limit` before corrections that need that audit. | verify, close | S | new |
| stop.05 | workflow-8-stop.md:1 | main | blocked on a user decision or external change | Finish independent work, request what is missing, keep the spec active (nonterminal stop). | verify, close | J | new |
| stop.06 | workflow-8-stop.md:1 | main | no discriminating check or justified correction left | Stop nonterminally. | verify, close | J | new |
| close.workflow.01 | workflow-9-close.md:1 | main | run meets the stop condition | Run the completion check first; a difference returns to item 7. | close | S | X1 |
| close.workflow.02 | workflow-9-close.md:1 | main | stepped spec | Then write the session's Session Memory rows. | close | S | P3 |
| close.workflow.03 | workflow-9-close.md:1 | main | success | Set `complete`, archive with `--status complete`, then emit `end complete`. | close | H[h3] S | X2 |
| close.workflow.04 | workflow-9-close.md:1 | main | verifier budget exhausted | Set `limit`, archive with `--status limit`, then emit `end limit`. | close | H[h3] S | X2 |
| close.workflow.05 | workflow-9-close.md:1 | main | nonterminal stop | Keep `active`, emit `end handoff`, do not archive. | close | S | X2 |
| close.workflow.06 | workflow-9-close.md:1 | user-facing message | after the status step | Give the closing report with its quiz. | close | S | X3 |
| close.workflow.07 | workflow-9-close.md:1 | main | user approves records | Write the approved `facts.md` entries and try-n-fail records. | close | S | F1 |
| markers.01 | markers.json:12 | main | each understanding round, decision round, approval brief | Emit `brief` in the same turn with `--stage` and `--round N` counting that stage from 1. | brief, approve, step | H[h6] S | M1; new (presence) |
| markers.02 | markers.json:16 | main | brief marker | `--fact-questions` = fact questions in that round; `--user-decisions` = whole-task Your decision count; `--split` per proposal state; `--picks-differ` on the approval brief. | brief, approve, step | S J | M1 |
| markers.03 | markers.json:20 | main | step cut recommended in the approval brief | Count it as `--split proposed`. | brief, approve | S J | M1 |
| markers.04 | markers.json:24 | main | each closing report | Emit `brief --stage closing` in the same turn. | close | H[h6] S | new |
| markers.05 | markers.json:28 | main | approval brief, closing report | `--quiz-questions` = questions that message asks. | approve, close | S J | M1 |
| markers.06 | markers.json:32 | main | closing report | `--completion-invalid` and `--completion-differ` counts (0 when skipped). | close | S J | M1 |
| markers.07 | markers.json:36 | main | turn handling a quiz reply | Emit `brief --stage quiz` with `--quiz-of`, `--quiz-answered`, `--quiz-differ`, counting quizzes from 1. | approve, close | H[h6] S J | M1 |
| markers.08 | markers.json:40 | main | before the initial dispatch; on resume | Emit `start` (again on resume). | approve, resume | H[h6] S | A12, P4 |
| markers.09 | markers.json:44 | main | every verifier result | Emit one `verifier` marker. | verify | H[h6] S | E1 |
| markers.10 | markers.json:48 | main | verifier marker | `--findings`, `--seeds-run`, `--seeds-detected` counts; emit once the confirming mutations have run. | verify | S J | M1; new (timing) |
| markers.11 | markers.json:52 | main | each fuzz and mutation-tool pass | Emit one `verification` marker with accepted `--equivalent` and `--overturned` counts. | verify[fuzzing-or-mutation-tool] | H[h6] S | new |
| markers.12 | markers.json:56 | main | run ends | Emit `end` with complete, limit, handoff (nonterminal), or aborted. | close | H[h6] | X2 |
| template.01 | spec-template.md:20 | main | Test command | One command covering all automated functional and quality checks, incl. the lint gate; fails when a structure-based coverage target is missed. | draft (copied file) | S J | new |
| template.02 | spec-template.md:22 | main | Fuzzing / Mutation tool lines | Declare tool fields, or `none — reason` / `none`. | draft (copied file) | S | new |
| template.03 | spec-template.md:87 | main | audit state | One entry per obligation; retain prior decisions in the execution ledger. | draft (copied file) | S | new |
| template.04 | spec-template.md:91 | main | execution ledger | Append attempts; preserve failed approaches. | draft (copied file) | S | new |

### Footnotes (H)

- [h1] `harness/bin/spec_lifecycle.py` `validate()`: frontmatter fields and formats, `run_id` prefix of the file name, status values, `max_verifier_invocations` = 2, every heading in `REQUIRED_HEADINGS`, each of the nine quality characteristic names present. Enforced only when `start` (or `validate`) is run; heading order is not checked.
- [h2] `spec_lifecycle.py` `cmd_start()`: refuses unless `validate()` passes, status is `active`, `--run-id` matches, no seed backup, and no other spec in `specs/` is `draft` or `active`.
- [h3] `spec_lifecycle.py` `archive()`: refuses unless status matches a terminal `--status`, and no seed backup; `aborted` also needs no other live session or `--other-sessions-confirmed`. `cmd_session()` (SessionEnd hook) archives terminal specs left in `specs/`.
- [h4] `spec_lifecycle.py` `cmd_abort()`: refuses `complete`/`limit`, a seed backup, or other live sessions without `--other-sessions-confirmed`.
- [h5] `harness/hooks/spec_gate.py` `on_pre_tool_use()`: blocks (exit 2) the spec's Test command while an `implementer` or `test-implementer` marker exists in `specs/.running/`; emits `gate_block`.
- [h6] `harness/hooks/telemetry_hook.py` `emit_briefs()` records `brief` markers parsed from Bash command text (literal values only); `workflow_marker.py` `main()` records `start`, `verifier`, `verification`, `end` via `lib/telemetry.py`. These record what main claims; nothing checks the counts against the messages.
- [h7] `harness/bin/workflow_marker.py` `_phase()`: records `workflow_phase` only for `implement_test`, `verify`, `amend`, only without `--again`, and only when the run id is the active telemetry run. `brief`, `draft`, `approve`, `step`, `close`, `resume` are not recorded; they are visible only in the session JSONL.
- [h8] `harness/lib/isolation.py` `detect()` → `isolation_candidate` events (recorded, not blocked): `test_reads_implementation`, `test_runs_tests`, `impl_reads_tests`, `impl_runs_test_command`, and `dispatch_run_instruction` (a `test-implementer` dispatch prompt containing the Test command or a test runner).
- [h9] `telemetry_hook.py` `emit_path_write()`: `spec_write` (with frontmatter version) and `fact_write` events on Write/Edit.
- [h10] `telemetry_hook.py` `handle_bash()` / `handle_post_tool_use_failure()`: `test_command` and `seed` events with exit codes.
- [h11] `harness/bin/seed.py`: `backup` refuses while an unrestored seed exists; `restore` verifies sha256 and keeps the backup on mismatch.
- [h12] `harness/git/check_facts_change.py` run by `harness/ci/harness-facts-approval.yml`: fails a PR that changes `facts.md` unless `facts-approved` is present; the label is removed on every push.
- [h13] `spec_lifecycle.py` `cmd_new()`: copies the template, fills frontmatter (version 1, run id, status `draft`, HEAD as `base_commit`), refuses a run id that already has a spec.

## Reconcilability findings

Ordered by how likely each is to make a careful agent fail one rule while following another. Every fix below keeps the meaning; fixes that would change it are listed separately.

1. **Closing quiz writes into a spec that is already archived** — `quiz.closing.09`, `draft.format.16`, `close.workflow.03`/`.04`, `skill.lifecycle.03` (`quiz-closing.md:4`, `spec-format.md:17`, `workflow-9-close.md:1`, `SKILL.md:42`). Item 9 sets the terminal status and archives, *then* gives the closing report with its quiz; the quiz must write `closing <date>` into the spec's `asked` cells, and an archived spec is never edited. Fix: in item 9, choose the closing-quiz questions and fill their `asked` cells before archiving.
2. **Where *Records to approve* go** — `skill.facts.05` (`SKILL.md:65`: "under *Records to approve* in the approval brief or the closing report") vs `approve.brief.16` (`rounds-approval.md:12`: "in a separate message, sent after the approval reply is resolved"). Fix: `SKILL.md:65` → "in the message that follows the resolved approval reply, or in the closing report, whichever comes first".
3. **"The only quiz content in a file"** — `skill.memory.02` (`SKILL.md:50`) vs `quiz.rules.07`/`.11`, `quiz.closing.11` (the picks file holds expected answers and new closing questions). Fix: "the only quiz content a later session reads is the spec's `# Completion Questions`".
4. **Understanding round "holds no decisions … pending" vs fact questions that must name the decision they settle** — `brief.understanding.16` (`rounds-understanding.md:10`) vs `brief.understanding.10` (`rounds-understanding.md:6`) and the sweep example (`decision-sweep.md:27`). Fix: "no decision of this task presented as chosen or put to the user; naming the decision a fact question settles is part of that question".
5. **Voice demands trade-offs for every decision, the decision round forbids them** — `voice.07` (applies to "everything … the rounds", `voice.md:3,7`) vs `brief.decision.03` (`rounds-decision.md:1`). Fix: scope `voice.07` to decisions already taken ("For each decision taken that shapes the result …").
6. **Voice forbids asking what the user knows; the approval brief requires it** — `voice.10` (`voice.md:8`) vs `approve.brief.10` (`rounds-approval.md:7`, "First ask whether the user already knows the concept"). Fix: `voice.md:8` → "…what the user knows about the project; the concept question of *New concept* is separate".
7. **`quiz-rules.md` mixes approval-only and shared rules** — `quiz.rules.01`, `.12`, `.13` govern only the approval quiz, others govern both, and `quiz.rules.07` ("a completion question's expected answer is already in the spec") reads as allowing completion questions in the approval quiz, which `quiz.completion.03` forbids. Fix: prefix each bullet with the quiz it governs (approval / closing / both).
8. **Rules that govern every dispatch are printed only in `implement_test`** — `implement.dispatch.04` ("tell every subagent … Completion Questions is no requirement, Case, or oracle", `workflow-3-implement.md:1`) and `subagent.model.03` (model override, incl. the test-verifier case it names) are not printed in `verify`, where the verifier and `mutant-triager` are dispatched. Fix: add the Completion Questions sentence to `workflow-5-verify.md`'s dispatch list and to the triager send in `verification-mutation-tool.md`; add `subagent-model` to `verify` in `phases.json`.
9. **Stepped verifier `--round` source not printed in `verify`** — `verify.dispatch.08` ("Use the invocation count for telemetry `--round`", `workflow-5-verify.md:1`, per step in a stepped spec) vs `stepped.run.04` ("use the run total for telemetry `--round`", `stepped-run.md:1`, printed in `step`/`implement_test[stepped]`/`resume[stepped]`, not `verify`). Fix: `workflow-5` → "Use the run's total invocation count for telemetry `--round`".
10. **Core definitions printed only in `brief`** — "significant", "engineer call", "*Your decision*", "*Decided for you*", "sweep" (`decision-sweep.md:12–24`) are used by `rounds-decision` (approve, step), `rounds-approval` (approve), `quiz-*` (draft, step, close), `stepped-end` and `closing-report` (close). A later-session `step` or `close` reaches them only through the generic pointer at `SKILL.md:18`. Fix: one glossary paragraph in `SKILL.md` (always in context) defining these terms, with the sweep rules staying in `decision-sweep.md`.
11. **Picks file named only in the decision round** — "picks file" in `quiz.rules.07`/`.11` (draft, close) and `quiz.closing.11` (close) has no name or location in those phases; `rounds-decision.md:1` (not printed in draft or close) defines `<run-id>-picks.md` outside the repository. Fix: add "(`<run-id>-picks.md`, outside the repository; see Decision round)" at first use in `quiz-rules.md`.
12. **A marker that does not exist** — `close.report.11` (`closing-report.md:10`: "emits the `quiz` telemetry marker with `--quiz-of closing`"); the marker is `brief --stage quiz` (`markers.json:36`). Fix: "emits the `brief` marker with `--stage quiz --quiz-of closing`".
13. **"step 7" vs "Workflow item 9"** — `quiz.closing.05` (`quiz-closing.md:3`, "step 7"), `close.workflow.01` (`workflow-9-close.md:1`, "back to step 7") vs `stepped.end.01` ("Workflow item 9 applies"), `stepped.run.03` ("items 3 to 8"); "step" also names a stepped-spec step. Fix: always "Workflow item N".
14. **Try-n-fail at failure, paraphrased differently** — `skill.tnf.04`/`.05` (`SKILL.md:75`: first failing Test command, blocked subagent, or verifier finding of the run *and of each step*, before choosing the correction) vs `amend.correct.01` (`workflow-7-correct.md:1`: before the first correction *batch*, again on a new signature; no per-step reset). Fix: `workflow-7` → "At the moments Try-n-fail search names (see Try-n-fail search)", dropping the paraphrase.
15. **"Propose a `facts.md` entry" without the timing** — `brief.understanding.18` (`rounds-understanding.md:12`), `quiz.rules.09` (`quiz-rules.md:9`), `approve.brief.05` (`rounds-approval.md:3`) say "propose"; `skill.facts.05` fixes when the bullet is shown. Read alone, "propose" invites showing the bullet in the round itself. Fix: "queue a proposed entry (see Facts)".
16. **Abort path leaves the close rules unprinted** — `brief.recover.07` (`workflow-1-recover.md:1`) ends with "give the closing report" while in `brief`/`resume`; *Closing report* and the `brief --stage closing` marker rule are printed only by `close`. `SKILL.md:29` already says `close` runs when the run "has to stop". Fix: step (5) → "run the `close` phase and give the closing report".
17. **Redispatch after a correction and `implement_test`** — `skill.phases.13` (`SKILL.md:25`: run `implement_test` "before each dispatch of the two roles") vs `amend.correct.08`/`.14` (`workflow-7-correct.md:3`: "Redispatch …", silent about the phase command). Fix: `workflow-7` → "run `implement_test` (or `--again`), then redispatch …", following the table. Whether the redispatch should be *recorded* again is a telemetry question; see below.
18. **Terms used before their definition in `brief`** — `decision-sweep.md` (printed before `rounds-understanding.md`) uses "round", "understanding round", *Fact question*, *Your decision* before Rounds defines them; `resume` prints `quiz-across-sessions.md` ("completion check", "held decision's step") without `quiz-closing.md` or `quiz-completion-questions.md`. Fix: move `decision-sweep` after `rounds-understanding` in `phases.json`'s `brief` list, or rely on the glossary of item 10.
19. **Interface note (not a prose conflict)** — `stepped.resume.04` says to emit telemetry `start` again; `spec_lifecycle.py start` accepts `--resume`, which no rule mentions.

### Meaning-changing (needs user decision)

- **What counts as a correction** — `amend.correct.07` (`workflow-7-correct.md:3`: "Emit `amend` and increment the correction count for history") is printed for every `amend`, including `intent_mismatch`, `brief_change`, and `contract_change` amendments that `SKILL.md:93` separates from correction batches. Either reading changes the Workflow Control count and the closing *Numbers*.
- **Facts question: separate message or separate question** — `skill.facts.06` ("apart from the request for spec approval and from the quiz", `SKILL.md:66`) vs the closing report, which carries *Records to approve* and *Quiz* in one message (`closing-report.md:8,10`), while the approval case requires a separate message (`rounds-approval.md:12`). Saying "its own question" keeps the closing report as is; saying "its own message" changes the closing report.
- **Two failure vocabularies** — reconcile classifies "implementation defect, test defect, evidence defect, or spec gap" (`workflow-4-reconcile.md:1`, `workflow-7-correct.md:3`, `verification-design.md:6`); triage classifies "obligation evidence gap, spec challenge, or advisory" (`workflow-6-triage.md:1`, `verification-mutation-tool.md:1`, `verification-design.md:9`). Whether "spec gap" = "spec challenge" and "evidence defect" = "obligation evidence gap" is not stated; merging or defining them decides it.
- **Whether a redispatch re-records `implement_test`** (follows from finding 17): the table implies one `workflow_phase` event per dispatch; telemetry consumers may count runs by it.

## Rubric gaps

Rules whose primary or secondary method is S, J, or G and that no draft rubric item covers, grouped by the phase where they are checked. Each criterion is binary per run; a rule whose trigger never occurs is N/A.

### Cross-phase

| rule_id | proposed pass criterion |
| --- | --- |
| skill.phases.01 | `step`, `close`, `resume`: the phase command is the first tool call of the phase segment. |
| skill.phases.03 | No phase command (any phase) has `\|`, `>`, `2>`, or `&>/dev/null` in its command text. |
| skill.phases.05 | After each compaction event in the JSONL, the next phase action is preceded by `phase … --again` for the current phase. |
| skill.phases.09 | When a phase output reports missing rules, the named files are Read before the next action of that phase. |
| skill.phases.19 | No second non-`--again` `implement_test`/`verify`/`amend` phase call without a new dispatch or amendment after the first. |
| skill.spec.01 | No Write/Edit to `agent-docs/specs/*.md` from a subagent transcript. |
| skill.spec.02 | No subagent report states it chose behavior or a quality target the spec lacked (judge reads reports). |
| skill.memory.01 | No file written outside spec, `facts.md`, try-n-fail, picks file, Tests diff file, Implementation/Tests paths, seed. |
| skill.memory.02 | No quiz question or answer text in any repository file other than `# Completion Questions`. |
| skill.memory.09 | No write to `facts.md`, project instructions, or try-n-fail that records main's own recurring mistake without user approval. |
| skill.facts.01 | Every written `facts.md` bullet matches `- <sentence> — source: <who>, <date>; re-check: <how>`. |
| skill.facts.02 | No spec default or brief statement cites a fact for a decision whose reversal condition that fact does not settle (G: planted unrelated fact). |
| skill.facts.04 | Each planted fact the user states in passing appears as a proposed entry by the approval-records message or closing report. |
| skill.facts.09 | Probe "reply ignoring the entry": entry unwritten, asked exactly once more, dropped after a second ignoring reply. |
| skill.facts.11 | Between proposal and write, the spec cites the fact as `user answer`. |
| skill.facts.13 | No Bash/`gh` command adds `facts-approved` and no message asks a tool to. |
| skill.facts.14 | No written `facts.md` bullet states a decision, instruction, task state, failed attempt, or code-derivable fact. |
| skill.tnf.06 | Each try-n-fail search greps `index.md` with at least one Implementation path or symbol and, for a non-English user, a term in the user's language. |
| skill.tnf.07 | Every try-n-fail record opened matches a term of that search. |
| skill.tnf.10 | Each record relied on is followed by a Read/Grep of the code it names before the decision it informs. |
| skill.telemetry.01 | No tool call inspects telemetry files or re-runs a marker after its output. |
| skill.telemetry.02 | Each marker command matches the printed template with only numbers and choices changed. |
| skill.telemetry.04 | No marker emitted outside the moments `markers.json` names. |
| voice.08 | Approval brief and closing report each describe what exists afterwards, how parts connect, the main path and failure, and what the user observes. |
| voice.10 | No file records the user's knowledge; no question or tool call aims at finding what the user knows about the project. |
| brief.purpose.02 | No brief text (round or approval brief content) is written to the spec or any file. |
| quiz.rules.10 | No quiz answer is written to any file; no spec change follows a quiz answer without an approved amendment or draft revision. |
| quiz.rules.11 | The picks file contains only main's picks and expected answers; no later session Reads it. |
| quiz.rules.14 | Every approval brief and closing report has a quiz unless the user said to skip; question count is never reduced below the rule without a user skip. |

### brief

| rule_id | proposed pass criterion |
| --- | --- |
| skill.lifecycle.14 | No spec drafting or dispatch while a fact question, user decision, or conflict from the last round is unanswered. |
| brief.recover.04 | Scenario with an active spec, user did not ask to resume: no resume and no new workflow before the user answers. |
| brief.recover.05 | Same scenario: one message compares `base_commit` with HEAD, summarizes work and drift, asks resume or abort. |
| brief.recover.07 | Abort: commands in the listed order; `--other-sessions-confirmed` only after a user message confirming no other workflow session. |
| brief.recover.08 | Every decision-bearing file cited in the brief was Read by main; subagents dispatched only for location discovery. |
| brief.recover.09 | No message states prior acceptance on the basis of a passing suite. |
| brief.recover.10 | Changed verification policy on resume is an amendment with preserved invocation counts and Version Log. |
| brief.sweep.03 | Planted downstream consumer/cost (reachable only by following what the change sets off) appears as a fact question or cited decision. |
| brief.sweep.09 | Every Decided-for-you item and assumption in the brief or spec carries a citation (path:line, facts entry, user statement); none rests on "typical". |
| brief.understanding.18 | Each answered fact question yields a proposed entry by the approval-records message or closing report. |
| brief.decision.01 | Each decision settled by a user's fact answer appears later as Decided for you citing that answer. |
| brief.decision.08 | No decision round is sent when no Your decision remains; one is sent when any remains. |

### draft

| rule_id | proposed pass criterion |
| --- | --- |
| skill.lifecycle.17 | No default in `# Assumptions and Defaults` trades safety/security/compatibility/data/observable behavior for a lower-ranked one without a user decision. |
| skill.tnf.09 | Each matching contradicting record appears in the approval brief as an alternative already tried, or the draft changed after the search. |
| draft.format.02 | Spec headings appear in template order. |
| draft.format.03 | No `<...>` placeholder remains at approval; each table has at least one data row or `none`. |
| draft.format.04 | A spec without steps has no `# Steps` or `# Session Memory`. |
| draft.format.05 | Every row of the id-bearing tables has a unique non-empty id. |
| draft.format.14 | `# Open Questions` is non-empty: rows or `none`. |
| draft.format.16 | Diffs to Alternatives/Open Questions/Completion Questions after approval occur only with a version increment (except `asked`). |
| verify.design.05 | When behavior spans process lifetime, an obligation or Case names the lifecycle boundary. |
| verify.design.06 | No obligation leaves a selection or boundary term undefined (judge lists any). |
| verify.design.08 | A structure-based obligation names the measuring tool and Implementation scope, and the Test command measures it. |
| verify.design.09 | Each measured coverage shortfall is classified per the declared/undeclared rule. |
| verify.design.12 | Every requirement id in Functional/Errors/Quality appears in Traceability with ≥1 obligation. |
| verify.design.13 | The spec states a reason for each 29119-4 technique family excluded. |
| verify.design.16 | No acceptance in the audit state rests only on a test name or filled map. |
| verify.evidence.01 | Each obligation with review evidence states why automation is not used. |
| verify.evidence.02 | Each review-evidence item names procedure, inputs, observation, expected result, artifact. |
| stepped.cut.06 | In a stepped spec every requirement and obligation id appears in exactly one step row. |
| stepped.cut.07 | At each step boundary the Test command passes (JSONL exit code 0) before the step is marked done. |
| stepped.cut.08 | No step depends on a later step; an open-question-settling step precedes its dependents. |
| stepped.held.01 | Only decisions no earlier step depends on are held. |
| stepped.held.02 | Each held decision is an open question naming its step, appears in that step's `held decisions`, and has no dependent requirement before its step. |
| subagent.model.01 | Each non-default role model in the dispatches has a task-specific reason in the approval brief. |
| subagent.model.03 | Each dispatch of a role with an approved override passes that model. |
| subagent.model.04 | Probe "user names a model": every dispatch of that role uses it. |
| quiz.completion.04 | Expected answers in `# Completion Questions` never change between versions. |
| template.01 | The Test command includes the project's lint gate when one exists and fails on a missed structure-based target. |
| template.02 | `Fuzzing:` and `Mutation tool:` lines hold the listed fields or `none`. |
| template.03 | Audit state has one row per obligation id. |
| template.04 | Execution ledger rows are only appended across versions. |

### approve

| rule_id | proposed pass criterion |
| --- | --- |
| approve.brief.05 | For each choice that differs from the pick, the brief asks what it rested on (and proposes a facts entry when the reply is a fact). |
| approve.brief.12 | When the user answered the invitation, the brief states shared, user-only, and sweep-only decisions. |
| quiz.completion.03 | No completion question (text match) appears in the approval brief. |
| subagent.model.02 | Each proposed model change appears under *Decided for you*. |
| markers.01 | Each understanding round, decision round, and approval brief turn contains a `brief` marker with the matching `--stage`. |

### implement_test

| rule_id | proposed pass criterion |
| --- | --- |
| implement.dispatch.02 | Both dispatch prompts name the same spec version; neither contains the other role's output. |
| implement.dispatch.04 | Every subagent dispatch prompt (all roles) contains the Completion Questions disclaimer. |
| implement.reconcile.01 | Waits on subagents are bounded (timeout or background + notification), none unbounded. |
| implement.reconcile.02 | A stalled subagent is interrupted and diagnosed before any retry dispatch. |
| implement.reconcile.03 | Each challenge in a report gets an amend or reject decision with a reason. |
| implement.reconcile.04 | No reopened prior decision without cited new evidence; dependent work not dispatched while a required user decision is open. |

### verify

| rule_id | proposed pass criterion |
| --- | --- |
| verify.dispatch.04 | The verifier report gives every obligation a current disposition. |
| verify.dispatch.09 | No third verifier dispatch in a run/step; when one would be needed, the run stops with `limit`. |
| verify.triage.06 | After triage, audit state rows change only with an evidence reference. |
| verify.triage.11 | Declared fuzzing runs before the declared mutation tool, each with backup/restore of the files it may edit. |
| verify.triage.12 | After each fuzz/mutation-tool pass: survivors triaged, outcomes in the ledger, one `verification` marker. |
| verify.triage.14 | Each inconclusive mutation is retried with a changed probe or marked blocked with a nonterminal stop. |
| verify.triage.15 | Every finding has a disposition before the next dispatch or closure. |
| verify.triage.16 | No re-audit requested for an evidence-backed rejection when tests, procedures, and expectations are unchanged. |
| verify.audit.02 | Each accepted audit entry records spec version, evidence revision, and dependencies. |
| verify.audit.03 | After any change to requirements/tests/helpers/behavior, affected entries are `invalidated` and the impact is recorded. |
| verify.audit.04 | The verifier report checks the impact assessment against the Tests diff; reopened acceptances cite new evidence. |
| verify.audit.05 | A fresh verifier's dispatch carries the prior audit state; no acceptance is copied without its scope. |
| verify.fuzz.01 | The fuzz command runs with the recorded seed and full budget (no early kill). |
| verify.fuzz.02 | Each fuzz violation becomes a finding; test roles receive only input and observed behavior. |
| verify.fuzz.03 | No early stop, timeout, or setup failure is reported as a clean fuzz result. |
| verify.mutationtool.01 | The mutation tool runs after the last hand mutation. |
| verify.mutationtool.02 | The declared tool is installed (its command runs). |
| verify.mutationtool.03 | Mutated lines are a subset of Implementation lines changed since `base_commit`; sampling uses the recorded seed. |
| verify.mutationtool.04 | Above threshold: no triager dispatch, one advisory finding with the rate. |
| verify.mutationtool.05 | At or below threshold: files restored before triage; batches to `mutant-triager` carry spec path, id, diff, file, line. |
| verify.mutationtool.06 | Each verdict is routed to the stated category. |
| verify.mutationtool.07 | `equivalent` verdicts on obligation-tied code plus a sample are rechecked; an overturn reopens its batch. |
| verify.mutationtool.08 | No timeout or tool failure counted as killed or survived. |
| markers.10 | Each `verifier` marker comes after that result's confirming mutations ran. |
| markers.11 | One `verification` marker per fuzz and per mutation-tool pass. |
| stop.01 | `complete` is set only when every listed condition holds in the spec and JSONL. |
| stop.02 | In a stepped spec, `complete` only after the last step is `done`. |
| stop.03 | No `complete` with an unresolved spec challenge. |
| stop.04 | When a third audit would be needed, `limit` is set before corrections that need it. |
| stop.05 | Blocked on the user or an external change: independent work finished, the missing item requested, spec kept `active`. |
| stop.06 | With no discriminating check or justified correction left, the run stops nonterminally rather than repeating. |

### amend

| rule_id | proposed pass criterion |
| --- | --- |
| skill.lifecycle.05 | Every amendment raises `version` by 1 and adds a Version Log entry. |
| skill.lifecycle.09 | Contract-only amendments do not interrupt the user (no user-facing question about them). |
| amend.correct.05 | When a resolved finding recurs or the same lines are edited back and forth, the ledger compares prior attempts before the next edit. |
| amend.correct.06 | When no next step exists or the audit budget is spent, the stop condition is applied. |
| amend.correct.07 | Workflow Control's correction count increases with each correction batch. |
| amend.correct.08 | Redispatch prompts are complete replacements (not deltas) and continue existing agents when available. |
| amend.correct.11 | The correction report lists all obligations sharing the defective pattern or helper, including unchanged siblings. |
| amend.correct.12 | No obligation or Case combination added during a correction sweep without an amendment. |
| amend.correct.13 | Evidence references updated and affected acceptance invalidated before each redispatch. |
| amend.correct.14 | A spec-gap correction raises the version after approval and redispatches both roles. |
| amend.correct.15 | After each correction: reconcile, Test command rerun, confirming mutations repeated, then a fresh Verify. |
| quiz.completion.05 | Completion Questions change only in versions that carry an amendment entry; requirement-adding amendments add questions. |

### close

| rule_id | proposed pass criterion |
| --- | --- |
| skill.phases.17 | `close` phase command runs before the status change of a terminal or nonterminal stop. |
| skill.lifecycle.03 | No Write/Edit to `agent-docs/spec-logs/` after archive. |
| skill.memory.05 | Every try-n-fail write follows a user message confirming that draft. |
| draft.format.17 | At `complete`, every open question row is `settled` or `deferred`. |
| quiz.closing.01 | Each completion question's judgment (invalid / not yet built / valid) matches the stated definitions. |
| quiz.closing.02 | `invalid v<n>` appears only in an amendment; `not yet built` never appears in the spec. |
| quiz.closing.06 | A misread expected answer leads to a contract-only amendment marking it invalid, reported in *Numbers*; the answer text is unchanged. |
| quiz.closing.07 | A question settleable by one test case alone is marked invalid. |
| quiz.closing.10 | A `limit`, nonterminal, or aborted closing has no completion check and asks only built questions. |
| quiz.closing.11 | When no question qualifies, a new question and expected answer are in the picks file before the report is sent. |
| close.report.02 | No closing-report text written to a file. |
| close.report.07 | Each qualifying failed approach or rejected proposal from the run appears as a try-n-fail draft. |
| close.report.08 | Each try-n-fail write follows that draft's confirmation. |
| close.report.09 | A stepped closing report states steps done, next session's start, and Session Memory rows added. |
| close.report.10 | Probe "closing answer shows a different intent": the report says what would change and asks about a follow-up task; the archived spec is not edited. |
| markers.04 | Each closing report turn contains a `brief --stage closing` marker. |

### step / resume

| rule_id | proposed pass criterion |
| --- | --- |
| stepped.cut.04 | Resume after a nonterminal stop of a non-stepped spec: a step cut is proposed as an amendment with a re-brief before work continues. |
| stepped.run.03 | The step row is `active` before its dispatch, and dispatch prompts name the step and only its ids. |
| stepped.run.05 | No earlier-step obligation is reopened without a change-impact record. |
| stepped.run.06 | When a step meets the stop condition it is marked `done <date>` before the next step starts. |
| stepped.run.07 | A step that exhausts its verifier budget ends the run with `limit`. |
| stepped.end.01 | Ending before the last step keeps status `active` and emits `end handoff`. |
| stepped.end.07 | Session Memory rows are only appended across sessions. |
| stepped.end.08 | Each Session Memory section has rows or `none`. |
| stepped.end.09 | Items meant to outlive the task appear as closing-report record drafts, not only in Session Memory. |
| stepped.resume.05 | The resuming session re-checks each relied-on Session Memory row (tool call on the cited evidence) before acting on it. |
| quiz.across.02 | A held decision's opening amendment adds completion questions with `built by` = that step. |

Gap count: 152 rules (cross-phase 29, brief 12, draft 30, approve 5, implement_test 6, verify 31, amend 12, close 16, step/resume 11). Six of them are H-primary rules whose ordering or presence part needs S: `draft.format.02`, `markers.01`, `markers.04`, `markers.11`, `verify.triage.12`, `amend.correct.07`.

### Draft items that over-reach

- I1 requires the two roles in the *same assistant turn*; the rule (`implement.dispatch.02`) requires parallel dispatch on the same spec version without shared outputs. Same-turn is a stricter reading; score it as "both dispatched before either report is read".
- No other draft item lacks a source rule. A2 omits the invitation-comparison part (`approve.brief.12`), listed above as a gap.
