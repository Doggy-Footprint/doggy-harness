---
version: 6
run_id: be2e81e92ec99a03
status: complete
base_commit: b65b0a261aba2198120712986689eb7156f88b20
max_verifier_invocations: 3
commit: b65b0a261aba2198120712986689eb7156f88b20
---

# User Intent
| id | stakeholder | intention | observable goal |
| --- | --- | --- | --- |
| I1 | project owner, as owner of each target repository | Each repository customizes the harness for its own use (its own conventions, lint enforcement, extra verification of implementations) only through additional files, and the customization survives every update | Files under `.harness/local/` and the text of `AGENTS.md` outside the harness block are byte-identical after install, update, and every migration; the harness reads each such file at a declared place |
| I2 | project owner | A customization is followed over harness text it disagrees with, on condition that the user can recognize the disagreement when the customization is added and when an update changes the harness text next to it | The agent is told at the write of a customization and at every session start until the user confirms it; the update report lists every customization the update affected |
| I3 | project owner, as harness developer | An agent changing `harness/` cannot remove or rename a declared customization point without saying, in a migration step, what happens to repositories that use it | The commit in this repository fails until the removed point is retired with a version and a note, and that version has a migration entry |
| I4 | project owner | Conflicts between a harness change and a repository's own files no longer pass silently | An edited harness file, a repository skill that shadows a new harness skill, an invalid config file, an unknown config key, and a repository Claude Code hook stored under `.harness/local/` each produce a line naming the file in update, doctor, or the session notice |

# Scope
In scope: a declaration of customization points shipped with the payload; one library that computes the state of every customization; a command to show states and to record the user's confirmation; a SessionStart notice and a Write/Edit context hook in Claude Code; a precedence rule in `harness-block.md`; refusals and a customization section in `install`/`update`, `doctor`, and `import`; runtime fallback for an invalid config file; the plug-in points under `.harness/local/` (git hooks, Claude Code hook scripts, doggy-workflow phase rules, subagent instructions); the commit check for harness developers in this repository; version 0.56.0 with its migration entry; README rewritten as a whole to what a user or developer needs (user, 2026-11-22). Existing tests in `tests/` that assert the old behavior replaced here (an edited harness file skipped and reported as `user-modified`) are updated by test-implementer to the new behavior.
Out of scope: replacing a harness file through a local copy (the user allows additions only); switching harness parts off; making `update` remember `--no-ci`; merging edited harness files; moving a repository's files into `.harness/local/` automatically; customizations in `CLAUDE.md`, `CLAUDE.local.md`, or other instruction files; rules shown at the first edit of a directory (not asked for); Codex guarantees beyond the shared `.codex/hooks.json` merge rule; a hook manager such as Husky (local git hooks run only where `.harness/git` is the hooks path); detecting a contradiction between texts automatically (the agent reads and reports).

# Paths
Implementation: harness/, installer/, README.md, AGENTS.md, .harness/, .claude/, .codex/, .agents/, .gitignore
Tests: tests/
Test command: HARNESS_TEXT_TESTS=1 uv run --python 3.12 --with pytest --with hypothesis python tests/run_parallel.py
Review evidence: main runs these after the Test command passes and after regenerating the installed copy with `python3 installer/harness.py update . --no-commit` (the implementer edits only `harness/`, `installer/`, `README.md`, and `AGENTS.md`; also `.harness/local/git/pre-commit`). Every run sets `HARNESS_TARGETS_FILE` to a file in the session scratchpad; commands, environment, and observed output are saved in the scratchpad as `review/<run>.md` and summarized in the execution ledger.
R1 (dogfood) — in this repository after the update: `python3 installer/harness.py doctor .` exits 0 and lists `AGENTS.md` and `.harness/local/git/pre-commit` under `manual review` as `unconfirmed`; `python3 .harness/hooks/customization_notice.py </dev/null` prints the instruction line and both item lines with their compare paths; after the user confirms, `python3 .harness/bin/customization.py confirm AGENTS.md .harness/local/git/pre-commit` and the notice prints nothing.
R2 (real target) — `git clone` `/Users/hwansu/tools/LLM-wiki` (0.55.1, has `.harness/git/pre-push`) and `/Users/hwansu/toy-projects/clip-manager` (0.47.0, has `.harness/git/post-checkout`) into the scratchpad; run the working-tree `installer/harness.py update <clone> --no-commit` answering `y` to each migration. Expected: both stop before writing with the conflict line naming `.harness/local/git/<name>`; after `git mv` of the hook there, update succeeds and the report's `customization` section lists `unconfirmed AGENTS.md` and the moved hook; in LLM-wiki a `git push` to a local bare remote's `master` is refused by the moved hook; in clip-manager `git worktree add` runs the moved post-checkout hook.
R3 (real Claude Code) — in the R2 LLM-wiki clone after its update: `claude -p "Copy every line of your context that starts with 'harness customization:' exactly, one per line, and nothing else." --model haiku --tools "" --strict-mcp-config --setting-sources project --no-session-persistence`. Expected: the output holds the `unconfirmed AGENTS.md` line.
R4 (text) — main reads `git diff <base_commit> -- README.md harness/instructions/harness-block.md`. Expected: (1) harness-block states that a customization is followed where it disagrees with a harness rule; (2) that the session notice lists unconfirmed customizations; (3) that the agent tells the user before other work; (4) that it confirms only after the user does; README states (5) each customization path with an example, (6) the precedence, (7) the `status` and `confirm` commands, (8) the git hook order, (9) when update stops; (10) its development section states the F26 items; (11) README keeps the strings F13 lists and carries no detail the code alone decides (output formats, internal merge rules, exact hash rules).
R5 (real Claude Code subagent) — in a scratch repository installed from the working tree with `.harness/local/agents/code-explorer.md` containing `Begin your report with the word PINEAPPLE.`: `claude -p "Use the code-explorer agent to find where README.md is, and print its report verbatim." --model haiku --setting-sources project --no-session-persistence`. Expected: the printed report begins with `PINEAPPLE`.
Fuzzing: none — the inputs (review file, config file, declaration, `AGENTS.md` markers, hook payloads, git hook stdin) are covered by the enumerated malformed cases of V3, V6, V13, and V17; no fuzzing tool is installed at this repository's root.
Mutation tool: none — this repository has no `pyproject.toml`, `package.json`, `go.mod`, or `Cargo.toml`, so no mutation tool is installed for it.

# Signatures
```
.harness/customization.json                                   # owned declaration (source harness/customization.json)
{
  "points": [
    {"id": "<kebab id>",
     "path": "<repo-relative path, or pattern under .harness/local/ with {name} or a trailing /**>",
     "names": ["<name>", ...],                                  # only when path contains {name}
     "compare": ["<repo-relative path, may contain {name}>", ...],
     "compare_phase_fragments": true}                           # phase-rules only
  ],
  "config_keys": ["<key>", ...],
  "retired": [{"path": "<path or pattern>", "version": "<x.y.z>", "note": "<one sentence>"}]
}
.harness/customization-review.json                            # committed; written only by `confirm`
{"items": {"<repo-relative path>": {"content": "<sha256 hex>", "compare": "<sha256 hex>",
                                     "harness_version": "<VERSION at confirm>", "confirmed": "<YYYY-MM-DD>"}}}

python3 .harness/bin/customization.py status            # lines `<state> <path>[ — compare with <p1>, <p2>, ...]`, problem lines, or `no customizations`; exit 0
python3 .harness/bin/customization.py confirm PATH...   # `confirmed <path>` per path, exit 0; or `<path>: not a recognized customization` / `<path>: not found`, exit 1, nothing written
python3 .harness/hooks/customization_notice.py          # SessionStart; stdin ignored; notice lines on stdout; exit 0
python3 .harness/hooks/customization_context.py         # PostToolUse Write|Edit|MultiEdit and SubagentStart; hook JSON on stdin; additionalContext JSON or nothing on stdout; exit 0
python3 installer/harness.py install|update|doctor|import ...   # existing; gain F7–F10, F16, F17
python3 .harness/bin/workflow_marker.py phase ...       # existing; gains F18
.harness/local/git/<name>                                # executable; run by .harness/git/<name>
.harness/local/doggy-workflow/<phase>.md                 
.harness/local/agents/<agent name>.md                    
.harness/local/hooks/**                                  # scripts the repository registers in .claude/settings.json itself
python3 installer/customization_check.py [--staged]      # not installed; exit 0 or 1
```
States: `unconfirmed`, `harness-changed`, `confirmed`, `unrecognized`, `retired`. Problems: `config-invalid`, `unknown-config-key`, `review-file-invalid`, `not-executable`, `missing`.

