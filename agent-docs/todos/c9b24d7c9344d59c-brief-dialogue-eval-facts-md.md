---
commit: 2fd7f048a8b24c24962126eb3cb85a257964a79d
---

# Align the brief dialogue evaluation with facts.md

## Goal
Make `evaluation/brief_facts` dialogue runs grade the fact handling that doggy-workflow has used since harness 0.51.0: one file `agent-docs/facts.md`, read whole before the understanding round, entries written only after the user approves their text.

## Observation
- `evaluation/brief_facts/run_dialogue.py:150-154` seeds each `seed_facts` item as its own file under `agent-docs/facts/`, and `copy_written` (line 102) collects written facts from that directory.
- `evaluation/brief_facts/grade_dialogue.py:12-13` expects one output file per fact named `facts-<16 hex>-<dimension>-<name>.md` holding `dimension:`, `fact:`, `source:`, `asked for:`, `re-check:`.
- `grade_dialogue.py:189` passes when each answered fact has such a file; `grade_dialogue.py:209` passes when seeded facts are found by search without listing or opening unrelated ones.
- `evaluation/brief_facts/dialogue_grader.md:56` and `evaluation/brief_facts/README.md:26,72` describe the same per-file format.
- `evaluation/brief_facts/cases/mail-backfill-facts.json` is the only case with `seed_facts`.
- The dialogue evaluation has no criterion for the quiz, the closing report, or the approval of a proposed `facts.md` entry.
- No dialogue or single-message measurement has been run against the 0.51.0 skill text.

## Next Step
- Seed `seed_facts` as bullets of `agent-docs/facts.md`, collect that file from the run, and replace the two fact criteria in `grade_dialogue.py` with: a proposed entry is shown before it is written, an entry is written only after the simulated user approves it, and an unrelated seeded fact does not appear as an assumption.
- Decide with the project owner whether the simulated user answers the quiz or skips it, then run the single-message cases against the 0.51.0 skill and record the result in `evaluation/brief_facts/runs.md`.

## Related
- `harness/skills/doggy-workflow/SKILL.md` sections Memory, Quiz, Closing report
- `evaluation/brief_facts/README.md` line 14 states the mismatch
