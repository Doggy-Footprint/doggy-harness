## Try-n-Fail Rule

Directory: `agent-docs/try-n-fail/`.

Records approaches a later task could plausibly try again: an attempt whose failure took real work to discover (an implementation, a run, or an investigation, not a reading of the code), or a concrete proposal the user rejected. Candidates come from a spec's execution ledger or a rejection in conversation. Show the draft to the user and write only after confirmation.

Records are found by search, not read up front: search `index.md` right before carrying out an approach and at the first failure, by the files, symbols, and nouns of the approach or failure, and open only the records that match. A record states what was observed; re-check it against the current code before relying on it.

Required file structure:

- `#` Title
- `## Goal` (what the attempts tried to achieve)
- `## Attempts` (table `| attempt | failure evidence | cause |`; cause marked `verified`, `hypothesis`, or `user rejected: <reason>`)
- `## Revisit Condition` (the observable change that would make another attempt worthwhile)

Append rows for new attempts at the same goal; never delete or edit existing rows. When the goal is dropped or an attempt later succeeds, mark the record stale with `python3 .harness/bin/records.py stale <path>`.