# Functional Requirements
| id | requirement | priority | source |
| --- | --- | --- | --- |
| F1 | The payload ships `harness/customization.json`, installed as the owned file `.harness/customization.json`. It declares the point `project-instructions`: path `AGENTS.md`, compare `.harness/instructions/harness-block.md`, `.harness/instructions/index-and-staleness.md`, `.harness/instructions/try-n-fail.md`, `.harness/instructions/todos.md`, `.harness/instructions/synced-comments.md`; and `config_keys` `docs_root`, `exclude_dirs`, `auto_install`, `agent_model`, `step_split_obligations`; and the points of F20. | must | I1, I2 |
| F2 | One library computes every customization item and its state. Items: `AGENTS.md` at the repository root when it exists (its content is the text with the managed block, as `installer/harness.py` `MARKER_RE` matches it, removed); every regular file under `.harness/local/` (recursive; `__pycache__` skipped). A file under `.harness/local/` that matches no point is `unrecognized`. A recognized item is `unconfirmed` when the review file has no record for its path or the record's `content` differs from the sha256 of its current content; `harness-changed` when `content` matches and `compare` differs from the current compare hash; `confirmed` when both match. The compare hash covers each compare path in declaration order, path and bytes, with a missing file hashed as missing. A review file that is not a JSON object with an object `items` yields problem `review-file-invalid` and no records. `.harness/config.json` that exists and is not a JSON object yields `config-invalid`; each top-level key not in `config_keys` yields `unknown-config-key <key>`. | must | I2, I4 |
| F3 | `customization.py status` prints one line per item, sorted by path: `<state> <path>`, followed by ` — compare with <comma-separated compare paths>` for `unconfirmed` and `harness-changed`; then one line per problem (`config-invalid .harness/config.json: <reason>`, `unknown-config-key <key>`, `review-file-invalid .harness/customization-review.json`); `no customizations` when there are no items and no problems. `confirm PATH...` accepts only paths of recognized items that exist; otherwise it prints `<path>: not a recognized customization` or `<path>: not found` for each bad path, writes nothing, and exits 1. On success it writes a record per path with the current hashes, `harness_version` from `.harness/VERSION`, and today's date, keeping other records, replacing an invalid review file, writing via a temporary file and rename, and prints `confirmed <path>` per path. | must | I2 |
| F4 | A SessionStart hook (`customization_notice.py`, Claude Code) prints nothing when every item is `confirmed` and there is no problem. Otherwise it prints, each line prefixed `harness customization: `: first the instruction line `before other work, tell the user about each line below. Where a customization disagrees with harness text, the customization is followed: read both and name each disagreement. Run the confirm command for an item only after the user confirms it.`; then per non-confirmed item `<state> <path>; compare with <paths>; confirm: python3 .harness/bin/customization.py confirm <path>` (for `unrecognized`: `unrecognized <path>; the harness does not read this file`); then per problem `config-invalid .harness/config.json; harness defaults are used until it is fixed`, `unknown-config-key <key> in .harness/config.json; the harness ignores it`, `review-file-invalid .harness/customization-review.json; every customization counts as unconfirmed`, `not-executable <path>; the git hook does not run until you run chmod +x <path>`, `missing .harness/local/<p> (referenced by .claude/settings.json); restore the file or remove the hook from .claude/settings.json`, and the declaration line of `# Errors`; a `retired` item is shown as `retired <path>: <note>`. It exits 0 and prints nothing to stdout on any internal error. | must | I2, I4 |
| F5 | A PostToolUse hook (`customization_context.py`, matcher `Write\|Edit\|MultiEdit`, Claude Code) reacts when the tool input's `file_path` resolves to the repository-root `AGENTS.md` or to a path under `.harness/local/`. For a recognized item it emits additionalContext `harness customization: <path> is a customization (<point id>). It is followed where it disagrees with <compare paths>. Read those files, tell the user each disagreement before you finish, and run python3 .harness/bin/customization.py confirm <path> only after the user confirms.`; for an unrecognized or retired path `harness customization: the harness does not read <path>. Recognized customization paths: <each point path>.` It emits at most once per item path per session, keeping its marker where git ignores it, and emits nothing without a session id, outside a git work tree, or on any internal error; exit 0. | must | I2 |
| F6 | `harness-block.md` states: the project's instructions in `AGENTS.md` outside the harness block and the files the harness reads from `.harness/local/` are this repository's customizations; where one disagrees with a harness rule, the customization is followed; a session-start notice lists customizations not yet confirmed against the current harness text; the agent tells the user about each before other work, names each disagreement it finds, and runs the confirm command only after the user confirms. | must | I2, D1 |
| F7 | Before any write, `update` (also with `--dry-run`) stops with exit 1 under `== conflict ==` when: (a) a file in the old manifest exists with a sha256 equal to neither its manifest entry nor its new content (also when the new version no longer ships it): `<path>: edited in place; harness files are not edited. Move the change to a customization (see README), delete <path>, and run update again to restore it`; (b) for a skill the new version ships, `.claude/skills/<name>` exists and is not a symlink to `../../.agents/skills/<name>`: `.claude/skills/<name> already exists and is not the harness link; rename the repository's own skill and run update again`. `install` and `update` stop the same way when `.harness/config.json` exists and is not a JSON object: `.harness/config.json: not a JSON object (<reason>)`. A deleted owned file is still written again. | must | I4, D7 |
| F8 | The `update` report gains a section `== customization ==` after `manual review`, listing `- <state> <path>` for each non-confirmed item and `- <problem> ...` for each problem, computed against the harness files the update leaves on disk (in `--dry-run`, against the files it would write). The section is absent when every item is confirmed and there is no problem. It does not change the exit status. | must | I2, I4 |
| F9 | `doctor` reports `config-invalid` under `conflict` (exit 1) and each non-confirmed item, `unknown-config-key`, and `review-file-invalid` under `manual review` (exit status unchanged by them). | must | I4 |
| F10 | `import` no longer lists files under `.harness/local/`, `.harness/customization-review.json`, or `.harness/config.json` under `added`. Its text output gains `== customization ==` with `<state> <path>` lines (or `none`); its JSON output gains `"customization": [{"path": ..., "state": ...}, ...]`. | should | I4 |
| F11 | When `.harness/config.json` exists and is not a JSON object, the harness's hooks and scripts use the defaults of `config.default.json` instead of raising; `pre-commit` prints `pre-commit: .harness/config.json is not a JSON object; harness defaults are used` to stderr and is not blocked by that alone; the checkout-setup rule that an unreadable config turns automatic install off is unchanged. | must | I4, D9 |
| F12 | `harness/VERSION` is `0.56.0` and `MIGRATIONS` gains one 0.56.0 entry whose planned lines say: customizations live in `AGENTS.md` outside the block and under `.harness/local/` (the four paths of F20) and are followed over harness text; the session notice lists every customization until the user confirms it once, starting with `AGENTS.md`; in-place edits of harness files stop update; a repository skill that shadows a harness skill stops update; an invalid config file stops install and update; an existing `.harness/git/<name>` stops update until moved to `.harness/local/git/<name>`; repository hook groups under `.harness/local/` are kept; no data is migrated. | must | AGENTS.md project rule |
| F13 | README (Korean) is rewritten as a whole to what a reader needs to use and develop the harness, dropping detail that the code shows or that goes stale. For customization it states only: each path with one example, the precedence, the notice with the `status` and `confirm` commands, the git hook order, and when update stops. It keeps every string that existing text tests pin (`auto_install`, `checkout_setup.py status`, `installer/harness.py update`, `--ask-tools`, `[y/N/never]`, `records.py`, and the sentence `항상 읽는 규칙은 [`harness-block.md`](harness/instructions/harness-block.md)에 있습니다.`). | must | I1, user 2026-11-22 |
| F14 | `install`, `update` (also `--dry-run`), and every migration leave every file under `.harness/local/` byte-identical with the same mode, and never remove a directory under it. | must | I1 |
| F15 | The payload ships an executable `.harness/git/<name>` for each of `applypatch-msg`, `pre-applypatch`, `post-applypatch`, `pre-commit`, `pre-merge-commit`, `prepare-commit-msg`, `commit-msg`, `post-commit`, `pre-rebase`, `post-checkout`, `post-merge`, `pre-push`, `pre-auto-gc`, `post-rewrite`. When git runs one of them: (1) the harness's own checks for that name run as today (`pre-commit`, `commit-msg`); a failing check ends the hook with its status as today; (2) `.harness/local/git/<name>`, when it exists and is executable, runs with the same arguments and the same stdin bytes, and a non-zero exit ends the hook with that status; when it exists and is not executable, stderr gets `<name>: .harness/local/git/<name> is not executable; run chmod +x .harness/local/git/<name>` and the hook continues; (3) the clone-private hook runs last as today, with the same stdin bytes. The dispatcher finds its shared code and the local hook next to its own file (the hooks directory it runs from, and `../local/git/<name>` beside that directory), not in the work tree being checked out: during `git worktree add`, git runs the hook of the existing hooks path while the current directory and `git rev-parse --show-toplevel` are the new worktree's, whose commit may predate these files. | must | I1 |
| F16 | When `install` or `update` finds a file not in the old manifest at a `.harness/git/<name>` path the new version ships, the conflict line is `.harness/git/<name> already exists; a repository's own git hook now lives at .harness/local/git/<name>: move it there (git mv) and run update again`. | must | I4, D8 |
| F17 | When `.claude/settings.json` and `.codex/hooks.json` are merged, a hook group counts as the harness's only when one of its commands contains `/.harness/` and none of them contains `/.harness/local/`; every other group stays, in its order. A command in `.claude/settings.json` that references `.harness/local/<p>` where `<p>` does not exist yields problem `missing .harness/local/<p> (referenced by .claude/settings.json)`. | must | I1, I4 |
| F18 | For phase P, when `.harness/local/doggy-workflow/P.md` exists, the phase command prints, after the rules and before `## Markers of this phase`: `## Project rules for this phase`, a line `From .harness/local/doggy-workflow/P.md. Where these disagree with the harness rules above, follow these.`, a blank line, and the file's text; also with `--again` and `--all`. When the file cannot be read as UTF-8 text, the text is replaced by `.harness/local/doggy-workflow/P.md could not be read; read it yourself.` | must | I1, D1 |
| F19 | On SubagentStart with `agent_type` naming a harness agent (`code-explorer`, `implementer`, `mutant-triager`, `test-implementer`, `test-verifier`) and a readable `.harness/local/agents/<agent_type>.md`, `customization_context.py` prints `{"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": "## Project instructions for this agent\nFrom .harness/local/agents/<agent_type>.md. Where these disagree with your instructions above, follow these.\n\n<text>"}}`; otherwise it prints nothing. Exit 0. The existing SubagentStart behavior of `spec_gate.py` is unchanged. | must | I1, D1, D10 |
| F20 | The declaration also declares the points `git-hook` (path `.harness/local/git/{name}`, names of F15, compare `.harness/git/{name}`), `phase-rules` (path `.harness/local/doggy-workflow/{name}.md`, names the nine phases, compare `.harness/skills/doggy-workflow/phases.json` plus each fragment `phases/<f>.md` that `phases.json` lists for `{name}`, conditional or not), `agent-instructions` (path `.harness/local/agents/{name}.md`, names of F19, compare `.claude/agents/{name}.md`), `hook-script` (path `.harness/local/hooks/**`, compare `.harness/hooks/hooks.spec.json`). A `git-hook` item without the executable bit yields problem `not-executable <path>`. F2–F10 apply to these points. | must | I1, I2 |
| F22 | `python3 installer/customization_check.py [--staged]` checks, against the working tree (or the index with `--staged`): (a) `harness/customization.json` parses; every `git-hook` name has `harness/git/<name>`; `phase-rules` names equal the keys of `harness/skills/doggy-workflow/phases.json`; `agent-instructions` names equal the `name` fields of `harness/agents/*.md`; every compare path, with `{name}` substituted, `.harness/` mapped to `harness/`, and `.claude/agents/<n>.md` mapped to `harness/agents/<n>.md`, exists; `config_keys` contains every key of `harness/config.default.json`; (b) every point id, point name, and config key in the declaration at `HEAD` that is absent now is covered by a `retired` entry whose `version` is a version in `MIGRATIONS` and not above `harness/VERSION`; the covering entry's `path` is the removed point's `path` for a removed point id, that `path` with `{name}` replaced for a removed name, and the key itself for a removed config key. Each failure prints one line naming the item and what to add, and a compare path that fails only because its `{name}` already failed is not reported again; any failure exits 1. (c) When the checked changes touch a compare path of a point (mapped as in a), it prints `customization: changes to <paths> will ask repositories with a customization at <point id> to review it after update` and does not fail for it. | must | I3, D12 |
| F23 | This repository's `.harness/local/git/pre-commit` runs `python3 installer/customization_check.py --staged`; its failure blocks the commit. | must | I3 |
| F24 | The test suite fails when `installer/customization_check.py` exits 1 on the working tree. | must | I3 |
| F25 | A file under `.harness/local/` that matches no current point and matches a `retired` entry has state `retired` and is shown as `retired <path>: <note>` in `status`, the notice, the update section, doctor's `manual review`, and `import`; `confirm` refuses it as not recognized. | must | I3, I2 |
| F26 | README's development section states, briefly: edit `harness/` only, with `.harness/local/` as the hand-edited exception; run `python3 installer/harness.py update . --no-commit`; add a migration for each version; `harness/customization.json` declares the customization points and the commit check stops a removal or rename until it is retired with a migrated version. `AGENTS.md` carries none of this (user, 2026-11-22: no detailed, staleable explanation in `AGENTS.md`). | must | I3, user 2026-11-22 |

