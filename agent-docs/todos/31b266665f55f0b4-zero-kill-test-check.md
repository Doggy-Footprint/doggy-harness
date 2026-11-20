---
commit: dcd1808afd6796da3ced28f5f0926d1bb05e72b3
---

# Check zero-kill tests so the test count stays bounded

## Goal
In a doggy-workflow run, tests added by the run that kill no mutant are examined, and those shown to detect nothing are reported to the user as removal candidates.

## Observation
- The project owner proposed on 2026-11-20 that an LLM check whether a test that kills zero mutants is meaningful.
- Workflow item 6 (`harness/skills/doggy-workflow/phases/workflow-6-triage.md`) and `harness/skills/doggy-workflow/phases/verification-mutation-tool.md` act only on surviving mutants, and every route they define adds or strengthens evidence. No workflow rule removes a test. `harness/agents/test-verifier.md` limits growth only with "Additional plausible tests are not automatically required."
- The mutation-tool step uses per-mutant outcomes (survived over executed); it collects no record of which test killed which mutant.
- The mutation tool mutates only Implementation lines changed since `base_commit`, sampled above the cap (`verification-mutation-tool.md`). A test of unchanged code therefore kills no mutant whatever it protects.
- Not checked: which of mutmut, Stryker, go-mutesting, and cargo-mutants report the killing tests per mutant, and which stop at the first failing test. Re-check: run each tool on a small project and read its report format.
- On 2026-11-20 this repository had no `pyproject.toml`, `package.json`, `go.mod`, or `Cargo.toml` at its root, so its own runs declare `Mutation tool: none`. Re-check: `ls pyproject.toml package.json go.mod Cargo.toml`.

## Proposal discussed on 2026-11-20 (the owner has not decided)
- Split zero-kill tests by obligation: a test that is the only evidence of an obligation is an evidence gap to strengthen; a test tied to no obligation, or to one with other evidence, is a removal candidate.
- Ask the LLM for one behavior violation that only this test fails on. Main injects it with `seed.py` and runs the Test command: detected keeps the test; none named, or not detected, reports the test to the user as a removal candidate.
- A test whose set of killed mutants is contained in another test's set is a second signal obtainable from the same test-by-mutant matrix.

## Next Step
- Ask the project owner to choose between measuring first and writing the rule directly; both were offered on 2026-11-20 and neither was chosen. Measuring first means: on runs of a repository that has a mutation tool installed, count the share of run-added tests that kill zero mutants and the share of those a person judges removable.

## Related
- harness/skills/doggy-workflow/phases/workflow-6-triage.md, harness/skills/doggy-workflow/phases/verification-mutation-tool.md, harness/agents/mutant-triager.md, harness/agents/test-verifier.md, harness/bin/seed.py
