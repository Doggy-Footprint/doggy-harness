# Store learned repo state inside the repository (opt-in), so it can be committed and shared across machines

## Problem

Everything TokenEconomizer learns about a repository (micro-skills facts, tool-pruning counters, loop-guard state) is stored under `~/.tokeneconomizer` (or `$TOKENECONOMIZER_HOME`), outside the repository. It cannot be committed, reviewed, shared with teammates, or follow the repo to another machine. Anyone who works on the same repo from several PCs, or in a team, has to re-learn the same facts from scratch on each one, which is the cost the tool exists to reduce.

## Request

Support an opt-in, per-repository state directory, for example `<repo>/.tokeneconomizer/`:

- A setting (or auto-detection when that directory already exists) that makes the learned, repo-specific data live inside the repository instead of the user home.
- Keep machine-specific and private data (errors.log, session transcripts, cost ledgers, absolute paths) in the home directory, and put only portable data (confirmed facts, pruned-tool list, thresholds) in the repo, in a diff-friendly format (JSON or Markdown, stable key order, no absolute paths).
- Make it safe to commit: no secrets or transcript excerpts, and a documented `.gitignore` snippet for the parts that should stay local.
- Merge-friendly: facts keyed by id so concurrent updates from two machines merge cleanly in git.

## Why `TOKENECONOMIZER_HOME` is not enough

It is one global directory per user, not per repository, and it has to be an absolute path, so it cannot be set in a committed `.claude/settings.json` and work for different users or machines.

## Context

Seen with the Claude Code plugin on Windows, where the same repo is used from several machines with different user names.