# Errors
- `AGENTS.md` missing — no `project-instructions` item; no line about it.
- `.harness/customization.json` missing or invalid at runtime — `status` prints `customization declaration missing or invalid: .harness/customization.json`; the notice prints that line with the prefix; every file under `.harness/local/` counts as `unrecognized`; exit 0.
- Review file invalid — problem `review-file-invalid`; every recognized item counts as unconfirmed; `confirm` replaces the file.
- `confirm` with a bad path — exit 1, message per bad path, review file unchanged (byte-identical or still absent).
- Config invalid — install/update conflict, exit 1, nothing written; doctor conflict; runtime defaults with the pre-commit warning and notice line (F11).
- Edited harness file — update conflict, exit 1, nothing written, the edited file byte-identical (F7a).
- Shadowing skill — update conflict, exit 1, nothing written (F7b).
- Existing `.harness/git/<name>` — conflict line of F16, exit 1, nothing written.
- Local git hook not executable — stderr line of F15, hook continues; problem `not-executable`.
- Local git hook exits non-zero — the git hook exits with that status; for `pre-commit` the commit is not created; the clone-private hook does not run.
- Local phase or agent file unreadable — F18 replacement line; for an agent file, no additionalContext.
- Notice or context hook internal failure — exit 0, no stdout; the session and the tool call go on.
- Declaration check failure — exit 1, one line per failure; in pre-commit the commit is not created.

