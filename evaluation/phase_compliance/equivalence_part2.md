# Equivalence check, part 2: A (0.55.0) → B2

Rules checked: 146 (`implement.`, `verify.`, `amend.`, `close.`, `stepped.`, `subagent.`) · equivalent: 132 · allowed B1 change: 11 · drift: 3 (1 changes what a compliant agent does, 2 wording-only risk). Reverse direction: 0 added rules beyond the allowed B1 fixes, apart from the order constraint in the first drift row.

Paths: `harness/skills/doggy-workflow/phases/` in A (commit a659104, harness 0.55.0) and in the B2 draft (not kept as a commit; B2 with the drifts below fixed is commit 5cba48c, harness 0.55.1). Line numbers are file lines of those versions.

Phase printing, computed from both `phases.json`: the only difference is `subagent-model`, which B2 also prints in `verify` (B1 finding 8). Every other fragment is printed in the same phases under the same `when` conditions. `markers.json` and `spec-template.md` are byte-identical to A.

## Drift

| rule_id or B2 file:line | A text | B2 text | kind | severity | minimal fix for B2 |
| --- | --- | --- | --- | --- | --- |
| amend.correct.11 (B2 `workflow-7-correct.md:3`) | `workflow-7-correct.md:3`: "Redispatch complete replacement instructions, … never implementation diffs. Correct the cause across all declared obligations sharing the defective pattern or helper; report the full affected set …". The sweep comes after the redispatch and has no time marker, so it reads as the scope of the redispatched correction. | `workflow-7-correct.md:3`: "Correct the cause across all declared obligations … and report the full affected set …; add no undeclared combinations in this sweep. Before redispatch, update … Run the `implement_test` phase command (or print it with `--again`), then redispatch … Then reconcile …" | order | changes what a compliant agent does. B2 puts the correction (fixing the cause and reporting the affected set) before the redispatch, so read literally main makes the correction itself and reports it before the roles are sent out again. A has no such order. amend.correct.12 moves with it but is a prohibition and stays equivalent. | Restore the B1/A order and keep the B2 wording: "Emit `amend` … Run the `implement_test` phase command (or print it with `--again`), then redispatch complete replacement instructions, …: implementation defects receive …; test and evidence defects receive …. Correct the cause across all declared obligations … ; add no undeclared combinations in this sweep. Before redispatch, update evidence references and invalidate affected acceptance. A spec gap … Then reconcile, …" |
| stepped.run.04 (B2 `stepped-run.md:4`) | `stepped-run.md:1`: "count invocations in the step's `verifier invocations` cell and the run total in Workflow Control, and use the run total for telemetry `--round`" | `stepped-run.md:4`: "count invocations in the step's `verifier invocations` cell and the run total in Workflow Control." The `--round` clause now exists only in `workflow-5-verify.md:2`. | phase-printing changed | wording-only risk. A prints the `--round` rule in `implement_test`[stepped], `step`, and `resume`[stepped] (plus `verify` through Workflow item 5). B2 prints it only in `verify`. The `verifier` marker is listed only under `verify` in `markers.json`, so the rule is still in view when the marker is emitted. | Restore the clause: "…and the run total in Workflow Control, and use the run total for telemetry `--round`." |
| stepped.cut.01 (B2 `stepped-cut.md:5`) | `stepped-cut.md:5`: "15 rows or more (the number is `step_split_obligations` in `.harness/config.json` when that key is set)". The configured number replaces 15. | `stepped-cut.md:5`: "15 rows or more (or the number set as `step_split_obligations` in `.harness/config.json`)". This can be read as either threshold triggering the cut. | scope | wording-only risk. With the key set above 15 (say 25), a spec with 15 to 24 obligations gets a cut recommendation under the "either" reading and none under A. | "15 rows or more (when `step_split_obligations` is set in `.harness/config.json`, that number instead)", or restore A's parenthetical. |

## Allowed B1 changes (rewrite_report.md, section (b))

