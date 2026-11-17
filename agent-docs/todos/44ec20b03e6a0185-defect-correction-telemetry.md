---
commit: 1b72f1765e1daacc34e1e4d727807ff084723eeb
---

# Record defects corrected by verifier findings and by mutations in telemetry

## Goal
For each doggy-workflow run, telemetry records how many errors were corrected because of test-verifier findings, split into test defects and implementation defects, and how many were corrected because of mutations.

## Observation
- `verifier_result` (harness/lib/telemetry.py) records only `round`, `result`, `findings`, `seeds_run`, `seeds_detected`; `verification_result` records only mutant and fuzz counts. Neither says what a finding or mutant led to (test fix, implementation fix, spec amendment, dismissal).
- The `amend` phase marker's `--reason correction` does not say whether the correction batch changed tests or implementation, or whether a verifier finding or a mutation triggered it.
- On 2026-11-16 this split could only be obtained by having subagents read session transcripts of five projects that have the harness installed (learn-to-tell, network-analysis, LLM-wiki, clip-manager, blog), about 210 verifier results.
- In two of those sessions, implementation bugs were found by main or by the test run before the verifier, not by a verifier finding; a defect's source therefore needs its own field, separate from its kind.

## Next Step
- Ask the project owner: whether "corrected by mutation" means confirming mutations, mutation-tool survivors, or both; whether spec amendments and dismissed findings are also counted; then decide whether this extends the `verifier`/`verification` markers or adds a marker emitted at the correction batch (`amend --reason correction`).

## Related
- harness/bin/workflow_marker.py, harness/lib/telemetry.py, harness/skills/doggy-workflow/SKILL.md, analytics/importer.py