# Cases
| id | level | input / state | expected result |
| --- | --- | --- | --- |
| C1 | normal | fresh install, `AGENTS.md` with a project definition, no review file | `status`: `unconfirmed AGENTS.md — compare with` the five F1 paths; notice: instruction line + that item line |
| C2 | normal | C1, then `confirm AGENTS.md` | `confirmed AGENTS.md`; review file has a record with both hashes, `harness_version` = VERSION, today's date; notice prints nothing |
| C3 | normal | C2, then the text outside the managed block changes | `unconfirmed AGENTS.md` |
| C4 | normal | C2, then only the managed block changes (whitespace inside the block markers untouched otherwise) or nothing outside it | still `confirmed` |
| C5 | normal | C2, then one compare file changes (e.g. via update writing a new `harness-block.md`) | `harness-changed AGENTS.md`; update section lists it |
| C6 | boundary | C2, then a harness file that is not a compare path changes | still `confirmed` |
| C7 | error | review file `[]`, `{"items": []}`, invalid JSON | `review-file-invalid`; `unconfirmed AGENTS.md`; `confirm AGENTS.md` writes a valid file |
| C8 | error | `confirm README.md`, `confirm .harness/local/x.md` (unrecognized), `confirm nope.md`, `confirm AGENTS.md nope.md` | exit 1; per-path messages; review file unchanged in every row |
| C9 | normal | file `.harness/local/notes.txt` | `unrecognized .harness/local/notes.txt`; notice line says the harness does not read it |
| C10 | error | `.harness/config.json` = `{"auto_install": false,` / `[]` / `"x"` | `status`/notice: `config-invalid`; doctor conflict exit 1; update and install conflict exit 1 nothing written; spec_gate PreToolUse blocks the Test command with a running marker under the default docs root; pre-commit warns and commits |
| C11 | normal | `.harness/config.json` = `{"auto_instal": false, "agent_model": "opus"}` | `unknown-config-key auto_instal` in status, notice, update section, doctor manual review; `agent_model` accepted |
| C12 | error | installed repo, one owned file edited (e.g. `.harness/hooks/spec_gate.py`), `update` and `update --dry-run` | exit 1; conflict line of F7a naming the file; no file written; manifest unchanged |
| C13 | boundary | owned file edited to exactly the new version's content | not a conflict; update proceeds |
| C14 | boundary | owned file deleted | written again; no conflict |
| C15 | error | owned file edited that the new version no longer ships | conflict of F7a |
| C16 | error | new version ships skill `zz`; repo has its own `.claude/skills/zz/` | update exit 1, F7b line, nothing written |
| C17 | normal | `.claude/skills/<harness skill>` is the harness symlink | no conflict |
| C18 | normal | PostToolUse Write to `AGENTS.md` with a session id, twice in one session, then in another session | context emitted on the first call of each session only; text names the compare paths and the confirm command |
| C19 | normal | PostToolUse Write to `.harness/local/notes.txt` | context says the harness does not read it and lists recognized paths |
| C20 | edge | PostToolUse Write to `docs/AGENTS.md`, to a path outside the repository, without session id, outside a git work tree, malformed stdin | no output, exit 0 |
| C21 | error | notice with an unreadable declaration, with a non-directory `.harness/local` file, with an exception inside the library | exit 0; no traceback on stdout |
| C22 | normal | update from a 0.47.0 fixture and from a 0.55.1 fixture | migrations listed and confirmed; 0.56.0 entry shown; report has `== customization ==` with `- unconfirmed AGENTS.md` |
| C23 | normal | `import` text and `--json` with a local file and a review file | neither listed under `added`; customization section/key present |
| C24 | normal | every file under `.harness/local/` (nested, executable and not, symlink-free) through install, update from 0.47.0, update `--dry-run`, and every migration | byte-identical, same mode; directories still present |
| C25 | normal | `.harness/local/git/pre-commit` exits 1 | commit not created; harness checks ran before it; clone-private hook not run |
| C26 | normal | `.harness/local/git/pre-push` reading stdin, plus a clone-private `pre-push` reading stdin | both receive the same stdin bytes; order local then private |
| C27 | error | harness `verify_rules.py` fails in pre-commit | local pre-commit does not run |
| C28 | error | local hook not executable | stderr line of F15; hook continues; `not-executable` problem |
| C29 | normal | each of the 14 names with no local and no private hook | the hook exits 0 and prints nothing |
| C43 | edge | `git worktree add` of a commit whose tree has no 0.56.0 git hook files, from a checkout that has them and a `.harness/local/git/post-checkout` | the local hook runs once with the new worktree as its current directory; `git worktree add` exits 0 |
| C30 | error | update over an existing `.harness/git/pre-push` / `post-checkout` | F16 line; exit 1; nothing written |
| C31 | normal | settings with a repo group `.../.harness/local/hooks/lint.py` and one `.../scripts/x.py`; update | both groups kept in order; harness groups replaced; Codex file likewise |
| C32 | error | settings group references `.harness/local/hooks/gone.py` | problem `missing .harness/local/hooks/gone.py (referenced by .claude/settings.json)` |
| C33 | normal | `.harness/local/doggy-workflow/verify.md` present; `phase --phase verify`, `--again`, `--all`; other phases | heading + precedence line + text between rules and markers for verify only |
| C34 | error | the verify file is not UTF-8 | replacement line; rules and markers unchanged |
| C35 | normal | SubagentStart `implementer` with `.harness/local/agents/implementer.md`; `Explore`; harness agent without a file; unreadable file | JSON of F19 for the first; nothing otherwise; spec_gate running marker still written for `implementer` |
| C36 | normal | a `phase-rules` item confirmed, then a fragment listed for that phase changes / a fragment of another phase changes | `harness-changed` / still `confirmed` |
| C37 | normal | a file `.harness/local/doggy-workflow/nope.md`, `.harness/local/agents/explore.md`, `.harness/local/git/pre-receive` | `unrecognized` |
| C38 | normal | declaration unchanged; harness text change to a phase fragment | check exit 0 with the F22c warning naming `phase-rules` |
| C39 | error | phase `verify` removed from `phases.json` and from the declaration names (both, since F22a ties them) without retirement; then with a `retired` entry whose version has no migration; then with one whose version has | exit 1; exit 1; exit 0 |
| C40 | error | a declared git hook name without `harness/git/<name>`; an agent name not in `harness/agents/`; a config default key missing from `config_keys`; a compare path that does not exist; invalid JSON | exit 1 with a line each |
| C41 | normal | this repository: staged commit that violates C39 | `git commit` refused by `.harness/local/git/pre-commit` |
| C42 | normal | target with `.harness/local/doggy-workflow/old.md` where `old` is retired with note N | `retired .harness/local/doggy-workflow/old.md: N` everywhere of F25; `confirm` refuses |

# Quality Applicability
| ISO/IEC 25010:2023 characteristic | applicable | rationale |
| --- | --- | --- |
| Functional suitability | yes | the requirements above |
| Performance efficiency | no | each repository has a handful of small files; the git dispatch adds a file-existence check per hook; no load or latency budget is stated |
| Compatibility | yes | coexistence with repositories' own Claude Code hooks, clone-private git hooks, and existing installs from 0.47.0 and 0.55.1 |
| Interaction capability | yes | every refusal and notice must name the file and the action, because the reader is an agent or a person acting on the message alone |
| Reliability | yes | the notice and context hooks must never fail a session or a tool call; a broken local file must not suppress harness rules |
| Security | no | local git hooks and hook scripts are repository-committed code run with the same trust as the harness's own committed hooks today; no new boundary is crossed |
| Maintainability | yes | one library computes states for every reporter; the declaration is checked against the payload |
| Flexibility | yes | installability: updates from existing versions keep working, with refusals that say how to continue |
| Safety | yes | no user file is overwritten or deleted: the installer refuses instead of overwriting an edited file and never writes under `.harness/local/` |

# Quality Requirements
| id | characteristic / subcharacteristic | target and context | measure method / inputs / unit | threshold and direction | evidence: automated, review, mutation | source |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | Compatibility / co-existence | repository hook groups and clone-private git hooks after install/update | count of repository groups lost or reordered in C31; count of private-hook runs missing or stdin mismatches in C25–C26 | 0, lower is better | automated V11, V12 | I1 |
| Q2 | Interaction capability / user error protection | every refusal line (F7, F16), notice line (F4), problem line, and check failure (F22) | fraction of lines that contain the repository-relative path of the cause and an action or command | 100%, higher is better | automated V2, V4, V8, V10, V16; review R4 | I4 |
| Q3 | Reliability / fault tolerance | notice and context hooks under the malformed inputs of C20, C21, C34, C35 | count of non-zero exits or stdout tracebacks | 0, lower is better | automated V5, V6, V14, V15 | I2 |
| Q4 | Maintainability / modularity | status, notice, context hook, update, doctor, import | count of reporters that compute a state without the shared library | 0, lower is better | review: main reads each reporter's call path during verify and records it in the ledger | D14 |
| Q5 | Flexibility / installability | update from 0.47.0 and 0.55.1 fixtures and the two real clones of R2 | count of fixtures where update fails for a reason other than the F7/F16 refusals, or where a refusal leaves a written file | 0, lower is better | automated V9; review R2 | I1, I4 |
| Q6 | Safety / fail safe | files under `.harness/local/` and edited owned files across install, update, dry-run, and migrations | count of files whose bytes or mode changed | 0, lower is better | automated V8, V10 | I1 |

