# doggy-workflow rewrite B — report

A = harness 0.55.0 (commit a659104). B = B1, a reconciliation patch over A that was not kept as a commit; B2 (below) rewrote it, and B2 with the drifts found in `equivalence_part1.md` and `equivalence_part2.md` fixed shipped as harness 0.55.1 (commit 5cba48c). Rule source: `rule_inventory.md` (395 rules).

## (a) Changed files, A → B

| file | lines | words |
| --- | --- | --- |
| SKILL.md | 93 → 109 | 2067 → 2363 |
| phases.json | 101 → 102 | 124 → 125 |
| phases/closing-report.md | 11 → 11 | 378 → 379 |
| phases/decision-sweep.md | 30 → 30 | 875 → 854 |
| phases/quiz-across-sessions.md | 1 → 1 | 103 → 107 |
| phases/quiz-closing.md | 4 → 4 | 278 → 279 |
| phases/quiz-rules.md | 12 → 18 | 504 → 537 |
| phases/rounds-approval.md | 12 → 12 | 396 → 397 |
| phases/rounds-decision.md | 3 → 3 | 315 → 301 |
| phases/rounds-understanding.md | 12 → 12 | 721 → 744 |
| phases/stepped-run.md | 1 → 6 | 174 → 176 |
| phases/subagent-model.md | 3 → 5 | 89 → 104 |
| phases/voice.md | 9 → 9 | 326 → 346 |
| phases/workflow-1-recover.md | 1 → 4 | 157 → 165 |
| phases/workflow-3-implement.md | 3 → 3 | 106 → 101 |
| phases/workflow-5-verify.md | 1 → 1 | 184 → 186 |
| phases/workflow-7-correct.md | 3 → 3 | 220 → 225 |
| phases/workflow-9-close.md | 1 → 1 | 106 → 129 |
| all skill prose (SKILL.md + phases/*.md) | 269 → 301 | 9676 → 10070 |

Unchanged: markers.json, spec-template.md, and the other 17 fragments. The word growth is the `# Terms` glossary (about 300 words); SKILL.md core is 2327 words against the test limit of 3000.

## (b) Reconcilability findings and the B wording

1. Archived spec vs closing-quiz `asked` cells — `workflow-9-close.md:1`: "Before archiving, choose the closing quiz's questions and write `closing <date>` into their `asked` cells, because an archived spec is never edited." (inserted after the Session Memory sentence, before the status/archive sentences). `quiz-closing.md` keeps "write `closing <date>` into their `asked` cell" as the content rule; item 9 holds the order.
2. Where *Records to approve* go — `SKILL.md:81` (Facts): "Show the exact bullet under *Records to approve* in the message that follows the resolved approval reply, or in the closing report, whichever comes first, or at once when the user asks for the entry". `rounds-approval.md:12` unchanged and now agrees.
3. "Only quiz content in a file" — `SKILL.md:66` (Memory): "the only quiz content a later session reads is the spec's `# Completion Questions`".
4. Understanding round "no decisions … pending" vs fact questions naming their decision — `rounds-understanding.md:10`: "no decision of this task presented as chosen or put to the user (naming the decision a fact question settles is part of that question, and an inherited decision is described as it stands, not proposed)".
5. Voice trade-offs vs decision-round neutrality — `voice.md:7`: "For each decision taken that shapes the result, say what was chosen, …".
6. Voice "do not ask what the user knows" vs *New concept* — `voice.md:8` adds: "The *New concept* question of the approval brief asks about a concept, not about the project, and is separate."
7. `quiz-rules.md` scope — split into "These rules hold for both the approval quiz and the closing quiz:" (predict/apply, brief level, expected answers, comparing answers, never recorded, skip) and "The approval quiz also follows these:" (2 to 4 questions at the end of the approval brief, approval in the same message, approval without answers). The expected-answer bullet now reads "write the expected answer to each question written for this quiz in the picks file; a completion question asked at closing has its expected answer in the spec already", so it no longer reads as allowing completion questions in the approval quiz.
8. Rules for every dispatch printed only in `implement_test` — the Completion Questions notice moved to its one home `subagent-model.md:5`: "Tell every subagent you dispatch that `# Completion Questions` is no requirement, Case, or oracle." `workflow-3-implement.md:1` now says "Instructions are task-specific and complete, and include what Subagent model says every dispatch includes:". `phases.json`: `subagent-model` appended to the `verify` list (the only phases.json change), so the verifier and `mutant-triager` dispatches see both the notice and the model override. `SKILL.md` phase table row for `verify` adds "Subagent model".
9. Stepped `--round` source — `workflow-5-verify.md:1`: "Use the run's total invocation count for telemetry `--round`." (matches `stepped-run.md`).
10. Core definitions printed only in `brief` — new `# Terms` section in `SKILL.md:34–48` (always in context): Sweep, Significant, *Your decision*, *Decided for you*, Engineer call, Fact question, Assumption, Picks file, Brief item, Amendment / contract-only, Correction batch. Their rules stay where they were. `decision-sweep.md` now refers to it: "Engineer calls (see Terms) are what the approval brief explains …"; identity rule 5 says "When it changes a brief item (see Terms)".
11. Picks file name and location — defined in `# Terms` ("`<run-id>-picks.md`, outside the repository (the session scratchpad when there is one, otherwise the system temporary directory)"); `rounds-decision.md:1` now writes "to the picks file (see Terms)".
12. Non-existent `quiz` marker — `closing-report.md:10`: "emits the `brief` marker with `--stage quiz --quiz-of closing`".
13. "step 7" for a Workflow item — `quiz-closing.md:3` "(Workflow item 7)", `workflow-9-close.md:1` "back to Workflow item 7", `stepped-run.md:3` "run Workflow items 3 to 8".
14. Try-n-fail at failure paraphrased differently — `workflow-7-correct.md:1`: "Search try-n-fail at the moments Try-n-fail search names, before choosing the correction." (paraphrase dropped; SKILL.md's Try-n-fail search is the one home).
15. "Propose a `facts.md` entry" without timing — `rounds-understanding.md:12` "Queue a proposed `facts.md` entry for each answered fact; Facts says when to show it."; `quiz-rules.md:10` "(queue a proposed `facts.md` entry; Facts says when to show it)"; `rounds-approval.md:3` "queue a proposed `facts.md` entry when the answer is a fact".
16. Abort path without close rules — `workflow-1-recover.md:3` step (5): "run the `close` phase and give the closing report".
17. Redispatch after a correction — `workflow-7-correct.md:3`: "Run the `implement_test` phase command (or print it with `--again`), then redispatch complete replacement instructions, …". The "(or print it with `--again`)" keeps the recording question (meaning-changing item 4) open.
18. Terms used before their definition in `brief`, and `resume` without the completion check — covered by `# Terms` (fact question, *Your decision*); `quiz-across-sessions.md:1` adds the pointer "in the completion check (Quiz, printed by `close`)". `phases.json` `brief` order unchanged (moving the sweep would split the Rounds section).
19. `spec_lifecycle.py start --resume` unmentioned — no change: it is an interface note, and naming it would add a rule.

Style changes that carry no finding: `workflow-1-recover.md` split into one lead sentence and three sub-bullets (active spec, abort order, reading and acceptance); `stepped-run.md` split into a lead paragraph and four bullets, with the `limit` sentence moved next to the budget sentence. No sentence was dropped in either.

## (c) The four meaning-changing items, left as in A

- What counts as a correction — `workflow-7-correct.md:3` keeps "Emit `amend` and increment the correction count for history." The `# Terms` entry for Correction batch says only what a batch is, not what it counts.
- Facts question: separate message or separate question — `SKILL.md:82` keeps "apart from the request for spec approval and from the quiz"; `closing-report.md:8` keeps "each with its own question (see Facts)"; `rounds-approval.md:12` keeps the separate message for the approval case.
- Two failure vocabularies — `workflow-4-reconcile.md:1` keeps "implementation defect, test defect, evidence defect, or spec gap"; `workflow-6-triage.md:1` keeps "obligation evidence gap, a spec challenge, or advisory"; neither is defined in `# Terms`.
- Whether a redispatch re-records `implement_test` — `workflow-7-correct.md:3` says "Run the `implement_test` phase command (or print it with `--again`)", which does not decide it.

## (d) Tests changed

- `tests/test_brief_telemetry.py` (`test_k12_quiz_flags_state_what_they_count`): `self.assertRegex(self.flat, r"emits the `quiz` telemetry marker with `--quiz-of closing`")` → `self.assertRegex(self.flat, r"emits the `brief` marker with `--stage quiz --quiz-of closing`")`. Same guard (the closing-quiz reply emits the quiz marker), with the real marker name (finding 12).

No other test changed. `CITATIONS` in `tests/test_phase_rules.py` needed no change: no tracked citation phrase was added or removed.

Suite: `HARNESS_TEXT_TESTS=1 <scratch venv with hypothesis>/bin/python tests/run_parallel.py` — 1166 tests, 4 failures, 1 error, 93 skipped. The 4 failures are `test_installed_copies_equal_the_shipped_skill` and `test_installed_copies_carry_the_same_files` for `.agents/` and `.harness/`: the installed copies are A because `installer/harness.py update` was not run. They pass once it is run. The error is `test_session_metrics`, which fails to import (`pytest` not installed); it fails the same way on A. On A with system python, `test_brief_telemetry` and `test_isolation_telemetry` also fail to import (`hypothesis` missing); the scratch venv was used to run them on B.

## (e) Rules that could not be placed without changing meaning

None. No rule was dropped, and each of the 395 inventory rules keeps A's actor, trigger, and strength. The only new sentences are the `# Terms` definitions (which restate definitions A already uses), the fixes in (b), and the reasons A already states.

## B2

B2 = a full rewrite of every fragment and of `SKILL.md` over B1. `phases.json`, `markers.json`, `spec-template.md`, the fragment file names, and the `SKILL.md` frontmatter are byte-identical to B1. The rule-by-rule placement is in `rewrite_b2_map.md` (all 395 rules placed; none restored to A wording).

### Word counts, A → B1 → B2

Counted with whitespace splitting (`str.split`, the same as `wc -w`).

| file | A | B1 | B2 |
| --- | --- | --- | --- |
| SKILL.md | 2067 | 2363 | 2199 |
| phases/brief-purpose.md | 56 | 56 | 53 |
| phases/closing-report.md | 378 | 379 | 375 |
| phases/decision-sweep.md | 875 | 854 | 822 |
| phases/quiz-across-sessions.md | 103 | 107 | 104 |
| phases/quiz-closing.md | 278 | 279 | 275 |
| phases/quiz-completion-questions.md | 122 | 122 | 121 |
| phases/quiz-rules.md | 504 | 537 | 521 |
| phases/rounds-approval.md | 396 | 397 | 388 |
| phases/rounds-decision.md | 315 | 301 | 294 |
| phases/rounds-understanding.md | 721 | 744 | 684 |
| phases/spec-format.md | 354 | 354 | 349 |
| phases/stepped-cut.md | 307 | 307 | 306 |
| phases/stepped-end.md | 330 | 330 | 323 |
| phases/stepped-held.md | 85 | 85 | 85 |
| phases/stepped-resume.md | 80 | 80 | 75 |
| phases/stepped-run.md | 174 | 176 | 166 |
| phases/subagent-model.md | 89 | 104 | 104 |
| phases/verification-audit-state.md | 92 | 92 | 94 |
| phases/verification-design.md | 360 | 360 | 361 |
| phases/verification-evidence.md | 70 | 70 | 70 |
| phases/verification-fuzz.md | 42 | 42 | 41 |
| phases/verification-mutation-tool.md | 152 | 152 | 153 |
| phases/voice.md | 326 | 346 | 326 |
| phases/workflow-1-recover.md | 157 | 165 | 166 |
| phases/workflow-2-draft.md | 115 | 115 | 117 |
| phases/workflow-3-implement.md | 106 | 101 | 102 |
| phases/workflow-4-reconcile.md | 101 | 101 | 103 |
| phases/workflow-5-verify.md | 184 | 186 | 188 |
| phases/workflow-6-triage.md | 248 | 248 | 251 |
| phases/workflow-7-correct.md | 220 | 225 | 230 |
| phases/workflow-8-stop.md | 163 | 163 | 163 |
| phases/workflow-9-close.md | 106 | 129 | 129 |
| SKILL.md + phases/*.md | 9676 | 10070 | 9738 |
| markers.json rule sentences | 353 | 353 | 353 |
| total incl. markers.json rule sentences | 10029 | 10423 | 10091 |

The target (SKILL.md + phases + marker sentences at or below 9676) is not met: B2 is 10091 on that measure, 415 over. A's 9676 counts SKILL.md and phases only; on the same measure as A's figure B2 is 9738 (+62 over A, −332 under B1), and including marker sentences for both, 10091 against A's 10029 (+62). The B1 glossary (`# Terms`, 288 words in B2) and the B1 fixes account for more than the remaining gap; what is left after the rewrite carries rules, reasons the instructions keep, or examples that define a rule's scope (the decision-sweep CSV example, the parenthesised cases in Voice and the understanding round). `SKILL.md` without frontmatter is 2163 words against the test limit of 3000.

### What B2 changes beyond rewording

- Order: rules are stated in acting order where B1 had them out of order. Decision round: skip condition and the picks-file write come before the presentation rules. Workflow item 5: the invocation-budget sentences come before the dispatch sentence. Workflow item 7: the correction sweep and the evidence-reference update come before the redispatch sentence. Stepped resume: written as instructions to the resuming session.
- One home per rule: the stepped-spec sentence "use the run total for telemetry `--round`" is dropped from `stepped-run.md`; Workflow item 5 (printed by `verify`, where the verifier marker is emitted) already says "Use the run's total invocation count for telemetry `--round`". Telemetry's "Emit `implement_test` … Emit `verify` …" merged into one sentence.
- Phase table: the "Workflow items" column is folded into "it prints" as "Workflow item N" names, so the `step` row no longer lists items 3 to 8 as if `step` printed them (it does not; `stepped-run.md` says to run them). The "(the spec template is a file to copy)" note and the sentence listing which sections phases print (the table names them) are dropped.
- `rounds-approval.md`: *Records to approve* is a paragraph after the list instead of the last list item, since it is not part of the approval brief.
- `quiz-rules.md`: the three cases of a differing answer are sub-bullets; the two scope lines read "Rules for both the approval quiz and the closing quiz:" and "Rules for the approval quiz only:".
- Pointer form: "Facts says when to show it" (B1) is "(see Facts)" everywhere; the CITATION-tracked pointers ("(see Quiz)", "the rules above", "as above", "Workflow item 9", …) keep their exact form and count, so `CITATIONS` in `tests/test_phase_rules.py` is unchanged.
- No ALL-CAPS emphasis ("will NOT do" → "will not do").
- The four meaning-changing items keep A's wording and ambiguity: "Emit `amend` and increment the correction count for history"; "apart from the request for spec approval and from the quiz" and "each with its own question (see Facts)"; the two failure vocabularies (`workflow-4-reconcile.md`, `workflow-6-triage.md`); "Run the `implement_test` phase command (or print it with `--again`)".

### Tests changed

None. Every sentence the tests pin (wording checks gated by `HARNESS_TEXT_TESTS=1`, and the ungated ones in `test_installer.py`, `test_remove_progress.py`, `test_workflow_markers.py`) was kept as B1 had it, including the strings `test_remove_progress.py` checks in both the shipped copy and the installed `.agents/` copy (still A), so changing them would have failed the A copy. The B1 change to `tests/test_brief_telemetry.py` stays.

### Test result

`HARNESS_TEXT_TESTS=1 <scratch venv with hypothesis>/bin/python tests/run_parallel.py`: 1166 tests, 4 failures, 1 error, 93 skipped. The 4 failures are the installed-copy checks (`test_installed_copies_equal_the_shipped_skill` and `test_installed_copies_carry_the_same_files`, for `.agents/` and `.harness/`), which still hold A because `installer/harness.py update` was not run. The error is `test_session_metrics` failing to import `pytest`, as on A and B1. Everything else passes.
