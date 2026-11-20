# Subagent model

Installed agent definitions carry their effort and the repository's default model, chosen with `harness.py install|update --model sonnet|opus` (`mutant-triager` keeps its own). Propose a different model for a role only with a task-specific reason, such as concurrency, a security boundary, or a cross-module change for `implementer`, or a large obligation map for `test-verifier`. List such a proposal under *Decided for you* in the approval brief, and pass the approved model as the Agent tool's model override for that role's dispatches. A model the user names overrides both.

Tell every subagent you dispatch that `# Completion Questions` is no requirement, Case, or oracle.