# Verification Obligations
| id | parent requirement/Case ids | variant and target surface | test layer and selection policy | ISO/IEC/IEEE 29119-4 technique | coverage items | coverage target | observation and expected result | evidence procedure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V1 | F2, F3, C1–C6 | state of the `project-instructions` item through `customization.py status` in an installed temporary repository | integration; every transition | state transition | T1 none→unconfirmed; T2 unconfirmed→confirmed by confirm; T3 confirmed→unconfirmed by an edit outside the block; T4 confirmed→confirmed by an edit inside the block only; T5 confirmed→harness-changed by a compare-file change; T6 confirmed→confirmed by a non-compare harness file change; T7 harness-changed→confirmed by confirm; T8 harness-changed→unconfirmed by an edit outside the block | 100% | exact status lines; review-file record fields | Test command |
| V2 | F3, C2, C7, C8, Q2 | `confirm` arguments and review-file forms | integration; every row | decision table | rows: one valid path; the same valid path given twice; one valid + one not found; unrecognized path; non-item path (`README.md`); not found; review file absent / invalid JSON / `[]` / `{"items": []}` / valid with another record | 100% | exit code; messages; review file bytes unchanged on every exit 1 row; other records kept; invalid file replaced | Test command |
| V3 | F2, F3, F4, C9–C11, Q2 | problems and unrecognized items | integration; every partition | equivalence partitioning | config: absent; valid known keys; unknown key; invalid JSON; JSON array; JSON string. local: no dir; empty dir; one unrecognized file; file in a nested dir; `__pycache__` file. declaration: missing; invalid | 100% | status and notice lines exact per partition | Test command |
| V4 | F4, C1, C2, Q2 | notice output | integration; every row | decision table | rows: all confirmed and no problem → empty; one unconfirmed; one harness-changed; one unrecognized; one problem only; mixed (order: instruction, items by path, problems) | 100% | exact stdout; exit 0 | Test command |
| V5 | F4, C21, Q3 | notice robustness | integration; every listed fault | error guessing | guessed defects: declaration unreadable; `.harness/local` is a file; review file is a directory; library raising (monkeypatched module by `PYTHONPATH` stand-in); stdin closed | none — experience-based | exit 0; no traceback on stdout | Test command |
| V6 | F5, C18–C20, Q3 | context hook | integration; every row | decision table | rows: AGENTS.md first call; same session second call; new session; `.harness/local/` unrecognized path; relative and absolute `file_path`; `docs/AGENTS.md`; outside repo; no session id; outside git work tree; tool `Read`; malformed stdin; non-object JSON | 100% | stdout JSON `hookSpecificOutput.hookEventName` = `PostToolUse` and exact additionalContext, or empty; exit 0; marker path ignored by git (`git check-ignore`) | Test command |
| V7 | F6, F13 | harness-block and README text | review | scenario | R4 items 1–9 and 11 | 100% | each item present | review R4 |
| V8 | F7, C12–C17, Q2, Q6 | install/update refusals | integration; every row | decision table | rows: owned file edited (update, dry-run); edited to new content; deleted; edited and dropped by new version; shadowing skill dir (update); harness symlink; config invalid (install, update, dry-run); config valid | 100% | exit code; conflict line text; `git status --porcelain` and manifest bytes unchanged on refusal; edited file bytes unchanged | Test command |
| V9 | F8, F12, C22, Q5 | update report and migration entry | integration; every listed fixture | scenario | E1 update from 0.47.0 fixture with project definition; E2 from 0.55.1 fixture; E3 dry-run where the update would change `harness-block.md` for a confirmed AGENTS.md (section shows `harness-changed`); E4 everything confirmed and no problem (no section) | 100% | report sections; 0.56.0 planned lines listed; exit 0 | Test command; review R2 |
| V10 | F9, F10, F11, C10, C11, C23, Q2, Q6 | doctor, import, runtime config fallback | integration; every row | decision table | doctor: invalid config (exit 1, conflict); unknown key (manual review, exit 0); unconfirmed (manual review). import: text and JSON with local file, review file, config file. runtime: invalid config with pre-commit (warning, commit created); spec_gate PreToolUse with a running marker under `agent-docs/specs/.running` and the spec's Test command (exit 2); checkout-setup auto install off | 100% | outputs and exit codes | Test command |
| V11 | F14, C24, Q6 | `.harness/local/` preservation | integration; every listed operation | equivalence partitioning | install over a repository that already has `.harness/local/`; update same version; update from 0.47.0 fixture with all migrations confirmed; update `--dry-run`; update with `--no-ci` | 100% | bytes and mode of each file; directories present | Test command |
| V12 | F15, C25–C29, Q1 | git hook dispatch | integration; every listed item | decision table | rows per hook kind (harness-checked `pre-commit`, `commit-msg`; unchecked `post-merge`, `pre-push`, `post-checkout`): local absent/present-exit-0/present-exit-1/not-executable × private absent/present; stdin identity for `pre-push` with both; harness check failing (pre-commit) with local present; all 14 names exist, are executable, and exit 0 with nothing installed; C43 worktree of an older commit (local hook ran, its cwd, exit 0) | 100% | run order (marker file lines), exit status, stdin bytes, stderr line | Test command |
| V13 | F16, F17, C30–C32, Q1, Q2 | conflicts for existing git hooks and kept repository hook groups | integration; every row | decision table | rows: existing `.harness/git/pre-push`; existing `.harness/git/post-checkout`; settings with `.harness/local/hooks/` group, `scripts/` group, harness group, mixed group (harness + local command); codex file likewise; missing referenced local script | 100% | conflict text; merged JSON groups and order; problem line | Test command |
| V14 | F18, C33, C34, Q3 | phase additions | integration; every row | equivalence partitioning | present for verify: `phase --phase verify` (recorded phase), `--again`, `--all`; absent; present for another phase only; non-UTF-8; empty file | 100% | stdout: position between rules and markers, exact heading and precedence lines, text; rules and markers byte-identical to the no-file run | Test command |
| V15 | F19, C35, Q3 | subagent additions | integration; every row | decision table | rows: harness agent with file; harness agent without file; non-harness agent with a same-named file; unreadable file; malformed stdin; `implementer` with file and a spec dir (spec_gate marker still written by its own hook) | 100% | stdout JSON exact or empty; exit 0 | Test command; review R5 |
| V16 | F20, C36, C37, Q2 | new points in the state library | integration; every row | equivalence partitioning | each point: recognized name / unrecognized name; compare change for own phase vs other phase; agent compare change; hook-script compare change; git-hook not executable | 100% | status lines | Test command |
| V17 | F22, C38–C40, Q2 | declaration check | integration (temporary git repository holding copies of `harness/` and `installer/`); every row | decision table | rows of C38–C40 plus: point id removed; config key removed; with `--staged` vs working tree differing; retired version above VERSION | 100% | exit code; one line per failure naming the item | Test command |
| V18 | F23, F24, C41 | dogfood check wiring | integration | scenario | E1 this repository's `.harness/local/git/pre-commit` present and executable, runs the check (stand-in commit in a temporary clone); E2 the suite's test runs the check on the working tree | 100% | commit refused in E1 for a violating stage; E2 passes on the working tree | Test command |
| V19 | F25, C42 | retired state | integration; every reporter | equivalence partitioning | status, notice, update section, doctor, import text, import JSON, confirm | 100% | `retired <path>: <note>` in each; confirm exit 1 | Test command |
| V20 | F26 | README development text | review | scenario | R4 item 10 | 100% | each item present | review R4 |