- implement.dispatch.04: the Completion Questions notice moved to `subagent-model.md:5`, and `workflow-3-implement.md:1` points to it (finding 8). It is now printed in draft, implement_test, and verify.
- subagent.model.01–04: also printed in `verify` (finding 8). The text is unchanged.
- verify.dispatch.08: "Use the run's total invocation count for telemetry `--round`" (finding 9).
- amend.correct.01: "Search try-n-fail at the moments Try-n-fail search names, before choosing the correction" (finding 14).
- amend.correct.08: "Run the `implement_test` phase command (or print it with `--again`), then redispatch …" (finding 17).
- close.report.11: "emits the `brief` marker with `--stage quiz --quiz-of closing`" (finding 12).
- close.workflow.01 ("Workflow item 7") and stepped.run.03 ("Workflow items 3 to 8"): finding 13.
- Reverse direction: `workflow-9-close.md:1` "Before archiving, choose the closing quiz's questions and write `closing <date>` …" (finding 1). It adds an ordering that B1 allows. close.workflow.03, .04, and .06 are otherwise unchanged.

## Meaning-changing items, as they touch this half

- What counts as a correction: `workflow-7-correct.md:3` keeps "Emit `amend` and increment the correction count for history" word for word. The `# Terms` entry for Correction batch does not say what is counted.
- Two failure vocabularies: these are kept unmerged and undefined in `workflow-4-reconcile.md:1`, `workflow-6-triage.md:1`, `workflow-7-correct.md:3` ("test and evidence defects"), `verification-design.md:6,9`, and `verification-mutation-tool.md:1`.
- Re-recording `implement_test` on redispatch: "(or print it with `--again`)" is kept, so the question stays open.
- Facts question in the closing report: `closing-report.md:8` keeps "each with its own question (see Facts)".

## Borderline cases accepted

- verify.design.17 (`verification-design.md:11`): "a blocking finding must identify … or cite" became "identifies … or cites". The sentence defines what makes a finding blocking, and a finding without these is still not blocking.
- verify.triage.07 (`workflow-6-triage.md:1`): "prioritizing blocking findings" became "blocking findings first". The priority order is the same.
- verify.dispatch.05, .06, .09 (`workflow-5-verify.md:2`): the budget sentences now come before the dispatch sentence. A already said "Before dispatch", so the order is unchanged.
- implement.dispatch.01 (`workflow-3-implement.md:1`): "Emit `implement_test`; dispatch" became "…, then dispatch". In A, SKILL.md Telemetry already puts the marker before the parallel roles.
- `workflow-8-stop.md:1`: the advisory sentence moved ahead of the stepped-spec sentence. The two statements are independent.
- Actor wording: "Main runs / selects / rechecks / marks" and "Test roles receive" became imperatives (`verification-evidence.md:1`, `verification-fuzz.md:1`, `verification-mutation-tool.md:1`, `verification-audit-state.md:1`, `verification-design.md:6`). Phase output is addressed to main, and the verifier's and `mutant-triager`'s actions keep their named actors.
- stepped.resume.01–05 (`stepped-resume.md:1`): "The next session reads …" became imperatives. Only the resuming session runs `resume`, so the actor is the same.
- stepped.held.02 (`stepped-held.md:1`): "the requirements … are not written" became "write none of the requirements". It is the same prohibition.
- stepped.end.09 (`stepped-end.md:7`): "when it ends" was dropped from the archiving clause. The clause is descriptive and no rule depends on it.
- close.report.07 (`closing-report.md:8`): the parenthetical qualifier for try-n-fail drafts became a colon clause. The qualifier is the same.
- Correction batch in `# Terms` (SKILL.md:48): this is the B1 glossary text with only "as … says" changed to "by".
- Reverse direction, `voice.md:3`: the parenthetical list of what Voice covers became a colon list. Both are equally open on whether the list is complete, and `stepped-run.md:1` still applies Voice to the step brief by name.
- Reverse direction, `rounds-decision.md:1–5`: the skip test and the picks-file write now come before the presentation rules. The picks are still written "Before sending the round", and the listed-decision sentence still comes before the skip test.
- Outside this half (draft.workflow.01, for the other checker): `workflow-2-draft.md:1` "Run the understanding round and wait for the user's confirmation or correction, then the decision round" became "Run the understanding round and, once the user confirms or corrects it, the decision round when …". When no decision round follows, item 2 no longer says to wait. The SKILL.md `draft` row ("after the user has answered the rounds") still covers the wait.