# Assumptions and Defaults
| id | decision | evidence and uncertainty | brief v<n> — approved / vetoed → <answer> / user answer / user decision (main: <own option>) / facts.md: <first words of the entry> |
| --- | --- | --- | --- |
| D1 | Where a customization disagrees with harness text, the customization is followed, on condition that the user can recognize the disagreement at add time and after an update | user statement, decision round 1 | user decision (main: harness rules win and additions may only add or tighten) |
| D2 | A customization takes effect at once, before confirmation; the notice repeats every session until the user confirms | the user's condition is that the user *can* recognize; the notice and the add-time context give that chance; uncertainty: an unattended session may act on an unseen addition | brief v1 — approved |
| D3 | Plug-in points: `AGENTS.md` outside the block, the config file, git hooks, Claude Code hook scripts, phase rules, subagent instructions; directory-first-edit rules are not built | user answer: own conventions, lint enforcement, extra implementation verification | user answer |
| D4 | Always-on conventions stay in `AGENTS.md` outside the harness block, made a reviewed item, rather than a new `.harness/local/instructions.md` imported by the block | PaperBox and LLM-wiki already keep conventions there (observed 2026-11-22); missing-file behavior of `@path` imports is not documented (Claude Code memory docs) | brief v1 — approved |
| D5 | Confirmations are committed in `.harness/customization-review.json`, shared by clones and worktrees | this repository has three worktrees; clip-manager's own post-checkout hook syncs files into new worktrees (observed) | brief v1 — approved |
| D6 | The agent runs `confirm` only after the user confirms in chat; nothing enforces it beyond the instruction | Task Guide "User Decision" rule; no mechanism can tell who typed the confirmation | brief v1 — approved |
| D7 | An edited harness-owned file stops update before any write, instead of being skipped and frozen | user: in-place edits are not allowed; 0 of 8 installed repositories have an edited harness file (observed 2026-11-22) | brief v1 — approved |
| D8 | Existing extra hooks in `.harness/git/` are not moved by the installer; update stops and names `.harness/local/git/<name>` | migration convention: `migrate_doggy_workflow` refuses until the user moves facts (`installer/harness.py:1223`); two repositories affected | brief v1 — approved |
| D9 | At runtime an invalid config file falls back to the defaults with warnings; install, update, and doctor fail on it | no installed repository has `.harness/config.json` (observed 2026-11-22), so defaults equal every repository's settings; Claude Code treats a PreToolUse exit other than 2 as non-blocking (hooks docs), so a crash opens the Test-command gate today | brief v1 — approved |
| D10 | Subagent additions are added at subagent start through SubagentStart `additionalContext`, not rendered into the agent files at update | hooks docs: SubagentStart can inject context, input names `agent_type`; an edit takes effect without running update | brief v1 — approved |
| D11 | Dispatched git hook names: the 14 of F15; excluded: `reference-transaction` (runs on every ref update), `push-to-checkout` (its presence changes push behavior), `fsmonitor-watchman` (git parses its output), `post-index-change`, `sendemail-validate`, `p4-*`, server-side hooks | git hook documentation | brief v1 — approved |
| D12 | The developer check fails a commit for a removed point without retirement and only warns for a changed compare file | pre-commit already blocks on record-structure violations (`harness/git/verify_rules.py`) and warns on comments | brief v1 — approved |
| D13 | One release, 0.56.0, with one migration entry; no step cut although the obligation map has 20 rows | the user declined the recommended cut | user decision (main: three releases 0.56.0, 0.57.0, 0.58.0) |
| D14 | One library module under `harness/lib/` computes items and states; every reporter calls it | Q4 | brief v1 — approved |
| D15 | The context hook speaks once per item per session; its marker lives under `.harness/sessions/rules-<session>.d/` (already git-ignored) | rule_injection's marker convention | brief v1 — approved |
| D16 | `hook-script` items compare against `hooks.spec.json`; `git-hook` items against the dispatcher of the same name only | a harness hook change is the only harness text next to a repository hook script | brief v1 — approved |
| D17 | Coverage targets 100% of enumerated items; hand mutations 8–10 at verify; no fuzzing and no mutation tool | no tool installed for this repository | brief v1 — approved |
| D18 | The notice and context text are English, like every harness message | harness messages are English | brief v1 — approved |
| D20 | The always-loaded `harness-block.md` may grow to 5100 bytes (was 4500, threshold A8 of spec c78afc0d4b2361e5) so that F6 sits in it | the block was 4494 bytes at `base_commit`; F6 adds about 540 bytes | user decision (main: none — asked as a conflict with the prior threshold) |
| D21 | The run allows three verifier invocations instead of two | the second audit left one blocking evidence gap (VF8) after the budget of two was used | user decision (main: stop with status `limit`) |
| D19 | `.claude/settings.json` hook groups are checked for missing local scripts; `.codex/hooks.json` only gets the merge rule | Codex is unsupported (AGENTS.md) | brief v1 — approved |

# Alternatives
| decision id | option not taken | what it gains and what it costs | reversal condition: the state of the world in which it wins |
| --- | --- | --- | --- |
| D1 | harness rules win; additions only add or tighten | keeps role separation and verification minimums intact in every repository; costs any customization that has to relax a harness rule | a repository's agent acts on a customization the user never saw, or the user wants harness guarantees identical across repositories |
| D2 | withhold a customization until confirmed | no unseen customization is ever followed; costs a confirm step before a new addition works | sessions run unattended (scheduled pipelines) where nobody reads the notice |
| D4 | `.harness/local/instructions.md` imported from the block | keeps conventions apart from the project definition; costs a new import whose missing-file behavior is undocumented | project-definition edits are frequent enough that re-confirming `AGENTS.md` becomes noise, and a missing import is verified harmless |
| D5 | per-checkout confirmations under `.harness/sessions/` | nothing to commit; costs re-confirming in every clone and worktree | each checkout is used by a different person who must recognize the disagreement |
| D6 | the agent confirms alone after reading both texts | no user round trip; costs the user's recognition, which D1 depends on | notices are frequent and the user delegates the review |
| D7 | keep skipping an edited file with a warning | an emergency patch in one repository survives; costs silent divergence from every later release | a repository needs a harness fix before it can be released upstream |
| D8 | migration moves the file after confirmation | no manual step for the two repositories; costs breaking the rule that the installer never writes under `.harness/local/` | many repositories have such files |
| D9 | fail closed: every hook exits 2 on an invalid config | no hook ever acts on wrong settings; costs blocking every Bash call until the file is fixed | a repository sets `docs_root` or other keys whose defaults would act on the wrong files |
| D10 | render the addition into `.claude/agents/<name>.md` at update | works without hooks and reaches Codex files; costs re-running update after each edit | Codex support matters, or SubagentStart context stops being honored |
| D12 | warn only on removal | no blocked commits while experimenting; costs releases that drop a point without a migration step | the harness gets a second developer who reviews every release by hand |

# Open Questions
| id | question | requirement, decision, or step it affects | what would settle it | open / settled v<n> — <answer> / deferred — <reason> |
| --- | --- | --- | --- | --- |
| O1 | Does a real Claude Code session receive the SessionStart notice text in context? | F4 | R3 | settled v4 — yes: R3 copied the item lines from its context |
| O2 | Does a real custom subagent receive SubagentStart additionalContext? | F19 | R5 | settled v4 — yes: R5's report began with PINEAPPLE |

# Completion Questions
| id | question | expected answer | what it tests: trade-off / engineer call (decision id) / final shape | built by: step id, or `all` | asked: no / closing <YYYY-MM-DD> | valid / invalid v<n> — <reason> |
| --- | --- | --- | --- | --- | --- | --- |
| CQ1 | A repository adds a verify-phase rule that drops part of the harness verification. Before the user confirms it, what does an agent running doggy-workflow there do, and what gives the user the chance to notice? | The agent follows the repository's rule, because a customization is followed even before confirmation. The context hook at the write and the session-start notice in every later session tell the agent to name the disagreement with the harness verification rules to the user; the notice repeats until the user confirms. | trade-off (D1, D2) | all | closing 2026-11-22 | valid |
| CQ2 | Someone fixes a bug directly in a harness hook file inside one repository. What happens at the next update, and why is the fix not kept? | Update stops before writing anything and names the edited file; the fix has to move into a customization or upstream. Keeping it would freeze that file against every later release without anyone noticing. | engineer call (D7) | all | closing 2026-11-22 | valid |
| CQ3 | A release rewrites the harness text of the verify phase. Trace what a repository with a verify-phase addition sees, from running update to the end of the next session. | Update writes the new phase fragments and its customization section lists the addition as harness-changed, because the hash of its compare files changed. The next session start prints the item with the files to compare and the confirm command; the agent compares, tells the user each disagreement, and runs confirm after the user agrees; later sessions print nothing for it. | final shape | all | closing 2026-11-22 | valid |
| CQ4 | A harness developer renames the verify phase. What stops the commit, and what must they add so repositories with a verify-phase addition learn what happened? | The commit check run by this repository's own local pre-commit fails, because a phase name declared at HEAD is gone without retirement. They add a retired entry with the version and a note, and a migration entry for that version; repositories with the file then see it as retired with the note. | final shape | all | no | valid |
| CQ5 | If confirmations were kept per checkout instead of committed, what would change for a repository worked from three worktrees? | Each worktree would show the notice again until the user confirmed in each one; with committed records one confirmation covers every clone and worktree once the commit reaches them. | engineer call (D5) | all | no | valid |

# Traceability
| requirement id | Case ids | obligation ids | evidence procedure |
| --- | --- | --- | --- |
| F1 | C1, C5 | V1 | Test command |
| F2 | C1–C7, C9–C11 | V1, V3 | Test command |
| F3 | C1, C2, C7, C8 | V1, V2, V3 | Test command |
| F4 | C1, C2, C9–C11, C21 | V3, V4, V5 | Test command; R1; R3 |
| F5 | C18–C20 | V6 | Test command |
| F6 | — | V7 | R4 |
| F7 | C10, C12–C17 | V8 | Test command |
| F8 | C5, C22 | V9 | Test command; R2 |
| F9 | C10, C11 | V10 | Test command; R1 |
| F10 | C23 | V10 | Test command |
| F11 | C10 | V10 | Test command |
| F12 | C22 | V9 | Test command |
| F13 | — | V7 | R4 |
| F14 | C24 | V11 | Test command |
| F15 | C25–C29, C43 | V12 | Test command; R2 |
| F16 | C30 | V13 | Test command; R2 |
| F17 | C31, C32 | V13 | Test command |
| F18 | C33, C34 | V14 | Test command |
| F19 | C35 | V15 | Test command; R5 |
| F20 | C36, C37 | V16 | Test command |
| F22 | C38–C40 | V17 | Test command |
| F23 | C41 | V18 | Test command |
| F24 | — | V18 | Test command |
| F25 | C42 | V19 | Test command |
| F26 | — 
# Workflow Control
| item | value |
| --- | --- |
| correction batches used | 6 |
| verifier invocations | 3 |
| open finding ids | none (advisory VA1, VA2, VA5–VA8 and invocation 3's two wording residuals remain advisory) |

Audit state (one entry per obligation; retain prior decisions in the execution ledger):
| obligation id | spec version | evidence references and revision | accepted / open / invalidated / pending | rationale and mutation outcome | dependencies and reopening evidence |
| --- | --- | --- | --- | --- | --- |
| V1 | v4 | tests/test_customization.py TestStateTransitions; Test command run 4 | accepted | verifier invocation 1 | — |
| V2 | v4 | tests/test_customization.py TestConfirmTable; Test command run 4 | accepted | verifier invocation 1 | — |
| V3 | v4 | tests/test_customization.py TestProblemPartitions; Test command run 4 | accepted | verifier invocation 1 | — |
| V4 | v4 | tests/test_customization_notice.py TestNoticeTable; Test command run 4 | accepted | verifier invocation 1 | — |
| V5 | v4 | tests/test_customization_notice.py TestNoticeRobustness; Test command run 4 | accepted | verifier invocation 1 | — |
| V6 | v5 | tests/test_customization_notice.py TestContextHookTable; Test command run 4 | accepted | verifier invocation 2; closed in it: VF4, VF7 | — |
| V7 | v5 | review R4 by main on README after I5 and harness-block.md; items 1–9 and 11 present | accepted | main review | README or harness-block change |
| V8 | v5 | tests/test_customization_refusals.py; Test command run 4 | accepted | verifier invocation 2; closed in it: VF3 | — |
| V9 | v6 | tests/test_customization_report.py TestUpdateReport (assert_migration_lines after T11); review R2; Test command run 8; mutations M1, M2, M12, M13 detected | accepted | verifier invocation 3; VF8 closed | helper assert_migration_lines |
| V10 | v4 | tests/test_customization_report.py TestDoctorAndImport, TestRuntimeConfigFallback; Test command run 4; tests/test_checkout_setup.py lines 416 and 1082 for the F11 checkout-setup rule (VA4) | accepted | verifier invocation 1 | — |
| V11 | v4 | tests/test_customization_report.py TestLocalPreservation; Test command run 4 | accepted | verifier invocation 1 | — |
| V12 | v4 | tests/test_local_git_hooks.py (incl. TestWorktreeAdd); review R2; Test command run 4 | accepted | verifier invocation 1 | — |
| V13 | v4 | tests/test_customization_conflicts.py; Test command run 4 | accepted | verifier invocation 1 | — |
| V14 | v4 | tests/test_phase_additions.py; Test command run 4 | accepted | verifier invocation 1 | — |
| V15 | v4 | tests/test_customization_notice.py TestSubagentAdditions; review R5; Test command run 4 | accepted | verifier invocation 1 | — |
| V16 | v4 | tests/test_customization.py TestNewPoints; Test command run 4 | accepted | verifier invocation 1 | — |
| V17 | v5 | tests/test_customization_check.py; Test command run 4 | accepted | verifier invocation 2; closed in it: VF5 | — |
| V18 | v5 | tests/test_customization_check.py TestDogfoodWiring; Test command run 4 | accepted | verifier invocation 2; closed in it: VF6 | — |
| V19 | v4 | tests/test_customization_report.py TestRetiredState; Test command run 4 | accepted | verifier invocation 1 | — |
| V20 | v5 | review R4 by main on README after I5; item 10 present | accepted | main review | README change |

Execution ledger (append attempts; preserve failed approaches):
| attempt | finding / failure signature | cause hypothesis | changed approach / new evidence | result / disposition |
| --- | --- | --- | --- | --- |
| 1 | Test command run 1 (spec v1 command, bare `python3`): `test_brief_telemetry`, `test_isolation_telemetry`, `test_session_metrics` fail to import `hypothesis`/`pytest` | the v1 Test command lacks the dependencies earlier specs ran with | v3 Test command under `uv` with both | pending rerun |
| 2 | run 1: 14 `test_phase_additions` failures, a blank line between `## Project rules for this phase` and the `From` line | implementation defect: F18 lists heading, `From` line, blank line, text | correction I1 to implementer | pending |
| 3 | run 1: `test_two_failures_get_one_line_each`, two lines for `pre-receive` | the compare check repeats a failed name | v3 F22 rule; correction I2 to implementer | pending |
| 4 | run 1: c40 config-key row removes `agent_model`, which is not a key of `harness/config.default.json`; confirm row expects `README.md` that the fixture never creates; E1/E2 assert the phrase `stops update`, which F12 does not quote | test defects | corrections T1–T3 to test-implementer | pending |
| 5 | run 1: existing tests pin the old payload: `test_remove_progress` hooks.spec entries, `test_facts_gate` migration answers (EOFError at the 0.56.0 prompt), `test_lazy_rules` block size 5035 > 4500 and heading order | test defects after the intended change; the size limit is a prior spec's threshold | D20 (user: raise to 5100); corrections T4–T6 | pending |
| 6 | run 1: `test_checkout_setup.TestStateTransitions.test_t5_timeout_marks_failed_and_kills_the_command`, `uv.pid` not found | pre-existing: the same test fails on an archive of `base_commit` run alone (`python3 tests/run_parallel.py test_checkout_setup`) | none in this run; reported to the user | outside this spec |
| 7 | Test command run 2 (spec v3): 1399 tests, 3 failures, all `test_every_phase_with_a_file_names_its_own_file_in_the_precedence_line` for `draft`, `implement_test`, `amend` | test defect: those phases print no `## Markers of this phase` section, and the test requires one | correction T7 | pending |
| 8 | opt-in legacy run (`HARNESS_LEGACY_MIGRATION_TESTS=1`, the seven modules batch 1 touched): 41 failures; the same run on an archive of `base_commit` fails 43, and no failure is new | pre-existing failures of opt-in tests; the batch-1 answer sweep put the extra 0.56.0 confirmation after the handoff answer, but all confirmations are asked before any migration applies and the handoff prompt comes while applying | correction T8 | pending |
| 9 | run 2: the t5 timeout test of row 6 passed | timing-dependent pre-existing test | none | no action |
| 10 | Test command run 3: 1399 tests OK (94 skipped) | — | — | passed |
| 11 | review R2, clip-manager clone at 0.56.0 before commit: `git worktree add` → `.harness/git/post-checkout: line 4: <new worktree>/.harness/git/hook_dispatch.sh: No such file or directory`, exit 1 (`GIT_TRACE`: git runs `<clone>/.harness/git/post-checkout` with `cd <new worktree>`) | implementation defect: the dispatcher resolves its shared code through `git rev-parse --show-toplevel` | v4 F15 rule and C43; corrections I3 and T9 | pending |
| 12 | Test command run 4 (after batch 3): 1401 tests, 1 error, the t5 timeout test of row 6 | timing-dependent pre-existing test: it passes alone three times in a row under the same command and failed on `base_commit` in a module run | none | 1400 pass; t5 reported as pre-existing |
| 13 | review R2 rerun on the clip-manager clone after batch 3: update exit 0; `git worktree add` exit 0 and the moved post-checkout printed `worktree: copied core/player/src/main/jniLibs`; R2 LLM-wiki: push to the bare remote's `master` refused by the moved pre-push; R3: a real `claude -p` session copied the `unconfirmed AGENTS.md` and `unconfirmed .harness/local/git/pre-push` notice lines from its context; R5: the code-explorer report began with `PINEAPPLE` | — | O1 and O2 settled | passed |
| 14 | verifier invocation 1: retry, 7 blocking evidence gaps VF1–VF7 (F12 precedence line and loose words; F8 section order guarded by an `if`; F7b under `--dry-run`; F5 retired path; F22b covering path; F23 staged vs working tree; F5 matcher), 6 advisory VA1–VA6 | evidence gaps: main read the implementation for each and it follows the spec, so no implementation change | correction T10 (VF1–VF7) to test-implementer; VA4 cited in V10's evidence; VA1, VA2, VA5, VA6 left advisory (outside the listed coverage items); VA3: the heading and its place are an implementation detail the existing heading-order test now pins | pending |
| 15 | Test command run 5 (after T10): 1411 tests; 4 failures, E1/E2 items `invalid config` and `existing git hook` of the F12 line check; the t5 error of row 6 | the 0.56.0 planned lines say `not a JSON object` and `git mv` where F12 says `an invalid config file` and `until moved`; T10.1 requires F12's words | correction I4: the two planned lines use F12's words | pending |
| 16 | Test command run 6 (after I4): 1411 tests; only the t5 error of row 6. Hand mutations, one at a time with seed backup and restore, each under the full Test command (strongest classes: the seven verifier gaps first, then the three behaviors whose failure would silently defeat the user's recognition or a blocking check): M1 drop the precedence planned line → E1/E2 migration-line tests fail; M2 customization section before manual review → section-order test fails; M3 skip the shadowing check in dry-run → dry-run shadowing test fails; M4 context hook silent for a retired path → retired-path test errors on the empty hook output it parses; M5 any retired entry covers a removal → the three wrong-path tests fail; M6 local pre-commit without `--staged` → both staged-vs-working-tree tests fail; M7 PostToolUse matcher `Write` only → registration test fails; M8 notice prints confirmed items → 11 notice/status tests fail; M10 confirm writes before rejecting bad paths → 4 confirm tests fail; M11 dispatcher ignores a failing local hook → 7 dispatch tests fail. `seed.py status`: none after the run | — | 10 of 10 detected by the intended assertions | passed |
| 17 | Test command run 7 (after I5 README rewrite): 1411 tests; only the t5 error of row 6. Verifier invocation 2: retry; VF2–VF7 closed; V6, V8, V17, V18 accepted; V9 open on new VF8 (F12 location line without the four F20 paths and notice line without `AGENTS.md` still pass E1/E2); advisory VA7 (git-hook line does not need "stops update"), VA8 (retired-path test order and trailing period) | evidence gap; the implementation's lines carry both | v6: user allowed a third invocation; correction T11 after the gap-probing mutations M12, M13 | pending |
| 18 | gap-probing mutations under the full Test command: M12 location planned line without the four F20 paths, M13 notice planned line without `AGENTS.md`; both left every test passing except the t5 error of row 6 | VF8 confirmed | correction T11 to test-implementer | pending |
| 19 | Test command run 8 (after T11): 1411 tests OK (94 skipped). M12 and M13 repeated: both now fail the E1 and E2 update tests (M13's run also had one unrelated timing failure in `test_checkout_setup`) | VF8 closed by evidence pending audit | verifier invocation 3 | pending |
| 21 | completion check over CQ1–CQ5, answered from the built result before rereading the expected answers (phase block text and no confirmation gate in `harness/bin/workflow_marker.py`; edited-file refusal before migrations in `installer/harness.py`; phase compare paths, notice, and confirm in `harness/lib/customization.py`; retirement matching in `installer/customization_check.py`; review file not git-ignored): 5 valid, 0 differ | — | — | complete |
| 20 | verifier invocation 3: pass; V9 accepted, VF8 closed, no new blocking finding; R1 dogfood after the user's confirmations: doctor exit 0 with no manual-review customization line, status `confirmed` for both items, notice prints nothing (scratchpad `review/r1.md`) | — | — | complete |

# Version Log
## v6
- The user raised `max_verifier_invocations` from 2 to 3 after verifier invocation 2 returned retry with one blocking evidence gap (VF8: the 0.56.0 planned-line checks do not pin the four F20 paths in the location line nor `AGENTS.md` in the notice line).

## v5
- [intent-mismatch] The user rewrote this repository's `AGENTS.md` project definition and stated that `AGENTS.md` carries no detailed, staleable explanation; the user then asked for the whole README to be simplified to what is needed, and chose to keep the rules "edit `harness/` only" and "update provides version-by-version migrations" in README only. F26 moves from `AGENTS.md` to README; F13 becomes a whole-README rewrite that keeps the strings existing text tests pin; R4 items 11–13 are replaced by item 11. The approval brief's resolution of the `.harness/` editing conflict (an exception sentence in `AGENTS.md`) is superseded: the exception lives in README.

## v4
- [contract] Review R2 on a clone of clip-manager: after the update (not yet committed), `git worktree add` ran the existing checkout's `.harness/git/post-checkout` with the new worktree as current directory; the dispatcher looked for its shared code under the new worktree's top level, found none, and the command exited 1. F15 now says the dispatcher finds its code and the local hook next to its own file; C43 and a V12 item cover it.

## v3
- [contract] Test command runs under `uv` with `pytest` and `hypothesis`, as earlier specs did: three existing test modules import them and fail to load under the bare interpreter. F22 does not repeat a compare-path failure that only follows from a failed name. D20: the user raised the always-loaded block limit from 4500 to 5100 bytes after the first Test command showed the earlier spec's size test failing at 5035 bytes.

## v2
- [contract] Reconcile of the first implementation and test delivery: F4 names the notice texts of `not-executable`, `missing`, the declaration line, and `retired` items; F5 gives a retired path the unrecognized text; F22(b) defines the covering retired `path` for a removed point id, name, and config key; C39 removes the phase from `phases.json` too, because F22(a) requires the names to equal its keys. Both deliveries already follow these rules (implementer report; test-implementer asserts only the parts the spec fixed), so neither role is redispatched.

## v1
- Drafted after understanding round 1 (fact answer: own conventions, lint enforcement, extra implementation verification) and decision round 1 (customization wins when the user can recognize the disagreement; the user's reason: the repository owner has the final say).
- Approval brief v1: the user accepted every decision taken for them and the resolution of the `.harness/` editing conflict, skipped the quiz, and declined the step cut; before approval the draft became one release, 0.56.0, without `# Steps` and `# Session Memory`.

